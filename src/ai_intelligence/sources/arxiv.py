from __future__ import annotations

import json
from datetime import datetime
from typing import cast

import feedparser
import httpx

ARXIV_API_URL = "http://export.arxiv.org/api/query"
DEFAULT_QUERY = "cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.MA"


def fetch_arxiv(query: str = DEFAULT_QUERY, max_results: int = 10) -> list[dict]:
    params = {
        "search_query": query,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": max_results,
    }
    response = httpx.get(ARXIV_API_URL, params=params, follow_redirects=True)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    return [_normalize(entry) for entry in feed.entries]


def _normalize(entry: feedparser.FeedParserDict) -> dict:
    published_at = (
        datetime.fromisoformat(cast(str, entry.published)) if "published" in entry else None
    )
    return {
        "source_type": "paper",
        "source_name": "arxiv",
        "external_id": entry.id,
        "title": _clean(cast(str, entry.title)),
        "url": entry.link,
        "summary": _clean(cast(str, entry.summary)),
        "authors": [a.name for a in entry.authors],
        "published_at": published_at,
        "raw": json.dumps(entry, default=str),
    }


def _clean(text: str) -> str:
    return " ".join(text.split())
