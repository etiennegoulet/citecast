# Data notes

Facts about the data, with evidence. Each note is **verified** (measured) or a **hypothesis**.

"180-paper sample": `scripts/sample_check.py`, 20 papers per (category, year) for cs.LG, hep-th, math.AG in 2015, 2018, 2021. Run 2026-11-03.

## Decisions

- **Yearly granularity only** (2026-11-03). 39% of citing-work dates are year-only (see "January 1st"), so monthly features would be partly fabricated.
- **Year 0 = year the paper became public on arXiv, from the ID's `YYMM`** (2026-11-06). Never from OpenAlex, which uses journal dates for merged records. A late-December submission announced in January counts as January.
- **Papers published before their arXiv posting are flagged (`exclude_reason`) and excluded from modelling** (2026-11-06). Their "early" citations are those of a mature paper. Rows stay in `papers.parquet`; modelling filters them out. Not future information: the earlier publication is known at posting time.
- **Cleaning is done by rules applied to all papers**, never by hand-picking.
- **Published versions are not reconciled** (2026-11-03): when OpenAlex keeps separate records, we pick one rather than combining them. Rule: `docs/duplicate-records.md`.

## Data cleaning log

Every correction or exclusion, with the number of papers affected. If a treatment changes, update the row and bump the table's `extractor_version`.

| Issue | Papers | Treatment | Version | Status |
|---|---|---|---|---|
| v1 date before arXiv opened (1991-08-01) | 67 | `exclude_reason = 'posted_after_publication'` | `papers-v2` | Done |
| Posted after journal publication, normal-looking dates | unknown, probably rare | Detect from citations before year 0 and OpenAlex date earlier than year 0; threshold to set from data (one early citation is noise) | | Open, after OpenAlex join |
| Announced the year after submission (mostly late December) | 9,030 (0.3%) | Year 0 from the ID year | `papers-v2` | Done |
| ID year earlier than v1 year | 49 | Year 0 from the ID year; v1 date probably wrong | `papers-v2` | Done |
| Paper matches several OpenAlex records | 95,548 (3%) | One record per paper: most citations, or the arXiv-DOI record if all are preprints (`docs/duplicate-records.md`) | | Decided, not implemented |
| Legacy categories (`astro-ph` before 2009, bare `cond-mat`, ...) | not counted | Map to current categories | | Open, before E1.1 |
| `doi`, `journal_ref`, `update_date` are current values | all | Data checks only, never features | `papers-v1` | Done |

## arXiv metadata (Kaggle snapshot)

Downloaded 2026-11-06: 5.7 GB JSON lines → `data/papers.parquet` (95 MB) via `pipeline/build_papers.py`.

- **Size** (verified): 3,233,620 papers, none missing a date or category. Growth is steep: 64k (2009), 186k (2022), 284k (2025). Early cutoffs have far fewer training papers per area. ML primaries (cs.LG, cs.CL, cs.AI): about 280k.
- **Sorted by ID as text, not by date** (verified): new IDs first, old (`hep-th/...`) last. Sample with an even stride, not head or tail.
- **Format is consistent** (verified, 6,467 papers): `versions[0]` is always `v1`, one date format, space-separated categories. No primary-category field.
- **First listed category = primary** (verified): 99.95% match with the archive in old IDs (414,206 papers); 175 of 175 match the arXiv API for papers since 2017.
- **ID year vs v1 year** (verified): equal for 99.7%. The +1 cases are mostly December submissions announced in January. 67 papers have v1 dates before arXiv existed (backdated imports, incl. a `math/9201` batch; that batch likely has more, with normal dates). Hypothesis: IDs are assigned at announcement.
- **Legacy categories** (verified, sample): `astro-ph` was split into `astro-ph.CO`, `.GA`, ... in 2009; similar for `cond-mat`, `solv-int`, `supr-con`. Without a mapping, E1.1 splits one field into two areas over time. `hep-th`, `quant-ph`, `gr-qc` are current, not legacy.
- **`doi` / `journal-ref` are weak** (verified, sample): filled for 32% / 21% of papers since 2017, 9% of ML papers have a `doi`. Hand-entered, current values.

## OpenAlex

### Bulk download

- **Filter** (verified): `locations.source.id:S4306400194` (arXiv) returns 3.29M works, merged journal records included. Don't use the source's `works_count` (1.08M, primary locations only).
- **Download** (verified): `pipeline/fetch_openalex.py`, 3,294,071 works, 831 MB, in `data/raw/openalex/2026-11-07/`. Years up to 2020 fetched 2026-11-07, 2021 to 2026 on 2026-11-09 (resumed after interruption); each year within minutes. 150 duplicate rows; deduplicate by OpenAlex ID.
- **Matching** (verified), arXiv ID read from `/abs/`, `/pdf/` and `10.48550/arxiv.` locations:
  - 3,188,260 of 3,233,553 papers matched (98.6%).
  - The 45,200 unmatched papers exist in OpenAlex but are missing from the list endpoint's index, even when queried by exact ID; single lookups find them (100 of 100 sampled; 9 of 9 also pass ID extraction). Mostly recent records (`W69...` to `W71...`), and 30k of them are from 2025 (about 10% of that cohort), so skipping them would bias the latest data.
  - 95,548 papers (3%) match several works. Summing them overcounts. See `docs/duplicate-records.md`.
  - 9,088 works list several arXiv IDs (likely bad merges). Not yet examined.
  - 2,192 works yield no arXiv ID; 10,059 extracted IDs are not in Kaggle. Not yet examined.
- **Costs** (verified, response headers): 10,000 credits/day free. List page 1 credit, `search=` 10, single-work lookup 0.

### Records change from day to day (verified, 180 papers)

Between 2026-11-03 and 11-06, 16 of 180 papers got a new OpenAlex ID (re-merged), and merged records went from 103 to 116. Old IDs redirect in single lookups but not in list filters. So: **join on the arXiv ID, never the OpenAlex ID**, and build the citation table from one dated download.

### Lookup trap (verified, 180 papers)

`filter=doi:<arXiv DOI>` only matches a record's main DOI, so it misses merged records (found 10 to 15% of hep-th). Use `/works/<arXiv DOI>` or match on locations.

### Merging (verified, 180 papers)

A preprint published in a journal is usually merged into the journal record (journal DOI, journal date, citations combined). Share merged:

| | 2015 | 2018 | 2021 |
|---|---|---|---|
| cs.LG | 20% | 10% | 45% |
| hep-th | 85% | 90% | 90% |
| math.AG | 70% | 50% | 55% |

ML conference versions often stay separate, so **ML is undercounted relative to physics and math**. Per-area models are less affected. Merged records carry the journal date, mostly 1 to 2 years after arXiv.

### Citation counts

- **`counts_by_year` starts in 2012** (verified, full bulk download, 2026-11-12): 13.7M yearly entries, none before 2012. Citations from earlier years are in `cited_by_count` but not in the yearly series (old papers: 5 of 30 sampled have a complete series; `cond-mat/0212039` has 2 citations, from 2005 and 2006, and an empty series). **Early citation histories are complete only for papers with year 0 ≥ 2012.** The earlier finding "complete for 179 of 180" holds only because that sample started in 2015.
- **Counts are computed today**, so backtests assume citations were visible immediately.
- **Citations before year 0 are rare** (verified, 180 papers): 2 papers, 1 citation each.
- **39% of citing works are dated January 1st** (verified, 1 paper: Longformer): year-only dates. Harmless yearly, fatal monthly.
- **Fields differ** (verified, small groups): median citations at year 5, 2018 papers: cs.LG 23, hep-th 15, math.AG 3.
- **Far below Google Scholar** (verified, 1 paper): "Attention Is All You Need", 122k vs 280k.
- **Indexing lag** (verified, 1 paper): same paper, 23,883 citations in 2025 vs 7,145 in 2026 so far. Latest cutoffs need a buffer.
- **Location labels are noisy** (verified, 1 paper): `acceptedVersion` on mirror copies doesn't mean a published version exists.

## Open questions

- Why do 49 papers have an ID year earlier than their v1 year?
- What are the 9,088 works listing several arXiv IDs, and the 10,059 extracted IDs missing from Kaggle?
