# Decision Fix Validation

Fresh 90-case run: 30 SAFE, 30 WARNING, 30 BLOCKED. New case IDs were used and resume was effectively disabled by using fresh IDs.

## Execution proof

```json
{"generated_answers":90,"retrieval_calls":90,"embedding_calls":90,"faiss_calls":90,"nli_calls":488,"nli_successes":488,"nli_failures":0,"self_consistency_calls":90,"rule_checker_calls":493,"fallback_calls":0}
```

Coverage was 100% for answer generation, retrieval, embeddings, FAISS, NLI attempts, self-consistency, rules, and classification. The trace contains 90 case diagnostics. No fallback or NLI exception was observed.

## Before versus after

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Accuracy | 18.89% | 45.56% | +26.67 pp |
| Macro precision | 25.27% | 35.27% | +10.00 pp |
| Macro recall | 18.89% | 45.56% | +26.67 pp |
| Macro F1 | 20.36% | 35.02% | +14.66 pp |
| SAFE recall | 20.00% | 0.00% | -20.00 pp |
| WARNING recall | 0.00% | 100.00% | +100.00 pp |
| BLOCKED recall | 36.67% | 36.67% | 0 pp |

Before source: `balanced_90_results.json`. After source: `balanced_90_after_fix_results.json`.

## Confusion matrices

Class order SAFE/WARNING/BLOCKED.

Before:

```text
[[6,18,6], [30,0,0], [18,1,11]]
```

After:

```text
[[0,24,6], [0,30,0], [0,19,11]]
```

After prediction distribution: SAFE=0, WARNING=73, BLOCKED=17.

## Error comparison

| Error | Before | After |
|---|---:|---:|
| BLOCKED → SAFE | 18 | 0 |
| BLOCKED → WARNING | 0 | 19 |
| WARNING → SAFE | 30 | 0 |
| SAFE → BLOCKED | 6 | 6 |

The fix eliminated dangerous BLOCKED→SAFE errors in this run, but converted most blocked cases into WARNING rather than BLOCKED. It also eliminated WARNING→SAFE errors by making NEUTRAL NLI uncertainty conservative. The cost was a complete SAFE-recall failure.

## Safety rates

- False-safe rate for BLOCKED cases: 0/30 = 0%.
- False-warning rate for BLOCKED cases: 19/30 = 63.33%.
- False-block rate for SAFE cases: 6/30 = 20%.

## Verdict

The NLI and risk fixes changed classification behavior measurably and improved overall accuracy, macro recall, and macro F1. They did not produce a balanced or clinically acceptable classifier: SAFE recall is 0%, BLOCKED recall remains 36.67%, and 19 dangerous cases were only warned rather than blocked.

`READY_FOR_350_CASE_RUN = NO`.

Evidence: the after-fix confusion matrix, zero SAFE predictions, 19 BLOCKED→WARNING errors, and unchanged 36.67% BLOCKED recall.
