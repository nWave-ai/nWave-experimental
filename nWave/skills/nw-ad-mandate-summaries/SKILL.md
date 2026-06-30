---
name: nw-ad-mandate-summaries
description: "Acceptance-designer operational summaries of the test-design mandates the agent applies during AT authoring (Contract Shape, Driving-Port-Only, Dormant-Seam, SSOT-via-Types, plus the Mandate-9-v2 tag-vs-composition rule and the adapter-integration slice authoring trigger). Operational summaries only — canonical definitions live in nw-test-design-mandates + nw-distill. Consult during Phase 2 scenario authoring and Phase 4 mandate-compliance evidence."
user-invocable: false
disable-model-invocation: true
---

# AD Mandate Summaries (operational)

KNOWLEDGE skill. No forced sequence. Consulted by `nw-acceptance-designer` during authoring.

**SSOT pointers (never re-derive here, refer by name):**
- Canonical mandate definitions + numbering → `nw-test-design-mandates` (Mandate Registry).
- Induction map, gate-G rubric, carpaccio tag contract, adapter-integration authoring contract → `nw-distill`.
- These are the **operational summaries** the agent applies; the number is an SSOT detail, not a contract — refer by descriptive name.

## Mandate operational summaries (apply during Phase 2)

| Mandate (name) | What the agent does at authoring | SSOT |
|---|---|---|
| Contract Shape Classification | Every scenario carries `@contract-shape:<pure-function \| bounded-change \| unbounded-preservation>`. Untagged scenarios block at review. Outcome Elevator Pitch uses ubiquitous-language verbs naming the user-valued outcome (technical verbs block); it propagates verbatim DISCUSS → DISTILL name → DELIVER test name. | `nw-test-design-mandates` |
| Driving-Port-Only Boundary (HARD) | Drive the SUT only through a composition-root driving port — Layer 3 subprocess (`des <subcmd>`) OR Layer 3 composition (real service via composition root) OR Layer 4 wiring_e2e. NEVER: direct production import in step composition (`from des.{domain,application,adapters}.X import Y`), function-level unit-test ATs, new behavioral ATs under `tests/des/unit/(?:domain\|cli)/*`. New ATs ship under `tests/des/(?:acceptance\|cli)/[feature-name]/` only. If dispatch instructs Layer-1 unit testing for behavioral coverage → REFUSE and escalate. | `nw-test-design-mandates` |
| Dormant-Seam Reconciliation (D11, HARD) | For every net-new seam declared load-bearing in the DESIGN driving-surface (net-new effectful entry-point param like `clock=`, net-new effectful call reached from the entry point like `absorb_ready_refs()`, net-new param threaded into an existing seam): the slice AT names THAT exact seam as its driving port, drives it through the REAL entry point, asserts an observable effect. Indirect registry/entry-point/DI wiring counts as witnessing (not naive name/protocol match). Owned residue cleared by `# dormant-ok: <F-id>`. Enforced by `nw-at-completeness-check` S3 + backstopped by `des dormant-seam-gate`. | `nw-test-design-mandates`, `nw-distill` |
| SSOT-via-Types-Services-DSL | Domain concepts expressed once via the type system (`tests/{path}/acceptance/steps/domain_types.py`); logic in composition-root services; step methods invoke services, never inline business logic. DSL = parameterized templates over enum-typed params. Four mechanical criteria: (a) domain types module with typed enums; (b) composition methods consume typed params (no raw `str` where an enum exists); (c) step body ≤2 statements, final = `composition.<service>.<method>(...)`, no control flow; (d) step-reuse-ratio measured + documented INFORMATIONAL (NOT a gate — below 4× is compliant when a-c pass; forced ≥4× that degrades Pillar 1 readability is refused). See ADR-026. | `nw-test-design-mandates` |

## Mandate-9-v2 tag-vs-composition rule (apply at Phase 3 composition)

A scenario tag MUST match the composition root it drives (OR-reduction, spike §3):

- `@in-memory` — ALL driven adapters are in-memory/mock/stub. PBT + universe + parametrize applies.
- `@real-io` — AT LEAST ONE driven adapter is real I/O (real filesystem, real subprocess, real network, real HMAC keys). Example-based + `assert_state_delta`; PBT precluded by OR-reduction.
- `@mixed` — disallowed; OR-reduction collapses to `@real-io`.

A `@real-io` scenario whose composition is observably all-mock is a TAG-COMPOSITION MISMATCH → reviewer flags NEEDS_REVISION (reviewer Critique Vector S3).

## Adapter-integration slice authoring trigger (apply at Phase 2 classification)

When the in-scope feature ships a CRITICAL (Port, Adapter) pair per the Adapter Criticality classification, DISTILL MUST author an adapter-integration slice in addition to the acceptance slice — the adapter is the SUT, not the feature. Authoring contract (10-property matrix + per-property EXERCISED/N/A/DEFERRED verdict + 4-step reviewer checklist + carpaccio-ceiling escape Option B = split per property) lives in `nw-distill` § Adapter Integration Slice Authoring.

A CRITICAL adapter shipped without an adapter-integration slice is a BLOCKER at the reviewer surface; acceptance slices alone are insufficient.

**Adapter Criticality source** (two SSOTs, reviewer checks both):
- Framework-shipped (Port, Adapter) pairs → `nWave/framework-catalog.yaml` (authoritative; consumers cannot reclassify).
- Project-local (Port, Adapter) pairs → `docs/architecture/atdd-infrastructure-policy.md` Adapter Criticality table.
