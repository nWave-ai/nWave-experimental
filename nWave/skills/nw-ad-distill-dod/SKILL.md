---
name: nw-ad-distill-dod
description: "DISTILL Definition of Done — the hard gate checklist at the DISTILL-to-DELIVER transition for nw-acceptance-designer. Consult at Phase 4 handoff (*validate-dod before *handoff-develop). Block handoff on any failure. Reference checklist only — mandate/gate definitions live in nw-test-design-mandates, nw-at-completeness-check, nw-distill."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Definition of Done

KNOWLEDGE skill. No forced sequence. Hard gate at the DISTILL-to-DELIVER transition.
Run `*validate-dod` before `*handoff-develop`. Block handoff on ANY failure.
Mandate/gate definitions are SSOT elsewhere — refer by name (`nw-test-design-mandates`, `nw-at-completeness-check`, `nw-distill`).

1. [ ] All acceptance scenarios written with passing step definitions
2. [ ] Test pyramid complete (acceptance + planned unit test locations)
3. [ ] Peer review approved (`nw-ad-critique-dimensions`, 6 dimensions)
4. [ ] Tests run in CI/CD pipeline
5. [ ] Story demonstrable to stakeholders from acceptance tests
6. [ ] Project Infrastructure Policy present at `docs/architecture/atdd-infrastructure-policy.md` (or bootstrap committed this run)
7. [ ] Target language detected and logged (`[lang-mode] <lang>`)
8. [ ] State-delta port present at `tests/common/state_delta.<ext>` (inherited or bootstrapped this run)
9. [ ] Wave-Decision Reconciliation HARD GATE passed (0 contradictions across DISCUSS / DESIGN / DEVOPS)
10. [ ] Mandate 8 — every step-method at layers 1-3 uses `assert_state_delta(before, after, universe, expected)` with port-exposed universe entries
11. [ ] Mandate 9 — PBT decorators (`@given`, `RuleBasedStateMachine`) appear ONLY on layer 1-2 tests; layer 3+ tests are example-only
12. [ ] Mandate 10 — Tier B `test_<feature>_state_machine.py` exists if journey is ≥3 chained scenarios AND input space domain-rich; absent otherwise
13. [ ] Mandate 11 — layer 3+ sad paths are named example-based tests (`Bug_<symptom>` or `Sad_<scenario>`); no PBT machinery imported at those layers
14. [ ] Pillar 1 — zero technical terms in scenario titles, Gherkin steps, or step-method names
15. [ ] Pillar 2 — chained narrative verified for multi-scenario journeys (`Given` of N reuses N-1's step-methods)
16. [ ] Pillar 3 — Tier A uses production composition root; Tier B uses `InMemoryComposition` honoring the same interfaces; only external/non-deterministic ports faked
17. [ ] Mandate-12 (criterion 1) — domain types module exists at `tests/{path}/acceptance/steps/domain_types.py` with typed enums / dataclasses / NewTypes for every domain noun in Gherkin
18. [ ] Mandate-12 (criterion 2) — composition methods consume typed parameters from `domain_types.py`; no raw `str` parameter where a domain enum exists
19. [ ] Mandate-12 (criterion 3) — AST mechanical check passes: every step function body has ≤2 statements, final statement is `composition.<service>.<method>(...)`, no control flow (`if`/`for`/`while`/`try`) in step bodies
20. [ ] Mandate-12 (criterion 4) — step-reuse-ratio measured (`total_step_invocations / unique_step_decorators`) and documented as informational natural ceiling in `distill/wave-decisions.md` (NOT a gate; below-4× acceptable when criteria 1-3 met)
21. [ ] AT-completeness audit run (Phase 2.5) — `nw-at-completeness-check` 15-item Tier-1 checklist computed; verdict ≥ ACCEPTABLE_WITH_DOCUMENTED_GAPS (≥ 10/15); gaps classified `AT_GAP_IN_DELIVERY_SCOPE` vs `SPECIFICATION_AMBIGUITY`; upstream routing emitted for the latter
21-bis. [ ] Tier-2 S-family structural-invariants gate run (Phase 2.5) — `nw-at-completeness-check` §2-bis computed (S1 step-text uniqueness + S2 driving-port-only boundary + S3 dormant-seam reconciliation); verdict = PASS; any FAIL is a BLOCKER regardless of Tier-1 band, routed as `AT_GAP_IN_DELIVERY_SCOPE`
22. [ ] PBT + parametrize density maximized (EXPAND plan v3 §3.A) — every unbounded input domain has a `@given` AT; every finite Cartesian flag combination has a `parametrize` AT; example-based reserved for unique invariants and walking skeleton
23. [ ] Mandate-13 (Driving-Port-Only Boundary) — every AT drives through a composition-root driving port at Layer 3 subprocess OR Layer 3 composition OR Layer 4 wiring_e2e; ZERO direct production imports in `composition.py` (grep `from des\.(?:domain\|application\|adapters)\.\w+ import` empty across step modules); ZERO new behavioral ATs under `tests/des/unit/(?:domain\|cli)/*` (new ATs under `tests/des/(?:acceptance\|cli)/[feature-name]/` only); if dispatch instructs Layer-1 unit testing for behavioral coverage, designer REFUSED and escalated
24. [ ] Mandate-15 / S3 (Dormant-Seam Reconciliation, D11) — every net-new seam declared load-bearing in the DESIGN driving-surface (net-new effectful entry-point param like `clock=`, net-new effectful call reached from the entry point like `absorb_ready_refs()`, net-new param threaded into an existing seam) has a witnessing AT that names THAT exact seam as its driving port, drives it through the REAL entry point, asserts an observable effect; indirect registry/entry-point/DI wiring counts (NOT naive name/protocol match); a declared seam with no witnessing AT BLOCKS (Tier-2 S3 FAIL); owned residue cleared by `# dormant-ok: <F-id>` is excused
25. [ ] `.feature` tag gate-form (carpaccio discovery) — every slice `.feature` file carries a file-level `@feature-{feature-id}` tag preceding its `Feature:` header, AND every scenario carries its own `@slice-NN` tag (feature-level tags do NOT inherit); source: `feature_at_files.py` + `carpaccio_format.py`
26. [ ] Carpaccio + readiness self-check run (Phase 4) — `des carpaccio-slice-gate --feature-id <id> --entering-slice <slice>` CLEARS for every slice, AND `des verify-readiness-pre-dispatch` reuse/slice-plan/scenario-tag legs CLEAR (the `at_review_verdict` leg is recorded downstream — its failure at authoring time is expected); no ATs handed off that fail the carpaccio discovery / scenario-resolution legs
27. [ ] Every new test-only import is declared in the project's dependency manifest (`requirements*.txt`/`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`) — an ambient-interpreter import is not evidence
