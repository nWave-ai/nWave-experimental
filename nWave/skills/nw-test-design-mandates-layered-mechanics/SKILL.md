---
name: nw-test-design-mandates-layered-mechanics
description: "Layered test-mechanics mandates for acceptance tests — Universe-bound assertion at layers 1-3 (assert_state_delta), Mandate-9-v2 three-way treatment by mock-status, layer-dependent PBT input mode, two-tier acceptance (Tier A Gojko + optional Tier B state-machine PBT), example-based integration sad paths, the Layered Test Discipline table, and the Polyglot Adapter Matrix. Consult while choosing assertion style, PBT mode, tier, and sad-path treatment for a given layer and driven-adapter realness. Canonical definitions; SSOT for these mandates."
user-invocable: false
disable-model-invocation: true
---

# Test-Design Mandates — Layered Mechanics

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are choosing the test MECHANICS for a scenario at a known layer and driven-adapter realness — which assertion style (universe state-delta vs traditional), which PBT mode (full / example-pinned / example-only), whether to add Tier B, and how to treat sad paths. Mandates 8-11 + the Layered Test Discipline table + the Polyglot Adapter Matrix. The layer table is the union lookup for all of these.

Numbering is an SSOT-internal index defined in the recomposing core `nw-test-design-mandates`; refer to mandates by descriptive name externally. Language-convention frame (non-Python target adaptation) lives in the core.

## Mandate 8 — Universe-bound assertion at layers 1-3

Every test at layers 1-3 (unit, in-memory acceptance, subprocess/FS acceptance) that mutates observable state MUST assert via `assert_state_delta(before, after, universe={...}, expected={...})` (Python reference: `nwave_ai/state_delta/__init__.py`; other-language equivalents are added as the matrix grows).

- `universe` declares the SET of port-exposed observable names the test promises to track. Names are always port-exposed (event types, public read-model fields, exit codes, captured outputs) — never internal struct fields.
- `expected` declares which universe entries change and how (predicate per entry: `set_to`, `unchanged`, `appended_with`, `prepended_with`, `containing`, ...).
- Anything in `universe` that changes UNEXPECTEDLY (mutates with no `expected` entry) → violation. Fail-closed.
- Layers 4+ (integration, walking-skeleton, E2E) MAY use traditional assertions — at that layer the test cost is dominated by subprocess / network / real I/O and the universe-guard payoff is smaller.

Bad universe entries couple the test to private mutation details (`BoardProjection._rows_cells_dict`) — a refactor rename reds the test for no functional reason. Good universe entries are port names (`events.PhaseEntered.emitted_count`, `board.rows[task_id].cells[wave].status`).

## Mandate 9 v2 — three-way test treatment by mock-status (slice-01 minimal frame)

**Status**: SCAFFOLD — slice-01 of `fix-mandate-9-v2-rollout` ships this
minimal frame as a stub. Slice-02 ships the full skill expansion
(rationale, examples, residuality discussion). Spike source:
`docs/analysis/adapter-integration-slice-design-2026-05-27.md`.

Mandate 9 driver changes from **layer-driven** (v1) to **mock-status driven**
(v2) per the empirical anchor of D4 Phase 3 dogfooding (3 of 5 ATs
mislabeled `@real-io`). Three test treatments:

| Treatment | When (OR-reduced across driven-set) | Test framework |
|---|---|---|
| **PBT + universe + parametrize** | ALL driven adapters in-memory | Hypothesis `@given` + `assert_state_delta` |
| **Example-based + `assert_state_delta`** | ≥1 driven adapter real, SUT = feature via driving port | Gherkin Scenario + production composition root |
| **Adapter integration slice** | (Port, Adapter) classified CRITICAL, SUT = adapter itself | Adapter constructor directly + real driven dep + 10-property matrix |

### OR-reduction rule

Treatment is determined by the MOST-real driven adapter in the composition
root, NOT the average. A slice with one real adapter + N in-memory adapters
= example-based, NOT PBT.

### Mandate 1 carve-out

A layer-1 unit test that hits a real subprocess is forbidden by
construction per Mandate 1 (Hexagonal Boundary Enforcement). The
"mock-status driven" claim of Mandate 9 v2 applies WITHIN the
Mandate-1-permitted compositions.

### PBT budget note

"PBT-friendly" does NOT mean "PBT-mandatory". A layer-3 in-process
composition with all-mock driven adapters running Hypothesis at 100
examples/property is ~10-50× wall-clock heavier than a layer-1 unit due
to composition-root setup/teardown. Per-test budget still applies.

(Full rationale, residuality discussion, and per-tier examples land in
slice-02 expansion.)

---

## Mandate 9 — PBT input mode is layer-dependent

Property-based test machinery (Hypothesis `@given`, `RuleBasedStateMachine`, equivalent in other languages) is constrained by layer:

- **Layers 1-2** (unit, in-memory acceptance with in-memory doubles): PBT full. Hypothesis explores the generative input space (100+ examples per property by default). Pinned `@example(...)` preserves a domain-readable canonical case for reviewers.
- **Layers 3-6** (subprocess/FS acceptance, integration, walking-skeleton, E2E): example-only. Sad paths are enumerated explicitly, never PBT-generated. PBT runtime cost is incompatible with real-I/O tests where each example is 100ms–seconds.

Rationale: layer 3+ tests serve wiring proof and contract verification; coverage exploration happens at layers 1-2 where iteration is cheap.

## Mandate 10 — Two-tier acceptance for rich journeys

Acceptance tests come in two tiers. Tier A is mandatory. Tier B is optional and applied only to rich journeys.

- **Tier A — Gojko-style**: production composition root, real DI, example-only, 1-2 scenarios per journey. Lives in `.feature` files (Gherkin) + `steps_*.py` (or host-language equivalent) invoking the production composition root. Purpose: prove wiring end-to-end, demonstrate the feature works for the canonical example.
- **Tier B — state-machine PBT** (optional): in-memory doubles composition root, generative inputs, `RuleBasedStateMachine` with `@rule` / `@precondition` / `@invariant`. Lives in `test_<feature>_state_machine.py` (or host-language equivalent), separate file from the `.feature`. Purpose: explore the journey state space and surface contract gaps that example tests miss.

**Vocabulary shared**: the same step-methods (`Given_/When_/Then_` named in the domain language) are invoked from both tiers. Step-methods are the contract; the two tiers are two composition roots over the same vocabulary.

**Composition root contract**:
- Tier A uses real DI (e.g. `WebApplicationFactory` in C#, real installer entry-point in Python, real router in Go).
- Tier B uses an `InMemoryComposition` class that wires the same interfaces with in-memory doubles. The `InMemoryComposition` exposes a `capture_universe()` method returning the universe snapshot used by `assert_state_delta`.

**When to add Tier B**:
- Journey has ≥3 chained scenarios (Pillar 2 active), AND
- Input space is domain-rich (emails, dates, payloads, free-text, IDs from a large set).

**When Tier B is NOT worth it**:
- Config-shaped features (single-shot installer config, schema validation, one-off CLI).
- Journeys with 1-2 scenarios (Tier A example covers the space).
- Features where the only observable is "did it crash" (no state mutation to model).

## Mandate 11 — Integration sad paths stay example-based

Sad-path coverage at layers 3+ (subprocess / real adapter / integration / WS / E2E) uses traditional example-based tests, one example per failure mode.

- No PBT explosion on slow tests. The wall-clock cost of generating sad inputs against a real adapter dwarfs the gain.
- `assert_state_delta` is OPTIONAL at layer 3+ (universe-guard is a Mandate 8 layer 1-3 requirement; layers 4+ may use traditional assertions per Mandate 8).
- Each sad path is named explicitly: `Bug_<symptom>` or `Sad_<scenario>` test, with explicit input that triggers the failure.
- Coverage requirement: every failure mode enumerated in DEVOPS environment matrix and every `failure_modes` entry from `docs/product/journeys/<name>.yaml` gets at least one named sad-path test.

## Layered Test Discipline

The four mandates above (Universe, PBT mode, two-tier acceptance, sad-path treatment) compose into this layered discipline. The table below is the single source of truth for "what does this layer look like."

| Layer | Speed | Real adapter? | Input mode | Assertion mode |
|---|---|---|---|---|
| Unit | <1ms | no | PBT full (`@given` 100+ examples) | state-delta + Universe |
| In-memory acceptance | ~10ms | no (in-memory doubles) | PBT example-pinned if AC tagged `@property`; example-only otherwise | state-delta + Universe |
| Subprocess / FS acceptance | ~100ms | yes (real adapter) | example-only — sad paths enumerated | state-delta + Universe |
| Integration | ~100ms | yes | example-only, sad-path coverage | traditional OK; state-delta optional |
| WS `@wiring_e2e` | 1-3s | yes (real stack) | example-only (1-2 representative) | traditional |
| E2E | seconds | full real | example-only | traditional |

**Polyglot note**: the Universe / state-delta and PBT laws are
language-agnostic — the prose is the contract, and Python imports
(`nwave_ai.state_delta`, Hypothesis) are illustrative. Author the same
semantic property with the host language's idiomatic generator,
shrinker/replay, assertion, and runner. Never translate syntax and silently
weaken the quantified law.

## Polyglot Adapter Matrix

Contract layer (3 Pillars + Mandates 8-11) is language-agnostic. The eight
distributed `nw-pbt-*` adapter families own the implementation bindings below;
DISTILL selects exactly one from repository evidence. Missing toolchain
availability makes that runtime probe `SKIP`/`INDETERMINATE`; it never selects
Python as a substitute.

| Adapter family | Languages | PBT binding | Test/step idiom |
|---|---|---|---|
| `nw-pbt-python` | Python | Hypothesis | pytest / pytest-bdd |
| `nw-pbt-typescript` | TypeScript, JavaScript | fast-check | Vitest/Jest; scenario + specification modules |
| `nw-pbt-dotnet` | C#, F# | CsCheck/FsCheck | xUnit/NUnit; partial classes or modules |
| `nw-pbt-jvm` | Java, Kotlin, Scala | jqwik/Kotest/ScalaCheck | JUnit/Kotest/ScalaTest companion tests |
| `nw-pbt-rust` | Rust | proptest | cargo test; scenario + specification modules |
| `nw-pbt-go` | Go | rapid | testing; `*_scenarios_test.go` + `*_specifications_test.go` |
| `nw-pbt-haskell` | Haskell | QuickCheck/Hedgehog | Hspec/Tasty property modules |
| `nw-pbt-erlang-elixir` | Erlang, Elixir | PropEr/PropCheck/StreamData | EUnit/Common Test/ExUnit property modules |

**State-delta port** per language lives at the project-local path
`tests/common/state_delta.<ext>` (apply-if-absent on first DISTILL in the
project). Python port is canonical at `nwave_ai/state_delta/`. Other-language
ports are templated bootstraps from the per-lang Tier-2 expansion catalogs.

**Universe assertion contract** is identical across languages: every
state-mutating test at layers 1-3 calls `assert_state_delta(before, after,
universe, expected)` (Python signature; idiomatic translations preserve the
same four parameters). Universe declares observable port-exposed names;
expected maps each declared key to a predicate. Anything in universe not in
expected MUST remain unchanged — fail-closed.

**Per-lang predicate library** mirrors the Python set: `set_to`, `unchanged`,
`appended_with`, `containing`, `normalized_to`, `idempotent_after`,
`legacy_healed`, `prepended_with`. Each language port implements all eight
with the same semantic contract.
