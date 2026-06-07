"""U1 -- the carpaccio entry gate as a `PreToolUse` intercept.

slice-01 of F-DES-ATDD-PURE-HOOK-GATES (U1 -- ADR-030 D1) + D4 Phase 3 slice-02
refactor (per `docs/analysis/d4-schema-spec-2026-05-26.md` § 5 Phase 3).

The carpaccio entry gate, while correct as a CLI (`scripts/cli/
carpaccio_slice_gate.py`), is *prose-invoked* -- an orchestrating LLM can
silently skip it. U1 moves it to a genuinely unskippable `PreToolUse` intercept:
`handle_pre_tool_use` calls `evaluate_atdd_pure_dispatch` for every Task/Agent
dispatch, and the carpaccio gate runs whether or not the orchestrator chose to
run it.

The intercept is a near-pure decision function -- it parses the dispatch
markers, runs the M3 positive-recognition classification, the M8
carpaccio-order check against the U3 AT-completion ledger, then delegates the
carpaccio CLI invocation to the **flavor dispatcher** reading
`nWave/flavors/atdd_pure.yaml` (D4 Phase 3 slice-02). The only injected I/O is
the `carpaccio_runner` (the carpaccio CLI subprocess) -- defaulted to the real
subprocess invocation, substitutable in tests.

D4 Phase 3 slice-02 contract (INV-12 future workflow change = reconfiguration,
INV-4 workflow IS data): the carpaccio gate invocation is now sourced from
`nWave/flavors/atdd_pure.yaml` `lifecycle_events.dispatch.pre` composition.
Reordering / swapping gates on the `dispatch.pre` event is a YAML edit -- zero
code change to this file. The carpaccio_runner is adapted to the dispatcher's
`gate_invoker` Port so the wrapping is layout-independent.

The U1 contract (feature-delta DESIGN/U1):

  * **M3 positive recognition** (in-house, NOT delegated -- INV-1 atomic
    responsibility: M3 is about marker parsing, not gate composition).
    `DES-MODE:atdd_pure` absent => not an atdd_pure dispatch => `passthrough`
    (the classic path is unchanged). Present + valid phase + valid slice =>
    the atdd_pure branch. Present + an incomplete / malformed remainder =>
    BLOCK `AtddPureMarkerSetIncomplete` -- never a fall-through.
  * **carpaccio CLI invocation** (DELEGATED to flavor dispatcher).
    Keyed on `DES-PHASE:A_GREEN_ATS`; other phases pass through the atdd_pure
    branch without a carpaccio invocation. The subprocess carries an explicit
    timeout strictly below the Claude Code `PreToolUse` hook-execution
    ceiling (M2). A timeout / signal-kill blocks identically to a non-zero
    exit.
  * **M8 carpaccio-order check** (in-house, NOT delegated -- the dispatcher
    YAML for `dispatch.pre` exposes only `carpaccio-slice-gate`; the order
    invariant lives at the intercept layer for now). Entering `slice-N` with
    N > 1 blocks `CarpaccioSliceOutOfOrder` when `slice-(N-1)` carries no
    terminal `SliceCommitVerified` record in the U3 ledger.
  * **M1 handler-exception fail-closed.** Any exception raised inside the U1
    branch is surfaced by `handle_pre_tool_use` as an `AtddPureHookInternalError`
    block.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import (
    AtCompletionLedger,
    LedgerIntegrityViolation,
)
from des.application.flavor_dispatcher import dispatch_lifecycle_event
from des.application.slice_at_completeness import missing_at_files
from des.domain.atdd_pure_phases import (
    CARPACCIO_ENTRY_PHASES as _CARPACCIO_ENTRY_PHASES,
)
from des.domain.des_marker_parser import (
    DesMarkerParser,
    DesMarkers,
    atdd_pure_missing_marker,
    classify_atdd_pure_dispatch,
)
from des.domain.slice_id_trailer import extract_slice_ids
from des.runtime.interpreter import python_for


# --- handler-budget ceiling (M2) --------------------------------------------
#
# The carpaccio-CLI subprocess timeout MUST be set strictly below the Claude
# Code `PreToolUse` hook-execution timeout. Both are named constants here.
CLAUDE_CODE_PRETOOLUSE_HOOK_TIMEOUT_SECONDS = 60
CARPACCIO_GATE_SUBPROCESS_TIMEOUT_SECONDS = 20

# The predecessor-backfill subprocess (`run_contract_gate --verify-gate-scope`)
# is a DELEGATED subprocess that recomputes a fresh whole-tree collect-only
# digest -- empirically ~11s, well under this ceiling. It runs at the 120s
# delegated-subprocess tier, NOT the 20s carpaccio sub-gate budget: the
# verify-gate-scope collect is a heavier, distinct operation than the in-house
# carpaccio CLI sub-gate.
BACKFILL_GATE_SUBPROCESS_TIMEOUT_SECONDS = 120

# The verify-gate-scope CLI the in-gate backfill delegates E2-evidence to.
_CONTRACT_GATE_MODULE = "des.cli.run_contract_gate"

# The atdd_pure phases U1 keys the carpaccio gate on — imported from the
# phase-identity SSOT (``atdd_pure_phases.CARPACCIO_ENTRY_PHASES``). The
# canonical A_GREEN entry phase plus the legacy A_GREEN_ATS replay word; the
# membership is single-sourced in the enum module, not restated here.

# F-11 (atdd-pure-dogfooding-friction-2026-05-20.md): the carpaccio gate is an
# importable `des.cli` module, so U1 runs it as a `python_for(None) -m` module
# subprocess -- layout-independent.
_CARPACCIO_GATE_MODULE = "des.cli.carpaccio_slice_gate"

# slice-05: the verify-readiness-pre-dispatch gate is an importable `des.cli`
# module (shipped slice-03), so U1 runs it the same way -- layout-independent
# `python_for(None) -m` module subprocess.
_READINESS_GATE_CLI_TARGET = "des"
_READINESS_GATE_SUBCOMMAND = "verify-readiness-pre-dispatch"
# slice-05: the readiness gate's subprocess timeout matches the carpaccio
# subprocess ceiling; both fit inside the Claude Code PreToolUse hook budget.
READINESS_GATE_SUBPROCESS_TIMEOUT_SECONDS = 20

# D4 Phase 3 slice-02 wiring: the flavor dispatcher reads workflow flavors
# from `nWave/flavors/`. Resolved the same way `des/cli/doctor.py` resolves
# `nWave/data/` (`Path(__file__).resolve().parents[N]/nWave/...`). The depth
# differs because carpaccio_intercept lives at
# src/des/adapters/drivers/hooks/, so parents[5] is the repo / install root.
_FLAVORS_DIR = Path(__file__).resolve().parents[5] / "nWave" / "flavors"

# The flavor + lifecycle-event keys this intercept dispatches on. Reordering
# / swapping gates on this event is a YAML edit to `atdd_pure.yaml`.
_ATDD_PURE_FLAVOR_ID = "atdd_pure"
_DISPATCH_PRE_EVENT_ID = "dispatch.pre"
_CARPACCIO_SLICE_GATE_ID = "carpaccio-slice-gate"
_VERIFY_READINESS_PRE_DISPATCH_GATE_ID = "verify-readiness-pre-dispatch"


# A carpaccio runner: (feature_id, entering_slice) -> (exit_code, stdout).
CarpaccioRunner = Callable[[str, str], "tuple[int, str]"]

# A readiness runner: (feature_id, entering_slice) -> (exit_code, stdout).
# Same shape as `CarpaccioRunner` -- the per-gate registry built in
# `_gate_invoker_for` looks up the runner by gate_id and delegates with the
# (feature_id, slice_id) pair extracted from the dispatcher context dict.
ReadinessRunner = Callable[[str, str], "tuple[int, str]"]


@dataclass(frozen=True)
class InterceptDecision:
    """The U1 intercept verdict for one PreToolUse dispatch.

    Attributes:
        is_block: True when the dispatch must be blocked.
        is_atdd_pure: True when the dispatch was recognised as atdd_pure (a
            block on a defective marker set is still an atdd_pure dispatch).
        event: The structured event name for the block payload, or None when
            the dispatch is allowed / passed through.
        reason: A human-readable block reason, or None.
    """

    is_block: bool
    is_atdd_pure: bool
    event: str | None = None
    reason: str | None = None

    @classmethod
    def passthrough(cls) -> InterceptDecision:
        """Not an atdd_pure dispatch -- the classic path is unchanged."""
        return cls(is_block=False, is_atdd_pure=False)

    @classmethod
    def allow(cls) -> InterceptDecision:
        """A recognised atdd_pure dispatch the U1 gate cleared."""
        return cls(is_block=False, is_atdd_pure=True)

    @classmethod
    def block(cls, event: str, reason: str) -> InterceptDecision:
        """A recognised atdd_pure dispatch the U1 gate rejected."""
        return cls(is_block=True, is_atdd_pure=True, event=event, reason=reason)


def _real_carpaccio_runner(project_root: Path) -> CarpaccioRunner:
    """Build the real carpaccio runner bound to ``project_root``.

    F-11: the gate runs as a `python_for(None) -m` module subprocess -- a
    layout-independent invocation of the `des.cli` gate module that ships with
    the `des` package. A timeout / signal-kill is surfaced as a non-zero exit
    so the caller blocks identically to an explicit gate rejection (ADR-030 D5
    fail-stuck).
    """

    def _run(feature_id: str, entering_slice: str) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                [
                    python_for(None),
                    "-m",
                    _CARPACCIO_GATE_MODULE,
                    "--feature-id",
                    feature_id,
                    "--entering-slice",
                    entering_slice,
                    "--repo-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
                timeout=CARPACCIO_GATE_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return 124, json.dumps(
                {
                    "event": "GateInvocationTimeout",
                    "gate": "carpaccio_slice_gate",
                    "entering_slice": entering_slice,
                }
            )
        return completed.returncode, completed.stdout

    return _run


def _real_readiness_runner(project_root: Path) -> ReadinessRunner:
    """Build the real readiness runner bound to ``project_root`` (slice-05).

    Mirrors `_real_carpaccio_runner`: runs the slice-03 verify-readiness-pre-
    dispatch CLI as `python_for(None) -m des verify-readiness-pre-dispatch ...`
    subprocess. A timeout / signal-kill is surfaced as a non-zero exit so the
    caller blocks identically to an explicit readiness rejection.
    """

    def _run(feature_id: str, entering_slice: str) -> tuple[int, str]:
        try:
            completed = subprocess.run(
                [
                    python_for(None),
                    "-m",
                    _READINESS_GATE_CLI_TARGET,
                    _READINESS_GATE_SUBCOMMAND,
                    "--feature-id",
                    feature_id,
                    "--slice-id",
                    entering_slice,
                    "--repo-root",
                    str(project_root),
                ],
                capture_output=True,
                text=True,
                timeout=READINESS_GATE_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return 124, json.dumps(
                {
                    "event": "GateInvocationTimeout",
                    "gate": "verify_readiness_pre_dispatch",
                    "entering_slice": entering_slice,
                }
            )
        return completed.returncode, completed.stdout

    return _run


def _slice_number(slice_id: str) -> int:
    """The integer N from a `slice-NN` id."""
    return int(slice_id.split("-", 1)[1])


def _predecessor_slice(slice_id: str) -> str:
    """The `slice-(N-1)` id for an entering `slice-N`, preserving padding."""
    digits = slice_id.split("-", 1)[1]
    return f"slice-{_slice_number(slice_id) - 1:0{len(digits)}d}"


def _carpaccio_order_block(
    markers: DesMarkers, feature_id: str, project_root: Path
) -> InterceptDecision | None:
    """The M8 carpaccio-order check -- block if the predecessor is unshipped.

    The dispatcher YAML for `dispatch.pre` exposes only the
    `carpaccio-slice-gate`; the order invariant lives at the intercept layer
    until a future flavor adds an explicit `carpaccio-order-gate` to the
    composition. Returns a block decision when the order is violated, or
    None when the order is satisfied (or there is no predecessor).
    """
    slice_id = markers.slice_id
    assert slice_id is not None  # guaranteed by the M3 valid-marker classification
    if _slice_number(slice_id) <= 1:
        return None

    predecessor = _predecessor_slice(slice_id)
    ledger = AtCompletionLedger(feature_id, project_root)
    if predecessor in ledger.verified_slices():
        return None

    # The predecessor has no SliceCommitVerified record. Before blocking,
    # attempt an in-gate auto-backfill: a predecessor that was committed on
    # disk but never recorded (the F-CRAFTER-RELIES-ON-SUBAGENTSTOP-FOR-
    # SLICECOMMITVERIFIED friction) is verify-then-recorded automatically so
    # the successor is no longer blocked out of order for a missing record.
    _attempt_predecessor_backfill(predecessor, feature_id, project_root)
    if predecessor in ledger.verified_slices():
        return None

    return InterceptDecision.block(
        event="CarpaccioSliceOutOfOrder",
        reason=(
            f"carpaccio slice {slice_id} entered out of order: its predecessor "
            f"{predecessor} has no SliceCommitVerified ledger record -- deliver "
            "carpaccio slices in order"
        ),
    )


def _predecessor_commit_sha(repo: Path, predecessor: str) -> str | None:
    """The SHA of the most recent commit carrying ``predecessor``'s Slice-Id.

    Searches the commit log for a `Slice-Id: <predecessor>` trailer (the F-07
    multi-trailer shape lists each slice on its own line). Returns None when no
    such commit exists on disk -- the backfill has no predecessor commit to
    verify against and fails closed by leaving the record absent.
    """
    try:
        completed = subprocess.run(
            [
                "git",
                "log",
                "--format=%H%x00%B%x1e",
                "--grep",
                f"^Slice-Id: *{predecessor}$",
                "--extended-regexp",
            ],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    for entry in completed.stdout.split("\x1e"):
        sha, _, message = entry.strip().partition("\x00")
        if sha and predecessor in extract_slice_ids(message):
            return sha
    return None


def _verify_gate_scope(repo: Path, commit: str) -> bool:
    """Run E2-evidence -- `run_contract_gate --commit --verify-gate-scope`.

    Recomputes a fresh whole-tree collect-only digest and compares it to the
    predecessor commit's `Gate-Scope:` trailer. Exit 0 (`GateScopeVerified`)
    ONLY when the trailer is present AND matches; any non-zero (absent / stale
    digest) or a subprocess timeout returns False so the backfill fails closed
    (no false-allow). Runs at the delegated-subprocess timeout tier.
    """
    try:
        completed = subprocess.run(
            [
                python_for(None),
                "-m",
                _CONTRACT_GATE_MODULE,
                "--verify-gate-scope",
                "--commit",
                commit,
                "--repo",
                str(repo),
            ],
            capture_output=True,
            text=True,
            timeout=BACKFILL_GATE_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False
    return completed.returncode == 0


def _record_slice_commit_verified(
    feature_id: str, predecessor: str, project_root: Path
) -> None:
    """Append the predecessor's `SliceCommitVerified` record (the backfill write).

    REUSES the M7 ledger writer (`AtCompletionLedger.append_gate_event`) -- the
    same record path `verify_slice_commit_completeness` uses -- so the appended
    record carries the gap-free `seq` + `record_hash` the carpaccio chain reads.
    The write is the single state mutation of the auto-backfill.
    """
    AtCompletionLedger(feature_id, project_root).append_gate_event(
        event="SliceCommitVerified", slice_id=predecessor
    )


def _attempt_predecessor_backfill(
    predecessor: str, feature_id: str, project_root: Path
) -> None:
    """Verify-then-record a committed-but-unrecorded predecessor in the entry gate.

    The auto-backfill happy path: when the predecessor has a commit on disk but
    no `SliceCommitVerified` ledger record, verify it in-gate and record it so
    the successor is allowed. The verify-then-record is fail-closed BY
    CONSTRUCTION -- the record is appended IFF every check passes:

      * E1 (in-gate, fast): the predecessor commit carries the slice's `.feature`
        AT files (REUSES `missing_at_files`, no test execution).
      * E2-evidence by digest: `run_contract_gate --verify-gate-scope` against
        the predecessor commit (digest VERIFICATION, not suite execution).

    On a missing predecessor commit, an E1 deficiency, a digest absent/stale, or
    a subprocess timeout, NOTHING is appended -- the caller re-reads
    `verified_slices()`, finds the predecessor still absent, and the block
    stands (no false-allow).
    """
    commit_sha = _predecessor_commit_sha(project_root, predecessor)
    if commit_sha is None:
        return
    if missing_at_files(project_root, commit_sha, predecessor, feature_id):
        return
    if not _verify_gate_scope(project_root, commit_sha):
        return
    _record_slice_commit_verified(feature_id, predecessor, project_root)


def _gate_invoker_for(
    carpaccio_runner: CarpaccioRunner,
    readiness_runner: ReadinessRunner | None = None,
) -> Callable[[str, dict[str, str]], tuple[int, str]]:
    """Adapt the per-gate runners into the dispatcher's `gate_invoker` Port.

    The dispatcher invokes `gate_invoker(gate_id, context_dict)`; this helper
    builds a 2-entry registry from the injected runners (keyed by gate_id) +
    delegates the (feature_id, slice_id) extraction uniformly. Adding a third
    gate to `dispatch.pre` requires ONLY a YAML edit (the gate enters the
    composition) plus a new runner kwarg on this intercept's public
    `evaluate_atdd_pure_dispatch` -- the dispatch loop itself never needs
    edits (INV-2 composable, INV-12 future workflow change = reconfiguration).

    When `readiness_runner` is None (slice-02 backward-compat call shape) the
    registry omits the readiness entry; the dispatcher then surfaces
    `UnknownGateOnDispatchPre` if the YAML still references it (fail-closed
    by design -- the same shape today's intercept emits).
    """
    registry: dict[str, Callable[[str, str], tuple[int, str]]] = {
        _CARPACCIO_SLICE_GATE_ID: carpaccio_runner,
    }
    if readiness_runner is not None:
        registry[_VERIFY_READINESS_PRE_DISPATCH_GATE_ID] = readiness_runner

    def _invoke(gate_id: str, context: dict[str, str]) -> tuple[int, str]:
        runner = registry.get(gate_id)
        if runner is None:
            return 1, json.dumps(
                {
                    "event": "UnknownGateOnDispatchPre",
                    "gate_id": gate_id,
                }
            )
        return runner(context["feature_id"], context["slice_id"])

    return _invoke


def evaluate_atdd_pure_dispatch(
    *,
    prompt: str,
    feature_id: str,
    project_root: Path,
    carpaccio_runner: CarpaccioRunner | None = None,
    readiness_runner: ReadinessRunner | None = None,
) -> InterceptDecision:
    """Evaluate the U1 carpaccio intercept for one PreToolUse dispatch.

    The single decision function `handle_pre_tool_use` delegates to. The
    carpaccio + readiness CLI invocations are sourced from
    `nWave/flavors/atdd_pure.yaml` via the flavor dispatcher (D4 Phase 3
    slice-02 + slice-05); the injected per-gate runners are wrapped into
    the dispatcher's `gate_invoker` Port via a 2-entry registry.

    The `readiness_runner` parameter is ADDITIVE on top of the slice-02 frozen
    signature -- defaulting to None preserves the slice-02 single-gate call
    shape (AT-4 regression-pin). When provided, the flavor's dispatch.pre
    composition can wire `verify-readiness-pre-dispatch` ahead of
    `carpaccio-slice-gate` as a YAML edit (INV-12).

    Returns an `InterceptDecision`:
      * `passthrough()` -- not an atdd_pure dispatch; the classic path runs.
      * `allow()`       -- a recognised atdd_pure dispatch the U1 gate cleared.
      * `block(...)`    -- a recognised atdd_pure dispatch the gate rejected.

    Note on the M1 handler-exception contract: this function does NOT swallow
    its own exceptions. `handle_pre_tool_use` wraps the call in a try/except and
    surfaces any exception as an `AtddPureHookInternalError` block.
    """
    carpaccio = carpaccio_runner or _real_carpaccio_runner(project_root)
    readiness = readiness_runner or _real_readiness_runner(project_root)

    markers = DesMarkerParser().parse(prompt)
    classification = classify_atdd_pure_dispatch(markers)

    # M3 positive recognition (in-house -- INV-1 atomic).
    if classification == "absent":
        return InterceptDecision.passthrough()
    if classification == "defective":
        missing = atdd_pure_missing_marker(markers) or "des-mode"
        return InterceptDecision.block(
            event="AtddPureMarkerSetIncomplete",
            reason=(
                f"atdd_pure dispatch prompt is missing a well-formed {missing} "
                "marker -- the dispatch prompt must carry all three markers "
                "(/nw-deliver rendering defect)"
            ),
        )

    # Recognised, valid atdd_pure dispatch. The carpaccio gate keys on the
    # canonical A_GREEN entry phase (the legacy A_GREEN_ATS word replays onto
    # it); other phases pass through without a carpaccio invocation.
    if markers.atdd_pure_phase not in _CARPACCIO_ENTRY_PHASES:
        return InterceptDecision.allow()

    # M8 carpaccio-order check (reads the U3 ledger; fail-closed on corruption).
    order_block = _carpaccio_order_block(markers, feature_id, project_root)
    if order_block is not None:
        return order_block

    # Carpaccio gate invocation -- delegated to the flavor dispatcher reading
    # `nWave/flavors/atdd_pure.yaml`. Reordering / swapping gates on
    # `dispatch.pre` is now a YAML edit (INV-12 future workflow change =
    # reconfiguration).
    slice_id = markers.slice_id
    assert slice_id is not None  # guaranteed by the M3 valid-marker classification
    composition_result = dispatch_lifecycle_event(
        event_id=_DISPATCH_PRE_EVENT_ID,
        flavor_id=_ATDD_PURE_FLAVOR_ID,
        context={
            "feature_id": feature_id,
            "slice_id": slice_id,
            "repo_root": str(project_root),
        },
        flavors_dir=_FLAVORS_DIR,
        gate_invoker=_gate_invoker_for(carpaccio, readiness),
    )

    return _decision_from_composition(
        composition_result, feature_id, slice_id, project_root
    )


def _decision_from_composition(
    result: object, feature_id: str, slice_id: str, project_root: Path
) -> InterceptDecision:
    """Map a `CompositionResult` to an `InterceptDecision` + emit ledger record.

    Preserves the pre-slice-02 audit contract per gate:
      * carpaccio success -- emit `CarpaccioGateCleared`, allow / continue.
      * carpaccio failure -- emit `CarpaccioGateRejected`, block.
      * readiness failure -- emit `ReadinessGateRejected`, block (slice-05).
      * empty composition -- allow (no gates fired).

    Composition halts on the first blocking gate; the halted blocking_gate_id
    determines the block event name. When no gate halts and every gate
    cleared, the dispatch is allowed (the carpaccio cleared event is emitted
    as today's audit pin).

    Each ledger emission is fail-OPEN on the audit write -- the gate verdict
    already stands (mirrors U2 `_emit_g_commit_ledger_event` pattern).
    """
    # CompositionResult has `gate_results: list[GateInvocationResult]` +
    # `halted` + `blocking_gate_id`. The dispatch.pre composition may carry
    # one or more gates (slice-02 single carpaccio; slice-05 readiness +
    # carpaccio); the block-event name is routed via blocking_gate_id.
    gate_results = result.gate_results  # type: ignore[attr-defined]
    if not gate_results:
        return InterceptDecision.allow()

    blocking_gate_id = result.blocking_gate_id  # type: ignore[attr-defined]
    if blocking_gate_id is None:
        # Every gate cleared; preserve the carpaccio-cleared audit pin when
        # the carpaccio gate was in the composition (slice-02 + slice-05
        # both wire it). The pin is conditional on its presence so future
        # flavors omitting carpaccio do not emit a misleading record.
        for gate_result in gate_results:
            if gate_result.gate_id == _CARPACCIO_SLICE_GATE_ID:
                _emit_carpaccio_gate_event(
                    "CarpaccioGateCleared", feature_id, slice_id, project_root
                )
                break
        return InterceptDecision.allow()

    blocking_result = next(gr for gr in gate_results if gr.gate_id == blocking_gate_id)
    if blocking_gate_id == _VERIFY_READINESS_PRE_DISPATCH_GATE_ID:
        _emit_carpaccio_gate_event(
            "ReadinessGateRejected", feature_id, slice_id, project_root
        )
        return InterceptDecision.block(
            event="ReadinessGateRejected",
            reason=(
                f"readiness gate rejected {slice_id} (exit "
                f"{blocking_result.exit_code}): "
                f"{_carpaccio_reason(blocking_result.stdout)}"
            ),
        )

    _emit_carpaccio_gate_event(
        "CarpaccioGateRejected", feature_id, slice_id, project_root
    )
    return InterceptDecision.block(
        event="CarpaccioGateRejected",
        reason=(
            f"carpaccio gate rejected {slice_id} (exit "
            f"{blocking_result.exit_code}): "
            f"{_carpaccio_reason(blocking_result.stdout)}"
        ),
    )


def _emit_carpaccio_gate_event(
    event: str, feature_id: str, slice_id: str, project_root: Path
) -> None:
    """Append a `CarpaccioGateCleared` / `CarpaccioGateRejected` ledger record.

    F2 (M4): the U1 intercept records one carpaccio gate event per dispatch so
    `reconcile_dispatch_count` is meaningful. The emission is **fail-OPEN on the
    audit write** -- a ledger-write failure is swallowed so it can never change
    the gate decision.
    """
    try:
        AtCompletionLedger(feature_id, project_root).append_gate_event(
            event=event, slice_id=slice_id
        )
    except Exception:
        # Fail-open: the gate verdict already stands; ledger emission is audit.
        pass


def intercept_atdd_pure_dispatch(
    *,
    prompt: str,
    feature_id: str,
    project_root: Path,
    carpaccio_runner: CarpaccioRunner | None = None,
    readiness_runner: ReadinessRunner | None = None,
) -> InterceptDecision:
    """The M1 fail-closed U1 intercept driving port.

    Wraps `evaluate_atdd_pure_dispatch` in the M1 try/except: ANY exception
    raised inside the U1 branch is surfaced as an `AtddPureHookInternalError`
    block, never re-raised. The `readiness_runner` parameter is additive on
    the slice-02 frozen signature (slice-05); callers passing only
    `carpaccio_runner` retain slice-02 behaviour.
    """
    try:
        return evaluate_atdd_pure_dispatch(
            prompt=prompt,
            feature_id=feature_id,
            project_root=project_root,
            carpaccio_runner=carpaccio_runner,
            readiness_runner=readiness_runner,
        )
    except Exception as exc:
        return InterceptDecision.block(
            event="AtddPureHookInternalError",
            reason=f"U1 carpaccio intercept raised: {exc!s}",
        )


def _carpaccio_reason(stdout: str) -> str:
    """Extract a human-readable reason from the carpaccio CLI JSON output."""
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return stdout.strip() or "no gate output"
    if isinstance(payload, dict):
        return str(payload.get("event") or payload.get("error") or stdout.strip())
    return stdout.strip() or "no gate output"


# `LedgerIntegrityViolation` is re-exported so callers can catch the ledger
# fail-closed exception by name without importing the ledger module directly.
__all__ = [
    "CARPACCIO_GATE_SUBPROCESS_TIMEOUT_SECONDS",
    "CLAUDE_CODE_PRETOOLUSE_HOOK_TIMEOUT_SECONDS",
    "InterceptDecision",
    "LedgerIntegrityViolation",
    "evaluate_atdd_pure_dispatch",
    "intercept_atdd_pure_dispatch",
]
