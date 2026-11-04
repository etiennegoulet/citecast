# Project context

## What this is

A citation forecasting system for arXiv papers. Given a paper and its early citation history, predict its future citation count. The dataset covers all of arXiv (every field); results for the ML categories (cs.LG, cs.CL, cs.AI) are the headline.

This is a reproduction and extension of **Zhang, F. and Wu, S. (2024), "Predicting citation impact of academic papers across research areas using multiple models and early citations," Scientometrics 129(7), 4137-4166** (open access, doi 10.1007/s11192-024-05086-0). Readable copy: Ulster University repository, https://pure.ulster.ac.uk/ws/files/206809081/s11192-024-05086-0.pdf (Springer's page requires a login for automated fetches).

Scope is deliberately narrow. This repo does **not** cover real-time importance ranking, digest generation, blog post ingestion, or LLM-based assessment. Those are separate concerns in a separate project.

## Where things are written down

- `README.md`: what the paper does, what this project changes and why, open questions in the paper.
- `docs/data-notes.md`: verified facts and decisions about the data, with numbers. Check it before making assumptions about OpenAlex or arXiv. Add to it when something new is learned.
- `docs/experiments.md`: planned experiments (e.g. E1, how to define research areas) and their results.
- `scripts/`: Phase 1 exploration scripts. Not part of the pipeline.

## The reference method (MM)

Zhang and Wu's method, stripped to essentials:

1. Assign each paper to a research area. For arXiv this is free, since authors supply category labels. No classifier needed (the paper's IBL classifier exists only for DBLP, which has no labels). Default area = the arXiv **primary** category; alternatives (archive level, adaptive roll-up, label pairs, multi-membership) are experiment E1 in `docs/experiments.md`.
2. Within each research area, bucket papers by how many citations they already have at year `m`. Bucketing rule: walk citation counts `cc(0), cc(1), ... cc(n)` in order, accumulating until the bucket holds at least 100 papers, then start a new bucket. The paper uses 10 buckets for DBLP, 5 for their (smaller) arXiv set. The paper does not say how the 100-paper rule and the fixed bucket count are reconciled; document the choice made.
3. Fit a separate multiple linear regression per (area, bucket):
   ```
   c'_t = w0*c0 + w1*c1 + ... + wm*cm + b
   ```
   where `c0..cm` are citation counts up to year 0..m and `c'_t` is the predicted count at year `t >= m`.

The estimator is plain linear regression. The contribution is the segmentation, not the model. Do not over-engineer this part.

**Key ablation finding from the paper:** research area is the more useful signal when `k = 0` or `k = 1` years of history; early citation counts overtake it when `k > 1`.

## Extensions planned (the actual contribution)

In rough order of effort:

1. **Scale and breadth.** The paper's arXiv experiment uses 5,876 training and 1,471 test papers, one temporal cutoff, and citations only from other arXiv papers (unarXive). Rerun on all of arXiv with citations from OpenAlex (millions of papers), across multiple cutoffs. Including every field makes the research-area segmentation meaningful: cs.LG, cs.CL and cs.AI alone overlap too much to test it.
2. **Author and venue features**, which is Zhang and Wu's own stated future work. Take the feature set from **Bai, X., Zhang, F. and Lee, I. (2019), "Predicting the citations of scholarly paper," Journal of Informetrics 13(1), 407-418**: author Q value (Sinatra et al. 2016), h-index, Author Impact Factor, journal impact factor, plus yearly citations c1..c5. In that paper's own feature-importance results the early-citation features dominate (c5 ≈ 0.35, c4 ≈ 0.10, c3 ≈ 0.08, c2 ≈ 0.06); author and venue features rank well below. Expect small gains.

**Dropped: monthly granularity** (2026-11-03). About 39% of OpenAlex citing works carry year-only dates stored as January 1st, so monthly features would be partly fabricated and would leak future information. Evidence in `docs/data-notes.md`. Everything is in yearly steps.

## Prediction task framing

Prefer **binary classification on cohort-normalized top-decile** over regression on raw counts. Raw-count regression fights the heavy tail and produces metrics nobody can interpret. Target: "will this paper reach the top decile of citations for its field-year cohort by year 2 after publication, given only citations through year k."

Report ranking metrics (precision@k, NDCG) alongside the paper's own metrics (MSE, R-squared) so results stay comparable to the reference.

## Baselines that must be beaten

Implement and always report these. They are named in the reference paper.

- **MEY** (mean of early years): average of early citations as the prediction.
- **AVR** (Cao et al. 2016): find training papers with the most similar early citation curve, average their later counts.
- **OLS variants** (Abramo et al. 2019): `OLS_res`, `OLS_log` use early citations only; `OLS2_res`, `OLS2_log` add venue impact factor. Note that `OLS2_res` beats MM in several of the paper's cells, especially at short history. The paper defines `_res` and `_log` only vaguely; take the exact definitions from Abramo et al. (2019).
- **Raw citation count at year k, used directly as a ranker.** This is the real bar. The literature says it is hard to beat. If the model does not beat it on held-out data, say so in the README rather than adding features until something looks better.

The paper's RNN and NCFCM baselines are deliberately not reproduced: they do not consistently beat OLS in the paper's own tables.

## Hard constraints

**Point-in-time discipline is non-negotiable.** Every feature for a paper evaluated at time T must be computed using only records whose timestamp is at or before T. Author h-index, venue citation rates, and citation counts are all point-in-time queries, not current values. A 2026-indexed fact must never appear in a 2022 feature vector. Violating this produces a model that looks excellent offline and fails in production.

**Year 0 is the calendar year of the arXiv v1 date.** Never use OpenAlex's `publication_date` for it: for preprints merged into a journal record, OpenAlex gives the journal date, usually 1 to 3 years later.

**No filtering on future information.** Do not drop papers that never get cited (the paper did this on DBLP); whether a paper is ever cited is only known later.

**Temporal splits only.** Train on papers up to year T, test on papers after. Never random-split. Backtest across multiple cutoffs, since the pre and post-LLM shift in ML publishing is large enough to break a single-cutoff estimate.

**Indexing lag is real and distinct from citation lag.** A paper from last month shows near-zero citations in OpenAlex not because it has none, but because citing works are not indexed yet. The current calendar year is always incomplete: treat the last full year as the end of the data, and leave a buffer before the latest backtest cutoffs. `counts_by_year` is computed today, so backtests assume citations were visible as soon as they were published; state this in results.

## Data

Details and evidence for everything here: `docs/data-notes.md`.

- **arXiv metadata** (IDs, primary and cross-listed categories, v1 dates) comes from the **Kaggle arXiv metadata snapshot** for the full dataset. The arXiv API is only for small samples: one request per 3 seconds, single connection, no citation counts. Cross-lists can be added after submission and the snapshot only shows current labels, so cross-list-based features carry a point-in-time risk.
- **OpenAlex** is the citation source. Yearly series come from `counts_by_year` on each work (verified complete: sums to `cited_by_count` for 179 of 180 sampled papers). Use OpenAlex's counts as given; published versions are not reconciled.
  - **Lookup trap:** `filter=doi:<arXiv DOI>` only matches a record's main DOI and misses preprints merged into journal records (most of physics and math). Look up `/works/<arXiv DOI>` directly, or for bulk work, match on the arXiv location (`arxiv.org/abs/<id>`) inside each record.
  - Merging is uneven: most hep-th and math papers are merged into journal records (complete counts), most cs.LG papers are not (conference versions often stay separate, so counts are partial). Cross-field comparisons of citation levels are biased by this.
  - API keys are required (free), stored in `.env` as `OPENALEX_API_KEY`. The bulk CC0 snapshot remains free.
  - Roughly 67% of OpenAlex works have no references, so reference-dependent features need cross-source reconciliation.
- **Semantic Scholar (S2AG)** for citation contexts and SPECTER2 embeddings if text features get added. Rate limit around 1 req/s with a key; prefer the bulk datasets.
- **unarXive** (Saier and Färber 2020, Zenodo doi 10.5281/zenodo.3385851) is the reference paper's own arXiv dataset. Not used: it only counts citations from other arXiv papers. Revisit only if our MM results diverge wildly from the paper's.

## Conventions

- Python 3.13, managed with uv (`uv add <pkg>`, `uv run <script>`). Commit `uv.lock`.
- Gradient boosting (not deep learning) for any model beyond the reference linear regressions. The literature consistently shows neural approaches do not beat GBDT here.
- Storage: Parquet files queried with DuckDB. Raw and derived data live in `data/` (gitignored) and are rebuilt by scripts.
- Log every scored paper with its full feature vector and model version. Without this, a bad result is undiagnosable.
- Store `extractor_version` on any derived field so old feature vectors stay reproducible after re-extraction.

## Working style

- The user wants to understand every piece of code. Show code and explain what it does, how it works and why, before writing it to disk. Work in small, reviewable steps.
- The user handles all git commits and pushes. Do not commit.
- This repo is part of an ML application to Mila: favour rigour, honest negative results and clear write-ups over features.

## Communication preferences

- No em dashes.
- Push back on bad ideas directly rather than implementing them. Flag when an approach has weak empirical support.
- Lead with the answer, not with a restatement of the question.
