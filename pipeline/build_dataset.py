"""Build data/dataset.parquet: one row per paper, yearly citations since year 0.

Papers: year 0 from FIRST_YEAR (counts_by_year starts in 2012) to
LAST_FULL_YEAR, not excluded in papers.parquet.

Year 0 = the calendar year the paper became public: its arXiv year
(year0_arxiv), or the year of an earlier publication found in OpenAlex if it
is less than a year before the arXiv v1 date (year0_source = 'openalex_earlier').

cit_y{i} = citations received in calendar year year0 + i.
  0    -> year observed, no citations
  NULL -> year after LAST_FULL_YEAR (not observed yet), or no OpenAlex record
cit_before_y0: citations dated before year 0. Data check only, never a feature.

exclude_reason: OpenAlex-based exclusions. Rows stay; modelling filters on
exclude_reason IS NULL AND has_record. Rules: docs/data-notes.md.

No labels or features here: they depend on the experiment (area definition,
history k, horizon) and are computed downstream from this table.
"""
import duckdb

EXTRACTOR_VERSION = "dataset-v3"  # v3: late-upload rule, redated year 0
FIRST_YEAR = 2012        # counts_by_year starts in 2012
LAST_FULL_YEAR = 2025    # 2026 is incomplete (indexing lag)
MAX_AGE = LAST_FULL_YEAR - FIRST_YEAR
REDATE_MAX_DAYS = 365    # earlier publication within this: redate; beyond: exclude
CITED_BEFORE_MAX = 10    # no earlier publication, more citations before y0: exclude
PAPERS = "data/papers.parquet"
RECORDS = "data/paper_records.parquet"
CITATIONS = "data/citations.parquet"
OUT = "data/dataset.parquet"

# One column per age. NULL if the year is not observed or there is no record;
# otherwise the year's citations, 0 when counts_by_year has no entry.
YEAR_COLS = ",\n".join(
    f"""CASE WHEN NOT has_record OR year0 + {i} > {LAST_FULL_YEAR} THEN NULL
             ELSE coalesce(sum(c.citations) FILTER (WHERE c.year = year0 + {i}), 0)
        END AS cit_y{i}"""
    for i in range(MAX_AGE + 1))

BUILD = f"""
COPY (
    WITH p AS (
        -- One extra year: a 2026 arXiv paper published in 2025 is redated
        -- into range. The final range filter is applied after redating.
        SELECT lower(arxiv_id) AS arxiv_id, year0 AS year0_arxiv,
               v1_datetime::DATE AS v1,
               primary_category, primary_archive, categories
        FROM '{PAPERS}'
        WHERE exclude_reason IS NULL
          AND year0 BETWEEN {FIRST_YEAR} AND {LAST_FULL_YEAR + 1}
    ),
    pr AS (
        -- Redate year 0 when an earlier publication is less than a year
        -- before v1. Strictly before v1, so the arXiv record's own date
        -- (= v1) never triggers it and late-December papers keep their
        -- announcement year.
        SELECT p.*, r.oa_id IS NOT NULL AS has_record,
               r.pattern AS record_pattern, r.shared_record, r.oa_earliest_date,
               coalesce(r.oa_earliest_date < v1
                        AND v1 - r.oa_earliest_date <= {REDATE_MAX_DAYS}
                        AND year(r.oa_earliest_date) < year0_arxiv, false) AS redated,
               CASE WHEN redated THEN year(r.oa_earliest_date)
                    ELSE year0_arxiv END AS year0
        FROM p LEFT JOIN '{RECORDS}' r USING (arxiv_id)
    )
    SELECT arxiv_id, year0, year0_arxiv,
           CASE WHEN redated THEN 'openalex_earlier' ELSE 'arxiv' END AS year0_source,
           primary_category, primary_archive, categories,
           has_record, record_pattern, shared_record,
           -- One reason per paper, first match wins. Rules: docs/data-notes.md.
           CASE WHEN oa_earliest_date < v1 - INTERVAL {REDATE_MAX_DAYS} DAY
                    THEN 'posted_after_publication'
                WHEN shared_record
                    THEN 'shared_openalex_record'
                -- No earlier publication date explains them, so the citations
                -- point to an unlinked old version or a broken record.
                WHEN oa_earliest_date >= v1
                     AND sum(c.citations) FILTER (WHERE c.year < year0) > {CITED_BEFORE_MAX}
                    THEN 'cited_before_posting'
           END AS exclude_reason,
           {YEAR_COLS},
           CASE WHEN has_record THEN
               coalesce(sum(c.citations) FILTER (WHERE c.year < year0), 0)
           END AS cit_before_y0,
           '{EXTRACTOR_VERSION}' AS extractor_version
    FROM pr
    LEFT JOIN (SELECT * FROM '{CITATIONS}' WHERE year <= {LAST_FULL_YEAR}) c
        USING (arxiv_id)
    WHERE year0 BETWEEN {FIRST_YEAR} AND {LAST_FULL_YEAR}  -- after redating
    -- Explicit list: GROUP BY ALL can't infer it when a column mixes
    -- aggregates with plain columns, as every cit_y{{i}} does.
    GROUP BY arxiv_id, year0, year0_arxiv, redated, v1, oa_earliest_date,
             primary_category, primary_archive, categories,
             has_record, record_pattern, shared_record
    ORDER BY arxiv_id
) TO '{OUT}' (FORMAT parquet)
"""

CHECKS = {
    "no duplicate papers (rows, distinct ids)": f"""
        SELECT count(*), count(DISTINCT arxiv_id) FROM '{OUT}'""",
    "papers per year 0, with record": f"""
        SELECT year0, count(*), sum(has_record::int) FROM '{OUT}'
        GROUP BY 1 ORDER BY 1""",
    "year 0 source (source, papers, of which excluded)": f"""
        SELECT year0_source, count(*), count(exclude_reason) FROM '{OUT}'
        GROUP BY 1 ORDER BY 1""",
    "yearly columns sum to citations.parquet (years 2012-2025)": f"""
        SELECT (SELECT sum({' + '.join(f'coalesce(cit_y{i}, 0)' for i in range(MAX_AGE + 1))}
                           + coalesce(cit_before_y0, 0)) FROM '{OUT}'),
               (SELECT sum(c.citations) FROM '{CITATIONS}' c
                JOIN '{OUT}' d USING (arxiv_id) WHERE c.year <= {LAST_FULL_YEAR})""",
    "exclusions (reason, papers)": f"""
        SELECT exclude_reason, count(*) FROM '{OUT}' GROUP BY 1 ORDER BY 1""",
    "kept papers with citations before year 0, by source": f"""
        SELECT year0_source, cit_before_y0 > 0, count(*) FROM '{OUT}'
        WHERE has_record AND exclude_reason IS NULL GROUP BY 1, 2 ORDER BY 1, 2""",
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
