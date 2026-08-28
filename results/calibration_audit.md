# Calibration Audit

Source: existing `results/case_diagnostics.jsonl` only. No benchmark was run and no code was changed.

## Group statistics

| True group | N | Support avg/median/min/max | Risk avg/median/min/max | Consistency avg/median | Confidence avg/median/min/max |
|---|---:|---|---|---|---|
| TRUE SAFE | 30 | .4173/.4900/.122/.490 | .3785/.2576/.2424/.8869 | 1.000/1.000 | .4142/.4669/.150/.5023 |
| TRUE WARNING | 30 | .4900/.4900/.490/.490 | .2299/.2380/.1937/.240 | 1.000/1.000 | .5315/.5126/.508/.6161 |
| TRUE BLOCKED | 30 | .3103/.4900/.000/.490 | .4532/.2340/.1725/.9165 | 1.000/1.000 | .4258/.5221/.150/.6655 |

## Overlap

- SAFE and WARNING confidence ranges overlap at .508–.502 only marginally, but SAFE cases predicted WARNING have confidence .4648–.5023 while true WARNING cases begin at .508.
- WARNING and BLOCKED confidence ranges overlap substantially: BLOCKED reaches .6655 and WARNING reaches .6161.
- SAFE and BLOCKED overlap strongly: SAFE reaches .5023 and BLOCKED reaches .6655; both include .15.
- Support is not discriminative after the NLI-neutral cap: WARNING and error subsets are exactly .49, while BLOCKED ranges 0–.49.
- Consistency is useless for calibration: every case is 1.0 because only one candidate was evaluated.

## Error cases

SAFE predicted WARNING (24): AFTERFIX-002, 003, 004, 005, 007, 008, 009, 010, 012, 013, 014, 015, 017, 018, 019, 020, 022, 023, 024, 025, 026, 027, 028, 030.

BLOCKED predicted WARNING (19): AFTERFIX-063, 064, 065, 068, 069, 070, 073, 074, 075, 078, 079, 080, 083, 084, 085, 087, 088, 089, 090.

Both error groups have NLI label distribution `NEUTRAL` only. SAFE→WARNING errors have average support .4900, risk .2519, confidence .4803. BLOCKED→WARNING errors have average support .4900, risk .2068, confidence .5855. The blocked errors therefore look safer to the current formula than the true warnings.

## Root cause

Primary: NLI-neutral handling and support-score weighting. Capping neutral claim confidence at .49 makes support saturate and removes useful separation. Risk is also too low for blocked cases without an explicit contradiction rule. Retrieval is contributing because evidence can be present while the action remains unsafe. Self-consistency cannot help because its score is constant 1.0.

## Threshold recommendations only

There is no safe scalar threshold that separates these groups. A provisional configuration is:

- Recommended SAFE threshold: **0.72**, retain provisionally.
- Recommended WARNING threshold: **0.70** as a provisional upper boundary for a three-way policy, not validated.
- Recommended BLOCK threshold: **0.20** for the existing no-evidence/risk-cap branch, supplemented by an explicit clinical-risk veto.

These values are not evidence of clinical calibration. Raising SAFE above .72 would reduce some SAFE false acceptance but would further reduce SAFE recall; lowering it is unsafe. A confidence boundary of .70 would capture the observed blocked-warning cases only if applied as a block rule, but it would also block all observed true SAFE cases whose confidence is ≤.5023. Thresholds alone are therefore insufficient.

## Expected impact from observed distributions

Under the current data, retaining .72 yields observed SAFE recall 0%, WARNING recall 100%, and BLOCKED recall 36.67%. No defensible numeric improvement estimate can be made for a new threshold without replaying decisions; any claimed impact would be speculation. The only reliable expectation is that increasing the SAFE threshold cannot improve SAFE recall and can increase false blocks.
