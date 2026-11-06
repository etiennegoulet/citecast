# Data notes

Facts learned about the data sources, with the evidence behind them. Each note says whether it is **verified** (measured, numbers given) or a **hypothesis** (plausible, not yet checked). Exploration scripts live in `scripts/`.

The 180-paper sample referred to below comes from `scripts/sample_check.py` (seed 0): 20 random papers per (primary category, year) for cs.LG, hep-th and math.AG in 2015, 2018 and 2021, each group drawn from one random two-week window. Run on 2026-11-03.

## Decisions

- **Yearly granularity only** (2026-11-03). Monthly granularity (originally extension 2) is dropped. Reason: 39% of citing works for one paper have year-only dates (see "January 1st" below), which would make monthly features partly fabricated and leak future information.
- **Year 0 comes from arXiv, never from OpenAlex** (2026-11-03). OpenAlex dates merged records with the journal date (see below).
- **Year 0 is the calendar year the paper became public on arXiv, read from the arXiv ID** (2026-11-06; replaces "calendar year of the v1 date" from 2026-11-03). A paper cannot be read or cited before it is announced, so the announcement year is the right start of its citation clock. The ID encodes the announcement month (`YYMM.NNNNN`, or `archive/YYMMNNN` for old IDs). This differs from the v1 submission year for 0.3% of papers, mostly late-December submissions announced in January (see "arXiv metadata" below). Implemented in `pipeline/build_papers.py`, `papers-v2`.
- **Papers already published before their arXiv posting are flagged and excluded from modelling** (2026-11-06). Such a paper is not new at its year 0: it may already have years of citations (OpenAlex merges it with its journal record), so its "early" citation history is really that of a mature paper, which is not what we predict. Rows are kept in `papers.parquet` with an `exclude_reason` column, and modelling drops flagged papers, so counts stay reproducible and the decision is reversible by changing a filter. This is not filtering on future information: that the paper was already published is known at posting time. Cleaning is done by rules applied to every paper, never by hand-picking papers.
- **Published versions are not reconciled** (2026-11-03). When OpenAlex keeps a published version as a separate record, its citations are not added. The target is "citations to the OpenAlex record that holds the arXiv version". See the merging note for the bias this introduces.
- **Calendar years**, as in the reference paper.

## Data cleaning log

Every correction, imputation or exclusion applied to the data, with how many papers it touches. If a treatment changes, update the row and bump the `extractor_version` of the affected table.

| Issue | Papers affected | Treatment | Table / version | Status |
|---|---|---|---|---|
| v1 date before arXiv opened (before 1991-08-01): papers that existed before they were posted | 67 (34 from 1986 to 1990, 33 from early 1991) | `exclude_reason = 'posted_after_publication'`; excluded from modelling | `papers` / `papers-v2` | Done |
| Papers posted to arXiv after their journal publication, with normal-looking dates (the general case of the row above) | unknown; probably rare (2 of 180 sampled papers had 1 early citation each, likely date noise) | Detect once OpenAlex is joined, from (a) citations in years before year 0 and (b) OpenAlex `publication_date` earlier than year 0; Kaggle `journal-ref` year as a weak extra signal. Same `exclude_reason`. A single early citation is not enough (citation dates are noisy); threshold to be set after looking at the full-scale distribution | `papers` | Open, after the OpenAlex join |
| v1 submitted in one year, announced (ID) in the next, mostly late December | 9,030 (0.3%) | Year 0 from the ID year, i.e. counted as January of the next year | `papers` / `papers-v2` | Done |
| ID year earlier than v1 year | 49 | Year 0 from the ID year (same rule). Cause unknown; a v1 date after the ID was assigned should be impossible, so the v1 date is probably wrong | `papers` / `papers-v2` | Done |
| Legacy categories (`astro-ph` before 2009, bare `cond-mat`, `solv-int`, `supr-con`, ...) | not yet counted | Map to current categories | `papers` | Open, needed before E1.1 |
| `doi`, `journal_ref`, `update_date` are snapshot values, not point-in-time | all | Kept for data checks only, never used as features | `papers` / `papers-v1` | Done (warning in the script docstring) |

## arXiv metadata (Kaggle snapshot)

Downloaded 2026-11-06 from Kaggle (`Cornell-University/arxiv`), file `arxiv-metadata-oai-snapshot.json`, 5.7 GB of JSON lines. Converted to `data/papers.parquet` (95 MB) by `pipeline/build_papers.py`.

### Size and coverage (verified, full file)

3,233,620 papers. No paper is missing a v1 date or a category. Papers per year grow steeply: 64k (2009), 113k (2016), 186k (2022), 284k (2025), 311k (2026 to late October, partial year). Consequence: early backtest cutoffs have far fewer training papers per area than late ones, which matters for bucket sizes.

Papers with an ML primary category (cs.LG, cs.CL, cs.AI): about 280k (estimated from a 1-in-500 sample). cs.CV is now the largest single primary category among papers since 2017, ahead of cs.LG.

### The file is sorted by ID as text, not by date (verified)

New-style IDs (`0704.0001` onward) come first, old-style IDs (`hep-th/9901001`) last, because digits sort before letters. Taking the head or tail of the file is not a sample of old or recent papers. Sample with an even stride (e.g. every 500th line).

### Format is consistent (verified, 6,467-paper evenly spread sample)

`versions[0]` is always `v1`. All version dates use the format `Mon, 2 Apr 2007 19:18:42 GMT`. Categories are always separated by single spaces. There is no explicit primary-category field.

### First listed category = primary category (verified for old IDs only)

Old-style IDs embed the primary archive (`hep-th/9901001`). For 414,206 old-ID papers, it matches the archive of the first listed category in 99.95% of cases. The 200 mismatches are reclassifications (127 `physics` papers now first-listed in `math-ph`, 57 `cs` now in `math`). This checks the archive level only, and only for papers before April 2007. **Still to verify** for recent papers at category level, against the arXiv API's `arxiv:primary_category`.

### Year in the arXiv ID vs v1 year (verified, full file)

The ID's `YYMM` is the month the paper was announced; the v1 date is when it was submitted. Difference (ID year minus v1 year): 0 for 3,224,541 papers (99.7%), +1 for 8,969, +2 or more for 61, negative for 49.

The +1 cases are almost all December submissions (7,993 of 8,969; 6,619 submitted on or after December 20). arXiv does not announce over the holidays, so these get January IDs and become public in January. Hypothesis, not checked against arXiv documentation: IDs are assigned at announcement, which is what makes the ID year the public year.

67 papers have v1 dates before arXiv opened in August 1991: 34 from 1986 to 1990 (e.g. `physics/9403001`: ID March 1994, v1 date April 1986) and 33 from January to July 1991, all `math/9201...` (a batch of older papers imported when the math archive opened in January 1992). These are papers that existed before they were posted. The same `math/9201` batch probably also contains papers with v1 dates from August 1991 onward, which this date rule does not catch; the OpenAlex check (data cleaning log) should.

Treatment of both: see "Decisions" and "Data cleaning log".

### Legacy categories change area labels over time (verified, sample)

Before 2009, astrophysics papers were filed as plain `astro-ph`; afterwards they are split into `astro-ph.CO`, `astro-ph.GA`, `astro-ph.SR`, etc. Bare `cond-mat`, `solv-int`, `supr-con` and others are similar. Old records sometimes list the legacy label first and its modern equivalent second (`"supr-con cond-mat.supr-con"`). Without a mapping, a per-category model (E1.1) would put 2008 and 2012 astrophysics papers in different areas, and `astro-ph` would vanish as a test area after 2009. Not every category without a dot is legacy: `hep-th`, `quant-ph`, `gr-qc` are current.

### `doi` and `journal-ref` are weak signals of publication (verified, sample)

Filled for 66% / 57% of pre-2007 papers, but only 32% / 21% of papers since 2017, and 9% of ML papers have a `doi`. Authors add them by hand and many never do. They are current values (point-in-time unsafe), so they cannot be features. Checking OpenAlex merging against them only works for older physics papers.

## OpenAlex

### Every sampled arXiv paper is in OpenAlex (verified, 180 papers)

180 of 180 sampled papers resolve through the single-work endpoint `GET /works/https://doi.org/10.48550/arXiv.<id>`.

**Trap:** the list filter `GET /works?filter=doi:<arXiv DOI>` only matches a record's *main* DOI. It found only 10 to 15% of hep-th papers, because most of them are merged into a journal record whose main DOI is the journal's (next note). The papers it did find were the unpublished ones, which biased every statistic toward low citations. Use the single-work lookup, or (for bulk) match on the arXiv location of each record.

### Preprints published in journals are merged into one record (verified, 180 papers)

When an arXiv paper appears in a journal with a DOI, OpenAlex merges the preprint into the journal record: main DOI = journal DOI, `type = article`, arXiv listed among the locations, citations to both versions combined. Example: arXiv 1509.07049 is `W2202834203`, Physics Letters B, 75 citations.

Share of sampled papers that are merged (record's main DOI is not the arXiv DOI):

| | 2015 | 2018 | 2021 |
|---|---|---|---|
| cs.LG | 20% | 10% | 45% |
| hep-th | 85% | 90% | 90% |
| math.AG | 70% | 50% | 55% |

ML papers are mostly published at conferences whose proceedings often have no DOI, so their published version is not merged and (as with "Attention Is All You Need" and NeurIPS) can sit in a separate record. **Consequence: the undercount from unmerged versions is uneven across fields, worse for ML than for physics or math.** Cross-field comparisons of citation levels are biased by this; per-field models (MM) are less affected, since each area is compared with itself.

### OpenAlex dates of merged records are journal dates (verified, 180 papers)

- Not merged (77 papers): OpenAlex `publication_date` equals the arXiv v1 date for 100%.
- Merged (103 papers): OpenAlex year minus arXiv v1 year is -1 (2 papers), 0 (29), +1 (52), +2 (16), +3 (3), +7 (1).

Hence the decision to take year 0 from arXiv.

### `counts_by_year` is complete (verified, 180 papers)

Its values sum to `cited_by_count` for 179 of 180 papers; the exception is off by 1 (1,268 vs 1,269). It covers more than 10 years (2012 to 2026 for "Attention Is All You Need"). Yearly citation series can therefore be read straight from the work record, without fetching citing works.

**Caveat:** these counts are computed today. A citation from 2019 that was indexed in 2023 still counts in 2019. Backtests built on them assume every citation was visible as soon as it was published, which is slightly optimistic for a live system.

### Citations dated before the paper are rare (verified, 180 papers)

Measured against the arXiv v1 year: 2 of 180 papers have any citation in a year before publication, 1 citation each. Earlier one-paper counts were larger (Longformer: 41 of 2,333 citing works dated before its publication *day*); most of those are probably year-only dates stored as January 1st (next note), which fall in the right *year* and are harmless at yearly granularity.

### Fields have clearly different citation curves (verified, 180 papers, small groups)

Median cumulative citations 5 years after publication: cs.LG 2018 = 23, hep-th 2018 = 15, math.AG 2018 = 3. Share of papers with zero citations to date: up to 25% in cs.LG, 15% in hep-th, 40% in math.AG (2021). Supports the premise of option B (all of arXiv): research areas behave differently. Groups are only 20 papers from one two-week window each, so treat individual numbers as rough.

Plot: `data/explore/sample_curves.png`.

### 39% of citing works are dated January 1st (verified on 1 paper)

Longformer (arXiv 2004.05150, published 2020-04-10): 915 of 2,333 citing works (39%) have `publication_date` = YYYY-01-01. Normal months get 15 to 40 citations; January 2021, 2022 and 2023 get about 200, 245 and 345. These are almost certainly works whose date only has year precision. At monthly granularity this would leak future information (a November citation counted from January); at yearly granularity it is harmless. This is why monthly granularity was dropped.

Script: `scripts/citation_curve.py`.

### OpenAlex counts far fewer citations than Google Scholar (verified on 1 paper)

"Attention Is All You Need", 2026-11-03: OpenAlex 122,093, Google Scholar 279,724. Likely causes: Google Scholar indexes more document types (theses, slides, reports), merges all versions, and extracts references from full text, while about two thirds of OpenAlex works have no references at all. Google Scholar is not usable anyway (no API, no bulk data, no point-in-time history).

### Location metadata is noisy (verified on 1 paper)

"Attention Is All You Need" has 8 locations from a Chinese preprint mirror (DOIs `10.65215/...`) labelled `version=acceptedVersion`. That label does not mean a peer-reviewed version exists.

### Indexing lag is visible (verified on 1 paper)

"Attention Is All You Need": 23,883 citations in 2025 vs 7,145 in 2026 (as of 2026-11-03), partly an incomplete year, partly unindexed citing works. The latest backtest cutoffs need a buffer.

## Open questions

- At full scale, what share of arXiv papers resolve in OpenAlex, by category and year? (100% in a 180-paper sample.)
- For the bulk pipeline: is the arXiv ID reliably present in the locations of merged records, so the join can be done locally?
- Is the first listed category the primary one for recent papers too? (Verified only at archive level for pre-2007 IDs.)
- Why do 49 papers have an ID year earlier than their v1 year?
