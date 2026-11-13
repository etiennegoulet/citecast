"""Build per-paper citation counts from the raw OpenAlex pages.

Outputs:
  data/paper_records.parquet  one row per paper: the OpenAlex record chosen
  data/citations.parquet      one row per (paper, year) with citations that year
Choice among several records: docs/duplicate-records.md.
"""
from pathlib import Path

import duckdb

EXTRACTOR_VERSION = "citations-v1"
RUN_DATE = "2026-11-07"
RAW = f"data/raw/openalex/{RUN_DATE}/*/*.json.gz"
MISSING_DIR = Path("data/raw/openalex/missing")  # from fetch_missing.py
PAPERS = "data/papers.parquet"
OUT_RECORDS = "data/paper_records.parquet"
OUT_CITATIONS = "data/citations.parquet"

RECORD_TYPE = """STRUCT(
    id VARCHAR, doi VARCHAR, type VARCHAR, cited_by_count BIGINT,
    counts_by_year STRUCT(year INTEGER, cited_by_count BIGINT)[],
    locations STRUCT(landing_page_url VARCHAR, pdf_url VARCHAR)[]
)[]"""
RECORD = RECORD_TYPE.removesuffix("[]")  # one record instead of a list

# Every source of records, with its fetch date. src orders the sources:
# if a work is in both, the bulk copy (src 0) wins.
SOURCES = f"""
    SELECT unnest(results) AS r, '{RUN_DATE}' AS fetched, 0 AS src
    FROM read_json('{RAW}', columns = {{results: '{RECORD_TYPE}'}})"""
if any(MISSING_DIR.glob("*.jsonl.gz")):
    SOURCES += f"""
    UNION ALL
    SELECT work AS r, fetched_at[1:10] AS fetched, 1 AS src
    FROM read_json('{MISSING_DIR.as_posix()}/*.jsonl.gz',
                   columns = {{work: '{RECORD}', fetched_at: 'VARCHAR'}})
    WHERE work IS NOT NULL"""

STEPS = [
    # 1. One row per OpenAlex work, with the arXiv IDs found in its locations:
    #    arxiv.org/abs/<id>, arxiv.org/pdf/<id>, or the DOI 10.48550/arxiv.<id>.
    f"""
    CREATE TABLE works AS
    SELECT DISTINCT ON (r.id)
        r.id AS oa_id, r.doi, r.cited_by_count, r.counts_by_year, fetched,
        list_distinct(list_filter(list_concat(
            list_transform(r.locations, lambda l: regexp_extract(
                lower(coalesce(l.landing_page_url, '') || ' ' || coalesce(l.pdf_url, '')),
                'arxiv\\.org/(?:abs|pdf)/([a-z\\-\\.]+/\\d{{7}}|\\d{{4}}\\.\\d{{4,5}})', 1)),
            list_transform(r.locations, lambda l: regexp_extract(
                lower(coalesce(l.landing_page_url, '')),
                '10\\.48550/arxiv\\.([a-z\\-\\.]+/\\d{{7}}|\\d{{4}}\\.\\d{{4,5}})', 1))
        ), lambda x: x <> '')) AS arxiv_ids
    FROM ({SOURCES})
    ORDER BY r.id, src
    """,
    # 2. One row per (work, arXiv ID). Old IDs sometimes carry a subject class
    #    in links (math.GT/0309136) but not in Kaggle (math/0309136): strip it.
    """
    CREATE TABLE links AS
    SELECT oa_id, doi, cited_by_count, counts_by_year, fetched,
           len(arxiv_ids) AS ids_on_record,
           regexp_replace(unnest(arxiv_ids), '^([a-z\\-]+)\\.[a-z\\-]+/', '\\1/') AS arxiv_id
    FROM works
    """,
    # 3. Keep links to known papers, tag each record, and pick one per paper.
    f"""
    CREATE TABLE chosen AS
    WITH tagged AS (
        SELECT l.*,
            coalesce(lower(l.doi) LIKE '%10.48550/arxiv.%', false) AS is_arxiv_doi,
            l.doi IS NOT NULL
                AND NOT lower(l.doi) LIKE '%10.48550/arxiv.%' AS is_published
        FROM links l
        JOIN (SELECT lower(arxiv_id) AS arxiv_id FROM '{PAPERS}') USING (arxiv_id)
    ),
    per_paper AS (
        SELECT *,
            count(*) OVER w AS n_records,
            bool_or(is_published) OVER w AS any_published,
            bool_and(is_published) OVER w AS all_published
        FROM tagged
        WINDOW w AS (PARTITION BY arxiv_id)
    )
    SELECT *,
        CASE WHEN n_records = 1 THEN 'single'
             WHEN all_published THEN 'C'
             WHEN any_published THEN 'A'
             ELSE 'B' END AS pattern
    FROM per_paper
    QUALIFY row_number() OVER (
        PARTITION BY arxiv_id
        ORDER BY
            -- B (preprints only): the arXiv-DOI record first
            CASE WHEN NOT any_published AND is_arxiv_doi THEN 0 ELSE 1 END,
            cited_by_count DESC,
            oa_id  -- tie-break, so reruns give the same choice
    ) = 1
    """,
    f"""
    COPY (
        SELECT arxiv_id, oa_id, pattern, n_records,
               ids_on_record > 1 AS shared_record,
               cited_by_count,
               fetched AS openalex_run_date,
               '{EXTRACTOR_VERSION}' AS extractor_version
        FROM chosen
    ) TO '{OUT_RECORDS}' (FORMAT parquet)
    """,
    # Years with zero citations are absent from counts_by_year; the dataset
    # builder fills them with 0. counts_by_year starts in 2012.
    f"""
    COPY (
        SELECT arxiv_id, c.year, c.cited_by_count AS citations,
               '{EXTRACTOR_VERSION}' AS extractor_version
        FROM (SELECT arxiv_id, unnest(counts_by_year) AS c FROM chosen)
    ) TO '{OUT_CITATIONS}' (FORMAT parquet)
    """,
]

CHECKS = {
    "papers with a record / all papers": f"""
        SELECT (SELECT count(*) FROM chosen), (SELECT count(*) FROM '{PAPERS}')""",
    "papers per pattern": """
        SELECT pattern, count(*) FROM chosen GROUP BY 1 ORDER BY 1""",
    "chosen record shared with other arXiv IDs": """
        SELECT ids_on_record > 1, count(*) FROM chosen GROUP BY 1""",
    "counts_by_year sums to cited_by_count": """
        SELECT list_sum(list_transform(counts_by_year, lambda c: c.cited_by_count))
                   = cited_by_count, count(*)
        FROM chosen GROUP BY 1""",
}


def main() -> None:
    con = duckdb.connect()
    for sql in STEPS:
        con.execute(sql)
    for name, sql in CHECKS.items():
        print(f"\n== {name}")
        for row in con.execute(sql).fetchall():
            print(row)


if __name__ == "__main__":
    main()
