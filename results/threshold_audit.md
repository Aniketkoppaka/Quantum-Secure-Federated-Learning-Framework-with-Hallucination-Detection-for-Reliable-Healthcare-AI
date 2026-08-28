# Threshold Audit — Fresh Pilot

Source: `pilot_results.json`, `pilot_component_proof.json`, and `hallucination_engine/decision_engine.py` only.

## Dataset limitation

The saved pilot contains 70 SAFE, 36 WARNING, and 14 BLOCKED cases. It therefore cannot provide 20 blocked cases. The artifacts also do not persist retrieved document contents, NLI labels/scores, support score, risk score, or consistency score per case. The saved `confidence` is the final composite score only. Those fields are reported as **NOT AVAILABLE**, not inferred.

## Source thresholds

From `HallucinationDecisionEngine.evaluate_response()`:

- `safe_threshold = 0.72`
- `warn_threshold = 0.48`, but the current final gate does not use it directly.
- `composite_score < 0.20` and no evidence → BLOCKED.
- Otherwise `composite_score < 0.72` → CLINICAL_WARNING.
- Otherwise → VERIFIED_SAFE.
- A critical contradiction caps the composite score at `0.15` and blocks.
- Risk above `0.50` caps composite score at `0.55`; risk above `0.80` caps it at `0.15`.

## Fresh pilot confusion matrix

Class order: VERIFIED_SAFE, CLINICAL_WARNING, BLOCKED.

```text
[[11, 53,  6],
 [29,  4,  3],
 [ 9,  0,  5]]
```

Prediction distribution: SAFE=49, WARNING=57, BLOCKED=14.

## Score distribution

Only final composite confidence is saved:

- SAFE predictions: 49 cases; exact source scores are in `pilot_results.json` records.
- WARNING predictions: 57 cases; exact source scores are in `pilot_results.json` records.
- BLOCKED predictions: 14 cases; exact source scores are in `pilot_results.json` records.
- Support, risk, consistency, evidence, and NLI score distributions: **NOT AVAILABLE** in the saved artifacts.

## Requested error cases

### BLOCKED → SAFE

`EXPERT-002-PILOT3`, `EXPERT-005-PILOT3`, `EXPERT-007-PILOT3`, `EXPERT-008-PILOT3`, `EXPERT-010-PILOT3`, `EXPERT-013-PILOT3`, `EXPERT-016-PILOT3`, `EXPERT-017-PILOT3`.

These are threshold/gating failures: the final composite score was at or above the 0.72 SAFE threshold despite blocked ground truth. The saved artifacts do not expose the component scores needed to attribute each case specifically to retrieval, NLI, rules, or consistency.

### SAFE → BLOCKED

`SAFE-001-PILOT3`, `SAFE-006-PILOT3`, `SAFE-011-PILOT3`, `SAFE-016-PILOT3`, `UNSEEN-SAFE-004-PILOT3`, `UNSEEN-SAFE-049-PILOT3`.

Each has final confidence `0.15`. Under the source code, that value is consistent with either a critical contradiction or risk above `0.80`; the artifacts do not save which condition caused it. No per-case rule flags were persisted for these decisions.

### WARNING → SAFE

The warning-to-safe errors are `UNSEEN-WARN-001-PILOT3` through `UNSEEN-WARN-030-PILOT3`, excluding 011, 016, 017, 021, 022, and 026, plus `EXPERT-003-PILOT3`, `EXPERT-006-PILOT3`, `EXPERT-012-PILOT3`, `EXPERT-015-PILOT3`, `EXPERT-018-PILOT3`.

Their final scores are at or above the 0.72 SAFE threshold. This indicates insufficient warning-specific gating or insufficiently conservative handling of clinical context.

## Recommendations

1. Persist `support_score`, `risk_score`, `consistency_score`, NLI label/score, retrieved documents, rule flags, and the exact gate branch for every case.
2. Do not lower the SAFE threshold to improve accuracy; that would worsen false-safe risk. Calibrate it on a validation set instead.
3. Add an explicit clinical-warning gate before SAFE for pregnancy, renal, hepatic, elderly, and medication-interaction contexts.
4. Require successful evidence/NLI support before allowing SAFE.
5. Add a separate blocked-risk override for contraindication and emergency cases.
6. Re-run with a balanced dataset containing at least 20 cases per class before selecting thresholds.

## Audit conclusion

The threshold implementation explains the observed boundary errors, but the current artifacts are insufficient for the requested component-level causal explanation. The next required change is trace enrichment, not blind threshold tuning.
