"""Download all OpenAlex works with an arXiv location, as raw JSON pages.

One slice per publication_year, each finished within a day. Resumable via
state.json: rerun the next day to continue.

Usage: uv run pipeline/fetch_openalex.py
"""
import gzip
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

FETCHER_VERSION = "openalex-fetch-v1"
API = "https://api.openalex.org/works"
ARXIV_FILTER = "locations.source.id:S4306400194"
FIELDS = "id,doi,publication_date,type,cited_by_count,counts_by_year,locations"
PER_PAGE = 200
ROOT = Path("data/raw/openalex")
STATE = ROOT / "state.json"
SAFETY_MARGIN = 20  # pages of slack when deciding whether a slice fits today


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def save_state(state: dict) -> None:
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=1))
    # Windows refuses the replace while another process (antivirus, a reader)
    # has state.json open. Retry briefly instead of crashing.
    for _ in range(20):
        try:
            tmp.replace(STATE)  # atomic: never a half-written state
            return
        except PermissionError:
            time.sleep(0.5)
    tmp.replace(STATE)  # still failing after 10 s: raise the error


def get(client: httpx.Client, params: dict) -> httpx.Response:
    """GET with retries on network errors, server errors and rate limits."""
    for attempt in range(6):
        last = attempt == 5
        try:
            r = client.get(API, params=params)
        except httpx.TransportError:
            # Network failure (connection reset, timeout): wait and retry.
            if last:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code in (429, 500, 502, 503, 504) and not last:
            time.sleep(2 ** attempt)
            continue
        r.raise_for_status()
        return r


def remaining(r: httpx.Response) -> int:
    return int(r.headers.get("x-ratelimit-remaining", 0))


def new_state(client: httpx.Client) -> dict:
    """First run: count works per publication_year to define the slices."""
    r = get(client, {"filter": ARXIV_FILTER, "group_by": "publication_year"})
    body = r.json()
    groups = {g["key"]: g["count"] for g in body["group_by"]}
    total = body["meta"]["count"]
    print(f"{total:,} works in {len(groups)} years; sum of groups {sum(groups.values()):,}")
    return {
        "run_date": date.today().isoformat(),
        "fetcher_version": FETCHER_VERSION,
        "total_at_start": total,
        "slices": {
            year: {"expected": n, "cursor": "*", "pages": 0, "works": 0,
                   "done": False, "started": None, "finished": None}
            for year, n in sorted(groups.items())
        },
    }


def main() -> None:
    load_dotenv()
    ROOT.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(params={"api_key": os.environ["OPENALEX_API_KEY"]},
                          timeout=120)
    state = json.loads(STATE.read_text()) if STATE.exists() else new_state(client)
    save_state(state)
    run_dir = ROOT / state["run_date"]
    credits = None  # unknown until the first page of this session

    for year, s in state["slices"].items():
        if s["done"]:
            continue
        pages_needed = s["expected"] // PER_PAGE + 1 - s["pages"]
        if credits is not None and credits < pages_needed + SAFETY_MARGIN:
            print(f"stopping: {credits} credits left, year {year} needs ~{pages_needed}. "
                  "Run again tomorrow.")
            return
        out_dir = run_dir / f"year={year}"
        out_dir.mkdir(parents=True, exist_ok=True)
        s["started"] = s["started"] or now()
        while not s["done"]:
            r = get(client, {"filter": f"{ARXIV_FILTER},publication_year:{year}",
                             "select": FIELDS, "per_page": PER_PAGE,
                             "cursor": s["cursor"]})
            body = r.json()
            if body["results"]:
                page_file = out_dir / f"page_{s['pages'] + 1:05d}.json.gz"
                page_file.write_bytes(gzip.compress(r.content))
                s["pages"] += 1
                s["works"] += len(body["results"])
            s["cursor"] = body["meta"]["next_cursor"]
            s["done"] = s["cursor"] is None or not body["results"]
            save_state(state)  # after the page file, so a crash just redoes that page
            credits = remaining(r)
        s["finished"] = now()
        save_state(state)
        print(f"year {year}: {s['works']:,} works (expected {s['expected']:,}), "
              f"{credits} credits left", flush=True)

    print("all slices done")


if __name__ == "__main__":
    main()
