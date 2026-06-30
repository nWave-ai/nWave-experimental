"""Acceptance tests: the readiness gate's SUSTAINABILITY invariant (invariant 7).

sustainable-test-suite gate-wiring AT. The slice 02-04 sustainability work
shipped `des validate-feature-delta --require-sustainability --with-metrics` as a
working CLI, but NO wave gate-stack invoked it -> it never fired automatically
(the "catalogued != wired" gap). This package authors the wave-fires-the-gate
oracle: `des verify-readiness-pre-dispatch` (the single-invocation aggregate
readiness gate wired into `nWave/flavors/atdd_pure.yaml` at dispatch.pre) gains a
7th invariant SUSTAINABILITY mirroring invariant 6 REUSE_FIRST -- it calls
`validate_sustainability_content` on the feature-delta and FAILS readiness when
the sustainability section is declared-but-missing/malformed.

The prior slices' ATs drove the `validate-feature-delta` CLI subprocess directly;
this AT proves the WAVE fires the gate (the missing wave-level oracle).
"""
