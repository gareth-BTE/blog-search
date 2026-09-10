"""
Auto-update blog search index by scraping the live Webflow blog.
Run this locally or via GitHub Actions to regenerate the index.
"""
import requests, re, sys, json, pathlib
from bs4 import BeautifulSoup

BLOG_URL = 'https://www.tbowleslaw.com/blog'
INDEX_FILE = 'blog-search-index.js'
# A scrape holding less than this share of the previous index is treated as a
# broken scrape, not as posts being deleted.
MIN_RETAINED_SHARE = 0.9
PAGINATION_PARAM = 'd6bb3522_page'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def previous_post_count(path=INDEX_FILE):
    """How many posts the committed index holds, or None if there isn't one."""
    try:
        text = pathlib.Path(path).read_text(encoding='utf-8')
    except OSError:
        return None
    match = re.match(r'\s*window\.BLOG_SEARCH_INDEX\s*=\s*(.*?);?\s*$', text, re.S)
    if not match:
        return None
    try:
        return len(json.loads(match.group(1)))
    except ValueError:
        return None

def rejection_reason(posts, previous):
    """Why this scrape must not be published, or None if it's safe to write.

    A selector that stops matching, or pagination that stops early, both fail
    silently - they just yield fewer posts. Publishing that wipes out working
    site search, so refuse and let the workflow go red instead.
    """
    if not posts:
        return 'scrape found 0 blog posts'
    if previous:
        floor = int(previous * MIN_RETAINED_SHARE)
        if len(posts) < floor:
            return (f'scrape found only {len(posts)} posts, '
                    f'down from {previous} (expected at least {floor})')
    return None

def parse_page(html):
    """Extract the blog posts from one rendered listing page."""
    return parse_items(BeautifulSoup(html, 'html.parser'))

def parse_items(soup):
    posts = []

    for item in soup.find_all('div', class_='collection-item'):
        # Image
        img = item.find('img', class_='blog-image')
        image = img.get('src', '') if img else ''

        # Title. Match on the class only - Webflow has served this as an <h3>
        # and as a rich-text <div>, and the tag may change again.
        heading = item.find(class_='blogheading')
        title = heading.get_text(strip=True) if heading else ''

        # Excerpt (first <p> inside div-block-6, not inside _0height)
        block6 = item.find('div', class_='div-block-6')
        excerpt = ''
        if block6:
            p = block6.find('p', recursive=False)
            if p:
                excerpt = p.get_text(strip=True)[:200]

        # Slug from READ MORE link
        read_more = item.find('a', class_='w-button')
        slug = ''
        href = ''
        if read_more:
            href = read_more.get('href', '')
            slug = href.rstrip('/').split('/')[-1]

        # Date from hidden CMS field
        date_el = item.find(class_='unhidden-date')
        date = date_el.get_text(strip=True) if date_el else ''

        # Get full text from all paragraphs for search
        full_text = ''
        if block6:
            all_p = block6.find_all('p', recursive=False)
            full_text = ' '.join(p.get_text(strip=True) for p in all_p if p.get_text(strip=True))

        if title and slug:
            post = {
                't': title,
                's': slug,
                'e': excerpt,
                'i': image,
                'h': href,
            }
            if full_text and len(full_text) > len(excerpt):
                post['b'] = full_text[:1000]
            if date:
                post['d'] = date
            posts.append(post)

    return posts

def scrape_all_blogs():
    session = requests.Session()
    session.headers.update(HEADERS)
    session.verify = False

    all_posts = []
    page = 1

    while True:
        url = BLOG_URL if page == 1 else f'{BLOG_URL}?{PAGINATION_PARAM}={page}'
        resp = session.get(url, timeout=20)
        if resp.status_code != 200:
            break

        soup = BeautifulSoup(resp.text, 'html.parser')
        posts = parse_items(soup)
        if not posts:
            break

        all_posts.extend(posts)

        # Check for next page
        if not soup.find('a', class_='w-pagination-next'):
            break

        page += 1
        if page > 200:
            break

    return all_posts

if __name__ == '__main__':
    import warnings
    warnings.filterwarnings('ignore')

    print(f'Scraping {BLOG_URL}...')
    posts = scrape_all_blogs()
    print(f'Found {len(posts)} blog posts')

    reason = rejection_reason(posts, previous_post_count())
    if reason:
        print(f'ERROR: {reason}.', file=sys.stderr)
        print(f'Refusing to overwrite {INDEX_FILE}; the live site keeps the '
              f'index it has. The page markup has probably changed - check the '
              f'selectors in parse_items().', file=sys.stderr)
        sys.exit(1)

    js = f'window.BLOG_SEARCH_INDEX={json.dumps(posts, ensure_ascii=False, separators=(",", ":"))};'

    with open(INDEX_FILE, 'w', encoding='utf-8') as f:
        f.write(js)

    size_kb = len(js) / 1024
    print(f'Saved blog-search-index.js ({size_kb:.0f}KB)')
