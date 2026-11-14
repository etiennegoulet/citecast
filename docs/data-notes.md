# Data notes

Facts about the data, with evidence. Each note is **verified** (measured) or a **hypothesis**.

"180-paper sample": `scripts/sample_check.py`, 20 papers per (category, year) for cs.LG, hep-th, math.AG in 2015, 2018, 2021. Run 2026-11-03.

## Decisions

- **Yearly granularity only** (2026-11-03). 39% of citing-work dates are year-only (see "January 1st"), so monthly features would be partly fabricated.
- **Year 0 = year the paper became public** (2026-11-06, extended 2026-11-13). Normally the arXiv year from the ID's `YYMM`; a late-December submission announced in January counts as January. **Exception:** if OpenAlex shows an earlier publication less than a year before the arXiv v1 date, year 0 is that earlier year (`year0_source = 'openalex_earlier'`, 22,555 papers). OpenAlex's date never moves year 0 later: merged records carry the journal date, 1 to 3 years after arXiv. Rule and evidence: "Late uploads".
- **Papers published before their arXiv posting are flagged (`exclude_reason`) and excluded from modelling** (2026-11-06). Their "early" citations are those of a mature paper. Rows stay in `papers.parquet`; modelling filters them out. Not future information: the earlier publication is known at posting time. Detection rule: see "Late uploads" below.
- **The population is new papers as they first appear on arXiv** (2026-11-13). The model predicts for a paper whose first public appearance is its arXiv posting. Once late uploads are excluded, that is "new papers in arXiv-covered fields", which for ML is nearly all new papers. Considered and rejected:
  - *Year 0 = OpenAlex publication date.* For most merged records it is the journal date, 1 to 3 years after arXiv, so it would push genuine early citations before year 0 across most of physics and math.
  - *Redating late uploads to their original year and keeping them.* Late uploads are selected on success (see "Late uploads"), so the old cohorts would contain papers that are on arXiv because they became important: future information.
  - *Dropping arXiv and using all of OpenAlex.* Loses author-assigned areas (OpenAlex topics are model-assigned and recomputed, so not point-in-time), brings the merged-versions problem to every field (bioRxiv, SSRN), 250M+ noisy works, and OpenAlex adds old works retroactively. Possible later experiment ("does it transfer?"), not the foundation.
- **Papers with year 0 from 2012 on** (2026-11-13). `counts_by_year` starts in 2012. The full history exists in OpenAlex's citation graph (see "Citation counts"), but rebuilding it costs either about 1M API credits (one `cites:` + `group_by` query per pre-2012 paper, 10k credits/day free) or processing the full bulk snapshot (hundreds of GB). Not worth it: 2012-2025 has 2.2M papers. Cost: the paper's own split (train 2008-2013, test 2014) is not reproduced. Train/test splits are not decided yet.
- **Citations before year 0 alone are not an exclusion criterion** (2026-11-13). Most small cases are genuinely new papers with misdated citing works; excluding them would drop about 54k new papers and bias toward cited papers.
- **Cleaning is done by rules applied to all papers**, never by hand-picking.
- **Published versions are not reconciled** (2026-11-03): when OpenAlex keeps separate records, we pick one rather than combining them. Rule: `docs/duplicate-records.md`.

## Data cleaning log

Every correction or exclusion, with the number of papers affected. If a treatment changes, update the row and bump the table's `extractor_version`.

| Issue | Papers | Treatment | Version | Status |
|---|---|---|---|---|
| v1 date before arXiv opened (1991-08-01) | 67 | `exclude_reason = 'posted_after_publication'` | `papers-v2` | Done |
| Posted after journal publication, normal-looking dates (late uploads) | 35,852 | Earliest OpenAlex date more than 365 days before v1: `exclude_reason = 'posted_after_publication'` in `dataset.parquet`. See "Late uploads" | `dataset-v3` | Done |
| Published less than a year before arXiv, in an earlier calendar year | 22,555 | Year 0 redated to the earlier year (`year0_source = 'openalex_earlier'`) | `dataset-v3` | Done |
| No earlier publication date, but more than 10 citations before year 0 (unlinked old version or broken record) | 563 | `exclude_reason = 'cited_before_posting'` | `dataset-v3` | Done |
| Paper's OpenAlex record shared with other arXiv papers (record lists several arXiv IDs) | 9,248 in 2012-2025 (0.42%); 8,744 carry this reason, the other 504 are labelled as late uploads (one reason per paper, first match wins) | `exclude_reason = 'shared_openalex_record'` in `dataset.parquet`. See "Shared records" | `dataset-v2` | Done |
| Duplicated arXiv IDs in the Kaggle snapshot | 81 IDs, 174 rows | All `math-ph`, year 0 ≤ 2007, rows differ in metadata. Outside the 2012+ data; dedup rule still to decide for `papers.parquet` | | Open |
| Announced the year after submission (mostly late December) | 9,030 (0.3%) | Year 0 from the ID year | `papers-v2` | Done |
| ID year earlier than v1 year | 49 | Year 0 from the ID year; v1 date probably wrong | `papers-v2` | Done |
| Paper matches several OpenAlex records | 95,548 (3%) | One record per paper: most citations, or the arXiv-DOI record if all are preprints (`docs/duplicate-records.md`) | `citations-v1` | Done |
| Legacy categories (`astro-ph` before 2009, bare `cond-mat`, ...) | 0 in 2012-2025 | Not needed: no legacy primaries, aliases already canonical (see "arXiv metadata") | | Closed |
| Record flagged as shared only through a truncated arXiv link (`1906.0980` for `1906.09800`) | 4 | Left excluded as `shared_openalex_record`: negligible, not worth a rebuild. Fix if the tables are rebuilt anyway (see "Shared records") | `citations-v2` | Known, not fixed |
| `doi`, `journal_ref`, `update_date` are current values | all | Data checks only, never features | `papers-v1` | Done |

## arXiv metadata (Kaggle snapshot)

Downloaded 2026-11-06: 5.7 GB JSON lines → `data/papers.parquet` (95 MB) via `pipeline/build_papers.py`.

- **Size** (verified): 3,233,620 papers, none missing a date or category. Growth is steep: 64k (2009), 186k (2022), 284k (2025). Early cutoffs have far fewer training papers per area. ML primaries (cs.LG, cs.CL, cs.AI): about 280k.
- **Sorted by ID as text, not by date** (verified): new IDs first, old (`hep-th/...`) last. Sample with an even stride, not head or tail.
- **Format is consistent** (verified, 6,467 papers): `versions[0]` is always `v1`, one date format, space-separated categories. No primary-category field.
- **First listed category = primary** (verified): 99.95% match with the archive in old IDs (414,206 papers); 175 of 175 match the arXiv API for papers since 2017.
- **ID year vs v1 year** (verified): equal for 99.7%. The +1 cases are mostly December submissions announced in January. 67 papers have v1 dates before arXiv existed (backdated imports, incl. a `math/9201` batch; that batch likely has more, with normal dates). Hypothesis: IDs are assigned at announcement.
- **Legacy categories** (verified, sample): `astro-ph` was split into `astro-ph.CO`, `.GA`, ... in 2009; similar for `cond-mat`, `solv-int`, `supr-con`. Without a mapping, E1.1 splits one field into two areas over time. `hep-th`, `quant-ph`, `gr-qc` are current, not legacy.
  - **Not an issue for year 0 ≥ 2012** (verified, `dataset.parquet`, 2026-11-14). No paper has a legacy primary: the splits all predate 2012. Alias pairs appear under one name only: `eess.SY` (never `cs.SY`), `math.NA` (never `cs.NA`), `cs.IT` (never `math.IT`), `math.ST` (never `stat.TH`), `econ.GN` (never `q-fin.EC`).
  - **The snapshot shows current names, even for older papers.** `eess` (created 2017) has 73,033 papers from year 0 = 2012, `econ` (2017) has 10,865 from 2014; `eess.SY` has 461 papers in 2014. arXiv relabelled old papers. This is a renaming, not information about the paper's future, so no point-in-time issue for area definitions.
- **`doi` / `journal-ref` are weak** (verified, sample): filled for 32% / 21% of papers since 2017, 9% of ML papers have a `doi`. Hand-entered, current values.

## OpenAlex

### Bulk download

- **Filter** (verified): `locations.source.id:S4306400194` (arXiv) returns 3.29M works, merged journal records included. Don't use the source's `works_count` (1.08M, primary locations only).
- **Download** (verified): `pipeline/fetch_openalex.py`, 3,294,071 works, 831 MB, in `data/raw/openalex/2026-11-07/`. Years up to 2020 fetched 2026-11-07, 2021 to 2026 on 2026-11-09 (resumed after interruption); each year within minutes. The folder name is the start date only; `build_citations.py` sets each record's `openalex_run_date` from its slice year.
- **150 works were downloaded twice** (verified, 2026-11-13). 149 have identical copies. One changed between the two days: `W3097946243` (`2010.14172`) was the arXiv preprint on 11-07 (arXiv DOI, 2020-10-27, 6 citations) and merged with its journal version by 11-09 (journal DOI, 2022-08-24, 10 citations), so it appeared in both the 2020 and 2022 slices. Deduplication used to pick a copy arbitrarily, which flipped this paper's pattern between builds. Since `citations-v2`, the copy from the later slice (fetched later) wins, so rebuilds are deterministic (checked: two rebuilds, identical). This relies on slices having been fetched in year order; the files carry no timestamp.
- **Matching** (verified), arXiv ID read from `/abs/`, `/pdf/` and `10.48550/arxiv.` locations:
  - 3,188,260 of 3,233,553 papers matched (98.6%).
  - The 45,200 unmatched papers exist in OpenAlex but are missing from the list endpoint's index, even when queried by exact ID; single lookups find them (100 of 100 sampled; 9 of 9 also pass ID extraction). Mostly recent records (`W69...` to `W71...`), and 30k of them are from 2025 (about 10% of that cohort), so skipping them would bias the latest data.
  - Fetched one by one with `pipeline/fetch_missing.py` (2026-11-12, `data/raw/openalex/missing/`): 44,941 found, 259 returned 404 (192 from `2508`, 43 from `2507`: probably not indexed yet). 2 found records have no arXiv location (`2507.15729` resolves to a TUM repository copy, `2508.11329` to a figshare preprint), so they stay unlinked.
  - **After the fetch: 3,233,266 papers have a record (99.99%).** Missing: 261 papers, all from 2024-2025.
  - 95,548 papers (3%) match several works. Summing them overcounts. See `docs/duplicate-records.md`.
  - 9,088 works list several arXiv IDs. Examined and excluded: see "Shared records".
  - 2,192 works yield no arXiv ID. Not examined: they cannot link to any paper, so they cannot affect the dataset.
  - **9,990 distinct extracted IDs are not in Kaggle** (verified, 2026-11-14; an earlier count of 10,059 used another method). 9,982 are 2026 IDs newer than the snapshot (Kaggle's newest is `2610.40657`). 4 are truncated links: a 4-digit number from 2015 on, when numbers have 5 digits (`1906.0980`, `2103.0852`, `2208.1468`, `2305.1978`). 2 are probably withdrawn papers (`2307.02646`, `2401.09755`). 2 are pre-2012 old-style IDs (`acc-phys/9607002`, the typo `hepph/0410176`). No format mismatch with real Kaggle papers.
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
- **The cut-off is in `counts_by_year`, not in OpenAlex** (verified, 1 paper, 2026-11-13). `math/0512560` (`W1597806979`): `/works?filter=cites:W1597806979&group_by=publication_year` gives citations from 2005 to 2023 summing to 32 = `cited_by_count` (2005: 1, 2006: 3, 2007: 2, 2008: 3, 2009: 3, 2011: 5, ...), while `counts_by_year` only has 2013 onward. The website's "cited by" view uses the graph, so it shows the full history. `cited_by_count` is computed from the same graph, so a rebuild would be as complete as the totals.
- **Citation years are the citing work's OpenAlex `publication_date`** (both in `counts_by_year` and in `group_by`), which can be off in both directions: too early for preprints (dated by first version; a reference added in a revision looks older), too late for citing works merged into a journal record (journal date, often 1 to 3 years after the citing preprint). Hypothesis: small at yearly granularity; "too late" lowers early counts (conservative), "too early" is a small leak (roughly 1 to 3% of papers, usually one citation by one year, judging from the 1-citation-before-year-0 sample). Not measured. Stated as a limitation in the README.
- **Counts are computed today**, so backtests assume citations were visible immediately.
- **Yearly series vs total** (verified, full data, 2026-11-13). For year 0 ≥ 2012: the series sums to `cited_by_count` for 2.03M papers (81%), is empty (uncited) for 455k (18%), and falls short for 27k (1.1%, median gap 1 citation). Before 2012, 498k papers fall short (median gap 10), as expected from the 2012 start.
- **Citations before year 0 are not rare** (verified, full data, 2026-11-13). The earlier "2 of 180 papers" was a small-sample artefact. Of papers with year 0 from 2013 to 2025, 81,509 (3.7%) have at least one, steady at 3 to 5% per year (2012 shows 0 only because the series starts that year). By count: 1 citation 54,504; 2 to 5: 17,342; 6 to 20: 7,044; more than 20: 2,619. Two different causes; see "Late uploads".
- **39% of citing works are dated January 1st** (verified, 1 paper: Longformer): year-only dates. Harmless yearly, fatal monthly.
- **Fields differ** (verified, small groups): median citations at year 5, 2018 papers: cs.LG 23, hep-th 15, math.AG 3.
- **Far below Google Scholar** (verified, 1 paper): "Attention Is All You Need", 122k vs 280k.
- **Indexing lag** (verified, 1 paper): same paper, 23,883 citations in 2025 vs 7,145 in 2026 so far. Latest cutoffs need a buffer.
- **Location labels are noisy** (verified, 1 paper): `acceptedVersion` on mirror copies doesn't mean a published version exists.

### Shared records: several arXiv papers on one OpenAlex record (2026-11-13)

**What they are** (verified, full data and 7 examples). 9,182 OpenAlex records are chosen by 17,757 papers and list more than one arXiv ID; 8,382 of them carry exactly 2 papers. In 2012-2025: 9,248 papers. Examples (OpenAlex title → arXiv papers):

| Record | Papers | What it looks like |
|---|---|---|
| "Hard choices in artificial intelligence", Artificial Intelligence 2021, 105 citations | `1911.09005` (2019, cs.AI), `2106.11022` (2021, cs.CY) | Two papers by one group, two years apart, one journal record |
| "Vehicle Routing Problem ... Hybrid Quantum Algorithms", IEEE TQE 2023 | `2112.15408`, `2205.07630` | Probably conference paper + journal extension |
| "Optimal number of terms in QED series ...", Phys. Rev. A 2015 | `1309.6894` (hep-th), `1409.3765` (cond-mat) | Two related papers in different fields |
| "Flux-induced topological superconductivity ...", Science 2020, 223 citations | `1809.05512`, `1809.05513`, `2003.13177` | Companion papers merged into the final paper |
| "Proceedings of the Workshop HIP3ES 2016" | `1602.03404`, `1701.03053`, `1801.03513`, `1901.04797` | Four years of a workshop's proceedings in one record: bad merge |
| "Heavy Quark Physics" (book) | 9 papers, 2002-2003 | Each lecture chapter on arXiv, one book record |

**Why their counts are unreliable.** Every paper on the record gets the record's full count, though each earned part of it (or one earned all). The later paper inherits the earlier one's citations, so it gets citations before year 0 and looks like a fast starter. Nothing in the data says who earned what.

**Decision: excluded** (`exclude_reason = 'shared_openalex_record'`, `dataset-v2`). The reason is that their outcome cannot be measured, not what their outcome is. Merging usually happens after year 0 (journal publication), so a deployed system would still score these papers at year 0; they are excluded from training and evaluation only. To be stated in results with the count. Rejected: keeping them (corrupt labels, possibly in the top decile), splitting the credit (no basis for a rule), switching to the paper's own preprint record where one exists (only 1,035 papers, and it trades an inflated count for an undercount).

**Not concentrated in ML** (verified): share of 2012-2025 papers excluded: cs.LG 0.28%, cs.CL 0.17%, cs.AI 0.40%, all fields 0.42%. Highest among archives with at least 5,000 papers: hep-lat 3.1% (likely conference proceedings), hep-ex 1.2%, hep-ph 1.0%; all others under 0.8%. So no sensitivity rerun needed for the headline.

**4 false positives** (verified, 2026-11-14). A truncated link (see "Matching") counts as a second arXiv ID, so the record is flagged as shared: `1906.09800`, `2103.08527`, `2305.19782` (each linked to a truncated copy of its own ID) and `2309.01997` (linked to `2208.1468`, which resolves to no paper). Left excluded: negligible. Fix if `build_citations.py` is rerun for another reason: drop IDs matching `^\d{4}\.\d{4}$` with YYMM ≥ 1501 right after extraction. Genuine sharing with a 2026 paper not yet in the snapshot (e.g. `2305.06795`, `2505.12354`) is correctly excluded.

### Late uploads: papers posted on arXiv after publication (2026-11-13)

**What they are** (verified, 12 random papers with more than 20 citations before year 0): all 12 were published years before their arXiv posting, usually confirmed by the arXiv `journal_ref`. Examples:

| arXiv ID | Year 0 | Originally published | Citations before year 0 |
|---|---|---|---|
| `2507.01682` (J. B. Pendry, "Negative Refraction Makes a Perfect Lens") | 2025 | Phys. Rev. Lett. 85, 2000 | 7,116 |
| `2507.03354` (Pendry) | 2025 | Science 312, 2006 | 6,218 |
| `2507.01680` (Pendry) | 2025 | IEEE 47, 1999 | 5,073 |
| `2504.01263` | 2025 | ApJ Letters, 1992 | 31 |
| `2307.06294` (Corona) | 2023 | ISCA, 2008 | 357 |
| `2209.05757` (cs.LG) | 2022 | Information Sciences, 2016 | 37 |

For these, arXiv's date is the posting date, not the publication date, and OpenAlex's date is the real one. Kept as they are, a 25-year-old classic counts as a "new" 2025 paper with 308 citations in its first year.

**Why they cannot just be redated and kept: selection on success.** Old papers get uploaded to arXiv mostly because they became classics. "Negative Refraction Makes a Perfect Lens" is one of the most cited papers in its field. Put back in its 2000 cohort, it would be in the data *because* of its later success, which nobody could know in 2000. It is the same kind of leak as dropping never-cited papers, in reverse. Hence exclusion (Decisions).

**The small cases are different** (verified, 12 random papers with exactly 1 citation before year 0): none was published before arXiv; OpenAlex's date was at or after year 0 for all 12.
- 8 of 12: the citing work is a **preprint** dated before our paper, e.g. `2009.13444` (posted 2020) cited by a preprint first posted in 2019. OpenAlex dates a preprint by its first version, so a reference added in a later revision looks earlier than it was. Real citations, misdated. This probably happens at every age, so some citations appear slightly earlier than they were made: a small point-in-time inaccuracy.
- 4 of 12: matching noise, e.g. a 2011 book ("The Exoplanet Handbook") citing a 2014 paper (likely a later edition or a wrong match).

**Bad merges exist** (verified, 1 paper): `2008.05254`'s `journal_ref` says Int. J. Mech. Sci. 2021, but OpenAlex links it to a different 2014 paper in CMAME by related authors. Its citations before year 0 belong to the other paper.

**Signals.** Three, all known at posting time: the earliest OpenAlex date over all records linked to the paper (`oa_earliest_date`), citations before year 0, and the year in `journal_ref`. Kept papers (shared records out), earliest OpenAlex date vs arXiv v1:

| Earliest OpenAlex date vs v1 | Papers | 0 citations before y0 | 1-2 | 3-10 | >10 | `journal_ref` year earlier |
|---|---|---|---|---|---|---|
| Not before | 1,933,930 | 1,884,392 | 46,159 | 2,816 | 563 | 15,559 |
| ≤ 6 months before | 167,448 | 161,348 | 5,636 | 411 | 53 | 5,680 |
| 6-12 months | 49,883 | 46,460 | 2,779 | 591 | 53 | 5,312 |
| 1-2 years | 16,043 | 9,310 | 4,150 | 2,195 | 388 | 9,185 |
| 2-3 years | 6,216 | 2,009 | 1,646 | 1,900 | 661 | 4,064 |
| > 3 years | 13,056 | 2,986 | 2,458 | 4,110 | 3,502 | 9,361 |

`journal_ref` is too noisy for a rule: the year extraction (regex) catches volume numbers and online-first dates (15,559 "earlier" even in the first row). Used only to check samples.

**Samples (8 random papers per group, checked by hand):**
- *More than 1 year before, 0 citations before y0* (14,305 papers): real late uploads, just uncited before posting. A 2018 dissertation, an IEEE conference paper from 2015, INFOCOM 2001 (`1207.3650`, posted 2012), IJMPA 2017. One unclear: `1904.06511` (second record dated `2017-01-01`).
- *6-12 months before, 3+ citations before y0* (644): new papers published in a journal first, posted months later: `1402.1709` (Nature Photonics May 2013, arXiv Feb 2014), `2401.03296` (Nature Jun 2023, arXiv Jan 2024). Their citations before y0 are genuine first-year citations.
- *Within 12 months before, more than 10 citations before y0* (106): the same kind, just highly cited: `1706.00680` (PRL 2016), `1904.02449` (IEEE TIP 2018), `1601.00217` (PNAS 2015), `1906.11078` (a 2018 report with 91 then 179 citations). Excluding these on citations would remove exactly the hot papers.
- *No earlier date, by citations before y0* (2 per band):
  - 1: misdated citing preprints on new papers (`2009.13444`, `1310.0807`).
  - 2: `1806.10063` (unclear), `1606.02174` (old manuscript, cited 2010 and 2013).
  - 3-5: `1610.09787` Edward (new and hot; citing preprints dated by first version), `1909.12054` (Journal of Network Intelligence 2016, posted 2019: old).
  - 6-10: `2404.19756` **KAN** (new and famous; a matching error and preprint revisions), `1401.3905` MAPP (JAIR 2011, posted 2014: old).
  - 11-20: `2009.03278` (CRYO-LETTERS 1998, posted 2020), `2001.06040` (cited from 2016, posted 2019). Both old.
  - 21-50: `2109.13726` (RANLP 2015, posted 2021), `2501.11768` (manuscript cited from 2015, published and posted 2025). Both old.
  - >50: `2012.02600` (wrong citation links: "cited" in 2017 by papers on peppers and self-compassion), `2206.05902` Gaia DR3 (123 citations before 2022; its OpenAlex record was created 2020-11-23, before the paper existed, so likely a reused record of another Gaia work). Both broken.
  - Counts, no earlier date: 0: 1,884,392; 1: 41,530; 2: 4,629; 3-5: 2,190; 6-10: 626; 11-20: 312; 21-50: 159; >50: 92.

**Rule (decided 2026-11-13, `dataset-v3`):**

| Situation | Decision | Papers |
|---|---|---|
| Earliest OpenAlex date more than 365 days before v1 | Exclude, `posted_after_publication` | 35,852 |
| Earliest OpenAlex date less than 365 days before v1 and in an earlier calendar year | **Redate year 0** to that year (`year0_source = 'openalex_earlier'`) | 22,555 (388 of them excluded for other reasons) |
| No earlier date (earliest ≥ v1), more than 10 citations before y0 | Exclude, `cited_before_posting` | 563 |

Reasons:
- **Exclusions are decided on dates, not on citations, wherever a date exists.** A citation cross-check would exclude the cited papers and keep the uncited ones (outcome bias). The 1-year boundary is arbitrary (published May 2013, posted June 2014 is excluded; posted February 2014 is kept), but a date-only rule loses edge cases at random with respect to outcome: lost data, not bias.
- **Redating short gaps.** These are new papers that went to a journal first. Without redating, their real first-year citations fall before year 0 and are lost, and "year 0" is really their second year. Little selection on success at gaps under a year, unlike the classics. Strictly before v1, so the arXiv record's own date never triggers it, and late-December papers keep their announcement year. After redating, 318 of the kept redated papers still have citations before year 0.
- **Citations decide only when there is no earlier date.** Then more than 10 citations before y0 means an unlinked old version or a broken record (all 6 samples above 10). Misdating explains small counts, and hot papers stay below (KAN at 6).

**Known misses and limitations:**
- Hidden old papers with 10 or fewer citations before y0 stay in (MAPP at 8, the 2016 robot paper at 5).
- 143 redated papers have a year-only (January 1st) earliest date.
- For redated papers, a k = 0 prediction falls before the paper was on arXiv.
- Possible refinement: OpenAlex `created_date` (record creation) flags old manuscripts (`2501.11768`, `2009.03278`, `2109.13726`, `2001.06040` all created in 2016, years before posting) and is not a citation count. But `2016-06-24` is a floor (the Microsoft Academic import date), so it says nothing for papers posted before mid-2016, and it is not downloaded (about 50k single lookups or a new bulk fetch).

## Derived tables

- **`data/paper_records.parquet`** (`pipeline/build_citations.py`, `citations-v2`, 2026-11-13): one row per paper, the chosen OpenAlex record. v2 adds `oa_publication_date` (chosen record) and `oa_earliest_date` (earliest over all records linked to the paper); no NULL dates. 64,761 papers have an earlier date on a non-chosen record: 60,614 within a month of the arXiv v1 date (the normal case: a separate preprint record next to a later journal record), about 4,100 more than a month before v1 (candidates for the late-upload rule).
- **`data/dataset.parquet`** (`pipeline/build_dataset.py`, `dataset-v3`, 2026-11-13): one row per paper with year 0 (after redating) from 2012 to 2025, not excluded in `papers.parquet`. 2,197,132 papers. `year0_arxiv` keeps the arXiv year; `year0_source` says which one `year0` is. `exclude_reason` holds OpenAlex-based exclusions: `posted_after_publication` 35,852, `shared_openalex_record` 8,744, `cited_before_posting` 563. **Modelling filter: `exclude_reason IS NULL AND has_record`** (2,151,713 papers). `cit_y{i}` = citations in calendar year `year0 + i` (i = 0..13). **0 = observed, no citations; NULL = year after 2025 (not observed yet) or no OpenAlex record.** 2026 citations are dropped (incomplete year). `cit_before_y0` is a data check, never a feature. No labels or features: those depend on experiment choices and are computed downstream. Checks: no duplicate IDs; yearly columns sum exactly to `citations.parquet` (54,058,520 citations in v3).

## Open questions

- Why do 49 papers have an ID year earlier than their v1 year?
- Idea for later, not planned: "published elsewhere before arXiv" (and where) is known at posting time, so it would be a legitimate feature in a model that included such papers. Under the exclusion rule it does not apply.
