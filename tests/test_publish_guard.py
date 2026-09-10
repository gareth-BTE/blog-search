"""The index must never be overwritten by an empty or truncated scrape.

On 2026-08-28 a scrape returned 0 posts, wrote `window.BLOG_SEARCH_INDEX=[]`,
exited 0, and the workflow committed it over a good 1199-post index while
reporting success. Nothing alerted; site search was dead for 13 days.
"""
import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def mod():
    spec = importlib.util.spec_from_file_location("updater", ROOT / "update-search-index.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_empty_scrape_is_rejected():
    assert mod().rejection_reason([], previous=1199)


def test_empty_scrape_is_rejected_even_with_no_previous_index():
    assert mod().rejection_reason([], previous=None)


def test_truncated_scrape_is_rejected():
    # Pagination breaking halfway is the other silent failure this design allows.
    assert mod().rejection_reason([{}] * 600, previous=1199)


def test_normal_scrape_is_accepted():
    assert mod().rejection_reason([{}] * 1204, previous=1199) is None


def test_small_shrink_is_accepted():
    # Posts do get unpublished; only a collapse should block.
    assert mod().rejection_reason([{}] * 1150, previous=1199) is None


def test_first_ever_run_is_accepted():
    assert mod().rejection_reason([{}] * 1199, previous=None) is None


def test_previous_post_count_reads_an_existing_index(tmp_path):
    f = tmp_path / "idx.js"
    f.write_text('window.BLOG_SEARCH_INDEX=[{"t":"a"},{"t":"b"}];', encoding="utf-8")
    assert mod().previous_post_count(f) == 2


def test_previous_post_count_is_none_when_absent(tmp_path):
    assert mod().previous_post_count(tmp_path / "nope.js") is None
