# Retrieval Quality Audit

Audit only; no retrieval was rerun. The latest diagnostics provide top citations and relevance scores. Manual topical-support assessment used the claim and cited evidence summaries.

## Sample and classifications

Ten SAFE, ten WARNING, and ten BLOCKED cases were sampled from the latest balanced run. Top-1 is the first saved citation; top-3 are the saved citations, where present. FAISS score is not separately persisted; the saved relevance score is the hybrid retrieval score, so a distinct FAISS score is **not available**.

| Group | Cases | Manual finding |
|---|---|---|
| SAFE | AFTERFIX-001..010 | 2 WEAK_SUPPORT, 8 IRRELEVANT |
| WARNING | AFTERFIX-031..040 | 4 WEAK_SUPPORT, 6 IRRELEVANT |
| BLOCKED | AFTERFIX-061..070 | 3 STRONG_SUPPORT, 3 WEAK_SUPPORT, 2 IRRELEVANT, 2 CONTRADICTORY |

Representative saved top-1 evidence:

- SAFE `AFTERFIX-030`: claim about cane use; top-1 PMID:24222018 (post-STEMI guideline), relevance .1351 → IRRELEVANT.
- WARNING `AFTERFIX-034`: claim about low blood pressure; top-1 PMID:33218228 (HCM guideline), relevance .1856 → WEAK_SUPPORT.
- BLOCKED `AFTERFIX-065`: metformin claim; top-1 PMID:35871239 (ADA diabetes guideline), relevance .5001 → STRONG_SUPPORT for the medication topic but insufficiently action-specific.
- BLOCKED `AFTERFIX-088`: bleach claim; top-1 PMID:29462276 (C. difficile guideline), relevance .1508 → IRRELEVANT.

Rates over the 30 selected cases:

| Classification | Count | Rate |
|---|---:|---:|
| STRONG_SUPPORT | 3 | 10.0% |
| WEAK_SUPPORT | 9 | 30.0% |
| IRRELEVANT | 16 | 53.3% |
| CONTRADICTORY | 2 | 6.7% |

## Verdict

Retrieval quality is a substantial contributor to NEUTRAL NLI output. More than half of the selected top-1 evidence was manually irrelevant, and even topical evidence often failed to encode the safety context needed for the claim.
