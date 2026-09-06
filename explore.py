"""Manual scratch script for testing fetchers and inserts one piece at a time.

Usage:
    uv run python explore.py arxiv          # fetch only, print results
    uv run python explore.py blogs          # fetch only, print results
    uv run python explore.py arxiv --store  # fetch + insert into DB
    uv run python explore.py blogs --store  # fetch + insert into DB
"""

import sys

from ai_intelligence.sources.arxiv import fetch_arxiv
from ai_intelligence.sources.blogs import fetch_all_blogs
from ai_intelligence.store import insert_items


def test_fetch_arxiv() -> list[dict]:
    items = fetch_arxiv(max_results=5)
    print(f"fetched {len(items)} arxiv items")
    for item in items:
        print(f"  - [{item['source_name']}] {item['title']}")
    return items


def test_fetch_blogs() -> list[dict]:
    items = fetch_all_blogs()
    print(f"fetched {len(items)} blog items")
    for item in items:
        print(f"  - [{item['source_name']}] {item['title']}")
    return items


def store(items: list[dict]) -> None:
    inserted, skipped = insert_items(items)
    print(f"{inserted} inserted, {skipped} skipped")


if __name__ == "__main__":
    args = sys.argv[1:]
    target = args[0] if args else "arxiv"
    should_store = "--store" in args

    if target == "arxiv":
        fetched = test_fetch_arxiv()
    elif target == "blogs":
        fetched = test_fetch_blogs()
    else:
        raise SystemExit(f"unknown target: {target!r} (expected 'arxiv' or 'blogs')")

    if should_store:
        store(fetched)
