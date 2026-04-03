"""
Auto-update blog search index by scraping the live Webflow blog.
Run this locally or via GitHub Actions to regenerate the index.
"""
import requests, re, sys, json
from bs4 import BeautifulSoup

BLOG_URL = 'https://www.tbowleslaw.com/blog'
PAGINATION_PARAM = 'd6bb3522_page'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

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
        items = soup.find_all('div', class_='collection-item')
        if not items:
            break

        for item in items:
            # Image
            img = item.find('img', class_='blog-image')
            image = img.get('src', '') if img else ''

            # Title
            h3 = item.find('h3', class_='blogheading')
            title = h3.get_text(strip=True) if h3 else ''

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

            if title and slug:
                post = {
                    't': title,
                    's': slug,
                    'e': excerpt,
                    'i': image,
                    'h': href,
                }
                if date:
                    post['d'] = date
                all_posts.append(post)

        # Check for next page
        has_next = bool(soup.find('a', class_='w-pagination-next'))
        if not has_next:
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

    js = f'window.BLOG_SEARCH_INDEX={json.dumps(posts, ensure_ascii=False, separators=(",", ":"))};'

    with open('blog-search-index.js', 'w', encoding='utf-8') as f:
        f.write(js)

    size_kb = len(js) / 1024
    print(f'Saved blog-search-index.js ({size_kb:.0f}KB)')
