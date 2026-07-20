---
name: nw-deliver-atdd-pure-slice-gates
description: "DELIVER ATDD-pure per-slice phase-boundary contracts — the D_REFACTOR_COMMIT exit gate (E1 slice-commit completeness + E2 contract-gate scope), Phase D routing decision rules, A_GREEN/D_REFACTOR_COMMIT separation enforcement, the verdict-hash trailer, per-phase-boundary telemetry, and the post-commit falsifier-gate hook. Load when a per-slice phase boundary beyond the A_GREEN entry dispatch must be governed."
user-invocable: false
disable-model-invocation: true
---

# DELIVER ATDD-Pure Per-Slice Phase-Boundary Gates (PROCEDURE)

**Kind**: PROCEDURE | **One job**: govern the per-slice phase-boundary contracts of the ATDD-pure DELIVER sequence | **One trigger**: a slice has entered the per-slice A_GREEN→C_REVIEWER_AUDIT→D_REFACTOR_COMMIT sequence and a phase boundary beyond the A_GREEN entry dispatch must be governed (routing a C_REVIEWER_AUDIT verdict, dispatching D_REFACTOR_COMMIT, or closing the D_REFACTOR_COMMIT commit).

Composed by `nw-deliver`. The dispatch markers, the carpaccio entry gate, and the per-slice phase table live in the `nw-deliver` core — this module holds the boundary contracts that fire after the A_GREEN entry dispatch.

## Reasoning Mandate (Caveman)

Verdict-first, tables over prose, evidence-dense, zero narrative. Depth comes from rigor, not padding. State the conclusion, then the supporting evidence; never bury the verdict under exposition.

## D_REFACTOR_COMMIT exit gate (after the commit, per slice)

slice-14 of the atdd-pure-roadmap-free-rollout wires a DES `exit_gate` onto
`D_REFACTOR_COMMIT` — the exit-side symmetric counterpart of the carpaccio `entry_gate`.
It closes the RCA-diagnosed "verification narrower than the contract" defect
class (`docs/analysis/rca-slice-shipped-broken-verification-narrower-than-contract-2026-05-20.md`).
For every slice (`Class = C` and `Class = P` alike) the orchestrator MUST run
the exit gate AFTER the `D_REFACTOR_COMMIT` commit and BEFORE marking the phase
complete. It is ONE DES gate object with two assertions:

```
des verify-slice-commit --repo . --commit HEAD --feature-id {feature-id}
des run-contract-gate --repo . --commit HEAD --verify-gate-scope
```

> **`--feature-id` is REQUIRED.** It selects the verify-then-record path (E1 completeness + E2 feature-scoped contract gate) which RECORDS the `SliceCommitVerified` ledger entry the successor slice's carpaccio entry gate blocks on. WITHOUT `--feature-id` the legacy E1-only path runs and emits `SliceCommitComplete` with NO ledger record — the successor slice is then blocked. Do NOT rely on the SubagentStop hook to emit `SliceCommitVerified`: it fires only on a distinct `D_REFACTOR_COMMIT`-phase return, which a folded lean-cycle commit may not produce (empirical 2026-05-29: a slice committed but left no record, blocking its successor until backfilled).

- **E1 — slice-commit completeness** (`verify_slice_commit_completeness`,
  pure-function, stdlib-only, no filesystem mutation): given the `D_REFACTOR_COMMIT`
  commit's `Slice-Id:`/`Step-Id:` trailer, asserts every `@slice-NN`-tagged
  `.feature` AT file for that slice is present in the commit OR already
  tracked-and-unmodified. Exit `0` complete · `1` incomplete (JSON names the
  missing files) · `2` malformed input.
- **E2 — terminating run == contract gate** (`run_contract_gate
  --verify-gate-scope`): asserts the commit carries a `Gate-Scope:` digest that
  matches a fresh `run_contract_gate --collect-only` digest of the whole-tree
  contract suite (`pytest -m "unit or integration or acceptance"`). Exit `0`
  verified · `1` absent/mismatching · `2` malformed input. `run_contract_gate`
  is the SINGLE canonical contract gate — the crafter's terminating run, the
  pre-commit wrapper, and CI all invoke this one definition, so verification
  scope can never be a proper subset of the contract.

The `D_REFACTOR_COMMIT` phase completes iff BOTH E1 and E2 exit `0`. On any non-zero
exit, DES blocks `D_REFACTOR_COMMIT` phase completion and halts with the gate's JSON
payload — the slice cannot reach `COMMIT`/`PASS` in the execution record.
"Shipped" is then mechanically derivable from the DES log (the exit gate
passed), never an agent's narrative claim.

## Phase D Routing (orchestrator decision rules)

Source: plan v3 §7.2. Decision sequence:

1. **BLOCKER severity in any gap** → emit `DeliverBlocker`, halt exit 42 `ARCHITECTURE_GAP_ESCALATION`, return `HUMAN_ESCALATION`.
2. **Cycle exhaustion** (`phase_d_cycle_count > 2`) → emit `DeliverCycleExhausted`, halt exit 42 `CYCLE_EXHAUSTION`, return `HUMAN_ESCALATION`.
3. **Wall-clock timeout** (>14400s) → emit `DeliverTimeoutExceeded`, checkpoint state, halt exit 42 `DELIVER_TIMEOUT`, return `CHECKPOINT_TIMEOUT`. Resume via `/nw-resume-deliver`.
4. **Second-order architecture-scope-miss** (≥2 gaps sharing a `scenario_class` mapping to a DESIGN-absent component) → emit `ArchitectureScopeMissDetected`, return `REROUTE_DESIGN`.
5. **`SPECIFICATION_AMBIGUITY` gaps** → emit `SpecificationAmbiguityDetected`, route per category (C2→DISCUSS, C5→DESIGN, C7→DEVOPS), return `REROUTE_DISCUSS` | `REROUTE_DESIGN` | `REROUTE_DEVOPS`.
6. **`AT_GAP_IN_DELIVERY_SCOPE` only** → emit `AcceptanceTestGapIdentified`, increment cycle counter, return `RELOOP_A`.
7. **No gaps** → return `PROCEED_TO_D_REFACTOR_COMMIT`.

Sentinels map to `PhaseExit` enum in `src/des/domain/atdd_pure_phases.py` — use those names verbatim in audit-log events.

## Separation Enforcement — SUPERSEDED (D_REFACTOR_COMMIT is commit-only)

**No separate crafter instance is required for `D_REFACTOR_COMMIT`.** The Ale 2026-05-19 mandate below governed a `D_REFACTOR_COMMIT` that DID L1-L6 refactor + review; that per-slice refactor is now SUPERSEDED (not re-dropped — see `nw-deliver`'s `D_REFACTOR_COMMIT` table row and commit a91bf4f6b, 2026-07-04) by the mandatory per-feature Prefactoring Assessment upstream in DESIGN. With no refactor and no review happening inside `D_REFACTOR_COMMIT` — it is `des commit-slice` and nothing else — the rubber-stamp-your-own-bias risk this section guarded against does not arise: there is no review of the implementer's own work to rubber-stamp. The SAME crafter instance that ran `A_GREEN` runs the commit-only `D_REFACTOR_COMMIT`.

Preserved for audit context (historical rationale, no longer enforced):

1. ~~Emit the D_REFACTOR_COMMIT dispatch event with `agent_instance_id` distinct from A_GREEN.~~
2. ~~Pre-flight: refuse a D_REFACTOR_COMMIT dispatch sharing `agent_instance_id` with the A_GREEN entry in `execution-log.json`.~~
3. Original rationale (2026-05-19): review independence — refactor by original implementer rubber-stamps their own bias. No longer applicable once the phase carries no refactor/review.

## Verdict-Hash Trailer (D_REFACTOR_COMMIT review → commit)

Plan v3 §8. The D_REFACTOR_COMMIT reviewer verdict pairs with a `Reviewed-by: <agent>:<verdict-hash>` trailer; the D_REFACTOR_COMMIT commit embeds it verbatim. The verdict-hash is the keyless content seal produced by `des.domain.at_review_signing.canonical_at_review_json`. Verification: `src/des/cli/verify_commit_trailers.py` audits the slice's ledger record (exit 45 on refusal).

## Telemetry per Phase Boundary

Each canonical phase (A_GREEN → C_REVIEWER_AUDIT → D_REFACTOR_COMMIT) emits JSONL at PhaseEntered + PhaseCompleted to `nWave/telemetry/wave-time-token-telemetry/pilot/{feature_id}.jsonl`:

```json
{
  "telemetry_schema_version": "1.0.0",
  "source": "des_sequencer",
  "event": "PhaseEntered",
  "feature": "{feature_id}",
  "phase": "C_REVIEWER_AUDIT",
  "wall_clock_s": 42.3,
  "token_cost": 8421,
  "reviewer_findings": 3,
  "cycle_n": 1,
  "verdict_hash": "ab12cd34...",
  "timestamp": "2026-05-19T18:42:13Z"
}
```

`reviewer_findings`, `cycle_n`, `verdict_hash` null outside their phases. Validator: `scripts/validation/validate_atdd_pure_telemetry.py`.

## Post-Commit (D_REFACTOR_COMMIT): Falsifier-Gate Hook

After the D_REFACTOR_COMMIT commit completes, invoke `python scripts/automation/atdd_pure_falsifier_gate.py` (plan v3 §4.5 Phase 5 deliverable):

- Reads N=3 latest pilot JSONL records.
- ANY breach (median wall-clock > 1.3× target | findings median > 12 | defect rate > 2× classic | Phase D cycle rate median ≥ 2.0) → patch `.nwave/config.yaml:workflow.mode = classic`, emit `FalsifierGateTripped`, exit 42. <!-- mode-ref-ok -->
- Otherwise → emit `FalsifierGateHealthy`, exit 0.

Exit 42 blocks subsequent CI release steps; operator review required before next pilot feature.
