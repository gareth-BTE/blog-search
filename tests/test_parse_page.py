"""Regression tests for blog index extraction against a saved copy of the live page.

Guards the failure of 2026-08-28: Webflow changed the post heading from
<h3 class="blogheading"> to <div class="blogheading blogs w-richtext">, the
tag-specific selector stopped matching, every post was silently skipped, and
the workflow published an empty index while still reporting success.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "blog-page1.html"


def parse_page(html):
    spec = importlib.util.spec_from_file_location("updater", ROOT / "update-search-index.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parse_page(html)


def posts():
    return parse_page(FIXTURE.read_text(encoding="utf-8"))


def test_finds_every_post_on_the_page():
    assert len(posts()) == 9


def test_every_post_has_a_title_and_slug():
    for p in posts():
        assert p["t"], f"empty title for {p.get('s')!r}"
        assert p["s"], f"empty slug for {p.get('t')!r}"


def test_title_does_not_depend_on_the_heading_tag():
    titles = [p["t"] for p in posts()]
    assert any("House Call" in t for t in titles), titles


def test_posts_carry_link_date_and_image():
    for p in posts():
        assert p["h"].startswith("/blogs/")
        assert p["i"].startswith("http")
    assert sum(1 for p in posts() if p.get("d")) >= 8
