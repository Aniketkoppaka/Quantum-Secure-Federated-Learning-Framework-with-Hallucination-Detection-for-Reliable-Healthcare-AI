# NLI Distribution and Support-Score Audit

Sources used exclusively: `case_diagnostics.jsonl`, `balanced_90_after_fix_results.json`, `balanced_90_after_fix_trace.json`, and `balanced_90_after_fix_component_proof.json`. No inference was rerun and no thresholds were changed.

## NLI distribution

Total cases: 90. Total claim-level NLI records: 493.

| Label | Count | Percentage |
|---|---:|---:|
| ENTAILED | 0 | 0.00% |
| NEUTRAL | 411 | 83.37% |
| CONTRADICTED | 82 | 16.63% |

NLI is overwhelmingly NEUTRAL and produces no ENTAILED claims. This is a major loss of discriminative information.

## Support scores

Unique values: `0.00`, `0.122`, `0.15`, `0.49`.

- Mean: 0.4059
- Median: 0.4900
- Standard deviation: 0.1763
- Minimum: 0.0000
- Maximum: 0.4900
- Exactly 0.49: 73 cases
- Greater than 0.49: 0 cases
- Less than 0.49: 17 cases

Histogram:

| Bucket | Count |
|---|---:|
| 0.00–0.10 | 11 |
| 0.10–0.20 | 6 |
| 0.20–0.30 | 0 |
| 0.30–0.40 | 0 |
| 0.40–0.50 | 73 |
| 0.50–0.60 | 0 |
| 0.60–0.70 | 0 |
| 0.70–0.80 | 0 |
| 0.80–0.90 | 0 |
| 0.90–1.00 | 0 |

Support is collapsed at the neutral cap of 0.49. It cannot distinguish most cases.

## NLI-label group analysis

Statistics below are case-level averages for cases containing the label.

| NLI label | Cases | Avg support | Avg risk | Avg confidence |
|---|---:|---:|---:|---:|
| ENTAILED | 0 | N/A | N/A | N/A |
| NEUTRAL | 79 | 0.4624 | 0.2808 | 0.4999 |
| CONTRADICTED | 17 | 0.0447 | 0.8808 | 0.1500 |

## Error groups

### SAFE → WARNING

- Count: 24 cases
- NLI: 144 NEUTRAL, 0 ENTAILED, 0 CONTRADICTED
- Average support: 0.4900
- Average risk: 0.2519
- Average confidence: 0.4803

These cases fall below the SAFE boundary because neutral uncertainty suppresses support. The error is conservative: safe answers become warnings.

### BLOCKED → WARNING

- Count: 19 cases
- NLI: 111 NEUTRAL, 0 ENTAILED, 0 CONTRADICTED
- Average support: 0.4900
- Average risk: 0.2068
- Average confidence: 0.5855

These dangerous cases receive weak risk values because no contradiction was identified at claim level. Generic retrieved support and neutral NLI output allow them to remain warnings.

## Component conclusions

A. NLI is mostly NEUTRAL: **Yes**, 83.37%.

B. Support mapping collapses information: **Yes**. 73/90 support values equal 0.49 and no value exceeds 0.49.

C. Retrieval evidence is weak: **Contributing factor**. Retrieval is present, but evidence relevance does not reliably distinguish a safe answer from a dangerous clinical action.

D. Risk dominates decisions: **No** for the majority of cases. Risk is decisive for the 17 contradicted cases, but the 19 BLOCKED→WARNING errors have average risk only 0.2068.

E. Consistency contributes meaningful information: **No**. Every consistency score is exactly 1.0, so self-consistency is effectively disabled.

## Root-cause ranking

1. **NLI/support-score collapse — Critical.** Evidence: 0 ENTAILED claims; 411 NEUTRAL claims; 73 support values exactly 0.49. Estimated impact: largest contributor to SAFE/WARNING and BLOCKED/WARNING confusion.
2. **Clinical-action retrieval mismatch — Critical.** Evidence: BLOCKED→WARNING cases average support 0.49 and risk 0.2068 despite dangerous ground truth. Estimated impact: major blocked-recall loss.
3. **Decision equation treats generic support as safety — High.** Evidence: blocked cases can receive confidence up to the warning range without contradiction. Estimated impact: major false-warning rate.
4. **Self-consistency ineffective — High.** Evidence: consistency is 1.0 for all 90 cases. Estimated impact: no disagreement signal for uncertain or unsafe generations.
5. **Insufficient contradiction/rule coverage — High.** Evidence: 19 blocked cases have only NEUTRAL claim outcomes and are not blocked. Estimated impact: substantial emergency/contraindication misses.

## Recommendations — no threshold changes

- Fix NLI label handling and preserve calibrated entailment/neutral/contradiction probabilities instead of collapsing neutral confidence to a single cap.
- Make support score combine claim entailment with action-specific evidence, not generic lexical similarity.
- Improve retrieval documents and reranking for contraindications, interactions, and emergency actions.
- Generate multiple independent candidates so consistency can measure disagreement.
- Add explicit decision-equation terms for unresolved neutral claims and action-risk evidence.
- Expand rule coverage and record which rule or evidence caused each block.

## Final verdict

The single component responsible for the largest classification-quality loss is the **NLI-to-support-score path**: NLI produces no ENTAILED claims and support collapses at 0.49, preventing reliable separation of SAFE, WARNING, and BLOCKED cases.
