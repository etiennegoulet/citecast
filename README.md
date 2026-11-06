# citecast

Forecasting future citation counts of arXiv papers from their early citation history. The dataset covers every arXiv field; results for the ML categories (cs.LG, cs.CL, cs.AI) are the headline.

This project reproduces and extends:

> Zhang, F. and Wu, S. (2024). Predicting citation impact of academic papers across research areas using multiple models and early citations. *Scientometrics* 129(7), 4137-4166. doi:10.1007/s11192-024-05086-0

## What the paper does

**Idea.** Citation patterns differ across research areas (AI papers peak around year 4, cryptography papers around year 11) and across papers of different impact within an area (highly cited papers peak later). So instead of one model for all papers, the paper fits many small models, each on a homogeneous group of papers.

**Method (MM, "Multiple Models").**

1. *Assign each paper a research area.* On DBLP, papers have no area label, so most of the paper is spent on a classifier (IBL: BM25 text similarity plus citation links to "seed" papers from top venues listed on CSRankings, 26 areas). On arXiv this step is skipped, because authors label their own papers.
2. *Group papers within each area by early citations.* Let `cc(i)` be the number of papers with `i` citations in the first `m` years. Walk `cc(0), cc(1), ...` in order, accumulating until the running total reaches 100 papers, then close the group and start a new one. The last group may hold fewer than 100. The paper uses 10 groups per area on DBLP and 5 on arXiv.
3. *Fit one linear regression per (area, group):* `c'_t = w0*c0 + w1*c1 + ... + wm*cm + b`, where `c0..cm` are citation counts up to years `0..m` and `c'_t` is the count in year `t >= m`.
4. *Predict* a new paper by finding its area and group, then applying that group's regression.

**Data.**

| | DBLP experiment | arXiv experiment |
|---|---|---|
| Source | AMiner DBLP dump (4.1M papers, 1961-2019) | unarXive (1.04M papers, 1991-2022, citations extracted from arXiv full texts) |
| Train | papers from 1990-1994 (38,247) | papers from 2008-2013 (5,876) |
| Test | papers from 1995 (9,967) | papers from 2014 (1,471) |
| Areas | 26 CSRankings areas, via the IBL classifier | author-assigned arXiv labels |

On DBLP, papers that never received a citation were removed before training and testing.

**Evaluation.** History length `k` from 0 to 5 years (`k = 0` means predicting in the publication year), predicting 1, 2 and 3 years ahead. Metrics are MSE and R² on raw citation counts, plus MSE on the 100 most cited test papers.

**Baselines.** MEY (mean of early years), AVR (Cao et al. 2016: average the later counts of the training papers with the most similar early curves), four OLS variants (Abramo et al. 2019; the `OLS2` variants add journal impact factor), an RNN, and NCFCM (an MLP combining simpler predictors).

**Findings.**

- MM wins most cells. `OLS2_res` wins several, especially with short history, because it is the only method using venue information.
- Ablation: research area alone beats early citations alone at `k = 0` and `k = 1`. Early citations take over for `k > 1`.
- On the 100 most cited arXiv papers, MM's MSE is roughly 20x lower than every baseline (2,523 vs ~46,000 to 69,000 at `k = 0`).
- Stated future work: add venue and author information.

## What this project changes

| | Paper | This project | Why |
|---|---|---|---|
| Citation source | unarXive (citing papers must themselves be on arXiv) | OpenAlex (citations from all indexed literature) | Counts citations from journals and conferences too, and scales to the full category |
| Papers | 5,876 train / 1,471 test, all arXiv fields | All arXiv papers, every field (millions) | Scale. ML categories are reported as the headline |
| Research areas | arXiv labels across all fields | arXiv primary category by default; other definitions compared in experiment E1 (`docs/experiments.md`) | Same mechanism; no classifier needed |
| Year 0 | Publication year (source not stated) | Year the paper was announced on arXiv (from its ID) | OpenAlex dates papers merged into a journal record with the journal date, usually 1 to 3 years later; and a paper submitted in late December is public, and citable, only from January (`docs/data-notes.md`) |
| Train/test split | One cutoff (train 2008-2013, test 2014) | Several rolling temporal cutoffs | ML publishing changed a lot after 2022; one cutoff can't show whether results hold over time |
| Time step | Years | Years | Monthly steps were planned but dropped: about 39% of OpenAlex citation dates have year precision only (`docs/data-notes.md`) |
| Zero-citation papers | Removed (DBLP) | Kept | Whether a paper is ever cited is only known later; removing them uses future information |
| Features | Early citations only | Early citations, then author and venue features | The paper's own stated future work |
| Prediction target | Raw citation count | Raw count (for comparison) and "top 10% of its field-year cohort by year 2" | Raw counts are heavy-tailed; a ranking target is easier to interpret |
| Metrics | MSE, R², top-100 MSE | Same, plus precision@k and NDCG | Comparable to the paper, plus ranking quality |
| Baselines | MEY, AVR, OLS ×4, RNN, NCFCM | MEY, AVR, OLS ×4, plus raw citation count used directly as a ranker | Raw count is the bar the literature says is hard to beat. The neural baselines are dropped: they don't consistently beat OLS in the paper's own tables and add a lot of complexity |
| Estimator | Linear regression per group | Same for MM; gradient boosting for any feature-rich model | The paper's contribution is the grouping, not the estimator |

## Open questions in the paper

Points the paper leaves ambiguous. Each choice made here will be documented.

- **Cumulative or yearly counts?** `c0..cm` are described as counts "up to year `i`" (cumulative) while the target is the count "in year `t`" (could be yearly).
- **Number of groups.** The 100-paper rule decides the number of groups by itself, yet the paper also says it "sets" 10 or 5 groups. How these are reconciled is not stated.
- **OLS variants.** `_res` and `_log` are described only as "linear" and "logarithmic regularization". The exact definitions must come from Abramo et al. (2019).
- **How the arXiv subset was built.** Only 5,876 of the 1.04M unarXive papers were used for 2008-2013; the selection criteria are not given.

## Known limitations

- **Citations are counted as OpenAlex indexes them**, which is far below Google Scholar (e.g. 122k vs 280k for "Attention Is All You Need").
- **Published versions are not reconciled.** OpenAlex merges a preprint into its journal record (complete counts), but conference versions, common in ML, often stay separate records whose citations are not counted. ML papers are therefore undercounted relative to physics or math.
- **Backtests assume citations are visible as soon as they are published.** OpenAlex's yearly counts are computed today, so indexing lag is ignored in backtests.

## Evaluation principles

- Temporal splits only, backtested across multiple cutoffs.
- Every feature is computed point-in-time: only data available at prediction time.
- Results are always compared against simple baselines, including the raw citation count at prediction time. Negative results are reported as such.

## Status

Early development. Results will be reported here.
