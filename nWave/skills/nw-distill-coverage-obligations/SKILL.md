---
name: nw-distill-coverage-obligations
description: "DISTILL coverage-verification procedure at gate-OUT — driving-adapter verification, per-adapter real-IO scenario coverage (Mandate 6), the adapter-integration slice (10-property matrix), outcomes registration, dormant-seam reconciliation cross-check, and the self-review checklist. Run after scenarios are authored, before reviewer dispatch."
user-invocable: false
disable-model-invocation: true
---

# DISTILL Coverage Obligations (PROCEDURE)

**Kind**: PROCEDURE | **One job**: verify every coverage obligation (adapter / driving-port / dormant-seam / outcome) is met before reviewer dispatch | **One trigger**: scenarios are authored and DISTILL is about to self-review / hand off.

Composed by `nw-distill`. The canonical dormant-seam + driving-port-only mandate definitions live in `nw-test-design-mandates-composition-contract` (Mandates 13/15) — this procedure verifies they are satisfied for the feature.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Deterministic step-sequence (run every time, in order)

At execution start create these as TaskCreate items and run in order:

1. **DRIVING ADAPTER VERIFICATION** — scan DESIGN for entry points (`python -m`, `cli`, `endpoint`, `hook adapter`); each match → ≥1 subprocess/HTTP/hook scenario invoking it via its protocol, tagged `@driving_adapter @walking_skeleton`, verifying exit/status + output + arg handling. Gate: zero uncovered entry points.
2. **ADAPTER SCENARIO COVERAGE (Mandate 6)** — inventory every driven adapter; map scenarios to adapters; produce the coverage table; add a scenario for every `NO — MISSING` row (costly externals: `@requires_external` contract smoke acceptable). Gate: zero `NO — MISSING` rows. MECHANIZED downstream by the L3/L4 gates — see the "Adapter Scenario Coverage" section below for the gate detail.
3. **ADAPTER-INTEGRATION SLICE** — when the feature ships a CRITICAL (Port, Adapter) pair, author an adapter-integration slice; declare each of the 10 properties EXERCISED / N/A / DEFERRED with citation. Gate: every property row carries a verdict + citation.
4. **REGISTER OUTCOMES** — per new typed contract surface, run `nwave-ai outcomes register`; skip when feature is methodology-only. Gate: every new contract registered, or skip documented.
5. **DORMANT-SEAM CROSS-CHECK** — per the Mandate-15 reconciliation (`nw-test-design-mandates-composition-contract`): every net-new DESIGN-declared load-bearing seam has a witnessing AT naming that seam, driving it through the real entry point, asserting an observable effect (indirect registry/DI wiring counts). Gate: zero declared seams without a witnessing AT.
6. **ARTIFACT LINEAGE CLOSURE** — classify DIRECT-SURFACE vs ASSEMBLED-SURFACE. For assembled surfaces, verify the single WS binds real producer -> immutable candidate -> clean consumer -> public journey -> observable capability, with no source/HOME/global-install borrowing. A producer manifest/configuration is not the produced property. Gate: PASS or DIRECT-SURFACE with named rationale.
7. **SELF-REVIEW CHECKLIST** — run the checklist below; every item passes or is documented N/A. Gate: checklist complete.

## Scenario writing guidance (induction-aligned)

Scenarios are INDUCED from the design code-design contract via the 3-source induction map (`nw-distill`), never authored from scratch by judgement. Priority order when writing the induced set:

- **Walking skeleton first** — SPIKE ran + **PROMOTED** a skeleton → inherit it (do NOT rewrite, do NOT duplicate, do NOT change its `@walking_skeleton` tag); add the next scenario layer on its established driving adapter + e2e path. SPIKE skipped/not-promoted → DISTILL induces the walking-skeleton scenario from the design contract. Either way: exactly ONE walking skeleton per feature marked `@walking_skeleton`, green before hand-off. Features only; optional for bugs.
- **Business language purity** — feature files use business language only; no technical terms (API, database, endpoint, schema) in scenario names or steps. Technical detail lives in step definitions (canonical: `nw-test-design-mandates-scenario-design` Pillar 1).
- **Error path coverage** — target ≥40% error/edge-case scenarios. Per happy path ask: invalid input? dependency unavailable? user cancels midway?
- **Environment-aware scenarios** — DEVOPS environment inventory → ≥1 walking skeleton scenario per environment (clean install vs upgrade vs stale config).
- **AT authoring granularity (atdd_pure)** — author ONLY the current slice's scenarios, JIT, active-RED; future slices ABSENT from disk; never `@skip`/`@pending` (ADR-GV-001 D6). <!-- mode-ref-ok -->

## Coverage-verification via the code-fact CLI (velocity — do NOT hand-read prod code)

Before authoring a NEW scenario, VERIFY whether an existing mechanism / test already covers the
behaviour — but resolve that as a CODE-FACT through `des code-fact` CLI, NEVER by manually reading production files. This is the DOMINANT DISTILL time-cost:
empirically the longest DISTILL phases are spent reading production code to check existing coverage,
NOT writing Gherkin (sister dogfood 2026-07-04 — 4 of 7 slices needed zero new code because an
existing mechanism already covered them; the cost was DISCOVERING that).

- **Query** "what already covers behaviour X?":
  ```bash
  des code-fact query.reads-of SYMBOL --root ROOT
  des code-fact query.callers-of SYMBOL --root ROOT
  ```
  These name every caller and reader of a load-bearing seam, each with file and line, which is the
  what-covers-what answer for a specific symbol. **Feature-level change-scope has no stable CLI today** — use bounded symbol-level queries above, then manual inspection with explicit limitation note.
- **Fallback (AST unavailable)**: the CLI degrades LOUD — generic TextSearch
  (last resort, tagged `noisy`). The guidance is identical whichever tier answers; only the confidence label changes. Never leave the developer without an answer because the top tier is absent.
- **Outcome**: already covered → REUSE the existing AT (Mandate-12), do NOT author a duplicate;
  genuinely uncovered → author the induced scenario. Either way the decision is a CITED code-fact
  (feature/test names), not a hunch from a manual read.

## Driving Adapter Verification (RCA fix P1)

| # | Rule (MUST) | Gate |
|---|---|---|
| 1 | ≥1 walking skeleton scenario invokes the entry point via its protocol — subprocess (CLI), HTTP request (API), hook JSON payload (hooks). Tag: `@driving_adapter @walking_skeleton` | scenario exists + exercises the user's actual invocation path |
| 2 | Scenario verifies exit code (or HTTP status), output format (stdout/response body), basic argument handling | all three verified |
| 3 | Pipeline/service-level tests do NOT replace driving adapter tests — calling `generate_matrix()` directly proves the pipeline, NOT that the CLI parses arguments, resolves PYTHONPATH, wires adapters, produces correct exit codes | both present |
| 4 | Scan DESIGN for entry points: grep for `python -m`, `cli`, `endpoint`, `hook adapter`; each match → ≥1 subprocess/HTTP/hook scenario | zero uncovered entry points |

Exists because of a systematic pattern, established by an nWave-internal "user-port gap" RCA (an analysis note, never shipped — do not look for a file; its finding is stated here in full): ATs entered from application services instead of user-facing CLIs — working pipelines shipped with broken entry points.

## Adapter Scenario Coverage (Mandate 6 Enforcement)

EVERY driven adapter gets ≥1 scenario with real I/O (or contract smoke for costly externals). Not optional, regardless of WS strategy. Tag: `@real-io @adapter-integration`.

> **Mechanized (L3/L4 gates).** This coverage obligation is no longer skill-normative only: the **L3 integration-per-adapter** and **L4 contract-per-port** invariants in `verify_readiness_pre_dispatch.py` enumerate `src/des/adapters/driven/**` (concrete classes) and `src/des/ports/**` (Protocols) and BLOCK on any uncovered surface that lacks both a test AND a cited waiver (silence is the BLOCKER; a justified waiver — a cited Port-contract excerpt — clears, mirroring the N/A verdict vocabulary below). The checklist here is the SPEC the gate enforces.

```
| Adapter | @real-io scenario | Covered by |
|---------|-------------------|------------|
| YamlWorkflowLoader | YES | WS (real YAML from tmp_path) |
| SubprocessGitVerifier | NO — MISSING | Add: "Git verifier reads real git log" |
```

Every `NO — MISSING` row MUST get a scenario. Costly-external adapter (e.g. `claude -p`): `@requires_external` contract smoke acceptable instead.

## Adapter Integration Slice Authoring

When the feature ships a CRITICAL (Port, Adapter) pair (framework-catalog row OR project-local `atdd-infrastructure-policy.md`), DISTILL authors an adapter-integration slice in addition to the acceptance slice. The adapter is the SUT, not the feature. Reference: `docs/analysis/adapter-integration-slice-design-2026-05-27.md` §5/§7.

### 10-property matrix

| # | Property | Description |
|---|---|---|
| 1 | Error class taxonomy | OSError subclasses, IOError, decoding errors — ENOENT / EACCES / EISDIR / ENOSPC |
| 2 | Concurrency | Multiple writers atomic; race absence; ordering invariant |
| 3 | Atomicity | Crash mid-write leaves state consistent; fsync; partial-failure containment |
| 4 | Idempotency | Re-invocation has well-defined semantics (append or no-op per contract) |
| 5 | Recovery | Partial-failure recoverable on next attempt; no orphan state |
| 6 | Edge cases | Unicode surrogates, NaN/Inf, very-large payload, file rotation, encoding boundary |
| 7 | Observability | Structured diagnostic emission on every failure-mode branch; stderr event-shape contract |
| 8 | Fail-mode contract | Fail-OPEN vs fail-CLOSED vs fail-LOUD declared and tested |
| 9 | Resource-leak absence | FDs / subprocesses / sockets released across success+failure paths |
| 10 | Driving-port purity | Adapter does NOT call back into driving port (no reverse coupling) |

### Per-property verdict vocabulary

Each property declared as one of:
- **EXERCISED** — cited by AT name (one AT per row minimum). Reviewer verifies AT path + line citation mechanically.
- **N/A** — cited by Port-contract excerpt excluding the property. Reviewer greps adapter source for the excerpt; absence = BLOCKER.
- **DEFERRED** — cited by backlog friction ID. Reviewer verifies friction exists.

**Empty / omitted property declaration = REVIEWER BLOCKER**. Every row carries verdict + citation; silence = verdict-omission failure, not default-pass.

### Carpaccio ceiling escape

Adapter-integration coverage matrices often yield 10-15 ATs — exceeds the ratified `carpaccio_slice_max: 7` (ADR-028 D2). **Option B (preferred)**: split coverage across N carpaccio slices grouped by property (one slice = "JsonlLogAdapter error taxonomy", etc.). **Option A (the designed path, not a fallback hack)**: `@adapter-integration @coupled` tags with a recorded coupling justification — adapter contract closure legitimately clears via `CoupledSliceAccepted` when the AT group cannot be decomposed without breaking the single end-to-end vertical it proves. **Option C**: N/A — the ceiling is already at its ratified value (7); a further raise is a fresh ratification decision, not a per-feature escape.

## Register Outcomes (per DISCUSS#D-5 grain)

**Trigger**: feature has a new typed contract surface — rule module, CLI subcommand, public service operation, or system-wide invariant. Each surface = one OUT-N registry row. **Skip when**: feature is methodology-only (skill propagation, prose, docs).

| `kind` | Meaning |
|---|---|
| `specification` | a rule (guard, validation predicate, policy) |
| `operation` | function/method exposed at a driving port |
| `invariant` | system-wide constraint that must always hold |

Run `nwave-ai outcomes register --id OUT-N --kind {kind} --input-shape "..." --output-shape "..." --keywords "k1,k2"`. Exit `0` registered; exit `2` refused after checking (duplicate id, or the entry fails the schema — retry with a corrected entry); exit `3` refused *without* checking (the packaged schema resource could not be read — nothing was written; reinstall `nwave-ai`). Registry at `docs/product/outcomes/registry.yaml`; schema at `nwave_ai/outcomes/schema.json`.

## Self-Review Checklist (Dimension 9 + Mandate 7)

- [ ] 1. WS strategy declared in wave-decisions.md
- [ ] 2. WS scenarios tagged correctly (@real-io / @in-memory per strategy)
- [ ] 3. Every driven adapter has at least one @real-io scenario
- [ ] 4. For InMemory doubles: documented what they CANNOT model
- [ ] 5. Container preference documented if applicable
- [ ] 6. Mandate 7: all production modules imported by tests have scaffold files
- [ ] 7. Mandate 7: all scaffolds include `__SCAFFOLD__` marker (or language equivalent)
- [ ] 8. Mandate 7: all scaffold methods raise an assertion error (not NotImplementedError)
- [ ] 9. Mandate 7: tests are RED (not BROKEN) when run against scaffolds
- [ ] 10. Driving Adapter: every CLI/endpoint/hook in DESIGN has ≥1 WS scenario exercising it via subprocess/HTTP/hook protocol
- [ ] 11. F-001: ≥1 `@real-io @adapter-integration` scenario per driven adapter
- [ ] 12. F-002: `capsys` used in `@when` step, NOT in `@then` step (step-scoped in pytest-bdd)
- [ ] 13. F-005: `@when` steps import ONLY from `des.application.*` or `des.domain.*` — never `des.adapters.driven.*`
- [ ] 14. F-004: timing assertions in `.feature` files use budget >= 200ms
- [ ] 15. F-003: BDD imports after `sys.path` manipulation have `# noqa` markers
- [ ] 16. Dormant-Seam: every net-new DESIGN-declared load-bearing seam this slice has a witnessing AT naming THAT seam, driving it through the REAL entry point, asserting an observable effect (indirect registry/entry-point/DI wiring counts — not a naive name/protocol match). Canonical: `nw-test-design-mandates-composition-contract` Mandate 15; mechanically gated by `nw-at-completeness-check` S3.
- [ ] 17. Artifact Lineage Closure: DIRECT-SURFACE carries a named rationale; ASSEMBLED-SURFACE has one immutable candidate produced once by the real pipeline and consumed in a clean environment through the public journey, asserting the capability rather than a producer designation. Canonical: `nw-test-design-mandates-composition-contract`.

## Success Criteria

- [ ] Zero uncovered driving-adapter entry points
- [ ] Zero `NO — MISSING` adapter-coverage rows
- [ ] Adapter-integration slice authored (when CRITICAL pair) with all 10 properties verdict+cited
- [ ] Every new typed contract registered, or methodology-only skip documented
- [ ] Zero declared seams without a witnessing AT
- [ ] Artifact Lineage Closure PASS, or DIRECT-SURFACE rationale documented
- [ ] Self-review checklist complete
