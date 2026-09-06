from ai_intelligence.db import get_connection

INSERT_SQL = """
INSERT INTO items (
    source_type, source_name, external_id, title, url,
    summary, authors, published_at, raw
) VALUES (
    %(source_type)s, %(source_name)s, %(external_id)s, %(title)s, %(url)s,
    %(summary)s, %(authors)s, %(published_at)s, %(raw)s::jsonb
)
ON CONFLICT (source_name, external_id) DO NOTHING
"""


def insert_items(items: list[dict]) -> tuple[int, int]:
    """Insert normalized items, skipping dupes. Returns (inserted, skipped)."""
    inserted = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for item in items:
                cur.execute(INSERT_SQL, item)
                inserted += cur.rowcount
    skipped = len(items) - inserted
    return inserted, skipped
