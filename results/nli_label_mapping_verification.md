# NLI Label Mapping Verification

```text
id2label: {0: 'contradiction', 1: 'entailment', 2: 'neutral'}
label2id: {'contradiction': 0, 'entailment': 1, 'neutral': 2}
```

System mapping is correct for labels emitted by the model.

| Test | Current claim-first output | Evidence-first output | System mapping | Conclusion |
|---|---|---|---|---|
| Identical insulin statement | entailment .995831 | entailment .995831 | ENTAILED | Correct |
| Insulin cures cancer | neutral .661635 | contradiction .999739 | current NEUTRAL; evidence-first CONTRADICTED | Current ordering incorrect |
| Diabetes affects blood sugar | neutral .999653 | entailment .974632 | current NEUTRAL; evidence-first ENTAILED | Model is over-entailing related text in reverse test |

Conclusion: label-ID mapping is correct. The NLI input ordering in `fact_checker.py:154` is not: it sends claim first and evidence second. For evidence-grounded verification, evidence must be the premise and claim the hypothesis. This ordering mismatch is sufficient to explain important neutral/contradiction failures.
