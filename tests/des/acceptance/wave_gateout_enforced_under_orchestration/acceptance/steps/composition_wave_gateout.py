"""Composition root for wave-gateout-enforced-under-orchestration slice-01 (WS).

DRIVING SURFACE (Mandate-13 driving-port-only -- TWO real wired seams, no
direct-domain import for business logic):

  * Layer 3 composition (AT-1..3) -- the REAL ``handle_subagent_stop`` hook entry,
    invoked exactly as Claude Code dispatches it in production
    (``python -m des.adapters.drivers.hooks.claude_code_hook_adapter
    subagent-stop``), driven as a subprocess with a constructed WAVE-ONLY return on
    stdin: an agent transcript carrying a
    ``<!-- DES-WAVE: design -->`` marker + a ``<!-- DES-PROJECT-ID: <id> -->``
    marker + ``<!-- DES-VALIDATION: required -->`` -- but NO ``<!-- DES-STEP-ID -->``
    and NO atdd_pure markers. That is the exact shape an Agent()-dispatched
    architect return carries. The hook routes the return through the production
    composition root (``service_factory.create_subagent_stop_service``) into
    ``SubagentStopService.validate``; the observable is the hook decision carried as
    a ``{"decision": "block"|"allow", "reason": ...}`` JSON body on the hook's
    stdout (the SubagentStop protocol ALWAYS exits 0 -- a non-zero exit makes Claude
    Code ignore stdout, so the decision rides the body, never the exit code;
    subagent_stop_handler.py:1686-1743). No production service is imported-and-called
    at the step boundary, and no ``des.domain.*`` value object is imported into this
    composition root -- the hook process IS the SUT (Mandate-13).

  * Layer 3 subprocess (AT-3) -- the REAL ``des record-design-review`` PRODUCER CLI
    as a black-box process; it records the architect's reviewer verdict into the
    AT-completion ledger the gate-out seals against. No fixture authors the verdict
    (No Fixture Theater) -- it is written by the REAL CLI, sealed against the
    feature-delta the architect returned.

DORMANT-SEAM RECONCILIATION (Mandate-15 / S3): the DESIGN driving-surface declares
ONE net-new load-bearing reachability seam reached from the REAL hook entry:

  (seam-1) the wave-only SubagentStop reachability route -- a return carrying a
           ``DES-WAVE`` marker + ``DES-PROJECT-ID`` (no classic execution-log
           marker set) MUST REACH ``SubagentStopService.validate`` so the existing
           ``_gate_out_review_verdict`` -> ``ReviewVerdictGate.evaluate`` veto fires.
           Today ``_resolve_des_context`` (subagent_stop_handler.py:209) returns a
           passthrough-allow (:274-275) for such a return BEFORE ``validate`` runs.
           Each slice-01 AT NAMES this seam, drives it through the REAL hook entry,
           and asserts an observable effect (the hook exit code: block on an absent
           review, allow on an approved review).

RED contract (fail-for-right-reason, atdd_pure active-RED -- NOT @skip):
  * AT-1 / AT-2: a wave-only DESIGN return with NO recorded review verdict. At HEAD
    the reachability route does not exist: ``extract_des_context_from_transcript``
    returns ``None`` (the return carries neither the classic nor the atdd_pure
    marker set), so ``_resolve_des_context`` returns the passthrough-allow and the
    hook emits NO ``{"decision":"block"}`` body (a silent allow) -- the DESIGN
    review veto never runs. AT-1's "refused" oracle (a block body on stdout) fails
    with a semantic AssertionError naming the unreachable gate-out. AT-2 SHARPENS
    it: the refusal must additionally NAME the missing-review reason (the cure's
    ``_gate_out_review_verdict`` emits ``DESIGN_REVIEW_INDETERMINATE: design review
    verdict absent`` -- "missing review read as refusal, never a silent pass");
    at HEAD that named reason never appears (no block body at all), so BOTH AT-2's
    block AND its reason-naming assertions fail as MISSING_FUNCTIONALITY. Every
    dependency (the ``des``/hook subprocess, the tmp work-tree, the armed floor +
    feature-delta) resolves cleanly -- a deliberate missing-functionality RED, not
    a test bug.
  * AT-3: a wave-only DESIGN return WITH an approved verdict recorded through the
    REAL producer CLI. At HEAD the return is allowed for the WRONG reason (silently,
    before the veto), so the allow is real but vacuous; the cure makes the allow
    CONDITIONAL on the recorded verdict. AT-3 pins the happy-path allow (no block
    body on stdout) so the cure cannot satisfy AT-1/AT-2 by blocking
    unconditionally. (At HEAD AT-3 passes for the wrong reason; it is the GREEN
    anchor the cure must preserve while making AT-1/AT-2 go green -- the
    discriminating pair.)
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process, run_hook_in_process

from des.adapters.drivers.hooks.hook_router import main as _hook_router_main

from .domain_types import ReviewState, WaveClosure
from .floor_fixture import activate_des_governance, arm_design_floor


# The production des dispatcher module (single entry point) -- drives the REAL
# producer CLI (`des record-design-review`).
_DES_MODULE = "des.cli.__main__"

# The REAL Claude Code hook adapter module + the subagent-stop command, invoked
# exactly as Claude Code dispatches the hook in production (the SubagentStop hook
# is NOT a `des` dispatcher subcommand -- it is a hook adapter entry point).
_HOOK_ADAPTER_MODULE = "des.adapters.drivers.hooks.claude_code_hook_adapter"
_SUBAGENT_STOP_COMMAND = "subagent-stop"

# The wave whose review veto must fire under autonomous orchestration (keystone).
_DESIGN_WAVE = "design"

# The synthetic feature under gate, provisioned in the tmp work-tree.
_GATED_FEATURE_ID = "synthetic-orchestrated-design-feature"

# The reviewer whose verdict the DESIGN producer records (brief / DDD-5).
_REVIEWER_AGENT_ID = "nw-solution-architect-reviewer"

# The SubagentStop hook protocol observable (subagent_stop_handler.py:1686-1743):
# the hook ALWAYS exits 0; the block-vs-allow decision is carried as a
# ``{"decision": "block"|"allow", "reason": ...}`` JSON body on stdout (a non-zero
# exit makes Claude Code IGNORE stdout, so the decision must ride the body). The
# block reason text is the named-LOUD veto reason the operator reads -- the
# observable Mandate-13 surface for the wave-closure decision.
_DECISION_BLOCK = "block"


@dataclass
class HookResult:
    """Observable outcome of one subagent-stop hook subprocess invocation."""

    exit_code: int
    stdout: str
    stderr: str

    @property
    def decision(self) -> str | None:
        """Parse the ``decision`` field off the hook's JSON-stdout body.

        ``None`` when stdout carries no parseable decision body (the allow path
        emits no body; the cure's allow path likewise emits none).
        """
        for line in reversed(self.stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "decision" in payload:
                value = payload.get("decision")
                return value if isinstance(value, str) else None
        return None

    @property
    def block_reason(self) -> str:
        """The block decision's ``reason`` text (empty when not a block body)."""
        for line in reversed(self.stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("decision") == _DECISION_BLOCK:
                reason = payload.get("reason")
                return reason if isinstance(reason, str) else ""
        return ""

    @property
    def closure(self) -> WaveClosure:
        """Project the hook's stdout decision body onto the wave-closure decision.

        REFUSED iff the hook emitted a ``{"decision": "block"}`` body (the veto
        fired); ALLOWED otherwise (no block body -- the return closes the wave).
        The hook exit code is NOT the discriminant (it is always 0).
        """
        if self.decision == _DECISION_BLOCK:
            return WaveClosure.REFUSED
        return WaveClosure.ALLOWED


def _run_module(
    module: str, argv: list[str], *, cwd: Path, stdin: str = ""
) -> HookResult:
    """Drive a production entry point IN-PROCESS under ``cwd`` (faithful analogue).

    The prior implementation forked ``python -m <module> <argv>``. Two module
    classes are driven here, both replaced by the shared in-process driver:

      * the REAL Claude Code hook adapter (``_HOOK_ADAPTER_MODULE``) -- driven via
        ``run_hook_in_process`` over the REAL ``hook_router.main`` with the SAME
        argv + stdin, so the production activation gate (armed by
        ``activate_des_governance``) runs before dispatch exactly as in the
        subprocess. Driving the router directly avoids the adapter facade's
        decision-irrelevant import-time freshness gate (stderr-only, uncaptured by
        any assertion here);
      * the ``des`` dispatcher CLI (the ``record-<wave>-review`` producer) --
        driven via ``run_cli_in_process`` over the real ``des.cli.__main__`` main.

    ``NWAVE_FRESHNESS=skip`` / ``PIPENV_DONT_LOAD_ENV`` are set around the call and
    restored in ``finally`` (shared-process safe). ``PYTHONPATH`` was a subprocess
    import-resolution concern only (``des`` is already importable in-process) -- a
    no-op here. The process is still exercised as a black box: exit code + stdout
    (+ stderr) are the only observables (Mandate-13 Layer 3 composition).

    ``DES_PROJECT_DIR`` is ALSO mirrored to ``cwd`` here: `resolve_nwave_root()`
    (now consulted by `activation_gate.apply_gate` and `pre_tool_use_handler`'s
    peek_entry/arm_inferred/clear_entry) must resolve the SAME root this call
    chdir's to (where `activate_des_governance`/`arm_design_floor` seeded state),
    not the per-test isolation root the autouse `_isolate_nwave_root` fixture sets
    (tests/conftest.py).
    """
    prior_env = {
        key: os.environ.get(key)
        for key in ("NWAVE_FRESHNESS", "PIPENV_DONT_LOAD_ENV", "DES_PROJECT_DIR")
    }
    os.environ["NWAVE_FRESHNESS"] = "skip"
    os.environ["PIPENV_DONT_LOAD_ENV"] = "1"
    os.environ["DES_PROJECT_DIR"] = str(cwd)
    try:
        if module == _HOOK_ADAPTER_MODULE:
            exit_code, stdout, stderr = run_hook_in_process(
                _hook_router_main,
                stdin_text=stdin,
                cwd=cwd,
                argv=["claude_code_hook_adapter", *argv],
            )
        else:
            exit_code, stdout, stderr = run_cli_in_process(argv, cwd=cwd)
    finally:
        for key, value in prior_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    return HookResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


@dataclass
class WaveGateoutComposition:
    """Drives the wave-gateout reachability cure through its real wired seams.

    Operates on a tmp work-tree carrying the armed DESIGN floor + the feature-delta
    the verdict seals against + the AT-completion ledger the verdict is recorded
    into. The orchestration return is a wave-only stdin payload fed to the REAL
    ``subagent-stop`` hook subcommand.
    """

    repo_dir: Path
    feature_id: str = field(default=_GATED_FEATURE_ID)
    _review_state: ReviewState = field(default=ReviewState.NONE)
    _record_result: HookResult | None = field(default=None)
    _hook_result: HookResult | None = field(default=None)

    def __post_init__(self) -> None:
        # ADR-AG-001 precondition: opt the synthetic project into DES governance
        # so the hook DISPATCHES into the production handler instead of the
        # activation gate silencing it (exit 0) before the wave gate-out runs.
        activate_des_governance(self.repo_dir)

    # ---- paths --------------------------------------------------------------

    @property
    def _feature_delta_path(self) -> Path:
        return self.repo_dir / "docs" / "feature" / self.feature_id / "feature-delta.md"

    @property
    def _transcript_path(self) -> Path:
        return self.repo_dir / ".nwave" / "_at" / "wave_only_transcript.json"

    # ---- given: the orchestration return precondition state ------------------

    def given_architect_returning_under_orchestration(self) -> None:
        """Provision the tmp DESIGN feature + arm the DESIGN floor (precondition).

        Precondition state ONLY (NOT the SUT): a docs/feature/<id>/feature-delta.md
        the verdict seals against, an armed DESIGN wave floor (the active-wave
        discriminant the gate-out keys on, never self-reported), and a wave-only
        agent transcript (a DESIGN wave marker + a project id, NO execution-log step
        identifier -- the shape an Agent()-dispatched architect return carries).
        No fixture authors any verdict here -- the ledger stays empty until a When
        records one through the REAL producer CLI.
        """
        self._feature_delta_path.parent.mkdir(parents=True, exist_ok=True)
        self._feature_delta_path.write_text(
            "# Feature Delta: synthetic orchestrated DESIGN feature fixture\n\n"
            "## Wave: DESIGN\n\n"
            "### [REF] Inherited commitments\n\n"
            "| Origin | Commitment | DDD | Impact |\n"
            "|--------|------------|-----|--------|\n"
            "| n/a | a synthetic DESIGN deliverable the gate seals against | n/a | "
            "the bytes the review verdict's content seal binds to |\n",
            encoding="utf-8",
        )
        # Arm the DESIGN wave floor (the active-wave discriminant the gate-out reads
        # from .nwave/wave-active at the return's cwd -- never self-reported). The
        # domain VO is constructed in the fixture helper (OUTSIDE this composition
        # root, Mandate-13 import boundary); the arming still goes through the REAL
        # WaveActiveFilesystemStore adapter (no mock).
        arm_design_floor(self.repo_dir, _DESIGN_WAVE)
        # Construct the wave-only agent transcript (the Agent() return shape).
        self._write_wave_only_transcript()

    def _write_wave_only_transcript(self) -> None:
        """Write a wave-only agent transcript: DES-WAVE + DES-PROJECT-ID, no step-id.

        The marker subset an Agent()-dispatched DESIGN architect return carries:
        the validation marker + a DESIGN wave marker + a project id + the project
        root, but deliberately NO ``DES-STEP-ID`` and NO atdd_pure markers. Today
        this subset resolves to ``None`` in ``extract_des_context_from_transcript``
        (neither classic nor atdd_pure) -> the passthrough-allow that is the bug.
        """
        markers = (
            "<!-- DES-VALIDATION : required -->\n"
            f"<!-- DES-WAVE : {_DESIGN_WAVE} -->\n"
            f"<!-- DES-PROJECT-ID : {self.feature_id} -->\n"
            f"<!-- DES-PROJECT-ROOT : {self.repo_dir} -->\n"
        )
        transcript_line = json.dumps(
            {"type": "assistant", "message": {"role": "assistant", "content": markers}}
        )
        self._transcript_path.parent.mkdir(parents=True, exist_ok=True)
        self._transcript_path.write_text(transcript_line + "\n", encoding="utf-8")

    def given_review_recorded(self, state: ReviewState) -> None:
        """Record the architect's review verdict via the REAL producer CLI, or not.

        ``ReviewState.NONE`` leaves the ledger empty (the un-reviewed deliverable).
        ``ReviewState.APPROVED`` drives the REAL ``des record-design-review``
        producer CLI to append an approved verdict sealed against the feature-delta
        (No Fixture Theater -- the test never writes a verdict directly).
        """
        self._review_state = state
        if state is ReviewState.NONE:
            return
        self._record_result = _run_module(
            _DES_MODULE,
            [
                "record-design-review",
                "--feature-id",
                self.feature_id,
                "--verdict",
                "approved",
                "--reviewer-agent-id",
                _REVIEWER_AGENT_ID,
                "--repo-root",
                str(self.repo_dir),
            ],
            cwd=self.repo_dir,
        )

    # ---- when: the orchestration return is evaluated at the wave boundary ----

    def when_orchestration_return_evaluated(self) -> None:
        """Drive the REAL subagent-stop hook with the wave-only return on stdin.

        Feeds the Claude Code hook protocol payload (an Agent() return: agent
        transcript path + cwd, no direct DES execution-log fields) to the REAL
        ``des subagent-stop`` hook subcommand, which routes through the production
        composition root into ``SubagentStopService.validate``. The observable is
        the hook decision projected onto the process exit code.
        """
        hook_input = {
            "agent_type": "nw-solution-architect",
            "agent_id": "at-orchestrated-architect",
            "agent_transcript_path": str(self._transcript_path),
            "cwd": str(self.repo_dir),
        }
        self._hook_result = _run_module(
            _HOOK_ADAPTER_MODULE,
            [_SUBAGENT_STOP_COMMAND],
            cwd=self.repo_dir,
            stdin=json.dumps(hook_input),
        )

    # ---- then: the projected wave-closure decision ---------------------------

    def then_wave_closure_refused(self) -> None:
        """The orchestration return is REFUSED (the review veto fired).

        Seam-named oracle (Mandate-15 seam-1): a wave-only DESIGN return with NO
        recorded review verdict must reach ``SubagentStopService.validate`` so the
        ``_gate_out_review_verdict`` veto refuses it (absence reads as a refusal --
        degrade-LOUD, never a silent pass). The observable is the hook's stdout
        decision body: a refusal emits ``{"decision": "block"}``. RED at HEAD: the
        return never reaches the veto (``_resolve_des_context`` returns the
        passthrough-allow before ``validate`` runs), so the hook emits NO block
        body -> the observed closure is ALLOWED, not REFUSED -> a semantic
        AssertionError naming the unreachable gate-out.
        """
        self._assert_closure(WaveClosure.REFUSED)

    def then_wave_closure_refused_unreviewed(self) -> None:
        """The refusal NAMES the missing-review reason (same seam, sharpened oracle).

        AT-2 sharpens AT-1: the refusal must specifically be the review-verdict veto
        refusing an ABSENT review (the wave cannot close because it was never
        reviewed), NOT some incidental block. The observable is the hook's stdout
        block body AND its ``reason`` text: it must NAME the DESIGN review-verdict
        gate-out reason over the absent ledger record -- the cure's
        ``_gate_out_review_verdict`` emits ``DESIGN_REVIEW_INDETERMINATE: design
        review verdict absent`` (subagent_stop_service.py:427-430 over
        ReviewVerdictGate.evaluate(None) -> INDETERMINATE("absent")). RED at HEAD:
        the return is silently allowed (no block body at all), so BOTH the block
        AND the reason-naming assertions fail as MISSING_FUNCTIONALITY -- the named
        missing-review reason never appears.
        """
        self._assert_closure(
            WaveClosure.REFUSED,
            reason_must_name=(
                # the named gate-out seam (review-verdict gate over the DESIGN wave)
                "review verdict",
                # the specific missing-review reason (degrade-LOUD on the absent
                # ledger record -- "missing review read as refusal, never silent
                # pass"); never a bare incidental block
                "absent",
            ),
        )

    def then_wave_closure_allowed(self) -> None:
        """The orchestration return is ALLOWED (an approved review was recorded).

        AT-3 (happy path): after an artefact-current APPROVED verdict is recorded
        through the REAL producer CLI, the wave-only return reaches the gate-out and
        the review-verdict veto finds "no objection" -> the hook allows (no block
        body on stdout). This pins the discriminating allow so the cure cannot
        satisfy AT-1/AT-2 by blocking unconditionally. (At HEAD the allow is real
        but vacuous -- the return is allowed silently before the veto runs; the cure
        makes the allow conditional on the recorded verdict.)
        """
        self._assert_review_recorded_cleanly()
        self._assert_closure(WaveClosure.ALLOWED)

    # ---- assertion helpers ---------------------------------------------------

    def _assert_closure(
        self,
        expected: WaveClosure,
        *,
        reason_must_name: tuple[str, ...] = (),
    ) -> None:
        result = self._hook_result
        assert result is not None, (
            "the orchestration return must be evaluated at the wave boundary (When) "
            "before asserting the wave-closure decision (Then)"
        )
        assert result.closure is expected, (
            "the wave-only DESIGN return (a DES-WAVE marker + a project id, no "
            "execution-log step id -- the Agent() orchestration return shape) must "
            "reach SubagentStopService.validate so the DESIGN review veto projects "
            f"the wave closure as {expected.value!r} onto the hook's stdout decision "
            'body (REFUSED -> {"decision":"block"}, ALLOWED -> no block body); '
            "the reachability route does not exist yet, so _resolve_des_context "
            "(subagent_stop_handler.py:209) returns the passthrough-allow BEFORE "
            "validate runs (:274-275) -- the gate-out never fires and the hook "
            f"observed closure {result.closure.value!r} (decision={result.decision!r}). "
            f"{self._observed()}"
        )
        if reason_must_name:
            reason = result.block_reason.lower()
            missing = [
                token for token in reason_must_name if token.lower() not in reason
            ]
            assert not missing, (
                "the refusal must NAME the missing-review reason (the DESIGN "
                "review-verdict gate-out reading an absent verdict as a refusal -- "
                "never a silent pass), not merely emit a bare block. The hook's "
                f"block reason must contain {list(reason_must_name)!r}; it is "
                f"missing {missing!r}. The cure's _gate_out_review_verdict emits "
                "'DESIGN_REVIEW_INDETERMINATE: design review verdict absent' "
                "(subagent_stop_service.py:427-430). RED at HEAD: the return is "
                "silently allowed before the veto runs, so no review-verdict reason "
                f"appears at all. observed_reason={result.block_reason[:300]!r}. "
                f"{self._observed()}"
            )

    def _assert_review_recorded_cleanly(self) -> None:
        record = self._record_result
        assert record is not None, (
            "AT-3 must record an approved review via the REAL `des "
            "record-design-review` producer CLI (When) before asserting the allow"
        )
        assert record.exit_code == 0, (
            "the `des record-design-review` producer CLI must record the architect's "
            "approved verdict cleanly (exit 0) so the gate-out has an artefact-current "
            f"verdict to read -- the producer exited {record.exit_code}. "
            f"record_stderr={record.stderr[:200]!r}"
        )

    # ---- diagnostics --------------------------------------------------------

    def _observed(self) -> str:
        hook = self._hook_result
        return (
            f"review_state={self._review_state.value}; "
            f"floor_armed={(self.repo_dir / '.nwave' / 'wave-active' / 'active.json').is_file()}; "
            f"feature_delta_exists={self._feature_delta_path.is_file()}; "
            "hook=(exit="
            + (str(hook.exit_code) if hook else "n/a")
            + ", decision="
            + (repr(hook.decision) if hook else "n/a")
            + ", stdout="
            + (repr(hook.stdout[:300]) if hook else "n/a")
            + ", stderr="
            + (repr(hook.stderr[:300]) if hook else "n/a")
            + ")"
        )
