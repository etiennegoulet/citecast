# Experiment log

Planned experiments and, once run, their results. Each entry states the question, the variants, and what would count as an answer. Every experiment uses the same temporal splits, test papers and metrics, so results are directly comparable.

## Evaluation setup

Decided with the user, 2026-11-14. Two split designs, run in this order:

1. **Paper-style (reproduction).** Train on the year-0 cohorts 2012-2016, test on the 2017 cohort; every paper carries its full citations up to `year0 + k + h`. Five training cohorts as in the paper's DBLP experiment (its arXiv experiment uses six): with data to 2025, five is the only single split where the paper's full grid (`k` 0-5, `h` 1-3) is observed, since `2017 + 5 + 3 = 2025`.
   - **Look-ahead bias, accepted for comparability.** Training labels are measured in calendar years after the test papers' prediction time (for `k = 5, h = 3`: test papers are predicted at the end of 2022, while 2016 training papers have labels from 2024). No test-paper information leaks, but the model sees the citation climate of those years (field growth, coverage changes), which is shared by all papers cited in them. Expected to make results optimistic, most at large `k + h`.
2. **Strict point-in-time.** Predict at the end of year `T` for the cohort `year0 = T - k`; train only on cohorts whose labels are observed by `T` (`year0 + k + h ≤ T`). Rolled over every `T` the data allows (`14 - k - 2h` cutoffs). Details (training window, which cutoffs to report) still to discuss.

The gap between the two measures how much the standard setup overstates performance.

**Target: cumulative** (decided 2026-11-14). Inputs `c0..ck` and target `c_t` are citations through year `i` (resp. `t = k + h`). Later variants, not yet planned in detail: a yearly target (citations in year `t` only), converted to cumulative for scoring by predicting each year up to `t`; a log-transformed target scored on raw counts. For `h = 1` the yearly and cumulative targets give identical linear-regression predictions, because `c_k` is an input.

Still open for the reproduction: groups (100-paper rule vs 5 groups), target and metrics, OLS definitions (Abramo et al. 2019).

## E1. How should research areas be defined?

**Question.** MM fits separate models per research area. Which definition of "area" built from arXiv labels gives the best predictions? This also tests the paper's core claim: if no area definition beats "no areas at all", segmenting by area doesn't help for arXiv.

**Background.** Every arXiv paper has one primary category (chosen by the author at submission) and optional cross-listed categories. Categories form a hierarchy: group (Physics, Math, CS, ...) > archive (hep-th, astro-ph, cs, math, ...) > category (astro-ph.CO, cs.LG, math.AG, ...), about 150 categories in total.

**Variants.**

| ID | Area definition | Notes |
|---|---|---|
| E1.0 | None (one area for all papers) | The paper's MM-CC ablation. The reference point |
| E1.1 | Primary category | Closest to the paper's arXiv experiment |
| E1.2 | Primary archive (e.g. `cs`, `hep-th`) | Coarser: fewer, bigger areas |
| E1.3 | Adaptive: primary category, rolled up to its archive when the category has too few training papers | Threshold is a parameter |
| E1.4 | Frequent label pairs as their own area (e.g. `cs.LG + stat.ML`); rare pairs fall back to the primary category | Tests whether interdisciplinary papers behave differently |
| E1.5 | Multi-membership: a paper trains every model of its listed categories; its prediction averages those models | The multi-label idea the paper mentions as future work |

Cross-list information can also be used as features instead of for grouping (number of cross-lists, archives spanned). That belongs to the feature extension, not here.

**Constraints.**

- Each area needs enough training papers to form its citation groups (each group needs at least 100 papers, and we want about 5 to 10 groups per area). Area definitions that create many small areas (E1.1, E1.4) need a minimum-size rule, and the rule must be reported.
- **Point-in-time risk for cross-lists.** Authors can add cross-lists after submission, and the arXiv metadata snapshot only shows the current labels. Variants E1.4 and E1.5 may therefore use labels that did not exist at prediction time. The primary category is fixed at submission (changes are rare), so E1.0 to E1.3 are safe. Before running E1.4 or E1.5, check whether the arXiv history (e.g. OAI-PMH records) records when cross-lists were added; if it doesn't, report the risk next to the results.
- The taxonomy changed over time (legacy categories, new archives like `eess` and `econ` in 2017), but no mapping is needed for year 0 ≥ 2012: the snapshot uses current names for all papers (`docs/data-notes.md`, "arXiv metadata").

**Answer looks like.** One table per history length `k`: metrics for each variant, plus the number of areas each variant produced.

**Status.** Planned.
