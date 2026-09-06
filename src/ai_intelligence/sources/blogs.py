from __future__ import annotations

import json
from datetime import datetime, timezone

import feedparser
import httpx

# (source_name, feed_url) - source_name is the dedup scope in the items table
FEEDS: list[tuple[str, str]] = [
    ("openai", "https://openai.com/news/rss.xml"),
    ("huggingface", "https://huggingface.co/blog/feed.xml"),
    ("google", "https://blog.google/technology/ai/rss/"),
]

def fetch_blog(source_name: str, feed_url: str) -> list[dict]:
    response = httpx.get(feed_url, follow_redirects=True, timeout=30)
    response.raise_for_status()

    feed = feedparser.parse(response.text)
    return [_normalize(entry, source_name) for entry in feed.entries]

def fetch_all_blogs() -> list[dict]:
    items = []
    for source_name, feed_url in FEEDS:
        items.extend(fetch_blog(source_name, feed_url))
    return items

def _normalize(entry: feedparser.FeedParserDict, source_name: str) -> dict:
    return {
        "source_type": "lab_blog",
        "source_name": source_name,
        # not every feed has a guid; the URL is a fine stable fallback
        "external_id": entry.get("id") or entry.link,
        "title": _clean(entry.get("title", "")),
        "url": entry.link,
        "summary": _clean(entry.get("summary", "")),
        # RSS often has no author at all
        "authors": [a.name for a in entry.get("authors", []) if "name" in a],
        "published_at": _parse_date(entry),
        "raw": json.dumps(entry, default=str),
    }

def _parse_date(entry: feedparser.FeedParserDict) -> datetime | None:
    # feedparser already handled RFC 822 vs ISO for us and normalized to UTC
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=timezone.utc)


def _clean(text: str) -> str:
    return " ".join(text.split())