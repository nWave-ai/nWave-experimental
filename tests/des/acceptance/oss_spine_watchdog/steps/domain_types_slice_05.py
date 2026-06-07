"""Domain types for oss-spine-watchdog slice-05 (collection-precheck gate-wiring).

Mandate-12 criterion 1 (SSOT via Types + Services + DSL): every domain noun the
slice-05 .feature scenarios speak lives here as a typed enum or frozen dataclass.
Step methods + composition consume these typed parameters; raw `str` parameters
are avoided wherever a domain enum exists.

Slice-05 is the LAST slice — it closes BLOCKER-1 of the deep feature-end review
(`a360758f`, 2026-06-05): slice-01 shipped the collection-precheck PROBE
(`run_contract_gate --collect-only`, the worker-side `crashing_module` capture) but
the G_COMMIT exit-gate handler NEVER CALLS it. grep `collect-only|precheck` in
`subagent_stop_handler.py` `_handle_g_commit_exit_gate` = 0. So on the LIVE spine a
real collection crash STILL flows into E2 (`run_contract_gate --verify-gate-scope`)
→ exit non-zero → the block branch → `{decision:block}` → the harness RE-FIRES the
agent forever — the exact #68 loop the walking-skeleton (slice-01) exists to kill is
NOT killed on the production hot path. "Walking-skeleton value half-delivered."

Slice-05 EXTENDs `_handle_g_commit_exit_gate` to run the no-skip collection precheck
(`run_contract_gate --collect-only`, NWAVE_FRESHNESS-cleared per D-7) BEFORE the E2
step via `_run_gate_subprocess`; on a collection crash (exit 2) it TERMINATES through
the slice-04 shared helper `_emit_terminating_indeterminate` (a durable terminal
ledger record + loud stderr + non-block exit 0), short-circuiting BEFORE E2 can
re-block opaquely — instead of re-firing.

── DRIVING PORT (Mandate-13, invariant 1+2): real hook subprocess (the AT-tier fix) ──
This is the EXACT defect BLOCKER-1 is about, so the AT-tier is load-bearing. The
slice-01 ATs drove the `--collect-only` probe DIRECTLY (the wrong tier — they asserted
the PROBE names a module, never that the GATE INVOKES the probe). Slice-05 drives the
REAL `handle_subagent_stop` G_COMMIT exit-gate hook over its JSON stdin protocol AS A
SUBPROCESS — exactly as the shipped, proven slice-02 (`composition_slice_02.py`) and
slice-04 (`composition_slice_04.py`) siblings drive it:

    python -c "... from ...subagent_stop_handler import handle_subagent_stop;
               sys.exit(handle_subagent_stop())"

against a real git repo under tmp_path whose COMMITTED contract suite crashes on
collection. The OBSERVABLE is that the REAL GATE terminates (a durable terminal
record + a non-block return), NOT that the probe in isolation names a module.
`AtCompletionLedger` is imported ONLY to RE-READ the durable terminal/block records
the assertions observe (the S2 tolerable-variant — observe observable state through
the production reader); it is the observable port surface, NEVER the SUT.

── THE ANTI-VACUITY DISCRIMINATOR (the divergence pair) ──
  COLLECTION_CRASHES — a committed contract suite with an import-time-crashing test
    module. The real collection precheck returns exit 2 → the gate TERMINATES (a
    durable terminal record + non-block, no re-fire). RED today (no precheck wiring →
    the crash flows into E2 → the block branch → `{decision:block}` re-fire →
    `terminated` is False / `blocked` is True). This is the BLOCKER-1 pin.
  COLLECTS_CLEAN — a committed contract suite that collects cleanly (whose commit
    still fails E1/E2 for an ORDINARY reason). The collection precheck does NOT fire
    the collection-crash terminal — the gate proceeds to E1/E2 and blocks NORMALLY.
    GREEN today (no precheck wiring → the ordinary block path is unchanged) and MUST
    STAY GREEN post-GREEN: a precheck that fired the collection terminal on EVERY
    commit (collection-blind) would wrongly terminate this clean-collecting commit.
    The discriminator pins that the terminal fires on a COLLECTION CRASH, not on any
    gate failure — without it, a gate that always-terminates would vacuously pass the
    crash pin.

A precheck that NEVER fires the collection terminal fails AT-01/AT-02 (the crash is
not terminated → re-fire loop survives). A precheck that ALWAYS fires it (collection-
blind) fails AT-03 (a clean commit is wrongly collection-terminated). The two cases
bracket the contract: the terminal is keyed on COLLECTION-CRASH (exit 2), nothing else.

── Mechanical assertion (Mandate-13 invariant 5) ──
Python + git + filesystem only (the hook resolves a real repo + the real precheck
collects a real synthetic suite + reads/writes a real ledger JSONL, as in production),
cross-OS. The terminal is exit 0 with NO `{decision:block}` body (DESIGN OQ-5 / DEVOPS
DV-5: loud via stderr + durable ledger record, NEVER a non-zero exit). The
durable-record observable is a re-read count delta on the ledger's GENUINE-terminal
records — a port-exposed observable, never an internal field. The crashing test
module is isolated to the tmp_path synthetic repo so it cannot poison the real test
tree's collection (DEVOPS CI constraint: reproduce the SHAPE, not the BLAST RADIUS).

Layer 3/4 (real git repo + real ledger JSONL + real collection-precheck subprocess +
real hook subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io because
the driven set includes a real filesystem adapter + a real git subprocess + a real
hook subprocess → NOT PBT; Mandate 11 — sad paths enumerated explicitly). No PBT
machinery imported.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import NewType


# A kebab-case feature identifier (e.g. "oss-spine-watchdog-demo").
FeatureId = NewType("FeatureId", str)

# A carpaccio slice identifier (e.g. "slice-NN").
SliceId = NewType("SliceId", str)


class SuiteCollectability(str, Enum):
    """Whether the committed contract suite the G_COMMIT gate inspects collects.

    The slice-05 precheck-wiring fix runs a no-skip collection precheck BEFORE E2 and
    terminates the gate on a collection crash. This enum names the two committed-tree
    topologies the AT builds to prove the wiring — the discriminator between
    "terminate" (crash) and "proceed to the ordinary block path" (clean).

    COLLECTION_CRASHES — the committed contract suite carries an import-time-crashing
        test module (a broken import). pytest collection aborts (exit 2 from the real
        `run_contract_gate --collect-only` precheck). The gate MUST TERMINATE: a
        durable terminal record + a non-block return, no re-fire (BLOCKER-1 pin, RED
        today — the precheck is not wired, so the crash flows into E2 → block →
        re-fire).

    COLLECTS_CLEAN — the committed contract suite collects cleanly; the commit still
        fails E1/E2 for an ordinary reason (no `Gate-Scope:` trailer → E2 exit 1).
        The collection precheck does NOT fire the collection terminal — the gate
        proceeds to the ORDINARY block path. The anti-vacuity discriminator: GREEN
        today and MUST STAY GREEN — a collection-blind precheck that terminated every
        commit would wrongly collection-terminate this clean commit.
    """

    COLLECTION_CRASHES = "the committed contract suite crashes on collection"
    COLLECTS_CLEAN = "the committed contract suite collects cleanly"


@dataclass(frozen=True)
class GateOutcome:
    """Observable outcome of ONE real G_COMMIT exit-gate hook invocation (slice-05).

    The driving port is the real `handle_subagent_stop` G_COMMIT exit-gate hook
    subprocess (Layer-3/4 wiring). The universe entries `assert_state_delta` tracks
    are built from THIS dataclass's port-exposed fields. Internal plumbing (Popen
    handle, env dict, the transcript JSONL bytes, the raw ledger file path) is NEVER
    in the universe (Mandate 8 — port-exposed observables only).

    - `terminated` — True iff a NEW durable GENUINE-terminal record (a collection-
                     crash terminal routed through the slice-04 shared
                     `_emit_terminating_indeterminate`) was appended to the
                     AT-completion ledger between the before-snapshot and the
                     after-snapshot (a re-read count delta over the genuine-terminal
                     event set, EXCLUDING the non-terminal `SliceCommitBlocked`
                     re-fire record). The durable half of "loud → terminating",
                     readable post-mortem by a not-watching operator. This is the
                     BLOCKER-1 pin: RED today for COLLECTION_CRASHES (the precheck is
                     not wired → the crash flows into E2 → a `SliceCommitBlocked`
                     re-fire record is written, NOT a terminal → delta 0), GREEN once
                     the precheck wiring terminates the gate on exit 2.
    - `blocked`    — True iff the hook stdout carried a `{decision:block}` body. The
                     collection terminal is NON-block (DESIGN OQ-5 / DV-5), so a
                     terminated outcome is NOT blocked — the harness reaches a Stop
                     rather than re-firing. RED today for COLLECTION_CRASHES (`blocked`
                     is True — the crash re-blocks). For COLLECTS_CLEAN `blocked` is
                     True BOTH today and post-GREEN (the ordinary block path is
                     unchanged — the discriminator pins the gate does NOT terminate a
                     clean-collecting commit).
    """

    terminated: bool
    blocked: bool


# --- Phrase -> typed-value lookup tables (Mandate-12 DSL emergence) -------

SUITE_COLLECTABILITY_BY_PHRASE: dict[str, SuiteCollectability] = {
    k.value: k for k in SuiteCollectability
}


__all__ = [
    "SUITE_COLLECTABILITY_BY_PHRASE",
    "FeatureId",
    "GateOutcome",
    "SliceId",
    "SuiteCollectability",
]
