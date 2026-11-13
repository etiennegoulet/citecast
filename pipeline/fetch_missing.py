"""Look up, one at a time, the papers the bulk download missed.

Missing = in papers.parquet (not excluded) but not in paper_records.parquet.
Single lookups cost 0 credits. Rerunning skips papers already saved.

Usage: uv run pipeline/fetch_missing.py, then rerun build_citations.py
"""
import gzip
import json
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

import duckdb
import httpx
from dotenv import load_dotenv

FETCHER_VERSION = "openalex-missing-v1"
API = "https://api.openalex.org/works/https://doi.org/10.48550/arXiv."
FIELDS = "id,doi,publication_date,type,cited_by_count,counts_by_year,locations"
OUT_DIR = Path("data/raw/openalex/missing")
BATCH = 500  # lines written per append; a crash loses at most one batch


def missing_ids() -> list[str]:
    return [r[0] for r in duckdb.sql("""
        SELECT arxiv_id FROM 'data/papers.parquet'
        WHERE exclude_reason IS NULL
          AND lower(arxiv_id) NOT IN
              (SELECT arxiv_id FROM 'data/paper_records.parquet')
        ORDER BY arxiv_id""").fetchall()]


def already_saved() -> set[str]:
    done = set()
    for f in OUT_DIR.glob("*.jsonl.gz"):
        with gzip.open(f, "rt", encoding="utf-8") as fh:
            done |= {json.loads(line)["arxiv_id"] for line in fh}
    return done


RETRY_STATUS = (429, 500, 502, 503, 504)


def lookup(client: httpx.Client, arxiv_id: str) -> httpx.Response:
    for attempt in range(6):
        last = attempt == 5
        try:
            r = client.get(API + arxiv_id, params={"select": FIELDS})
        except httpx.TransportError:
            # Network failure (connection reset, timeout): wait and retry.
            if last:
                raise
            time.sleep(2 ** attempt)
            continue
        if r.status_code in RETRY_STATUS:
            if last:
                # Don't save a persistent server error as "not found".
                r.raise_for_status()
            time.sleep(2 ** attempt)
            continue
        return r


def append(lines: list[dict]) -> None:
    out = OUT_DIR / f"{date.today().isoformat()}.jsonl.gz"
    with gzip.open(out, "at", encoding="utf-8") as fh:
        fh.writelines(json.dumps(x) + "\n" for x in lines)


def main() -> None:
    load_dotenv()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    done = already_saved()
    todo = [a for a in missing_ids() if a not in done]
    print(f"{len(todo):,} papers to look up ({len(done):,} already saved)", flush=True)
    client = httpx.Client(params={"api_key": os.environ["OPENALEX_API_KEY"]},
                          timeout=60, follow_redirects=True)
    buffer, found = [], 0
    for i, arxiv_id in enumerate(todo, 1):
        r = lookup(client, arxiv_id)
        work = r.json() if r.status_code == 200 else None
        found += work is not None
        buffer.append({"arxiv_id": arxiv_id, "status": r.status_code,
                       "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                       "fetcher_version": FETCHER_VERSION, "work": work})
        if len(buffer) == BATCH or i == len(todo):
            append(buffer)
            buffer = []
            print(f"{i:,}/{len(todo):,} done, {found:,} found", flush=True)


if __name__ == "__main__":
    main()
