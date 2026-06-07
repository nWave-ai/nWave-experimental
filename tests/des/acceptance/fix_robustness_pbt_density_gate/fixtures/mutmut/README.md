# Slice-04 mutmut fixture reports

Committed fixtures consumed by the slice-04 layer-2 ATs of
`fix-robustness-pbt-density-gate`. Per the M2 architect mandate (feature-delta
§6 slice-04 row), slice-04 ATs are **fixture-driven** -- they exercise the
production CLI's mutmut-report parser against committed JSON documents and
**MUST NEVER invoke live mutmut**, else the slice inherits the very environment
coupling (M2) the gate exists to bound. The C1 mechanical self-check in
`tests/des/acceptance/fix_robustness_pbt_density_gate/steps/test_slice_04_genuineness_layer_2_mutmut.py`
enforces this discipline statically.

## Schema (gate-internal, v1)

The fixture JSON shape is intentionally narrower than mutmut's own
`.mutmut-cache` because v1's CLI consumes only what the three-state R5 logic
requires (the gate is NOT a general mutmut report consumer). Future v2
(paired-falsifier fixture, backlog) MAY converge on the upstream schema; v1
declares its own minimal contract so slice-04 ships without coupling to
mutmut's internal cache format (which differs across mutmut 2.x point
releases).

Top-level object:

```json
{
  "mutmut_ran": true,
  "positive_control": {"seeded": true, "killed": true},
  "mutants": {
    "tests/fixture/test_target.py::function_under_test": {"killed": 1, "survived": 0}
  }
}
```

Classification logic the production CLI's layer-2 branch implements against
this shape:

| Fixture state                                    | R5 cell                  | Token                          | Exit |
|--------------------------------------------------|--------------------------|--------------------------------|------|
| JSON unparseable                                 | REPORT_MALFORMED         | RobustnessLayer2Unavailable    | 3    |
| `mutmut_ran == false`                            | REPORT_MALFORMED         | RobustnessLayer2Unavailable    | 3    |
| `mutants == {}`                                  | REPORT_EMPTY             | RobustnessLayer2Unavailable    | 3    |
| declared sut symbol absent from `mutants`        | REPORT_PARTIAL_MISSING   | RobustnessLayer2Unavailable    | 3    |
| `positive_control.killed != true`                | POSITIVE_CONTROL_FAILED  | RobustnessLayer2Unavailable    | 3    |
| `mutants[sut].killed == 0` + positive control OK | KILL_RATE_ZERO           | RobustnessPBTNotFalsifiable    | 1    |
| `mutants[sut].killed > 0` + positive control OK  | KILL_RATE_POSITIVE       | (positive observable / silent) | 0    |

## Files

| File                            | R5 cell instantiated                     | Used by AT |
|---------------------------------|------------------------------------------|------------|
| `valid_killing.json`            | KILL_RATE_POSITIVE                       | AT2        |
| `zero_kills.json`               | KILL_RATE_ZERO (positive control killed) | AT1        |
| `malformed.json`                | REPORT_MALFORMED                         | (DELIVER)  |
| `empty.json`                    | REPORT_EMPTY                             | (DELIVER)  |
| `partial.json`                  | REPORT_PARTIAL_MISSING_SUT               | (DELIVER)  |
| `positive_control_failed.json`  | POSITIVE_CONTROL_FAILED                  | AT3        |

AT3 instantiates the canonical positive-control-failed cell because the four
untrustworthy-cell fixtures classify identically at the gate-verdict universe
(exit 3 + `RobustnessLayer2Unavailable` token); DELIVER may extend slice-04 with
table-driven Examples rows for the remaining three without changing the AT
shape. The other three fixtures ship anyway so DELIVER can exercise the gate's
R5 branch against each in unit tests below the AT layer.

## Reference (mutmut upstream)

This schema is **not** mutmut's `.mutmut-cache` format -- it is a gate-internal
contract. For the upstream schema see <https://github.com/boxed/mutmut> /
`mutmut --help` / the project's `pyproject.toml` `[tool.mutmut]` block. The
divergence is intentional and documented per the architect spec.
