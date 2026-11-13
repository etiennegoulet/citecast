# Papers with more than one OpenAlex record

95,557 papers (3%) match two or more OpenAlex records. Which record should supply the citation counts? Investigated 2026-11-12 on the bulk download.

## Patterns

A record is "published" if its main DOI is not an arXiv DOI.

| Pattern | Papers |
|---|---|
| **A**: preprint + published record | 67,423 (71%) |
| **B**: preprint records only | 23,621 (25%) |
| **C**: published records only | 4,513 (5%) |

Flaw: preprints with their own DOI (e.g. SSRN) count as published, so A includes some preprint-on-two-servers cases.

## Examples (hand-checked 2026-11-12)

| Paper | Pattern | Records (type, citations) | Note |
|---|---|---|---|
| [1305.7388](https://arxiv.org/abs/1305.7388) | A | [W1531677314](https://openalex.org/works/W1531677314) journal article, 100; [W2963040043](https://openalex.org/works/W2963040043) preprint, no DOI, 11 | |
| [1909.01112](https://arxiv.org/abs/1909.01112) | A | [W2971588116](https://openalex.org/works/W2971588116) SSRN preprint, 6; [W3090402637](https://openalex.org/works/W3090402637) arXiv DOI, 5 | Misclassified as A |
| [1204.6004](https://arxiv.org/abs/1204.6004) | B | [W912476626](https://openalex.org/works/W912476626) no DOI, 15; [W2952301043](https://openalex.org/works/W2952301043) arXiv DOI, 12 | |
| [2104.04987](https://arxiv.org/abs/2104.04987) | B | [W3153011556](https://openalex.org/works/W3153011556) arXiv DOI, 18; [W3154696725](https://openalex.org/works/W3154696725) no DOI, 11 | |
| [1902.06841](https://arxiv.org/abs/1902.06841) | C | [W3088492475](https://openalex.org/works/W3088492475) IEEE Access, 60; [W3020890707](https://openalex.org/works/W3020890707) Springer conference, 7 | Same article, different format |
| [hep-ph/0605319](https://arxiv.org/abs/hep-ph/0605319) | C | [W1964697409](https://openalex.org/works/W1964697409) Physics Letters B, 24; [W2789804196](https://openalex.org/works/W2789804196) PoS proceedings, 4 | Same work, partly different text |

## Do records share citing works?

30 papers per pattern (2 records, at most 400 citations each). "True" = distinct citing works across both records.

| Pattern | Median overlap | True | Sum | Max |
|---|---|---|---|---|
| A | 92% | 1,382 | +5% | −2% |
| B | 50% | 525 | +11% | −10% |
| C | 50% | 1,724 | +17% | −8% |

- **Summing overcounts in every pattern**: citing works often cite both records.
- The exact count (union of citing works) would take 20+ days of API credits. Not pursued.
- Small sample: directions are clear, percentages rough.

## Rule "take the arXiv-DOI record"? (all 95,557 papers)

| Pattern | Has an arXiv-DOI record | It has the most citations | Its citations / max |
|---|---|---|---|
| A | 15% | 25% | 41% |
| B | 99% | 90% | 96% |

Good for B, and it avoids choosing by today's citation totals. Not for A: mostly unavailable, keeps 41% of citations, and treats these papers differently from papers OpenAlex merged into their journal record.

## Decision (2026-11-12)

| Pattern | Take |
|---|---|
| A: preprint + published | The record with the most citations |
| B: preprints only | The record with the arXiv DOI |
| C: published only | The record with the most citations |

Why "most citations": each record holds part of the paper's true citations, so the highest record is the single record closest to the truth (never overcounts). In A it is usually the published version, which also matches papers OpenAlex merged. Caveat: it chooses by today's totals, but only to pick which copy of the same paper to read, not which papers to keep.

Store `n_records` and the pattern per paper for a sensitivity check.
