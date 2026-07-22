"""Regression AT -- fix-feature-end-examine-agent.

DEFECT, reproduced verbatim (task DES-PROJECT-ID fix-feature-end-examine-agent):

    des dispatch --mode atdd_pure --project-id codefact-similar-responsibility \
        --slice feature-end --phase FEATURE_END_EXAMINE --wave feature-end \
        --intent "..."

emits ``Agent: nw-software-crafter`` (WRONG -- must be ``nw-user-examiner``)
plus a crafter-shaped ``QUALITY_GATES`` / ``TERMINATING_RUN`` /
``TIMEOUT_INSTRUCTION`` body. Vera the examiner's entire epistemic value is
that she CANNOT read source -- her verdict comes from observed behaviour. A
crafter reads source by definition. The envelope is handed over VERBATIM
(that IS the discipline), so an "examination" is silently performed by the
author of the code, with no gate noticing.

RCA (confirmed, file:line, ``src/des/cli/dispatch.py`` on this checkout):

  * Cause A (:168-172, :243-259) -- ``_PHASE_AGENTS`` maps ``D_DISTILL``,
    ``C_REVIEWER_AUDIT``, ``FEATURE_END_RETURN_PHASE`` (``F_FINAL_REVIEW``).
    ``FEATURE_END_EXAMINE`` is ABSENT, so ``_resolve_agent`` falls through to
    ``_DEFAULT_AGENT`` = ``"nw-software-crafter"``.
  * Cause B (:557-598) -- independent, and ALREADY live today for the
    correctly-routed ``C_REVIEWER_AUDIT``: ``QUALITY_GATES`` /
    ``TERMINATING_RUN`` / ``TIMEOUT_INSTRUCTION`` branch ONLY on the
    ``runs_tests`` bool, never on ``agent`` -- so those three sections stay
    crafter-shaped for a non-code-facing dispatch regardless of who is
    named. By contrast ``SKILL_LOADING`` (``_skill_loading_body``) and
    ``DESIGN_CONTEXT`` (``_design_context_body``) ARE already role-aware via
    the existing ``_NON_CODE_FACING_AGENTS`` frozenset and adapt correctly
    today.
  * Cause C (the class) -- a phase absent from ``_PHASE_AGENTS`` degrades
    SILENTLY toward the PERMISSIVE default (the crafter), never loudly.

The fix this AT pins (crafter's job, NOT implemented here):
  (a) add ``ATDDPurePhase.FEATURE_END_EXAMINE.value: _EXAMINER_AGENT`` to
      ``_PHASE_AGENTS``;
  (b) make ``QUALITY_GATES`` / ``TERMINATING_RUN`` / ``TIMEOUT_INSTRUCTION``
      role-aware via the SAME ``_NON_CODE_FACING_AGENTS`` set, mirroring
      ``_skill_loading_body``'s shape;
  (c) replace the unconditional ``_DEFAULT_AGENT`` phase fallback with a
      closed-world check (an explicit crafter-default allowlist) and a LOUD
      refusal (GDP-3/GDP-6: WHAT/WHY/HOW) for any phase in neither map.

Driving surface (Mandate 2/16, driving-port-only, default IN-PROCESS): every
assertion drives the REAL ``des dispatch`` CLI entry in-process via
``tests/common/in_process_cli.run_cli_in_process`` (the in-process analogue
of ``python -m des.cli.__main__ dispatch ...``) against THIS checkout's real
``nWave/dispatch/atdd_pure.yaml`` SSOT -- no mocking of the prompt builder --
mirroring the established convention across every sibling
``tests/bugs/des/test_dispatch_*.py`` file. The ONE exception is the LOUD-
REFUSAL leg (requirement 4): argparse fences ``--phase`` to the canonical 6
values, so an unmapped phase string cannot reach the CLI at all -- that leg
drives ``dispatch._resolve_agent`` directly, the seam the dispatch
instruction names for this reason.

RED-for-right-reason (current state, real semantic ``AssertionError``, never
an import/collection error):
  * the ``FEATURE_END_EXAMINE`` row of the exhaustive phase->agent table is
    RED (names ``nw-software-crafter``, expects ``nw-user-examiner``);
  * the class-level role-coherent-body negative AT is RED for BOTH
    parametrized legs (``FEATURE_END_EXAMINE`` -- Cause A + B compounded;
    ``C_REVIEWER_AUDIT`` -- Cause B alone, already-correctly-routed agent
    but still crafter-shaped ``QUALITY_GATES``/``TERMINATING_RUN``/
    ``TIMEOUT_INSTRUCTION``);
  * the loud-refusal leg is RED (today ``_resolve_agent`` silently returns
    the crafter default for ANY unmapped phase, never raises);
  * the exhaustiveness witness, the negative controls (``A_GREEN``,
    ``D_REFACTOR_COMMIT``), the generality leg's non-``FEATURE_END_EXAMINE``
    rows, and the no-new-stderr-warning control are already GREEN today and
    must stay GREEN after the fix.

covers: fix-feature-end-examine-agent
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli import dispatch
from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# established convention in every sibling test_dispatch_*.py file).
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _run_dispatch(argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=_REPO_ROOT)


def _agent_identity_line(stdout: str) -> str:
    """Extract the `Agent: ...` line following the `# AGENT_IDENTITY` header
    (established helper shape, mirrors every sibling test_dispatch_*.py)."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "# AGENT_IDENTITY":
            for following in lines[index + 1 :]:
                if following.startswith("Agent:"):
                    return following
            return ""
    return ""


def _phase_argv(*, phase: str, project_id: str = "probe-x") -> list[str]:
    """Build a dispatch argv for `phase`, choosing the ONLY coherent slice
    scope (feature-end for a FEATURE_END_PHASES member, slice-01 otherwise --
    the generator auto-corrects a mismatched slice anyway, ADR-028 D6)."""
    slice_id = "feature-end" if phase in FEATURE_END_PHASES else "slice-01"
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        "--phase",
        phase,
        "--intent",
        "x",
        "--repo-root",
        str(_REPO_ROOT),
    ]


def _feature_end_examine_argv(*, project_id: str) -> list[str]:
    """The EXACT reported repro shape (`--wave feature-end` included), used
    by the generality leg (requirement 5) -- deliberately distinct from
    `_phase_argv` (which omits `--wave`, matching the D_DISTILL sibling
    convention) so this file also pins the literal reported command."""
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        "feature-end",
        "--phase",
        "FEATURE_END_EXAMINE",
        "--wave",
        "feature-end",
        "--intent",
        "examine the finished feature",
        "--repo-root",
        str(_REPO_ROOT),
    ]


def _stderr_carries_no_new_refusal(stderr: str) -> bool:
    """True iff every non-blank stderr line is a pre-existing readiness
    ADVISORY (starts with 'advisory:') -- never a NEW refusal/warning the
    agent-routing fix might introduce as an unintended regression on an
    already-succeeding dispatch."""
    return all(
        line.startswith("advisory:") for line in stderr.splitlines() if line.strip()
    )


# ---------------------------------------------------------------------------
# Requirement 1 -- EXHAUSTIVE PHASE -> AGENT table, derived from the
# production SSOT (`dispatch._canonical_phase_values()`), never a
# hand-copied literal list of phases. The expectation table below (phase ->
# agent) is the one explicit thing in this test; a phase present in the
# production SSOT but absent from it fails loudly, by name, in the
# exhaustiveness witness immediately following.
# ---------------------------------------------------------------------------

_EXPECTED_AGENT_BY_PHASE: dict[str, str] = {
    "A_GREEN": "nw-software-crafter",
    "D_REFACTOR_COMMIT": "nw-software-crafter",
    "C_REVIEWER_AUDIT": "nw-user-examiner",
    "D_DISTILL": "nw-acceptance-designer",
    "FEATURE_END_EXAMINE": "nw-user-examiner",
    "F_FINAL_REVIEW": "nw-software-crafter-reviewer",
}


def test_expectation_table_covers_every_canonical_phase() -> None:
    """Exhaustiveness witness: a phase present in the production
    `dispatch._canonical_phase_values()` SSOT (the SAME set argparse's
    `--phase` choices resolves from) but ABSENT from
    `_EXPECTED_AGENT_BY_PHASE` must FAIL loudly, naming the unmapped phase --
    this is what makes requirement 1 EXHAUSTIVE rather than six independent
    examples: a future 7th phase cannot be added to the generator without a
    deliberate decision being pinned here.
    """
    live_phases = set(dispatch._canonical_phase_values())
    unmapped = live_phases - set(_EXPECTED_AGENT_BY_PHASE)
    assert not unmapped, (
        f"phase(s) {sorted(unmapped)!r} are generable by `des dispatch` "
        "(present in dispatch._canonical_phase_values()) but have NO "
        "expected-agent entry in this test's _EXPECTED_AGENT_BY_PHASE table "
        "-- a phase was added to the dispatch SSOT without a deliberate "
        "agent-routing decision being pinned in THIS test. Add the phase's "
        "expected agent to _EXPECTED_AGENT_BY_PHASE."
    )


@pytest.mark.parametrize("phase", sorted(dispatch._canonical_phase_values()))
def test_dispatch_names_expected_agent_per_phase(phase: str) -> None:
    """Every canonical, generable phase's `AGENT_IDENTITY` line must name
    EXACTLY the expected agent from `_EXPECTED_AGENT_BY_PHASE` -- RED today
    only for `FEATURE_END_EXAMINE` (names `nw-software-crafter`, expects
    `nw-user-examiner`); every other row is already correctly routed.
    """
    expected_agent = _EXPECTED_AGENT_BY_PHASE.get(phase)
    assert expected_agent is not None, (
        f"phase {phase!r} has no expected-agent entry -- see "
        "test_expectation_table_covers_every_canonical_phase for the "
        "authoritative exhaustiveness failure."
    )

    exit_code, stdout, stderr = _run_dispatch(
        _phase_argv(phase=phase, project_id=f"probe-agent-{phase.lower()}")
    )
    assert exit_code == 0, (
        f"dispatch generation for phase {phase!r} must succeed before its "
        f"AGENT_IDENTITY can be inspected -- exit_code={exit_code}, "
        f"stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)
    assert f"Agent: {expected_agent}" == agent_identity_line.strip(), (
        f"phase {phase!r} must name '{expected_agent}' in AGENT_IDENTITY -- "
        f"got line={agent_identity_line!r} from stdout={stdout!r} "
        f"(exit_code={exit_code}, stderr={stderr!r})"
    )


# ---------------------------------------------------------------------------
# Requirement 2 -- ROLE-COHERENT BODY, class-level negative AT: for a
# dispatch resolving to a NON-CODE-FACING agent, the FULL rendered envelope
# must carry NO crafter-role language, AND must carry a positive instruction
# to observe/exercise the real surface and report a verdict.
# ---------------------------------------------------------------------------

_CRAFTER_ROLE_FORBIDDEN_TOKENS: tuple[str, ...] = (
    "crafter",
    "ATs are green",
    "files created/modified",
    "No new tests authored",
    "nw-tdd-methodology",
)

#: Tolerant, meaning-based positive markers (NOT one exact sentence the fix
#: must reproduce byte-for-byte) -- the examiner envelope must instruct her
#: to exercise the real product surface and report what she observed.
_OBSERVE_AND_REPORT_MARKERS: tuple[str, ...] = (
    "observ",  # observe / observed / observing / observation
    "exercise the real",
    "real product surface",
    "verdict",
    "what you saw",
    "report what",
)


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "argv,description",
    [
        pytest.param(
            _feature_end_examine_argv(project_id="probe-role-fe-examine"),
            "FEATURE_END_EXAMINE (Cause A + Cause B compounded)",
            id="feature-end-examine",
        ),
        pytest.param(
            _phase_argv(phase="C_REVIEWER_AUDIT", project_id="probe-role-c-reviewer"),
            "C_REVIEWER_AUDIT (Cause B alone -- agent already correctly routed)",
            id="c-reviewer-audit",
        ),
    ],
)
def test_non_code_facing_envelope_carries_no_crafter_role_language(
    argv: list[str], description: str
) -> None:
    """NEGATIVE AT: a dispatch resolving to a non-code-facing agent must
    never carry crafter-role language ANYWHERE in the rendered envelope --
    not just in AGENT_IDENTITY. RED today for BOTH parametrized legs (see
    module docstring for why each is RED).
    """
    exit_code, stdout, stderr = _run_dispatch(argv)
    assert exit_code == 0, (
        f"dispatch generation must succeed for {description} before its body "
        f"can be inspected -- exit_code={exit_code}, stderr={stderr!r}"
    )

    for token in _CRAFTER_ROLE_FORBIDDEN_TOKENS:
        assert token not in stdout, (
            f"NEGATIVE AT: a non-code-facing envelope ({description}) must "
            f"never carry crafter-role language -- found forbidden token "
            f"{token!r} in the generated envelope. stdout={stdout!r}"
        )

    lowered = stdout.lower()
    assert any(marker in lowered for marker in _OBSERVE_AND_REPORT_MARKERS), (
        f"POSITIVE: the non-code-facing envelope ({description}) must "
        "instruct the examiner to exercise/observe the real product surface "
        "and report a verdict on what she observed -- none of "
        f"{_OBSERVE_AND_REPORT_MARKERS!r} were found (case-insensitive) in "
        f"the generated envelope. stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# Requirement 3 -- NEGATIVE CONTROL (no-overcorrection): a code-facing
# crafting phase must STILL name the crafter and STILL carry its
# crafter-shaped bodies. Must be GREEN both before AND after the fix.
# ---------------------------------------------------------------------------

_CRAFTER_SHAPED_MARKERS: tuple[str, ...] = (
    "No new tests authored by the crafter",
    "STOP after the ATs are green",
)


@pytest.mark.parametrize("phase", ["A_GREEN", "D_REFACTOR_COMMIT"])
def test_code_facing_phase_still_names_crafter_with_crafter_shaped_body(
    phase: str,
) -> None:
    """POSITIVE CONTROL: `A_GREEN` and `D_REFACTOR_COMMIT` (code-facing
    crafting phases) must keep naming `nw-software-crafter` AND keep their
    crafter-shaped `QUALITY_GATES`/`TIMEOUT_INSTRUCTION` bodies -- the fix
    routes ONLY the non-code-facing phases differently, it must never
    misroute or reword an implementation phase's envelope.
    """
    exit_code, stdout, stderr = _run_dispatch(
        _phase_argv(phase=phase, project_id=f"probe-control-{phase.lower()}")
    )
    assert exit_code == 0, (
        f"dispatch generation for phase {phase!r} must succeed -- "
        f"exit_code={exit_code}, stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)
    assert agent_identity_line.strip() == "Agent: nw-software-crafter", (
        f"phase {phase!r} must still name nw-software-crafter -- got "
        f"line={agent_identity_line!r} from stdout={stdout!r}"
    )
    for marker in _CRAFTER_SHAPED_MARKERS:
        assert marker in stdout, (
            f"phase {phase!r} must keep its crafter-shaped body -- expected "
            f"marker {marker!r} not found. stdout={stdout!r}"
        )


# ---------------------------------------------------------------------------
# Requirement 4 -- THE LOUD REFUSAL (fix c): a phase in neither
# `_PHASE_AGENTS` nor a crafter-default allowlist must be refused LOUDLY,
# never silently resolved to the crafter default. argparse fences `--phase`
# to the canonical 6 values, so an unmapped phase string cannot reach the
# CLI at all -- this leg drives `dispatch._resolve_agent` directly, the seam
# the dispatch instruction names for exactly this reason.
# ---------------------------------------------------------------------------


def test_unmapped_phase_refused_loudly_not_silently_defaulted() -> None:
    """RED today: `_resolve_agent` silently returns `_DEFAULT_AGENT` for ANY
    phase absent from `_PHASE_AGENTS`, with no distinction between a
    legitimate crafter-default phase and a typo/unknown one. Deliberately
    asserts on OBSERVABLE behaviour (raises vs. does not raise) rather than
    a specific exception type or class -- the simplest assertable shape,
    since the not-yet-written fix's exact exception class is not this test's
    business to dictate.
    """
    unmapped_phase = "ZZZ_UNMAPPED_PHASE_PROBE"
    assert unmapped_phase not in dispatch._PHASE_AGENTS, (
        "fixture problem: the probe phase must not already be a real mapped "
        "phase, or this test is vacuous"
    )

    raised: Exception | None = None
    resolved_silently: str | None = None
    try:
        resolved_silently = dispatch._resolve_agent(unmapped_phase, None, "deliver")
    except Exception as exc:
        raised = exc

    assert raised is not None, (
        "an unmapped phase must be refused LOUDLY (raise), never silently "
        f"resolved to a default agent -- got resolved_silently="
        f"{resolved_silently!r} with NO exception raised for "
        f"phase={unmapped_phase!r}"
    )

    message = str(raised)
    assert unmapped_phase in message, (
        f"the refusal must NAME the offending phase (GDP-3 WHAT) -- "
        f"got message={message!r}"
    )
    assert any(
        word in message.lower() for word in ("unmapped", "unknown", "no agent", "not")
    ), (
        f"the refusal must explain WHY the phase was refused (GDP-3 WHY) -- "
        f"got message={message!r}"
    )
    assert any(
        word in message.lower()
        for word in ("add", "map", "_phase_agents", "fix", "register")
    ), f"the refusal must say HOW to fix it (GDP-3 HOW) -- got message={message!r}"


# ---------------------------------------------------------------------------
# Requirement 5 -- GENERALITY: the corrected behaviour must not be keyed to
# one feature-id. Parametrize the FEATURE_END_EXAMINE leg over multiple
# --project-id values, including one invented string never used in
# diagnosis.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "project_id",
    [
        "codefact-similar-responsibility",  # the exact reported repro id
        "fix-feature-end-examine-agent",  # this feature's own id
        "zzz-never-used-in-diagnosis-probe",  # invented, unseen id
    ],
)
def test_feature_end_examine_names_examiner_across_feature_ids(
    project_id: str,
) -> None:
    """The `FEATURE_END_EXAMINE` fix must not be keyed to one feature-id --
    parametrized over the EXACT reported repro id, this feature's own id, and
    a wholly invented id never used during diagnosis. All three must name
    `nw-user-examiner` after the fix; all three are RED today.
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_examine_argv(project_id=project_id)
    )
    assert exit_code == 0, (
        f"dispatch generation must succeed for project_id={project_id!r} -- "
        f"exit_code={exit_code}, stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)
    assert agent_identity_line.strip() == "Agent: nw-user-examiner", (
        f"FEATURE_END_EXAMINE for project_id={project_id!r} must name "
        f"nw-user-examiner -- got line={agent_identity_line!r} from "
        f"stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# Requirement 6 -- NO NEW WARNING/REFUSAL on a previously-working dispatch.
# A dispatch that succeeds today must still exit 0 and must not gain a new
# stderr warning. The pre-existing feature-delta readiness ADVISORY (a
# feature with no feature-delta.md) is legitimate and must be preserved,
# never accidentally pinned away.
# ---------------------------------------------------------------------------


def test_feature_end_examine_dispatch_exits_zero_with_no_new_stderr_refusal() -> None:
    """POSITIVE CONTROL (must stay GREEN both before AND after the fix): the
    `FEATURE_END_EXAMINE` dispatch already succeeds (exit 0) today -- the fix
    corrects WHO it names and WHAT the body says, it must not introduce a new
    refusal/warning as a side effect. The pre-existing readiness advisory
    (no feature-delta.md for a fresh probe id) is expected and preserved.
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_examine_argv(project_id="probe-no-regression")
    )
    assert exit_code == 0, (
        "a dispatch that succeeds today must still exit 0 after the fix -- "
        f"exit_code={exit_code}, stderr={stderr!r}"
    )
    assert stdout != "", "a successful dispatch must still emit a usable envelope"
    assert _stderr_carries_no_new_refusal(stderr), (
        "a dispatch that already succeeds today must not gain a NEW "
        "warning/refusal on stderr as a side effect of the agent-routing "
        "fix -- the pre-existing feature-delta readiness ADVISORY is "
        f"legitimate and must be preserved, but nothing else. stderr={stderr!r}"
    )
