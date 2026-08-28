# Support-Score Pipeline Audit

## Trace

`decision_engine.py:98-106` retrieves evidence, derives `s_ret`, invokes fact checking, and assigns `s_ent = fact_report.overall_factual_score`.

`fact_checker.py:204-207` calls `_nli_status` on each extracted claim with the first retrieved evidence item. `fact_checker.py:249-272` sums claim confidences and computes:

```python
overall_factual_score = round(total_score / len(clinical_claims), 3)
```

The diagnostic `support_score` is this `overall_factual_score`.

## Cap and collapse

`fact_checker.py:160` returns:

```python
return "NEUTRAL", min(float(result["score"]), 0.49)
```

Therefore any neutral raw score above .49 becomes .49. In the latest artifacts, raw neutral scores are generally .99+, so 73/90 case-level support scores collapse to .49. Contradicted claims are assigned confidence .0 later in `check_factual_accuracy` (`fact_checker.py:249-270`). Mixed outputs and averaging produce the remaining .122 and .15 values.

Observed case-level support values: `0.0`, `.122`, `.15`, `.49`. No code permits a NEUTRAL-derived score above `.49`; only ENTAILED claims can produce support above .49, and no ENTAILED claim occurred in the latest run.

## Thirty-case trace summary

The first thirty diagnostics show the same pattern: SAFE claims map to NEUTRAL/.49 or CONTRADICTED/.0; their evidence is often unrelated. The complete claim, evidence citation, NLI label, NLI score, and support value are persisted in `case_diagnostics.jsonl`. The relevant source cause is the neutral cap, not the final confidence formula.

## Verdict

Support-score collapse is mechanically explained by the neutral cap and the absence of ENTAILED outputs. The upstream NLI ordering defect and retrieval mismatch cause the absence of entailed outputs.
