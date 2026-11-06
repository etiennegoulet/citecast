"""Build data/papers.parquet from the Kaggle arXiv metadata snapshot.

One row per arXiv paper, keeping only what the pipeline needs
(no titles, authors or abstracts).

Point-in-time warning: `doi`, `journal_ref` and `update_date` are the values
as of the snapshot date, not as of any prediction time. They can describe
events after a backtest cutoff, so they must never be used as features.
They are kept only for data checks (e.g. OpenAlex merging).
"""
from pathlib import Path

import duckdb

EXTRACTOR_VERSION = "papers-v2"
RAW = Path("data/raw/arxiv/arxiv-metadata-oai-snapshot.json")
OUT = Path("data/papers.parquet")

BUILD = f"""
COPY (
    WITH raw AS (
        SELECT * FROM read_json('{RAW.as_posix()}',
            format = 'newline_delimited',
            columns = {{
                'id': 'VARCHAR',
                'categories': 'VARCHAR',
                'doi': 'VARCHAR',
                'journal-ref': 'VARCHAR',
                'versions': 'STRUCT(version VARCHAR, created VARCHAR)[]',
                'update_date': 'DATE'
            }})
    ),
    parsed AS (
        SELECT
            id AS arxiv_id,
            -- YYMM of the month the paper was announced on arXiv:
            -- old IDs look like hep-th/9901001, new ones like 2004.05150.
            CASE WHEN id LIKE '%/%' THEN split_part(id, '/', 2)[1:4]
                 ELSE id[1:4] END AS id_yymm,
            strptime(
                list_filter(versions, lambda v: v.version = 'v1')[1].created,
                '%a, %d %b %Y %H:%M:%S GMT'
            ) AS v1_datetime,
            string_split(categories, ' ') AS categories,
            len(versions) AS n_versions,
            doi,
            "journal-ref" AS journal_ref,
            update_date
        FROM raw
    )
    SELECT
        arxiv_id,
        v1_datetime,
        -- Year 0 = year the paper became public (announced) on arXiv,
        -- read from the ID's YYMM. Two-digit years: 91-99 are 1990s.
        -- (Breaks in 2091.)
        (CASE WHEN id_yymm[1:2]::INT >= 91 THEN 1900 ELSE 2000 END)
            + id_yymm[1:2]::INT AS year0,
        id_yymm[3:4]::INT AS announced_month,
        year(v1_datetime) AS v1_year,
        -- Assumption, not yet verified against the arXiv API:
        -- the first listed category is the primary one.
        categories[1] AS primary_category,
        split_part(categories[1], '.', 1) AS primary_archive,
        categories,
        n_versions,
        doi,
        journal_ref,
        update_date,
        -- Papers that should not be modelled, and why. Rows are kept;
        -- dataset building drops them with WHERE exclude_reason IS NULL.
        -- A v1 date before arXiv opened means the paper existed before
        -- it was posted (see docs/data-notes.md, data cleaning log).
        CASE WHEN v1_datetime < TIMESTAMP '1991-08-01'
             THEN 'posted_after_publication' END AS exclude_reason,
        '{EXTRACTOR_VERSION}' AS extractor_version
    FROM parsed
) TO '{OUT.as_posix()}' (FORMAT parquet);
"""

CHECKS = {
    "rows, null year0, null primary": f"""
        SELECT count(*), count(*) FILTER (year0 IS NULL),
               count(*) FILTER (primary_category IS NULL)
        FROM '{OUT.as_posix()}'""",
    "year0 range": f"SELECT min(year0), max(year0) FROM '{OUT.as_posix()}'",
    "papers per year0": f"""
        SELECT year0, count(*) FROM '{OUT.as_posix()}'
        GROUP BY year0 ORDER BY year0""",
    # Old-style IDs (before April 2007) embed the primary archive,
    # e.g. hep-th/9901001. Compare it with the first listed category.
    "old IDs: archive in ID matches first category": f"""
        SELECT split_part(arxiv_id, '/', 1) = primary_archive AS match,
               count(*)
        FROM '{OUT.as_posix()}'
        WHERE arxiv_id LIKE '%/%'
        GROUP BY match""",
    "year0 minus v1_year (expect ~9,079 nonzero)": f"""
        SELECT year0 - v1_year AS diff, count(*) FROM '{OUT.as_posix()}'
        GROUP BY diff ORDER BY diff""",
    "exclude_reason": f"""
        SELECT exclude_reason, count(*) FROM '{OUT.as_posix()}'
        GROUP BY exclude_reason ORDER BY exclude_reason""",
}


def main() -> None:
    con = duckdb.connect()
    con.execute(BUILD)
    for name, sql in CHECKS.items():
        print(f"\n== {name}")
        for row in con.execute(sql).fetchall():
            print(row)


if __name__ == "__main__":
    main()
