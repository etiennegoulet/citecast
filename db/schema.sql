CREATE TABLE IF NOT EXISTS items (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,       -- 'lab_blog' | 'paper'
    source_name TEXT NOT NULL,       -- e.g. 'anthropic', 'arxiv'
    external_id TEXT NOT NULL,       -- dedup key: blog post URL, arXiv ID, etc.
    title TEXT NOT NULL,
    url TEXT NOT NULL,
    summary TEXT,
    authors TEXT[],
    published_at TIMESTAMPTZ,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    raw JSONB NOT NULL,
    UNIQUE (source_name, external_id) -- per source rather than just external_id to be unique, in case of 2 external_id equal but different sites and articles
);

CREATE INDEX IF NOT EXISTS idx_items_published_at ON items (published_at DESC);
CREATE INDEX IF NOT EXISTS idx_items_source_type ON items (source_type);
