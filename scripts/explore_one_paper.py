"""Fetch one arXiv paper from OpenAlex, save the raw JSON, print the key fields.

Exploration only (Phase 1), not part of the pipeline.
Usage: uv run scripts/explore_one_paper.py [arxiv_id]
"""
import json
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

OPENALEX_URL = "https://api.openalex.org"
OUT_DIR = Path("data/explore")


def fetch_work_by_arxiv_id(arxiv_id: str, api_key: str) -> dict:
    """Look up a work in OpenAlex by its arXiv DOI."""
    doi = f"https://doi.org/10.48550/arXiv.{arxiv_id}"
    response = httpx.get(
        f"{OPENALEX_URL}/works/{doi}",
        params={"api_key": api_key},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def main() -> None:
    load_dotenv()
    api_key = os.environ["OPENALEX_API_KEY"]
    arxiv_id = sys.argv[1] if len(sys.argv) > 1 else "1706.03762"

    work = fetch_work_by_arxiv_id(arxiv_id, api_key)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"work_{arxiv_id}.json"
    out_path.write_text(json.dumps(work, indent=2), encoding="utf-8")

    print(f"Saved full JSON to {out_path}")
    print(f"Top-level fields: {sorted(work.keys())}\n")
    for field in ["id", "doi", "title", "type", "publication_date", "cited_by_count", "ids"]:
        print(f"{field}: {work.get(field)}")
    print(f"\nnumber of locations: {len(work.get('locations', []))}")
    for loc in work.get("locations", []):
        source = loc.get("source") or {}
        print(f"  - {source.get('display_name')} | version={loc.get('version')}")
    print(f"\nnumber of referenced_works: {len(work.get('referenced_works', []))}")
    print(f"counts_by_year: {work.get('counts_by_year')}")


if __name__ == "__main__":
    main()
