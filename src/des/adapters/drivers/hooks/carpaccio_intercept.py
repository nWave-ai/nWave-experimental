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
    `DES-MODE:atdd_pure` absent => unresolved dispatch => BLOCK. Present + valid phase + valid slice =>
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
import re
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
from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from des.domain.des_marker_parser import (
    BOOTSTRAPPABLE_GATES,
    DesMarkerParser,
    DesMarkers,
    atdd_pure_missing_marker,
    classify_atdd_pure_dispatch,
    classify_bootstrap,
)
from des.domain.feature_delta_source import (
    FEATURE_DELTA_SECTION_MISSING,
    FEATURE_DELTA_UNDECODABLE,
)
from des.domain.slice_id_trailer import extract_slice_ids
from des.runtime.interpreter import des_spawn


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

# f-nonbypassable-attestation slice-05 (DDD-8): the wave-dispatch guard gate is
# an importable `des.cli` module (shipped slice-05), run the same way -- a
# layout-independent `python_for(None) -m des verify-wave-dispatch` subprocess.
_WAVE_DISPATCH_GATE_CLI_TARGET = "des"
_WAVE_DISPATCH_GATE_SUBCOMMAND = "verify-wave-dispatch"
# slice-05: the wave-dispatch gate's subprocess timeout matches the carpaccio /
# readiness ceiling; all fit inside the Claude Code PreToolUse hook budget.
WAVE_DISPATCH_GATE_SUBPROCESS_TIMEOUT_SECONDS = 20
# The gate's BLOCK exit code (off-spine wave-owner). The gate also returns 0
# (ALLOW) and 2 (malformed input). Per DDD-8 the guard is fail-OPEN: ONLY a
# definite BLOCK (exit 1) blocks the dispatch; ALLOW, malformed input, and any
# module-absent / freshness-autoskip non-{0,1} exit fall through to ALLOW so a
# guard error never bricks the dispatch flow.
_WAVE_DISPATCH_GATE_BLOCK_EXIT_CODE = 1

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
_VERIFY_WAVE_DISPATCH_GATE_ID = "verify-wave-dispatch"

# f-design-devops-review-gate slice-03 (CT-9 / DDD-5): the DELIVER-entry
# AT-completeness BACKSTOP gate is the EXISTING completeness CLI -- an importable
# `des.cli` module, run the SAME layout-independent `python_for(None) -m des
# check-slice-at-completeness ...` subprocess as the readiness gate. Zero new
# gate logic: the runner just maps the dispatch slice context to the existing
# CLI's argv (--repo / --commit HEAD / --slice-id / --feature-id).
_CHECK_SLICE_AT_COMPLETENESS_GATE_ID = "check-slice-at-completeness"
_COMPLETENESS_GATE_CLI_TARGET = "des"
_COMPLETENESS_GATE_SUBCOMMAND = "check-slice-at-completeness"
# The completeness gate's subprocess timeout matches the carpaccio / readiness
# ceiling; all fit inside the Claude Code PreToolUse hook budget.
COMPLETENESS_GATE_SUBPROCESS_TIMEOUT_SECONDS = 20


# A carpaccio runner: (feature_id, entering_slice) -> (exit_code, stdout).
CarpaccioRunner = Callable[[str, str], "tuple[int, str]"]

# A readiness runner: (feature_id, entering_slice) -> (exit_code, stdout).
# Same shape as `CarpaccioRunner` -- the per-gate registry built in
# `_gate_invoker_for` looks up the runner by gate_id and delegates with the
# (feature_id, slice_id) pair extracted from the dispatcher context dict.
ReadinessRunner = Callable[[str, str], "tuple[int, str]"]

# A completeness runner: (feature_id, slice_id) -> (exit_code, stdout)
# (f-design-devops-review-gate slice-03, CT-9). SAME (feature_id, slice_id)
# shape as `CarpaccioRunner` / `ReadinessRunner` -- the per-gate registry in
# `_gate_invoker_for` looks it up by gate_id and delegates the same pair. The
# DELIVER-entry BACKSTOP for the EXISTING completeness CLI.
CompletenessRunner = Callable[[str, str], "tuple[int, str]"]

# A wave-dispatch runner: (subagent_type, prompt) -> (exit_code, stdout)
# (slice-05, DDD-8). DISTINCT shape from the (feature_id, slice_id) runners --
# the wave-dispatch guard keys on the dispatched agent's subagent_type + the
# dispatch prompt text (carrying the DES-WAVE marker), not the feature/slice
# pair. `_gate_invoker_for` routes the wave gate to this runner reading
# `subagent_type` + `prompt` from the dispatcher context dict. The runner
# writes the prompt to a hermetic temp FILE (the gate reads `--prompt-path`).
WaveDispatchRunner = Callable[[str, str], "tuple[int, str]"]


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
        how: A TRUE, actionable recovery step for THIS block (GDP-3), or None
            when the block site has not yet earned one. Never a generic
            placeholder -- only a cure the caller can verify is true for the
            exact cause that fired.
    """

    is_block: bool
    is_atdd_pure: bool
    event: str | None = None
    reason: str | None = None
    how: str | None = None

    @classmethod
    def allow(cls) -> InterceptDecision:
        """A recognised atdd_pure dispatch the U1 gate cleared."""
        return cls(is_block=False, is_atdd_pure=True)

    @classmethod
    def block(
        cls, event: str, reason: str, how: str | None = None
    ) -> InterceptDecision:
        """A recognised atdd_pure dispatch the U1 gate rejected."""
        return cls(
            is_block=True, is_atdd_pure=True, event=event, reason=reason, how=how
        )


def _real_carpaccio_runner(
    project_root: Path,
    at_kind: str = "gherkin",
    regression_test_file: str | None = None,
) -> CarpaccioRunner:
    """Build the real carpaccio runner bound to ``project_root``.

    F-11: the gate runs as a `python_for(None) -m` module subprocess -- a
    layout-independent invocation of the `des.cli` gate module that ships with
    the `des` package. A timeout / signal-kill is surfaced as a non-zero exit
    so the caller blocks identically to an explicit gate rejection (ADR-030 D5
    fail-stuck).

    fix-carpaccio-intercept-honors-at-kind (ADD-not-mutate, template-identical
    to the RC4-b `_real_readiness_runner` `lane` closure): when ``at_kind`` is
    ``pytest-regression`` the closure appends ``--at-kind pytest-regression
    --regression-test-file <file>`` so the shipped pytest-regression gate mode
    becomes reachable from a live dispatch. The extra args are closed over at
    BUILD time, so the returned `_run(feature_id, entering_slice)` Callable
    signature is UNCHANGED. With the default ``at_kind="gherkin"`` the des_spawn
    call is byte-identical to the pre-fix invocation -- zero blast-radius.

    rust-regression-at-kind-semi-wired: the same threading now also covers
    ``native-regression`` and its ``rust-regression`` alias (both consumed by
    `des.cli.carpaccio_slice_gate`, which normalizes the alias itself) -- this
    hook is the U1 dispatch-guard site the defect named; before this fix ANY
    non-``pytest-regression`` regression kind was silently dropped here,
    falling through to a default `gherkin` gate call that then false-rejects
    a Rust/native-regression slice with `no-scenarios-for-slice`.
    """

    _REGRESSION_AT_KINDS = frozenset(
        {"pytest-regression", "native-regression", "rust-regression"}
    )
    _at_kind_args: tuple[str, ...] = (
        ("--at-kind", at_kind, "--regression-test-file", regression_test_file)
        if at_kind in _REGRESSION_AT_KINDS and regression_test_file is not None
        else ()
    )

    def _run(feature_id: str, entering_slice: str) -> tuple[int, str]:
        try:
            completed = des_spawn(
                None,
                _CARPACCIO_GATE_MODULE,
                "--feature-id",
                feature_id,
                "--entering-slice",
                entering_slice,
                "--repo-root",
                str(project_root),
                *_at_kind_args,
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


_DES_LANE_PATTERN = re.compile(r"<!--\s*DES-LANE\s*:\s*(\S+)\s*-->")
_DES_LANE_JUSTIFICATION_PATTERN = re.compile(
    r"<!--\s*DES-LANE-JUSTIFICATION\s*:\s*(.+?)\s*-->"
)


def _parse_lane_from_prompt(prompt: str) -> tuple[str | None, str]:
    """Parse the optional DES-LANE markers from a dispatch ``prompt``.

    Two separate HTML-comment markers (NOT one colon-delimited marker) so an
    embedded colon in the justification text is unambiguous:

      <!-- DES-LANE : bugfix -->
      <!-- DES-LANE-JUSTIFICATION : <text> -->

    Whitespace around the ``:`` is tolerated like the other DES markers. Absent
    DES-LANE marker yields ``(None, "")`` -- the default (feature-readiness) path.
    """
    lane_match = _DES_LANE_PATTERN.search(prompt)
    if lane_match is None:
        return None, ""
    justification_match = _DES_LANE_JUSTIFICATION_PATTERN.search(prompt)
    justification = justification_match.group(1).strip() if justification_match else ""
    return lane_match.group(1), justification


_DES_AT_KIND_PATTERN = re.compile(r"<!--\s*DES-AT-KIND\s*:\s*(\S+)\s*-->")
_DES_REGRESSION_TEST_FILE_PATTERN = re.compile(
    r"<!--\s*DES-REGRESSION-TEST-FILE\s*:\s*(\S+)\s*-->"
)


def _parse_at_kind_from_prompt(prompt: str) -> tuple[str, str | None]:
    """Parse the optional DES-AT-KIND markers from a dispatch ``prompt``.

    Two separate HTML-comment markers (mirroring the DES-LANE pair) so an
    embedded path in the regression-test-file value is unambiguous:

      <!-- DES-AT-KIND : pytest-regression -->
      <!-- DES-REGRESSION-TEST-FILE : tests/build/x/test_y.py -->

    Whitespace around the ``:`` is tolerated like the other DES markers. Absent
    DES-AT-KIND yields ``("gherkin", None)`` -- the default (Gherkin) path, so a
    dispatch with no marker stays byte-identical to today.
    """
    at_kind_match = _DES_AT_KIND_PATTERN.search(prompt)
    if at_kind_match is None:
        return "gherkin", None
    file_match = _DES_REGRESSION_TEST_FILE_PATTERN.search(prompt)
    regression_test_file = file_match.group(1) if file_match else None
    return at_kind_match.group(1), regression_test_file


def _real_readiness_runner(
    project_root: Path,
    lane: str | None = None,
    lane_justification: str = "",
) -> ReadinessRunner:
    """Build the real readiness runner bound to ``project_root`` (slice-05).

    Mirrors `_real_carpaccio_runner`: runs the slice-03 verify-readiness-pre-
    dispatch CLI as `python_for(None) -m des verify-readiness-pre-dispatch ...`
    subprocess. A timeout / signal-kill is surfaced as a non-zero exit so the
    caller blocks identically to an explicit readiness rejection.

    RC4-b (ADD-not-mutate): when ``lane`` is set, the closure appends
    ``--lane <lane> --lane-justification <text>`` so the shipped bugfix-lane
    gate-logic becomes reachable from a live dispatch. The lane is closed over at
    BUILD time, so the returned `_run(feature_id, entering_slice)` Callable
    signature is UNCHANGED. With ``lane is None`` (default) the des_spawn call is
    byte-identical to the pre-RC4-b invocation -- zero blast-radius.
    """

    _lane_args: tuple[str, ...] = (
        ("--lane", lane, "--lane-justification", lane_justification)
        if lane is not None
        else ()
    )

    def _run(feature_id: str, entering_slice: str) -> tuple[int, str]:
        try:
            completed = des_spawn(
                None,
                _READINESS_GATE_CLI_TARGET,
                _READINESS_GATE_SUBCOMMAND,
                "--feature-id",
                feature_id,
                "--slice-id",
                entering_slice,
                "--repo-root",
                str(project_root),
                *_lane_args,
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


def _real_completeness_runner(project_root: Path) -> CompletenessRunner:
    """Build the real AT-completeness backstop runner bound to ``project_root``.

    f-design-devops-review-gate slice-03 (CT-9 / DDD-5): the DELIVER-entry
    BACKSTOP for the EXISTING completeness CLI -- ZERO new gate logic. Mirrors
    `_real_readiness_runner`: runs `python_for(None) -m des
    check-slice-at-completeness --repo <root> --commit HEAD --slice-id <s>
    --feature-id <f>` (the CLI's argv) as a layout-independent module subprocess.
    A timeout / signal-kill is surfaced as a non-zero exit so the caller treats
    it identically to an explicit gate verdict.
    """

    def _run(feature_id: str, entering_slice: str) -> tuple[int, str]:
        try:
            completed = des_spawn(
                None,
                _COMPLETENESS_GATE_CLI_TARGET,
                _COMPLETENESS_GATE_SUBCOMMAND,
                "--repo",
                str(project_root),
                "--commit",
                "HEAD",
                "--slice-id",
                entering_slice,
                "--feature-id",
                feature_id,
                capture_output=True,
                text=True,
                timeout=COMPLETENESS_GATE_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            return 124, json.dumps(
                {
                    "event": "GateInvocationTimeout",
                    "gate": "check_slice_at_completeness",
                    "entering_slice": entering_slice,
                }
            )
        return completed.returncode, completed.stdout

    return _run


def _real_wave_dispatch_runner(project_root: Path) -> WaveDispatchRunner:
    """Build the real wave-dispatch guard runner bound to ``project_root`` (slice-05).

    Mirrors `_real_readiness_runner`: runs the slice-05 verify-wave-dispatch CLI
    as a `python_for(None) -m des verify-wave-dispatch ...` subprocess. The
    dispatch prompt is written to a hermetic temp FILE the gate reads via
    `--prompt-path` (the gate takes a FILE, not stdin).

    The guard is fail-OPEN (DDD-8): only a definite BLOCK (exit 1) is surfaced as
    a gate failure to the dispatcher; ALLOW (0), malformed input (2), a timeout,
    and any other non-{0,1} exit (module-absent / freshness-autoskip) are mapped
    to exit 0 so a guard error never bricks the dispatch flow. The BLOCK exit 1
    is passed through unchanged so the dispatcher halts the composition and the
    intercept maps it to `decision:block` (warn+ask).
    """

    def _run(subagent_type: str, prompt: str) -> tuple[int, str]:
        prompt_path = project_root / ".nwave" / "des" / "wave-dispatch-prompt.txt"
        try:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt, encoding="utf-8")
        except OSError:
            # Cannot stage the prompt -> fail-OPEN (allow); a guard staging
            # failure must never block the dispatch.
            return 0, json.dumps(
                {"event": "WaveDispatchGuardStagingFailed", "verdict": "allow"}
            )
        try:
            completed = des_spawn(
                None,
                _WAVE_DISPATCH_GATE_CLI_TARGET,
                _WAVE_DISPATCH_GATE_SUBCOMMAND,
                "--subagent-type",
                subagent_type,
                "--prompt-path",
                str(prompt_path),
                "--repo-root",
                str(project_root),
                capture_output=True,
                text=True,
                timeout=WAVE_DISPATCH_GATE_SUBPROCESS_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            # Fail-OPEN on timeout: a slow guard never bricks the dispatch.
            return 0, json.dumps(
                {"event": "WaveDispatchGuardTimeout", "verdict": "allow"}
            )
        if completed.returncode == _WAVE_DISPATCH_GATE_BLOCK_EXIT_CODE:
            return completed.returncode, completed.stdout
        # Fail-OPEN: ALLOW (0), malformed (2), module-absent / autoskip
        # non-{0,1} -> allow (exit 0). Preserve the gate's stdout for audit.
        return 0, completed.stdout

    return _run


def _slice_number(slice_id: str) -> int:
    """The integer N from a numeric `slice-NN` id.

    Slice ids are INTEGER-ONLY (`slice-NN`, digits only). Non-integer shapes
    -- a letter suffix (`slice-04a`) or a decimal (`slice-04.1`) -- are NOT
    supported: the slice-ordering machinery (this order check + the
    predecessor computation) is defined only over integers. To insert an
    intermediate slice, RENUMBER the plan (shift the later slices up by one)
    rather than minting a fractional/letter sub-slice -- simple, and the
    ordering stays guaranteed by construction. Raises a self-explaining
    ValueError instead of a cryptic ``invalid literal for int()`` so this
    constraint is documented at the point of use and never rediscovered.
    """
    suffix = slice_id.split("-", 1)[1]
    if not suffix.isdigit():
        raise ValueError(
            f"slice id {slice_id!r} is not an integer 'slice-NN' (digits only). "
            f"Non-integer slices (letter-suffix 'slice-04a', decimal "
            f"'slice-04.1') are not supported -- the slice-ordering machinery is "
            f"integer-only. To insert an intermediate slice, RENUMBER the plan "
            f"(shift the later slices up by one), do not mint a sub-slice."
        )
    return int(suffix)


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
    # Integer-only slice ids: a non-integer shape (letter-suffix `slice-04a`,
    # decimal `slice-04.1`) is refused HERE with a self-explaining gate message
    # carrying the fix, rather than crashing the downstream integer-only
    # ordering machinery with a cryptic `int()` error.
    if not slice_id.split("-", 1)[1].isdigit():
        return InterceptDecision.block(
            event="CarpaccioSliceNonInteger",
            reason=(
                f"slice id {slice_id} is not an integer 'slice-NN' (digits "
                "only). Non-integer slices (letter-suffix 'slice-04a', decimal "
                "'slice-04.1') are not supported -- the slice-ordering machinery "
                "is integer-only. FIX: to insert an intermediate slice, RENUMBER "
                "the plan -- shift the later slices up by one (e.g. old slice-05 "
                "becomes slice-06, the new slice takes slice-05) -- do not mint a "
                "sub-slice. Renumbering keeps the ordering guaranteed by "
                "construction."
            ),
        )
    if _slice_number(slice_id) <= 1:
        return None

    predecessor = _predecessor_slice(slice_id)
    ledger = AtCompletionLedger(feature_id, project_root)
    if _predecessor_satisfies_in_order(ledger, predecessor):
        return None

    # The predecessor has no satisfying record. Before blocking, attempt an
    # in-gate auto-backfill: a predecessor that was committed on disk but never
    # recorded (the F-CRAFTER-RELIES-ON-SUBAGENTSTOP-FOR-SLICECOMMITVERIFIED
    # friction) is verify-then-recorded automatically so the successor is no
    # longer blocked out of order for a missing record.
    _attempt_predecessor_backfill(predecessor, feature_id, project_root)
    if _predecessor_satisfies_in_order(ledger, predecessor):
        return None

    # swarm-parallel-delivery exemption: a slice N>1 developed in an ISOLATED
    # parallel worktree cannot see its predecessor's SliceCommitVerified record
    # until a later, in-order integration folds it onto the shared line -- where
    # the true ordering is still guaranteed. A `DES-SWARM-ISOLATED-DISPATCH:
    # <justification>` marker declares exactly this, exempting ONLY the M8 order
    # check and deferring the verification to the integrator. Unlike DES-BOOTSTRAP
    # this is ROUTINE (every slice N>1 of a swarmed feature needs it), so it
    # carries NO reuse cap. The truthiness check fails CLOSED on an empty/absent
    # justification -- the order check blocks exactly as before.
    if markers.swarm_isolated_justification:
        _emit_swarm_isolated_deferral_event(
            justification=markers.swarm_isolated_justification,
            feature_id=feature_id,
            slice_id=slice_id,
            predecessor=predecessor,
            project_root=project_root,
        )
        return None

    return InterceptDecision.block(
        event="CarpaccioSliceOutOfOrder",
        reason=(
            f"carpaccio slice {slice_id} entered out of order: its predecessor "
            f"{predecessor} has no SliceCommitVerified ledger record -- deliver "
            "carpaccio slices in order"
        ),
        # GDP-3 HOW: the one universally-true cure regardless of WHICH of the
        # 3 backfill no-op conditions fired (no commit on disk / E1-deficient /
        # digest-unverified, `_attempt_predecessor_backfill` collapses all
        # three to a silent None -- RCA Q4(b) "Constraint on (b)"). Naming a
        # more specific cause here would overclaim discrimination the code
        # cannot verify, so this names ONLY the re-establish path.
        how=(
            f"an in-gate auto-backfill was already attempted for {predecessor} "
            "and could not recover a record -- re-establish its "
            "SliceCommitVerified record via `des commit-slice --slice-id "
            f"{predecessor} --feature-id {feature_id} --message <message> "
            "--path <paths>` (or --all), which stamps the Slice-Id trailer and "
            f"re-verifies. Then retry this dispatch for {slice_id}."
        ),
    )


def _emit_swarm_isolated_deferral_event(
    *,
    justification: str,
    feature_id: str,
    slice_id: str,
    predecessor: str,
    project_root: Path,
) -> None:
    """Append the `CarpaccioOrderCheckDeferredToIntegration` audit record (fail-OPEN).

    Mirrors `_emit_bootstrap_exemption_event`: the exemption verdict already
    stands, so a lost ledger line never changes the decision -- but the write is
    best-effort, never silently omitted. Records the deferred predecessor so the
    integrator's async review has the order-verification it now owns.
    """
    try:
        AtCompletionLedger(feature_id, project_root).append_gate_event(
            event="CarpaccioOrderCheckDeferredToIntegration",
            slice_id=slice_id,
            gate="carpaccio-order-gate",
            justification=justification,
            predecessor=predecessor,
        )
    except Exception:
        # Fail-open: the deferral verdict already stands; ledger emission is audit.
        pass


def _predecessor_satisfies_in_order(
    ledger: AtCompletionLedger, predecessor: str
) -> bool:
    """Whether ``predecessor`` carries a record that satisfies the in-order gate.

    DDD-3: the predecessor-satisfied predicate accepts a `SliceCommitVerified`
    OR a `SliceCommitIndeterminate` OR a `SliceProseDelivered` record -- the
    3-reader union is the semantic `attested == true` contract. An INDETERMINATE
    predecessor is the honest "unverified on this machine" the non-Python-target
    E2 degrade-path mints (the gate could not resolve a usable interpreter); a
    PROSE_DELIVERED predecessor is the honest "doc-review attested, no acceptance
    tests" a principle-b prose slice mints (DDD-2). Each satisfies in-order just
    as a verified record does, so a non-Python OR a prose slice chain progresses
    instead of wedging -- the unblock is never silent (every record is explicit
    on the ledger and the prose record stays DISTINCT from a fabricated verified
    record).
    """
    return (
        predecessor in ledger.verified_slices()
        or predecessor in ledger.indeterminate_slices()
        or predecessor in ledger.prose_delivered_slices()
    )


def _predecessor_commit_sha(
    repo: Path, predecessor: str, feature_id: str
) -> str | None:
    """The SHA of the most recent commit carrying ``predecessor``'s identity
    AND belonging to ``feature_id``.

    Two lookup strategies, EACH tried against ALL its candidates (most
    recent first) before falling through to the next strategy:

      1. The modern `Slice-Id: <predecessor>` trailer (the F-07 multi-trailer
         shape lists each slice on its own line).
      2. A pre-trailer-era fallback -- for a commit whose SUBJECT line
         carries the legacy `(slice-NN)` / `[slice-NN]` parenthetical suffix
         (the convention in use before the Slice-Id trailer shipped; e.g.
         `1ad46e416`'s subject "...(slice-01)"). A slice-01 committed before
         the trailer convention existed can never carry a trailer, so
         without this fallback its successor is permanently blocked
         out-of-order.

    Cross-feature collision (F-CARPACCIO-PREDECESSOR-FEATURE-SCOPING): slice
    IDs like `slice-01`/`slice-02` are reused across every feature in the
    repo, so trusting git's single most-recent match can resolve to a
    DIFFERENT feature's commit -- and that wrong commit does not have to be
    newer than the real predecessor to cause harm: it is enough for it to be
    the ONLY (or first) match a strategy finds, which happens whenever the
    real predecessor's own commit predates the trailer convention (no
    trailer at all, so strategy 1 never even sees it) while an unrelated
    feature's commit happens to carry a genuine `Slice-Id: <predecessor>`
    trailer. The OLD code returned strategy 1's first hit unconditionally,
    which starves strategy 2 of ever running even when EVERY strategy-1
    candidate fails E1. This function instead walks ALL of strategy 1's
    candidates (most recent first) checking E1 (`missing_at_files`) per
    candidate -- the same check `_attempt_predecessor_backfill` runs
    afterward, applied here PER CANDIDATE instead of trusting the first
    candidate blindly -- and falls through to strategy 2's candidates (same
    per-candidate E1 walk) only if NONE of strategy 1's candidates satisfy
    E1. E1 + E2 (verify-gate-scope digest) still feed the unmodified final
    verification in `_attempt_predecessor_backfill`; this only widens HOW
    the candidate commit is found and picked, never what is verified
    against it. Returns None when no candidate from either strategy
    satisfies E1 -- the backfill has no predecessor commit to verify against
    and fails closed by leaving the record absent.
    """
    for sha in _predecessor_commit_shas_via_trailer(repo, predecessor):
        outcome = missing_at_files(repo, sha, predecessor, feature_id)
        if outcome.verifiable and not outcome.missing:
            return sha
    for sha in _predecessor_commit_shas_via_subject_marker(repo, predecessor):
        outcome = missing_at_files(repo, sha, predecessor, feature_id)
        if outcome.verifiable and not outcome.missing:
            return sha
    return None


def _predecessor_commit_shas_via_trailer(repo: Path, predecessor: str) -> list[str]:
    """All commit SHAs (most recent first) carrying ``predecessor``'s Slice-Id.

    Searches the commit log for a `Slice-Id: <predecessor>` trailer (the F-07
    multi-trailer shape lists each slice on its own line). Returns an empty
    list when no such commit exists on disk.
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
        return []
    shas: list[str] = []
    for entry in completed.stdout.split("\x1e"):
        sha, _, message = entry.strip().partition("\x00")
        if sha and predecessor in extract_slice_ids(message):
            shas.append(sha)
    return shas


_SUBJECT_SLICE_MARKER_RE = re.compile(r"[(\[](slice-\d+(?:[a-z])?)[)\]]\s*$")


def _predecessor_commit_shas_via_subject_marker(
    repo: Path, predecessor: str
) -> list[str]:
    """All commit SHAs (most recent first) whose SUBJECT names ``predecessor``.

    The pre-trailer-era convention: a commit subject ending in a `(slice-NN)`
    or `[slice-NN]` parenthetical/bracket suffix (no `Slice-Id:` trailer
    anywhere in the message). Returns an empty list when no such commit
    exists on disk, or when `git` itself is unavailable.
    """
    try:
        completed = subprocess.run(
            ["git", "log", "--format=%H%x1f%s"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    shas: list[str] = []
    for line in completed.stdout.splitlines():
        sha, _, subject = line.partition("\x1f")
        if not sha:
            continue
        match = _SUBJECT_SLICE_MARKER_RE.search(subject)
        if match and match.group(1) == predecessor:
            shas.append(sha)
    return shas


def _verify_gate_scope(repo: Path, commit: str) -> bool:
    """Run E2-evidence -- `run_contract_gate --commit --verify-gate-scope`.

    Recomputes a fresh whole-tree collect-only digest and compares it to the
    predecessor commit's `Gate-Scope:` trailer. Exit 0 (`GateScopeVerified`)
    ONLY when the trailer is present AND matches; any non-zero (absent / stale
    digest) or a subprocess timeout returns False so the backfill fails closed
    (no false-allow). Runs at the delegated-subprocess timeout tier.
    """
    try:
        completed = des_spawn(
            None,
            _CONTRACT_GATE_MODULE,
            "--verify-gate-scope",
            "--commit",
            commit,
            "--repo",
            str(repo),
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
    commit_sha = _predecessor_commit_sha(project_root, predecessor, feature_id)
    if commit_sha is None:
        return
    outcome = missing_at_files(project_root, commit_sha, predecessor, feature_id)
    if outcome.missing or not outcome.verifiable:
        return
    if not _verify_gate_scope(project_root, commit_sha):
        return
    _record_slice_commit_verified(feature_id, predecessor, project_root)


def _gate_invoker_for(
    carpaccio_runner: CarpaccioRunner,
    readiness_runner: ReadinessRunner | None = None,
    wave_dispatch_runner: WaveDispatchRunner | None = None,
    completeness_runner: CompletenessRunner | None = None,
) -> Callable[[str, dict[str, str]], tuple[int, str]]:
    """Adapt the per-gate runners into the dispatcher's `gate_invoker` Port.

    The dispatcher invokes `gate_invoker(gate_id, context_dict)`; this helper
    builds a per-gate registry from the injected runners (keyed by gate_id) +
    delegates the per-gate context extraction. The (feature_id, slice_id) gates
    (carpaccio + readiness + the slice-03 completeness BACKSTOP) read those two
    context keys uniformly; the wave-dispatch guard (slice-05, DDD-8) reads
    `subagent_type` + `prompt` from the context instead (its DISTINCT runner
    shape). Adding a gate to
    `dispatch.pre` requires ONLY a YAML edit plus a new runner kwarg here -- the
    dispatch loop itself never needs edits (INV-2 composable, INV-12 future
    workflow change = reconfiguration).

    When a runner kwarg is None (a backward-compat call shape) the registry
    omits that entry; the dispatcher then surfaces `UnknownGateOnDispatchPre` if
    the YAML still references it (fail-closed by design -- the same shape today's
    intercept emits).
    """
    slice_registry: dict[str, Callable[[str, str], tuple[int, str]]] = {
        _CARPACCIO_SLICE_GATE_ID: carpaccio_runner,
    }
    if readiness_runner is not None:
        slice_registry[_VERIFY_READINESS_PRE_DISPATCH_GATE_ID] = readiness_runner
    if completeness_runner is not None:
        slice_registry[_CHECK_SLICE_AT_COMPLETENESS_GATE_ID] = completeness_runner

    def _invoke(gate_id: str, context: dict[str, str]) -> tuple[int, str]:
        # ADR-001 DES-BOOTSTRAP: a dispatch repairing dispatch-gate G is
        # surgically exempted from G's OWN check only. The classifier runs FRESH
        # per composed gate; a `valid` verdict (the marker names THIS firing
        # gate) SKIPS exactly this gate (the real runner is NOT invoked) and
        # emits a distinct `BootstrapGateExempted` audit record. Every other
        # verdict (`absent-for-this-gate`, including no-marker and the canonical
        # divergence rule) falls through to the real runner byte-identically.
        bootstrap_markers = DesMarkerParser().parse(context.get("prompt", ""))
        verdict = classify_bootstrap(bootstrap_markers, gate_id)
        if verdict == "malformed":
            return _bootstrap_malformed_block(bootstrap_markers)
        if verdict == "valid":
            return _bootstrap_exempt(gate_id, bootstrap_markers, context)

        # RC4-b bugfix lane (charter: readiness-gate-lightweight for small
        # slices): a declared `DES-LANE: bugfix` skips the carpaccio Slice-Plan
        # CEREMONY gate. A single-slice bugfix has NO feature-delta, so the
        # carpaccio-slice-gate's `## ... Slice Plan` requirement is structurally
        # unsatisfiable (SlicePlanSectionMissing) -- disproportionate ceremony
        # for a one-defect fix. The verify-readiness-pre-dispatch bugfix lane
        # (run as its own composed gate) remains the lane's VALIDITY guard: it
        # REFUSES a vacuous justification and enforces the 2 mechanical safety
        # guards, so an invalid lane is still blocked there. The AT-completeness
        # BACKSTOP gate is NOT skipped -- the mechanical quality floor stays.
        lane, _lane_just = _parse_lane_from_prompt(context.get("prompt", ""))
        if lane == "bugfix" and gate_id == _CARPACCIO_SLICE_GATE_ID:
            return 0, json.dumps(
                {
                    "event": "BugfixLaneCarpaccioSkipped",
                    "gate_id": gate_id,
                    "lane": "bugfix",
                    "reason": (
                        "DES-LANE: bugfix skips the carpaccio Slice-Plan ceremony "
                        "(no feature-delta on a single-slice bugfix); "
                        "verify-readiness-pre-dispatch validates the lane + "
                        "enforces the mechanical guards."
                    ),
                }
            )

        # The wave-dispatch guard reads its OWN context keys (subagent_type +
        # prompt), distinct from the (feature_id, slice_id) gates.
        if (
            gate_id == _VERIFY_WAVE_DISPATCH_GATE_ID
            and wave_dispatch_runner is not None
        ):
            return wave_dispatch_runner(
                context.get("subagent_type", ""), context.get("prompt", "")
            )
        runner = slice_registry.get(gate_id)
        if runner is None:
            return 1, json.dumps(
                {
                    "event": "UnknownGateOnDispatchPre",
                    "gate_id": gate_id,
                }
            )
        return runner(context["feature_id"], context["slice_id"])

    return _invoke


def _bootstrap_malformed_block(markers: DesMarkers) -> tuple[int, str]:
    """Fail-CLOSED BLOCK a malformed DES-BOOTSTRAP claim (ADR-001 D4, slice-02).

    The single `malformed` verdict maps to two DISTINCT block events so the
    async-review trail names the malformation precisely:

      * gate-id NOT in `BOOTSTRAPPABLE_GATES` (out-of-vocab) ->
        `BootstrapMarkerMalformed`;
      * an in-vocab gate but missing / empty justification ->
        `BootstrapJustificationMissing`.

    The real gate runner is NOT invoked (neither run nor skipped) and NO
    exemption is written -- an invalid claim can never buy a surgical skip.
    """
    if markers.bootstrap_gate not in BOOTSTRAPPABLE_GATES:
        return 1, json.dumps(
            {
                "event": "BootstrapMarkerMalformed",
                "gate": markers.bootstrap_gate,
                "reason": (
                    f"DES-BOOTSTRAP names an out-of-vocabulary gate "
                    f"{markers.bootstrap_gate!r} (not in BOOTSTRAPPABLE_GATES) -- "
                    "fix the gate-id to a bootstrappable dispatch-gate"
                ),
            }
        )
    return 1, json.dumps(
        {
            "event": "BootstrapJustificationMissing",
            "gate": markers.bootstrap_gate,
            "reason": (
                "DES-BOOTSTRAP carries no DES-BOOTSTRAP-JUSTIFICATION marker -- "
                "add a non-empty justification for the async-review trail"
            ),
        }
    )


def _bootstrap_exempt(
    gate_id: str, markers: DesMarkers, context: dict[str, str]
) -> tuple[int, str]:
    """Skip the CURRENTLY-firing gate for a `valid` DES-BOOTSTRAP dispatch.

    The surgical exemption (ADR-001 D2): the real gate runner is NOT invoked;
    the gate clears with exit 0, and a distinct `BootstrapGateExempted{gate,
    justification, feature_id}` audit record is written so the async-review
    trail exists from the first commit. The audit write is fail-OPEN (mirrors
    `_emit_carpaccio_gate_event`): the exemption verdict already stands, so a
    lost ledger line never changes the decision -- but the write is best-effort,
    never silently omitted.

    D8 reuse cap (slice-02): BEFORE granting, the fail-CLOSED reuse cap reads
    the ledger for a prior exemption of this (gate, feature); a second bootstrap
    of the same gate within one feature is BLOCKed so a gate can never be
    silently disabled by repeated stamping.
    """
    feature_id = context.get("feature_id", "")
    project_root = Path(context.get("repo_root", "."))
    justification = markers.bootstrap_justification or ""
    cap_block = _reuse_cap_block(gate_id, feature_id, project_root)
    if cap_block is not None:
        return cap_block
    _emit_bootstrap_exemption_event(
        gate_id, justification, feature_id, project_root, context.get("slice_id", "")
    )
    return 0, json.dumps(
        {
            "event": "BootstrapGateExempted",
            "gate": gate_id,
            "justification": justification,
            "feature_id": feature_id,
        }
    )


def _reuse_cap_block(
    gate_id: str, feature_id: str, project_root: Path
) -> tuple[int, str] | None:
    """The D8 per-feature-per-gate reuse cap of 1 -- fail-CLOSED (slice-02).

    Reads the ledger for a prior `BootstrapGateExempted{gate}` record for this
    feature under the M7 fail-closed integrity contract (the per-feature ledger
    file already scopes to `feature_id`). When one exists, the reuse cap is
    spent -> BLOCK `BootstrapReuseCapExceeded`, writing NO new exemption. When
    none exists, return None so the caller grants the first exemption.

    Fail-CLOSED on a corrupt ledger: `read_records` raises
    `LedgerIntegrityViolation`, which propagates to the M1 handler wrapper (the
    same fail-closed-on-corruption pattern the M8 order check uses) -- an
    unreadable ledger cannot prove the cap unspent, so the bootstrap never
    silent-passes.
    """
    records = AtCompletionLedger(feature_id, project_root).read_records()
    already_exempted = any(
        record.get("event") == "BootstrapGateExempted" and record.get("gate") == gate_id
        for record in records
    )
    if not already_exempted:
        return None
    return 1, json.dumps(
        {
            "event": "BootstrapReuseCapExceeded",
            "gate": gate_id,
            "feature_id": feature_id,
            "reason": (
                f"gate {gate_id!r} was already DES-BOOTSTRAP-exempted for feature "
                f"{feature_id!r} (reuse cap = 1) -- a gate cannot be disabled twice"
            ),
        }
    )


def _emit_bootstrap_exemption_event(
    gate: str,
    justification: str,
    feature_id: str,
    project_root: Path,
    slice_id: str,
) -> None:
    """Append the distinct `BootstrapGateExempted` audit record (fail-OPEN).

    REUSES the M7 ledger writer via the ADR-001 signature delta -- the optional
    `gate` + `justification` kwargs carry the exemption honestly. Fail-OPEN on
    the write (the exemption verdict already stands; the audit is async-review
    material, not part of the decision).
    """
    try:
        AtCompletionLedger(feature_id, project_root).append_gate_event(
            event="BootstrapGateExempted",
            slice_id=slice_id,
            gate=gate,
            justification=justification,
        )
    except Exception:
        # Fail-open: the exemption verdict already stands; ledger emission is audit.
        pass


def evaluate_atdd_pure_dispatch(
    *,
    prompt: str,
    feature_id: str,
    project_root: Path,
    subagent_type: str = "",
    carpaccio_runner: CarpaccioRunner | None = None,
    readiness_runner: ReadinessRunner | None = None,
    wave_dispatch_runner: WaveDispatchRunner | None = None,
    completeness_runner: CompletenessRunner | None = None,
) -> InterceptDecision:
    """Evaluate the U1 carpaccio intercept for one PreToolUse dispatch.

    The single decision function `handle_pre_tool_use` delegates to. The
    wave-dispatch + readiness + carpaccio CLI invocations are sourced from
    `nWave/flavors/atdd_pure.yaml` via the flavor dispatcher (D4 Phase 3
    slice-02 + slice-05); the injected per-gate runners are wrapped into
    the dispatcher's `gate_invoker` Port via a per-gate registry.

    The `readiness_runner` + `wave_dispatch_runner` + `completeness_runner`
    parameters are ADDITIVE on top of the slice-02 frozen signature -- defaulting
    to None preserves the slice-02 single-gate call shape (AT-4 regression-pin).
    When the `wave_dispatch_runner` is provided, the flavor's dispatch.pre
    composition can wire `verify-wave-dispatch` ahead of
    `verify-readiness-pre-dispatch` / `carpaccio-slice-gate` as a YAML edit
    (INV-12). The wave-dispatch guard is fail-OPEN (DDD-8): its runner surfaces
    only a definite BLOCK (gate exit 1) as a composition failure; malformed
    input / module-absent / timeout map to ALLOW. The `completeness_runner`
    (f-design-devops-review-gate slice-03, CT-9) is the DELIVER-entry
    AT-completeness BACKSTOP wired onto dispatch.pre as `on_failure: warn`, so an
    incomplete slice is surfaced (not bricked) at DELIVER entry even if the
    DISTILL gate-out was bypassed.

    Returns an `InterceptDecision`:
      * `block(...)`    -- an unresolved or legacy dispatch carrier.
      * `allow()`       -- a recognised atdd_pure dispatch the U1 gate cleared.
      * `block(...)`    -- a recognised atdd_pure dispatch the gate rejected.

    Note on the M1 handler-exception contract: this function does NOT swallow
    its own exceptions. `handle_pre_tool_use` wraps the call in a try/except and
    surfaces any exception as an `AtddPureHookInternalError` block.
    """
    _at_kind, _regression_test_file = _parse_at_kind_from_prompt(prompt)
    carpaccio = carpaccio_runner or _real_carpaccio_runner(
        project_root, at_kind=_at_kind, regression_test_file=_regression_test_file
    )
    _lane, _lane_just = _parse_lane_from_prompt(prompt)
    readiness = readiness_runner or _real_readiness_runner(
        project_root, lane=_lane, lane_justification=_lane_just
    )
    wave_dispatch = wave_dispatch_runner or _real_wave_dispatch_runner(project_root)
    completeness = completeness_runner or _real_completeness_runner(project_root)

    markers = DesMarkerParser().parse(prompt)
    classification = classify_atdd_pure_dispatch(markers)

    # M3 positive recognition (in-house -- INV-1 atomic).
    if classification == "absent":
        return InterceptDecision.block(
            event="DispatchModeUnresolved",
            reason=(
                "WHAT: the dispatch omits DES-MODE: atdd_pure. "
                "WHY: absence cannot select a retired workflow. "
                "HOW: regenerate the dispatch with the explicit atdd_pure marker."
            ),
        )
    if classification == "defective":
        missing = atdd_pure_missing_marker(markers)
        if missing is not None:
            return InterceptDecision.block(
                event="AtddPureMarkerSetIncomplete",
                reason=(
                    f"atdd_pure dispatch prompt is missing a well-formed {missing} "
                    "marker -- the dispatch prompt must carry all three markers. "
                    "GENERATE it instead of hand-writing it: `des dispatch --mode "
                    "atdd_pure --project-id <id> --slice <slice-NN> --phase "
                    "<phase>` emits every marker BY CONSTRUCTION."
                ),
            )
        # NOTHING is missing -- every marker parsed cleanly. The dispatch is
        # defective for the OTHER reason classify_atdd_pure_dispatch rejects:
        # the (phase, scope) pair is INCOHERENT. Blaming a marker here (the
        # former `or "des-mode"` default) sends the reader to repair a marker
        # that is demonstrably well-formed -- measured 2026-07-18: six dispatches
        # refused for a "missing des-mode marker" whose value the parser read
        # correctly every time. Name the real incoherence instead.
        return InterceptDecision.block(
            event="AtddPurePhaseScopeIncoherent",
            reason=(
                f"atdd_pure dispatch declares phase '{markers.atdd_pure_phase}' "
                f"with scope '{markers.slice_id}' -- every marker is present and "
                "well-formed, but the PAIR is not legal. A feature-end-cycle "
                # DERIVED from the vocabulary SSOT, never hand-listed: a
                # hardcoded enumeration silently becomes a LIE the moment a
                # phase word is added (it already omitted D_DISTILL, and
                # FEATURE_END_EXAMINE would have made it wrong again).
                f"phase ({' / '.join(sorted(FEATURE_END_PHASES))}) is the only "
                "kind that may carry scope 'feature-end'; every other phase is "
                "and must carry a 'slice-NN' scope (ADR-028 D6). Fix ONE of the "
                "two so they agree: either name the per-slice scope this phase "
                "belongs to, or -- if you genuinely mean the whole feature -- "
                "declare a feature-end-cycle phase. Do NOT touch the markers: "
                "they are fine."
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
            # slice-05 (DDD-8): the wave-dispatch guard's context keys.
            "subagent_type": subagent_type,
            "prompt": prompt,
        },
        flavors_dir=_FLAVORS_DIR,
        gate_invoker=_gate_invoker_for(
            carpaccio, readiness, wave_dispatch, completeness
        ),
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
    if blocking_gate_id == _VERIFY_WAVE_DISPATCH_GATE_ID:
        # slice-05 (DDD-8): a wave-OWNER dispatched off-spine. The runner is
        # fail-OPEN, so a halt here is a DEFINITE off-spine BLOCK (gate exit 1) --
        # the warn+ask the wave-level silent-entry hole closes.
        reason = (
            "wave-dispatch guard rejected an off-spine wave-owner dispatch "
            f"(exit {blocking_result.exit_code}): "
            f"{_carpaccio_reason(blocking_result.stdout)}"
        )
        _emit_carpaccio_gate_event(
            "WaveDispatchGateRejected",
            feature_id,
            slice_id,
            project_root,
            reason=reason,
        )
        return InterceptDecision.block(event="WaveDispatchGateRejected", reason=reason)

    if blocking_gate_id == _VERIFY_READINESS_PRE_DISPATCH_GATE_ID:
        reason = (
            f"readiness gate rejected {slice_id} (exit "
            f"{blocking_result.exit_code}): "
            f"{_readiness_reason(blocking_result.stdout)}"
        )
        _emit_carpaccio_gate_event(
            "ReadinessGateRejected", feature_id, slice_id, project_root, reason=reason
        )
        return InterceptDecision.block(event="ReadinessGateRejected", reason=reason)

    reason = (
        f"carpaccio gate rejected {slice_id} (exit "
        f"{blocking_result.exit_code}): "
        f"{_carpaccio_reason(blocking_result.stdout)}"
    )
    _emit_carpaccio_gate_event(
        "CarpaccioGateRejected", feature_id, slice_id, project_root, reason=reason
    )
    return InterceptDecision.block(event="CarpaccioGateRejected", reason=reason)


def _emit_carpaccio_gate_event(
    event: str,
    feature_id: str,
    slice_id: str,
    project_root: Path,
    *,
    reason: str | None = None,
) -> None:
    """Append a `CarpaccioGateCleared` / `*GateRejected` ledger record.

    F2 (M4): the U1 intercept records one carpaccio gate event per dispatch so
    `reconcile_dispatch_count` is meaningful. The emission is **fail-OPEN on the
    audit write** -- a ledger-write failure is swallowed so it can never change
    the gate decision.

    D04b (canali muti class-scope): the optional `reason` persists the SAME
    human-readable rejection reason `InterceptDecision.reason` already carries
    to the operator -- before this, the record told THAT a rejection happened
    but never WHY (measured: 60/60 CarpaccioGateRejected + 82/82
    ReadinessGateRejected records carried no reason field). Defaults to None
    (the `CarpaccioGateCleared` call site passes none -- a clearance has
    nothing to explain).
    """
    try:
        AtCompletionLedger(feature_id, project_root).append_gate_event(
            event=event, slice_id=slice_id, reason=reason
        )
    except Exception:
        # Fail-open: the gate verdict already stands; ledger emission is audit.
        pass


def intercept_atdd_pure_dispatch(
    *,
    prompt: str,
    feature_id: str,
    project_root: Path,
    subagent_type: str = "",
    carpaccio_runner: CarpaccioRunner | None = None,
    readiness_runner: ReadinessRunner | None = None,
    wave_dispatch_runner: WaveDispatchRunner | None = None,
    completeness_runner: CompletenessRunner | None = None,
) -> InterceptDecision:
    """The M1 fail-closed U1 intercept driving port.

    Wraps `evaluate_atdd_pure_dispatch` in the M1 try/except: ANY exception
    raised inside the U1 branch is surfaced as an `AtddPureHookInternalError`
    block, never re-raised. The `readiness_runner` + `wave_dispatch_runner` +
    `subagent_type` parameters are additive on the slice-02 frozen signature
    (slice-05); callers passing only `carpaccio_runner` retain slice-02 behaviour.
    The wave-dispatch guard is fail-OPEN -- an absent `subagent_type` (the empty
    default) makes the guard treat the dispatch as a non-owner -> ALLOW, never a
    block, so threading remains best-effort.
    """
    try:
        return evaluate_atdd_pure_dispatch(
            prompt=prompt,
            feature_id=feature_id,
            project_root=project_root,
            subagent_type=subagent_type,
            carpaccio_runner=carpaccio_runner,
            readiness_runner=readiness_runner,
            wave_dispatch_runner=wave_dispatch_runner,
            completeness_runner=completeness_runner,
        )
    except Exception as exc:
        return InterceptDecision.block(
            event="AtddPureHookInternalError",
            reason=f"U1 carpaccio intercept raised: {exc!s}",
        )


# FR-7 (discoverability): when a gate refuses a dispatch for a MISSING
# feature-delta ceremony (SlicePlanSectionMissing / the feature-readiness
# invariants), the human-facing reason must SURFACE the bugfix-lane escape + its
# exact marker format -- so a single-slice bugfix does not thrash through the
# gate cascade discovering the lane by reading source (as happened during
# charter #1's own dogfood).
_BUGFIX_LANE_HINT = (
    " | If this is a SINGLE-SLICE BUGFIX (no feature-delta / Slice Plan by"
    " design), skip this feature-readiness ceremony by re-dispatching with the"
    " marker pair `<!-- DES-LANE: bugfix -->` + `<!-- DES-LANE-JUSTIFICATION:"
    " <names the defect + the regression test test_...> -->`. The mechanical"
    " RED->GREEN safety guard still applies."
)

#: The readiness invariants whose failure MAY mean "this dispatch carries no
#: feature-delta by design" -- the only shape for which the bugfix-lane escape
#: above is honest advice.
_FEATURE_DELTA_CEREMONY_INVARIANTS = frozenset(
    {
        "slice_plan_section",
        "reuse_first_or_design_skip",
        "sustainability",
        "at_review_verdict",
    }
)

#: Read-state causes (`des.cli.feature_delta_source`) that CONTRA-INDICATE the
#: escape: each one proves the feature-delta EXISTS, so the dispatch is a real
#: feature with an authoring/encoding gap, not a delta-less bugfix. A payload
#: carrying no cause at all (a legacy or non-readiness producer) is not a
#: contra-indication -- absence of the fact is not the opposite fact.
_BUGFIX_LANE_HINT_CONTRAINDICATIONS = frozenset(
    {FEATURE_DELTA_SECTION_MISSING, FEATURE_DELTA_UNDECODABLE}
)


def _carpaccio_reason(stdout: str) -> str:
    """Extract a human-readable reason from the carpaccio CLI JSON output.

    Prefers the gate's rich ``error`` (already carries the actionable
    "To fix: ..." HOW) and folds in ``instruction`` when present and not
    already covered by ``error``, over the bare ``event`` name (GDP-3: a
    bare event name is not self-explaining). ``event`` is still surfaced
    for identification -- prefixed onto the rich content -- but is never a
    substitute for it. Falls back to the bare ``event`` only when the
    payload carries no ``error``/``instruction`` at all (graceful
    degrade), and degrades further to stripped stdout / a sane default
    when the payload is unparseable or non-dict. Never raises.
    """
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return stdout.strip() or "no gate output"
    if not isinstance(payload, dict):
        return stdout.strip() or "no gate output"

    event = payload.get("event")
    error = payload.get("error")
    instruction = payload.get("instruction")

    rich_parts: list[str] = []
    if error:
        rich_parts.append(str(error))
    if instruction:
        instruction_str = str(instruction)
        if not any(instruction_str in part for part in rich_parts):
            rich_parts.append(instruction_str)

    if rich_parts:
        rich_content = " | ".join(rich_parts)
        reason = f"{event}: {rich_content}" if event else rich_content
    elif event:
        reason = str(event)
    else:
        reason = stdout.strip() or "no gate output"

    if payload.get("event") == "SlicePlanSectionMissing":
        reason += _BUGFIX_LANE_HINT
    return reason


def _readiness_reason(stdout: str) -> str:
    """Build a what/why/how refusal reason from the readiness gate JSON output.

    The `verify-readiness-pre-dispatch` gate already computes, per invariant, an
    ``{id, status, remediation}`` triple (see `_emit_report` in
    `des.cli.verify_readiness_pre_dispatch`). The opaque-rejection defect was
    collapsing that rich payload to the bare top-level ``event``
    ("ReadinessRefused") via `_carpaccio_reason`, forcing the agent to re-run the
    gate by hand to discover WHAT failed. This surfaces, for EVERY failed
    invariant: WHAT failed (the invariant ``id``), WHY (its ``status``), and HOW
    (the ``remediation`` the gate already produced) -- so the agent never needs to
    re-run the gate to learn the next step (STANDING every-failure-explains rule).

    Degrades LOUD to `_carpaccio_reason` when the payload is unparseable, is not a
    dict, carries no ``invariants`` list, or lists no failed invariant -- never
    silently dropping the diagnostic.
    """
    try:
        payload = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        return _carpaccio_reason(stdout)
    if not isinstance(payload, dict):
        return _carpaccio_reason(stdout)
    invariants = payload.get("invariants")
    if not isinstance(invariants, list):
        return _carpaccio_reason(stdout)
    failed = [
        inv
        for inv in invariants
        if isinstance(inv, dict) and inv.get("status") == "failed"
    ]
    if not failed:
        return _carpaccio_reason(stdout)
    event = str(payload.get("event") or "ReadinessRefused")
    lines = [f"{event} -- {len(failed)} invariant(s) failed:"]
    for inv in failed:
        inv_id = str(inv.get("id") or "<unknown-invariant>")
        remediation = inv.get("remediation")
        how = str(remediation).strip() if remediation else "(no remediation provided)"
        lines.append(f"  - {inv_id}: {how}")
    # FR-7: when the failures are the feature-delta ceremony invariants, surface
    # the bugfix-lane escape -- a single-slice bugfix has no feature-delta by
    # design and should not have to discover the lane by reading source.
    #
    # CONDITIONED (this defect): the escape is advice for a dispatch that has NO
    # feature-delta by design. When the delta demonstrably EXISTS -- it is there
    # but a section is missing, or there but undecodable -- "re-mark it as a
    # bugfix" is a gate teaching how to get around itself, printed at the exact
    # moment the operator most wants a way through. Withheld on any failure
    # carrying a delta-exists cause; the invariant's own remediation already
    # names the real action.
    failed_ids = {str(inv.get("id")) for inv in failed}
    causes = {str(inv.get("cause") or "") for inv in failed}
    if failed_ids & _FEATURE_DELTA_CEREMONY_INVARIANTS and not (
        causes & _BUGFIX_LANE_HINT_CONTRAINDICATIONS
    ):
        lines.append(_BUGFIX_LANE_HINT.strip())
    return "\n".join(lines)


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
