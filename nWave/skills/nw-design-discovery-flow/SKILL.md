---
name: nw-design-discovery-flow
description: "DESIGN discovery-driven architecture flow — problem understanding, constraints, Conway's Law mapping, paradigm selection, Reuse Analysis (contract pinned in the nw-design core), architecture recommendation, optional stress analysis, deliverables, and the Outcome Collision Check. Run when architecture work begins, after the wave-entry decisions are resolved."
user-invocable: false
disable-model-invocation: true
---

# DESIGN Discovery Flow + Outcome Collision Check (PROCEDURE)

**Kind**: PROCEDURE | **One job**: execute the discovery-driven architecture flow from problem understanding through deliverables | **One trigger**: a DESIGN session has resolved the wave-entry decisions (scope + interaction mode) and is about to do architecture work.

Composed by `nw-design`.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## Discovery Flow

Architecture decisions are driven by quality attributes, not pattern shopping. Execute these steps in order:

1. **Understand the Problem** — review JTBD artifacts from DISCUSS. Ask: What are we building? For whom? Which quality attributes matter most? (scalability|maintainability|testability|time-to-market|fault tolerance|auditability). Gate: quality attribute priorities ranked.
2. **Understand Constraints** — ask: Team size/experience? Timeline? Existing systems to integrate? Regulatory requirements? Operational maturity (CI/CD, monitoring)? Gate: constraints list documented.
3. **Map Team Structure (Conway's Law)** — ask: How many teams? Communication patterns? Does proposed architecture match org chart? Gate: team-architecture alignment confirmed.
4. **Select Development Paradigm** — identify primary language(s) from constraints, then: FP-native (Haskell|F#|Scala|Clojure|Elixir) → recommend Functional; OOP-native (Java|C#|Go) → recommend OOP; Multi-paradigm (TypeScript|Kotlin|Python|Rust|Swift) → present both, let user choose. After confirmation, ask user permission to write paradigm to project CLAUDE.md: FP: `This project follows the **functional programming** paradigm. Use @nw-functional-software-crafter for implementation.` OOP: `This project follows the **object-oriented** paradigm. Use @nw-software-crafter for implementation.` Default if user declines/unsure: OOP. Gate: paradigm selected and optionally written to CLAUDE.md.
5. **Reuse Analysis (MANDATORY — RCA F-1 fix)** — run the Reuse Analysis step + Reuse-first DESIGN exit gate defined in the `nw-design` core (§Reuse Analysis + §Reuse-first DESIGN exit gate) — the full contract (canonical heading, columns, decision tokens, methodology components, lenient match, enforcement CLI, rejection-rationale templates) is AT-pinned to that file and is NOT re-inlined here. Gate: Reuse Analysis table present with zero unjustified CREATE_NEW decisions.
6. **Recommend Architecture Based on Drivers** — recommend based on quality attribute priorities|constraints|paradigm from steps 1-5. Default: modular monolith with dependency inversion (ports-and-adapters). Overrides require evidence. If functional paradigm: apply types-first design, composition pipelines, pure core / effect shell, effect boundaries as ports, immutable state — in architecture document only, no code snippets. Gate: architecture pattern selected with written rationale.
7. **Stress Analysis** (HIDDEN — `--residuality` flag only) — when activated: apply complexity-science-based stress analysis (stressors|attractors|residues|incidence matrix|resilience modifications) using the `stress-analysis` skill. When not activated: skip entirely, do not mention. Gate: activated only when flag present.
8. **Produce Deliverables** — write architecture document with component boundaries|tech stack|integration patterns. Produce C4 System Context diagram (Mermaid) — mandatory. Produce C4 Container diagram (Mermaid) — mandatory. Produce C4 Component diagrams (Mermaid) — only for complex subsystems. Write ADRs for significant decisions. Gate: mandatory C4 diagrams present, ADRs written.

## Outcome Collision Check (per DISCUSS#D-5 grain)

Provenance: feature `outcomes-registry` — DISCUSS#D-2 (lean Tier-1 + Tier-2 default), D-5 (per-typed-contract grain), D-6 (gate-scoping: code-feature pipelines only).

**Trigger**: a new feature-delta has been emitted in DESIGN with a Reuse Analysis table. Run this check AFTER step 5 (Reuse Analysis) in the Discovery Flow and BEFORE producing the final architecture deliverables in step 8.

**Skip when**: the feature is methodology-only (skill propagation, prose changes, no new typed contract surface). Per D-6 gate-scoping, the outcomes registry tracks code-feature pipelines only.

**Procedure**:

1. **Run** the collision-check CLI against the freshly-emitted feature-delta:
   ```
   nwave-ai outcomes check-delta docs/feature/{feature-id}/feature-delta.md
   ```
2. **Handle exit codes**:
   - **Exit `0`** — no collisions detected. Proceed to step 8 (Produce Deliverables).
   - **Exit `1`** — one or more candidate outcomes overlap with existing OUT-N rows in `docs/product/outcomes/registry.yaml`. Review the reported OUT-ids. For each:
     - **Genuine duplication**: link the new candidate to the existing OUT-N via `related: [OUT-N]` in the registry, OR mark the existing OUT-N `superseded_by: OUT-M` if the new contract replaces it. Re-run `check-delta` to confirm.
     - **False positive** (Tier-1 keyword/shape match fired but Tier-2 disambiguation reveals the contracts are distinct): annotate the candidate's keywords in the registry to be more distinctive, then re-run.

The registry at `docs/product/outcomes/registry.yaml` is the SSOT for "what we promise the system does." Reuse Analysis (step 5) deduplicates within the codebase; the Outcome Collision Check deduplicates across the contract registry — they are complementary gates.

Gate: `check-delta` exits `0`, OR every reported collision has been resolved (linked, superseded, or disambiguated) and the re-run exits `0`, OR the feature is documented as methodology-only and the check is correctly skipped.
