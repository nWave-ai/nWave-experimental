---
name: nw-test-design-mandates-composition-contract
description: "Composition-root authoring-contract mandates for acceptance tests — SSOT + Zero Duplication via Types + Services + DSL, Driving-Port-Only Boundary (Farley four-layer protocol-driver contract, fixture-theater/tautological-test anti-pattern), Contract Shape Classification (@in-memory/@real-io tag-vs-composition), and Dormant-Seam Reconciliation (AT drives the DESIGN-declared seam, not the new component). Consult while composing the AT's driving surface, structuring step/type/service code, and tagging the contract shape. Canonical definitions; SSOT for these mandates."
user-invocable: false
disable-model-invocation: true
---

# Test-Design Mandates — Composition Contract

**Kind**: KNOWLEDGE (reference). No forced sequence — consulted on its trigger.

**Trigger**: you are composing the AT's DRIVING SURFACE and its code contract — how the step/type/service code is structured (SSOT-via-types), which driving port the AT reaches the SUT through (and which surfaces are forbidden), which contract-shape tag the scenario carries, and whether the AT drives the DESIGN-declared seam. Mandates 12-15. These are HARD invariants enforced at review + the hook spine.

Numbering is an SSOT-internal index defined in the recomposing core `nw-test-design-mandates`; refer to mandates by descriptive name externally. Language-convention frame (non-Python target adaptation) lives in the core.

## Mandate 12 — SSOT + Zero Duplication via Types + Services + DSL

Domain concepts are expressed once via the type system; logic lives in composition-root services as the single source of truth; step methods invoke services and never inline business logic.

- Domain concepts live in `tests/{path}/acceptance/steps/domain_types.py` (Python pilot; host-language equivalent otherwise) as typed enums / dataclasses / NewTypes.
- Business logic lives in composition-root services, not in step bodies.
- The DSL emerges from typed domain concepts — parameterized templates over enum-typed parameters, NOT hundreds of unique step decorators.

Compliance is mechanical via four criteria:
1. **(criterion 1)** Domain types module exists with typed enums / dataclasses / NewTypes for every domain noun used in the Gherkin.
2. **(criterion 2)** Composition methods consume typed parameters from `domain_types.py`; no raw `str` parameter where a domain enum exists.
3. **(criterion 3)** No business logic in step bodies — AST: ≤2 statements, final statement is `composition.<service>.<method>(...)`, no control flow (`if`/`for`/`while`/`try`).
4. **(criterion 4)** Step-reuse-ratio (`total_step_invocations / unique_step_decorators`) measured and documented as INFORMATIONAL natural ceiling per feature — NOT a gate; below 4× is acceptable when criteria 1-3 are met (forcing ≥4× would sacrifice Pillar 1 readability).

Anti-pattern: a scenario rewrites Given/When/Then verbatim with hard-coded literals, OR collapses readable Gherkin into ratio-maximizing parameterized templates that degrade domain coherence. Reference: ADR-026; `[[feedback_atdd_ssot_via_types_services_dsl_2026_05_18]]`, `[[feedback_mandate12_refinement_2026_05_18]]`.

**DISTILL-before-DELIVER timing (atdd_pure)**: under `atdd_pure`, DISTILL authors `domain_types.{py,ts,...}` BEFORE DELIVER has created any production domain module — at authoring time there is nothing to import. <!-- mode-ref-ok --> This is expected and NOT a violation of "expressed once": the DISTILL-authored module is a PLACEHOLDER for the slice(s) still to ship, not a permanent second definition. Two rules follow:
- The placeholder's doc comment MUST say it is a DISTILL-time placeholder pending DELIVER (e.g. "placeholder until DELIVER lands `src/domain/...` — at implementation, this declaration MOVES into production source and this module IMPORTS it from there, it does not keep its own copy"). A comment stating the split as a PERMANENT design choice ("these are NOT imported from production code" with no reconciliation obligation) is the anti-pattern this note exists to close — it re-introduces exactly the "test passes against the old behavior — silent drift" failure Mandate 12 forbids, because production and test-side types WILL diverge in shape the moment either evolves independently.
- Once DELIVER lands the production domain module for a given concept, ITS SAME SLICE's GREEN phase (or a dedicated reconciliation step, never deferred past that slice) MUST move that type's declaration into the production source and change `domain_types.{py,ts,...}` to IMPORT it directly from there — a bare `import { X } from "src/domain/..."` (or language equivalent), never a re-export wrapper, never a structurally-independent redeclaration, however similarly shaped. A domain type that still exists standalone (declared, not imported) in the test-side module AFTER its production counterpart has shipped is a Mandate-12 violation, mechanically detectable as: for each type name declared in both places, the test-side declaration is not a direct import of the production one (e.g. a test-side bare string-literal union next to a production discriminated union for the same concept name is the signature of this exact drift).

## Mandate 13 — Driving-Port-Only Boundary

ATs drive the SUT **exclusively** through a composition-root driving port at one of three layers — never via direct-domain / function-level / CLI-internal testing. HARD invariant.

**The three permitted driving surfaces**:
- **Layer 3 subprocess** — real CLI invocation via the `des <subcommand>` kebab dispatcher (preferred for CLI/script behaviors).
- **Layer 3 composition** — real service via composition root (e.g. `PreToolUseService(...).evaluate(...)`, for hook/intercept behaviors).
- **Layer 4 wiring_e2e** — full stack, real hook subprocess invocation (for end-to-end gate behaviors).

**ATs MUST NOT**:
1. Import production modules directly in step composition (`from des.{domain,application,adapters}.X import Y; Y().method(...)` is FORBIDDEN — adapters are infrastructure, not a driving surface, the same forbidden class as domain).
2. Test pure-function behavior at the function boundary (function-level unit testing is an anti-pattern for ATs).
3. Ship NEW behavioral coverage under `tests/des/unit/(?:domain|cli)/*` (that path is reserved for pre-existing legacy + arch tests; new ATs ship under `tests/des/(?:acceptance|cli)/[feature-name]/` only).

**Rejection rule**: if a dispatch prompt instructs Layer-1 unit testing (`tests/des/unit/(?:domain|cli)/.*` path OR direct production import in composition) for behavioral coverage, REFUSE the AT-design dispatch and escalate. **Reviewer self-application**: a reviewer recommendation that introduces direct-domain testing is itself an anti-pattern — always recommend a driving-port alternative.

### Protocol-driver contract (Farley four-layer ATDD)

Two conditions, BOTH mandatory — the boundary is not satisfied by traversal alone:

1. **Real protocol only.** The AT reaches the SUT exclusively via the real protocol — subprocess (`des <subcommand>`) or production composition root. The protocol driver is the only place the real protocol lives; only genuinely external systems may be stubbed (Farley Test → DSL → Protocol Driver → SUT).
2. **Assert a shipped artifact or an observed effect.** Every assertion reads an **artifact the SUT actually shipped** (a file on disk written by the SUT, an emitted event, a captured stdout, a process exit code) or an **observable effect the SUT produced** — NEVER a string/structure rendered by the test itself.

**Anti-pattern — *tautological test / self-fulfilling fixture***: a green test whose oracle is data the test fabricated (the fixture supplies the expected output, the assertion re-reads the fixture). Zero validation power: passes with the production code deleted. (Phenomenon naming per `docs/research/walking-skeleton-atdd-best-practices-2026-06-12.md`; the term "The Mockery" is Bugayenko-specific and NOT used here.) nWave term: **fixture-theater** (Critical Rule 7).

**Prose-surface case** — when the shipped surface is a markdown asset (skill / task / agent under `nWave/...`): the AT MUST read the **real file shipped from the repo** (not an inline test string), and every marker MUST be a **discriminating phrase**, never a substring that matches a common word. Empirical false-positives: `"table"` matches `"acceptable"`; `"rigor"` matches `"rigorous"`. Assert on a multi-word phrase unique to the shipped surface.

### Artifact Lineage Closure — assembled surfaces

When the paying user consumes a derived or assembled artifact — wheel, package,
archive, image, generated tree, installed plugin set, executable bundle,
deployment manifest, or synchronized configuration — reaching the producer's
real entry point is necessary but insufficient. The AT MUST close the full
consumer lineage:

```
production input
  -> real production pipeline
  -> one immutable candidate
  -> clean consumer environment
  -> public user journey
  -> user-observable capability
```

All six links are mandatory:

1. **Real production pipeline** — build through the same public producer used
   for release. A test-authored copy, reconstructed fixture, or hand-assembled
   directory is not the release artifact.
2. **One immutable candidate** — identify the candidate by exact path plus
   digest (or equivalent immutable identity). Build once; downstream probes
   consume that same candidate. A rebuild is a different subject.
3. **Clean consumer environment** — install/load where the candidate cannot
   borrow from the source checkout, developer HOME, editable install, or global
   installation.
4. **Public user journey** — exercise the command/API/loader/runtime a customer
   uses. Archive inspection alone is insufficient when the product claim is
   installation or execution.
5. **User-observable capability** — assert what the user can actually do, not
   merely a packaging declaration, manifest entry, configured source path, or
   producer success message.
6. **Loud failure** — an incomplete candidate returns explicit non-success
   naming WHAT capability/artifact is unavailable, WHY the journey cannot
   complete, and HOW to produce a valid candidate.

**Decide on the produced PROPERTY, never its DESIGNATION.** A declaration is
evidence only when the declaration itself is the public contract. When it is
meant to produce another artifact/effect, assert the produced property: a
manifest naming `nWave/templates` is weaker than the immutable wheel containing
those templates and a clean installation loading them. Never require the
Acceptance Designer to resolve this rule through another skill that its phase
does not load.

This obligation does NOT multiply E2E tests. The feature's single
`@walking_skeleton` closes the lineage when the feature is assembly-sensitive;
focused behavioral scenarios remain at L2. If one feature truly exposes
multiple independent assembled consumer journeys, justify the additional E2E
or split the feature along those value boundaries.

Rationale: hexagonal boundary discipline + ATDD-pure paradigm (Layer 3 only) + recursive compounding. Ale directive 2026-05-25 verbatim: "ma perche ci sono unit test? il nuovo DES non dovrebbe farne scrivere. Inoltre il domain non dovrebbe essere testato direttamente." Empirical anchors (2 caught 2026-05-25 before shipping): M15 composition imported `DesMarkerParser` directly under `tests/des/unit/domain/*` — REMOVED; M16 reviewer recommended a Layer-1 parity guard — recommendation itself was the anti-pattern, REMOVED. Mechanical enforcement: `nw-at-completeness-check` S2 (Tier-2 gate), enforced at the nWave hook spine (PreToolUse/SubagentStop — Python + filesystem, git-free). Friction: `F-ATDD-PURE-AT-DIRECT-DOMAIN-TESTING-ANTI-PATTERN`.

### The 6-level composition — the induction target for a new AT

A new acceptance test is INDUCED onto exactly one of six composition levels. The default level is **L2 in-process acceptance** — drive the real entry `cli main(argv)` IN-PROCESS with a fake output port, config-switchable in-memory ↔ prod-like (per `nw-distill-port-treatment-policy`). subprocess-e2e (L1) is reserved for the one `@walking_skeleton` per command. The other levels are induced only when the contract calls for them; sad-paths / ZOMBIES are enumerated at EVERY level (language-agnostic — the level names are the rule, the Python entry forms are illustration):

| Level | Proves | DEFAULT for a new AT? | Induced when... |
|---|---|---|---|
| **L1 walking-skeleton** | the installed artifact is wired end-to-end (real fork, real terminal) | no — **ONLY** the one `@walking_skeleton` per command | always exactly one per command (terminal-wiring facet) |
| **L2 in-process acceptance** | the command computes + emits the right output, driven in-process | **YES — the default** | every non-WS behavioural AT; the in-memory ↔ prod-like config-switch is owned by `nw-distill-port-treatment-policy` |
| **L3 integration (adapter ↔ real)** | a driven adapter works against its real I/O | no | a driven adapter ships → ≥1 `@real-io @adapter-integration` AT names it (Mandate 6) |
| **L4 contract (per port)** | a port's method contract holds for all implementations | no | a port/Protocol ships → ≥1 contract test exercises its contract |
| **L5 architecture** | layering / forbidden-imports hold | no | structural invariants (arch-tests under `tests/build/**`) |
| **L6 unit / PBT** | a pure function's law holds + the executed path is covered | no | a declared law needs a property test, or an AT cannot reach GREEN without a unit-level pin |

- **Default = L2.** Absent a specific contract reason to descend, a new AT is L2 in-process acceptance — it is the speed default. Reaching for L1 subprocess on a non-WS scenario is the regression the subprocess-overuse gate flags.
- **L1 is singular.** One walking-skeleton per command, never per scenario (the terminal-wiring facet of the CLI split; see `nw-distill-port-treatment-policy`).
- **L3/L4 are mechanized coverage obligations, not agent-discipline.** A driven adapter without an L3 `@real-io` AT, or a port without an L4 contract test, BLOCKS at the readiness gate (cross-ref `nw-distill-coverage-obligations`).
- **Sad-paths at every level.** Each level carries its own error-path / ZOMBIES enumeration (≥40% error/edge per `nw-distill-coverage-obligations`); a level proving only the happy path is incomplete.

The reference exemplar that proves the L2 in-process active-RED pattern is executable: `tests/des/acceptance/at_in_process_port_default/` driving `des.cli.run_contract_gate.main` through the `OutputPort` (`src/des/ports/driven_ports/output_port.py`). The active-RED authoring pattern (P1-P4) lives in `nw-distill-red-scaffolding`.

## Mandate 14 — Contract Shape Classification

Each scenario declares its contract shape so the reviewer can verify the assertion style matches. The scenario tag MUST match the composition root it drives, per the Mandate 9 v2 OR-reduction rule:

- `@in-memory` — ALL driven adapters in the composition root are in-memory / mock / stub fakes. PBT + universe + parametrize treatment applies.
- `@real-io` — AT LEAST ONE driven adapter is a real I/O adapter (real filesystem, subprocess, network, HMAC keys). Example-based + `assert_state_delta` treatment applies; PBT is precluded by OR-reduction.
- `@mixed` — disallowed; OR-reduction collapses the mixed case to `@real-io`.

A scenario tagged `@real-io` whose composition is observably all-mock is a TAG-COMPOSITION MISMATCH (reviewer flags NEEDS_REVISION). Enforced by `nw-acceptance-designer-reviewer` Critique Vector S3 (mock-tag consistency) and the `@contract-shape:` machine-parseable tag. Spike source: `docs/analysis/adapter-integration-slice-design-2026-05-27.md` §3/§6.

## Mandate 15 — Dormant-Seam Reconciliation

The AT-oracle target is the DESIGN-declared **seam**, not the new component. HARD invariant (D11).

For every net-new seam declared load-bearing in the DESIGN driving-surface for the slice — a net-new effectful entry-point parameter (e.g. `clock=`), a net-new effectful call reached from the entry point (e.g. `absorb_ready_refs()`), or a net-new param threaded into an existing seam — the slice AT MUST:
1. Name THAT exact seam as the port it drives.
2. Drive it through the **real entry point**.
3. Assert an **observable effect** (state delta / emitted event / captured side effect).

Re-deriving the AT target from "what's new in the slice" silently substitutes the COMPONENT for the SEAM — the intra-commit contradiction that ships a seam DORMANT (no production call-site, never reached from the real entry point) despite all per-slice gates passing.

**Witnessing counts INDIRECT wiring**: a seam reached via registry / entry-point discovery / DI is validly witnessed even with no direct call-site or protocol call (never a naive name/protocol match). A declared seam with no witnessing AT BLOCKS; owned residue cleared by a `# dormant-ok: <F-id>` marker is excused. Mechanical enforcement: `nw-at-completeness-check` S3 (Tier-2 BLOCKER) + the shipped `des dormant-seam-gate` (INDETERMINATE, non-halting). Empirical anchor (2026-06-07): `background-loops-hybrid-c` slices 04/05/07/08 shipped absorb/clock/drain-selector/reaper uncalled from `handle_session_start`; all per-slice gates green; see `[[feedback_dormant_seams_ship_green_horizontal_slicing_2026_06_07]]`.
