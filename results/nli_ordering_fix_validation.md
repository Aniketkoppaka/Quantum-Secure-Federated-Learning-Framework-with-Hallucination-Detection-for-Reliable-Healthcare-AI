# NLI Ordering Fix Validation

## Implemented change

`fact_checker.py:_nli_status()` now invokes the NLI pipeline as:

```python
{"text": evidence.content[:2000], "text_pair": claim}
```

This establishes premise=retrieved evidence and hypothesis=generated claim. Thresholds were not modified.

## Controlled verification

Evidence: `Insulin is used to treat Type 1 diabetes.`

| Expected relation | Claim | Raw output | Mapped label | Score |
|---|---|---|---|---:|
| ENTAILMENT | Insulin is used to treat Type 1 diabetes. | entailment | ENTAILED | .995831 |
| CONTRADICTION | Insulin cures cancer. | contradiction | CONTRADICTED | .999739 |
| NEUTRAL | Diabetes affects blood sugar. | entailment | ENTAILED | .974632 |

Counts for the three verification cases:

```json
{"ENTAILED":2,"CONTRADICTED":1,"NEUTRAL":0}
```

## Conclusion

The ordering correction succeeded: the cancer claim changed from the prior claim-first `neutral` result to evidence-first `contradiction` with .999739 confidence. This confirms the premise/hypothesis order is now correct for the intended evidence-grounding task.

The neutral control did not behave as expected: this general-domain NLI model over-entails `Diabetes affects blood sugar` from the insulin evidence. This is a model calibration/domain-scope limitation, not an ordering or label-mapping defect.

## Test result

The test suite produced `5 passed, 1 failed`. The failing existing assertion expects a broad HFrEF guideline response to be VERIFIED_SAFE, but after the corrected NLI path the model returned neutral and the engine issued CLINICAL_WARNING. No thresholds or classification rules were changed during this validation.

## Next sequence

1. Run a 30-case diagnostic benchmark with the ordering fix.
2. Audit retrieval alignment using its diagnostic records.
3. Run a balanced 90-case benchmark.
4. Only then decide whether a 350-case run is justified.
