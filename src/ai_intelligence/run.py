"""Pipeline entrypoint: fetch every source, insert into the item store, print a summary.

    uv run ai-intelligence
"""

from ai_intelligence.sources.arxiv import fetch_arxiv
from ai_intelligence.sources.blogs import FEEDS, fetch_blog
from ai_intelligence.store import insert_items

ARXIV_MAX_RESULTS = 50


def run() -> None:
    # (source_name, inserted, skipped) for every source that made it through
    summary: list[tuple[str, int, int]] = []
    failures: list[tuple[str, Exception]] = []

    try:
        items = fetch_arxiv(max_results=ARXIV_MAX_RESULTS)
        inserted, skipped = insert_items(items)
        summary.append(("arxiv", inserted, skipped))
    except Exception as exc:
        failures.append(("arxiv", exc))

    # one feed at a time, so a single dead feed doesn't take the whole run down
    for source_name, feed_url in FEEDS:
        try:
            items = fetch_blog(source_name, feed_url)
            inserted, skipped = insert_items(items)
            summary.append((source_name, inserted, skipped))
        except Exception as exc:
            failures.append((source_name, exc))

    _print_summary(summary, failures)


def _print_summary(
    summary: list[tuple[str, int, int]],
    failures: list[tuple[str, Exception]],
) -> None:
    for source_name, inserted, skipped in summary:
        print(f"{source_name:>14}: {inserted:>4} inserted, {skipped:>4} skipped")

    for source_name, exc in failures:
        print(f"{source_name:>14}: FAILED - {type(exc).__name__}: {exc}")

    total_inserted = sum(inserted for _, inserted, _ in summary)
    print(f"{'total':>14}: {total_inserted} new items ({len(failures)} source(s) failed)")


if __name__ == "__main__":
    run()
