"""Build a monthly citation curve for one arXiv paper from OpenAlex.

Fetches every work that cites the paper, buckets the citing works by
publication month, and plots monthly and cumulative citations.
Exploration only (Phase 1).
Usage: uv run scripts/citation_curve.py <arxiv_id>
"""
import itertools
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import httpx
import matplotlib.pyplot as plt
from dotenv import load_dotenv

OPENALEX_URL = "https://api.openalex.org"
OUT_DIR = Path("data/explore")
MAX_CITATIONS = 5000  # more than this is slow to page through for exploration


def get_json(path: str, params: dict, api_key: str) -> dict:
    """GET an OpenAlex endpoint and return the parsed JSON."""
    response = httpx.get(
        f"{OPENALEX_URL}{path}", params={**params, "api_key": api_key}, timeout=30
    )
    response.raise_for_status()
    return response.json()


def fetch_citing_dates(work_id: str, api_key: str) -> list[date]:
    """Return the publication date of every work that cites `work_id`."""
    dates = []
    cursor = "*"
    while cursor:
        page = get_json(
            "/works",
            {
                "filter": f"cites:{work_id}",
                "select": "id,publication_date",
                "per_page": 200,
                "cursor": cursor,
            },
            api_key,
        )
        for w in page["results"]:
            if w["publication_date"]:
                dates.append(date.fromisoformat(w["publication_date"]))
        cursor = page["meta"]["next_cursor"]
    return dates


def month_index(d: date, start: date) -> int:
    """Calendar months between start and d (0 = same month as start)."""
    return (d.year - start.year) * 12 + (d.month - start.month)


def main() -> None:
    load_dotenv()
    api_key = os.environ["OPENALEX_API_KEY"]
    arxiv_id = sys.argv[1]

    work = get_json(f"/works/https://doi.org/10.48550/arXiv.{arxiv_id}", {}, api_key)
    work_id = work["id"].rsplit("/", 1)[-1]  # "https://openalex.org/W123" -> "W123"
    pub_date = date.fromisoformat(work["publication_date"])
    print(f"{work['title']}\n{work_id}, published {pub_date}, cited_by_count={work['cited_by_count']}")
    if work["cited_by_count"] > MAX_CITATIONS:
        sys.exit(f"More than {MAX_CITATIONS} citations, pick a smaller paper.")

    dates = fetch_citing_dates(work_id, api_key)
    too_early = [d for d in dates if d < pub_date]
    counts = Counter(month_index(d, pub_date) for d in dates if d >= pub_date)
    jan_first = sum(1 for d in dates if d.month == 1 and d.day == 1)

    print(f"fetched {len(dates)} citing works with a date")
    print(f"dropped {len(too_early)} dated before the paper itself")
    print(f"{jan_first} citing works dated exactly January 1st")

    monthly = [counts.get(m, 0) for m in range(max(counts) + 1)]
    cumulative = list(itertools.accumulate(monthly))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7), sharex=True)
    ax1.bar(range(len(monthly)), monthly)
    ax1.set_ylabel("citations in month")
    ax2.plot(cumulative)
    ax2.set_ylabel("cumulative citations")
    ax2.set_xlabel(f"months since publication ({pub_date})")
    fig.suptitle(work["title"][:80])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"curve_{arxiv_id}.png"
    fig.savefig(out_path, dpi=120)
    print(f"saved plot to {out_path}")


if __name__ == "__main__":
    main()
