# H9 — Word-Padding Bypass Regression Fixture

## Purpose

Documents the empirical bypass of E4 v1.0 (stressor S1 from spdd-bench)
and confirms that E4 v1.1 (US-12 R2) closes it.

## The Bypass (H9)

Impact text: `"the the the the the the the the the the"` (10 words, no verb, no citation)

| Rule version | Result | Reason |
|-------------|--------|--------|
| E4 v1.0 | PASS | word-count >= 10 satisfies the heuristic |
| E4 v1.1 | FAIL | no DDD-N or row#N structural citation present |

## Fixture Usage

Used in acceptance tests (validation.feature @US-09 @AC-3) to document the
v1.0 conceded gap, and in (@US-12 @AC-2) to confirm v1.1 blocks it.

Used in unit tests (tests/feature_delta/unit/test_e4_rules.py):
- `test_word_padding_bypass_passes_e4_v1_0` — v1.0 PASS (documented gap)
- `test_word_padding_without_citation_fails_e4_v1_1` — v1.1 FAIL (gap closed)

## Citation Pattern (v1.1)

E4 v1.1 requires at least one of:
- `DDD-\d+` — design decision reference (e.g. DDD-1, DDD-42)
- `row#\d+` — standalone row reference (e.g. row#3)
- `#row\d+` — origin-qualified reference (e.g. DISCUSS#row3, DESIGN#row1)

## Closure

Stressor S1 closed by step 01-13 (US-12 AC-2). E4 bumped to v1.1 stable in
`nWave/data/feature-delta-rule-maturity.json`. --enforce mode unblocked (DD-A2).
