# Data notes

Facts learned about the data sources, with the evidence behind them. Each note says whether it is **verified** (measured, numbers given) or a **hypothesis** (plausible, not yet checked). Exploration scripts live in `scripts/`.

The 180-paper sample referred to below comes from `scripts/sample_check.py` (seed 0): 20 random papers per (primary category, year) for cs.LG, hep-th and math.AG in 2015, 2018 and 2021, each group drawn from one random two-week window. Run on 2026-11-03.

## Decisions

- **Yearly granularity only** (2026-11-03). Monthly granularity (originally extension 2) is dropped. Reason: 39% of citing works for one paper have year-only dates (see "January 1st" below), which would make monthly features partly fabricated and leak future information.
- **Year 0 comes from the arXiv v1 date, never from OpenAlex** (2026-11-03). OpenAlex dates merged records with the journal date (see below).
- **Published versions are not reconciled** (2026-11-03). When OpenAlex keeps a published version as a separate record, its citations are not added. The target is "citations to the OpenAlex record that holds the arXiv version". See the merging note for the bias this introduces.
- **Calendar years**, as in the reference paper: year 0 is the calendar year of the arXiv v1 date.

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
