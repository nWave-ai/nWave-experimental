"""Regression AT -- fix-dispatched-agent-background-job-never-wakes.

DEFECT, reproduced verbatim (real user report): a DISPATCHED agent that starts
a long command in the BACKGROUND and then ENDS ITS TURN waiting for the
task-notification stalls forever. Background-job notifications are delivered
ONLY to the orchestrator; a subagent never receives one for its own shell job.
Observed: a DISTILL agent backgrounded ``des verify-red-green``, closed its
turn saying it was waiting for the notification, and stayed stopped until the
orchestrator found it with ``pgrep``. The agent is not in error -- it is alive,
coherent, and waiting for an event that by construction never arrives, so from
outside it is INDISTINGUISHABLE from a slow agent and nobody intervenes. A
failure that disguises itself as slowness is not diagnosed, it is waited on.

RCA (confirmed, file:line, ``src/des/cli/dispatch.py`` on this checkout): the
rule is ABSENT from the GENERATED dispatch envelope. ``_section_body``
(:663-769) builds every section body of every prompt ``des dispatch`` emits;
its ``"TIMEOUT_INSTRUCTION"`` entry (:752-767) is the section governing how a
dispatched agent manages its own time and its own termination, and it has
exactly three branches -- (a) non-code-facing agent ->
``_NON_CODE_FACING_TIMEOUT_INSTRUCTION`` (:625-628); (b) ``runs_tests`` -> the
crafter body; (c) else -> the authoring-wave body. NONE of the three mentions
background jobs.

COMMON POINT (verified here, not asserted by hand): ``TIMEOUT_INSTRUCTION`` is
a required section in EVERY dispatch profile -- all 3 ``LANE_PROFILES`` rows
(prefactoring / bugfix / charter) and all 6 ``WAVE_DISPATCH_PROFILES`` rows
(discuss / design / devops / distill / deliver / feature-end, whose
``_AUTHORING_BASE`` comment already calls it "how long they have"). So
``_section_body``'s ``TIMEOUT_INSTRUCTION`` entry IS the single common locus.
``test_timeout_instruction_is_required_by_every_lane_and_wave_profile`` pins
that claim mechanically against the live SSOT data.

The fix this AT pins (crafter's job, NOT implemented here): ONE module-level
constant in ``src/des/cli/dispatch.py``, APPENDED to each of the three
``TIMEOUT_INSTRUCTION`` branch bodies -- never three copies of the prose --
carrying in substance: if you need the result of a long-running command, run it
in the FOREGROUND inside this turn, or poll for it within the SAME turn; never
end your turn waiting for a background job you started, because the
notification reaches the ORCHESTRATOR and never a dispatched agent, so such a
turn waits forever while merely looking slow; backgrounding is an
orchestrator tool, not a dispatched agent's.

Driving surface (Mandate 2/16, driving-port-only, default IN-PROCESS): every
leg drives the REAL ``des dispatch`` CLI entry in-process via
``tests.common.in_process_cli.run_cli_in_process`` (the in-process analogue of
``python -m des.cli.__main__ dispatch ...``) against THIS checkout's real
``nWave/dispatch/atdd_pure.yaml`` SSOT -- no mocking of the prompt builder --
mirroring the established convention across every sibling
``tests/bugs/des/test_dispatch_*.py``. The rule is asserted inside the
EXTRACTED ``# TIMEOUT_INSTRUCTION`` section body (via the validator's own
``_extract_section_body``), never as a substring of the whole prompt: a rule
that lands in some OTHER section is not the fix, because the section a
dispatched agent reads for its own termination discipline is that one.

Assertions key on MEANING, not on one byte-for-byte sentence: five
discriminating token GROUPS (the background notion, the turn-close
prohibition, the notification notion, WHO the notification actually reaches,
and the foreground/poll remedy), each satisfied by any of several
alternatives. A reworded-but-equivalent body still passes; a silently-dropped
rule still fails.

RED-for-right-reason (current state, real semantic ``AssertionError``, never
an import/collection error):
  * ``test_timeout_instruction_forbids_ending_a_turn_on_a_background_job`` is
    RED for EVERY shape in the matrix (all three branches carry none of the
    five token groups today);
  * ``test_timeout_instruction_carries_the_rule_for_every_canonical_phase`` is
    RED for every generable phase;
  * ``test_background_turn_close_rule_is_byte_identical_across_shapes`` is RED
    (today the longest text shared by all shapes is ``"\\nTarget ~60 turns"`` --
    it carries no token group at all);
  * the COMMON-POINT witness, the shape-matrix coverage witness, the
    branch-prose-survives negative AT, the validator-acceptance legs and the
    frozen mandatory-section floor are GREEN today and MUST stay GREEN after
    the fix -- they are what stops the fix being bought by collapsing the
    three branch bodies into one, by adding a new mandatory section, or by
    emitting an envelope the system's own validator then refuses.

covers: fix-dispatched-agent-background-job-never-wakes
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from des.application.atdd_pure_prompt_validator import (
    ATDD_PURE_MANDATORY_SECTIONS,
    AtddPurePromptValidator,
    _extract_section_body,
)
from des.cli import dispatch
from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from des.domain.lane_profile import LANE_PROFILES
from des.domain.wave_dispatch_profile import WAVE_DISPATCH_PROFILES
from tests.common.delivery_contract_fixture import contract_args
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# established convention in every sibling test_dispatch_*.py file).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: The section that governs a dispatched agent's own time + termination. THE
#: single common locus (see the COMMON POINT witness below).
_SECTION = "TIMEOUT_INSTRUCTION"


# ---------------------------------------------------------------------------
# The rule, expressed as MEANING: five discriminating token groups, each
# satisfied by ANY of its alternatives (case-insensitive). This is deliberately
# NOT one exact sentence the fix must reproduce byte-for-byte -- a reworded but
# substantively equivalent body passes; a dropped rule fails.
# ---------------------------------------------------------------------------

_RULE_TOKEN_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "the BACKGROUND notion (what the agent must not do)",
        ("background",),
    ),
    (
        "the TURN-CLOSE prohibition (never end the turn waiting)",
        (
            "end your turn",
            "end the turn",
            "ending your turn",
            "end its turn",
            "ends its turn",
            "close your turn",
            "close the turn",
        ),
    ),
    (
        "the NOTIFICATION notion (the event being waited on)",
        ("notification", "notified", "notify", "notifies"),
    ),
    (
        "WHO the notification actually reaches (the orchestrator)",
        ("orchestrator",),
    ),
    (
        "the REMEDY (run it in the foreground, or poll in the same turn)",
        ("foreground", "poll"),
    ),
)


def _missing_token_groups(text: str) -> list[str]:
    """The names of every rule token group NOT satisfied by ``text``."""
    lowered = text.lower()
    return [
        name
        for name, alternatives in _RULE_TOKEN_GROUPS
        if not any(alternative in lowered for alternative in alternatives)
    ]


# ---------------------------------------------------------------------------
# The dispatch-shape matrix. Exercises all THREE `_section_body`
# TIMEOUT_INSTRUCTION branches:
#   (a) non-code-facing agent  -- FEATURE_END_EXAMINE (examiner), charter lane
#                                 (product owner), --wave discuss (product owner)
#   (b) runs_tests (crafter)   -- A_GREEN / D_REFACTOR_COMMIT / D_DISTILL /
#                                 F_FINAL_REVIEW, bugfix lane, prefactoring lane
#   (c) authoring wave         -- --wave design / devops / distill
# The coverage witness below proves the matrix spans EVERY lane and EVERY wave
# in the live SSOT data, so a lane/wave added later cannot silently escape it.
# ---------------------------------------------------------------------------

#: Appended to every shape. `--delivery-contract` is unused by a phaseless
#: shape (only consumed when `runs_tests` is True) but harmless there --
#: sharing ONE tail keeps the matrix from branching per-shape on a fact the
#: matrix itself does not track.
_TAIL: tuple[str, ...] = ("--intent", "x", *contract_args(_REPO_ROOT, seed=False))


def _argv(
    *,
    project_id: str,
    slice_id: str = "slice-01",
    extra: Sequence[str] = (),
) -> tuple[str, ...]:
    return (
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        slice_id,
        *extra,
        *_TAIL,
    )


_SHAPES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "deliver-a-green-crafter",
        _argv(project_id="probe-bg-a-green", extra=("--phase", "A_GREEN")),
    ),
    (
        "deliver-refactor-commit-crafter",
        _argv(project_id="probe-bg-refactor", extra=("--phase", "D_REFACTOR_COMMIT")),
    ),
    (
        "deliver-distill-acceptance-designer",
        _argv(project_id="probe-bg-distill-phase", extra=("--phase", "D_DISTILL")),
    ),
    (
        "feature-end-examine-examiner",
        _argv(
            project_id="probe-bg-examine",
            slice_id="feature-end",
            extra=("--phase", "FEATURE_END_EXAMINE", "--wave", "feature-end"),
        ),
    ),
    (
        "feature-end-final-review",
        _argv(
            project_id="probe-bg-final-review",
            slice_id="feature-end",
            extra=("--phase", "F_FINAL_REVIEW", "--wave", "feature-end"),
        ),
    ),
    (
        "feature-end-reviewer-audit",
        _argv(
            project_id="probe-bg-reviewer-audit",
            extra=("--phase", "C_REVIEWER_AUDIT"),
        ),
    ),
    (
        "authoring-wave-discuss",
        _argv(project_id="probe-bg-discuss", extra=("--wave", "discuss")),
    ),
    (
        "authoring-wave-design",
        _argv(project_id="probe-bg-design", extra=("--wave", "design")),
    ),
    (
        "authoring-wave-devops",
        _argv(project_id="probe-bg-devops", extra=("--wave", "devops")),
    ),
    (
        "authoring-wave-distill",
        _argv(project_id="probe-bg-distill-wave", extra=("--wave", "distill")),
    ),
    (
        "lane-bugfix",
        _argv(
            project_id="probe-bg-lane-bugfix",
            extra=(
                "--phase",
                "A_GREEN",
                "--lane",
                "bugfix",
                "--defect",
                "a dispatched agent backgrounds a job and never wakes",
                "--regression-test",
                "test_dispatch_forbids_background_turn_close",
            ),
        ),
    ),
    (
        "lane-prefactoring",
        _argv(
            project_id="probe-bg-lane-prefactoring",
            extra=("--phase", "A_GREEN", "--lane", "prefactoring"),
        ),
    ),
    (
        "lane-charter",
        _argv(project_id="probe-bg-lane-charter", extra=("--lane", "charter")),
    ),
)

_SHAPE_PARAMS = tuple(pytest.param(argv, id=shape_id) for shape_id, argv in _SHAPES)


# ---------------------------------------------------------------------------
# Driving-port helpers (in-process, real CLI edge, real SSOT).
# ---------------------------------------------------------------------------

_ENVELOPE_CACHE: dict[tuple[str, ...], str] = {}


def _generate_envelope(argv: Sequence[str]) -> str:
    """Generate a real dispatch envelope through the REAL CLI edge.

    Asserts generation itself succeeded, so a generation failure can never
    masquerade as a missing-rule verdict. Cached per argv -- the generator is a
    pure read-only render, so one run per shape serves every leg.
    """
    key = tuple(argv)
    cached = _ENVELOPE_CACHE.get(key)
    if cached is not None:
        return cached
    exit_code, stdout, stderr = run_cli_in_process(["dispatch", *key], cwd=_REPO_ROOT)
    assert exit_code == 0, (
        f"dispatch generation must succeed before its {_SECTION} section can "
        f"be inspected -- argv={list(key)!r}, exit_code={exit_code}, "
        f"stderr={stderr!r}"
    )
    assert stdout.strip(), (
        f"dispatch generation must emit a usable envelope -- argv={list(key)!r}, "
        f"stderr={stderr!r}"
    )
    _ENVELOPE_CACHE[key] = stdout
    return stdout


def _timeout_instruction_body(argv: Sequence[str]) -> str:
    """The EXTRACTED ``# TIMEOUT_INSTRUCTION`` section body of a generated
    envelope -- extracted with the validator's OWN ``_extract_section_body``,
    never a substring search over the whole prompt."""
    envelope = _generate_envelope(argv)
    body = _extract_section_body(envelope, _SECTION)
    assert body.strip(), (
        f"fixture problem: the generated envelope carries an EMPTY '# {_SECTION}' "
        f"body, so every assertion on it would be vacuous -- argv={list(argv)!r}, "
        f"envelope={envelope!r}"
    )
    assert len(body) < len(envelope), (
        f"fixture problem: the extracted '# {_SECTION}' body is the WHOLE "
        "envelope -- section extraction has degenerated into a whole-prompt "
        f"substring search. argv={list(argv)!r}"
    )
    return body


def _phase_argv(*, phase: str, project_id: str) -> tuple[str, ...]:
    """Dispatch argv for a PHASE, choosing the only coherent slice scope
    (feature-end for a FEATURE_END_PHASES member, slice-01 otherwise)."""
    slice_id = "feature-end" if phase in FEATURE_END_PHASES else "slice-01"
    return _argv(project_id=project_id, slice_id=slice_id, extra=("--phase", phase))


def _longest_common_substring(texts: Sequence[str]) -> str:
    """The longest contiguous text present in EVERY string of ``texts``.

    Position-agnostic on purpose: the fix appends ONE shared constant to each
    branch body, but a reword that places it mid-body is equally valid -- what
    must hold is that the rule text is BYTE-IDENTICAL wherever it lands, which
    is exactly what "shared by all shapes" measures. Bodies are a few hundred
    characters, so the naive scan is instant.
    """
    if not texts:
        return ""
    shortest = min(texts, key=len)
    for length in range(len(shortest), 0, -1):
        for start in range(len(shortest) - length + 1):
            candidate = shortest[start : start + length]
            if all(candidate in text for text in texts):
                return candidate
    return ""


# ---------------------------------------------------------------------------
# COMMON-POINT witness -- pins the "one locus governs every dispatch" claim
# mechanically against the live SSOT data. GREEN today; must stay GREEN.
# ---------------------------------------------------------------------------


def test_timeout_instruction_is_required_by_every_lane_and_wave_profile() -> None:
    """Every ``LANE_PROFILES`` row and every ``WAVE_DISPATCH_PROFILES`` row must
    require the ``TIMEOUT_INSTRUCTION`` section.

    This is what makes ONE constant in ``_section_body`` a sufficient cure: if
    some future lane/wave profile dropped the section, that profile's dispatches
    would silently ship without the rule and the single-locus fix would be a
    false economy. Derived from the live datums, never a hand-copied list.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    lanes_without = sorted(
        lane
        for lane, profile in LANE_PROFILES.items()
        if _SECTION not in profile.required_sections
    )
    assert not lanes_without, (
        f"lane profile(s) {lanes_without!r} do NOT require the '{_SECTION}' "
        "section, so a dispatch on that lane would ship with no turn/termination "
        "discipline at all -- the background-turn-close rule cannot reach it "
        "from _section_body. Add the section to those LANE_PROFILES rows."
    )
    waves_without = sorted(
        wave
        for wave, profile in WAVE_DISPATCH_PROFILES.items()
        if _SECTION not in profile.required_sections
    )
    assert not waves_without, (
        f"wave profile(s) {waves_without!r} do NOT require the '{_SECTION}' "
        "section -- same consequence as the lane case above. Add the section to "
        "those WAVE_DISPATCH_PROFILES rows."
    )


def test_shape_matrix_covers_every_lane_and_wave_in_the_dispatch_ssot() -> None:
    """Non-vacuity + generality witness: the shape matrix must exercise EVERY
    lane in ``LANE_PROFILES`` and EVERY wave in ``WAVE_DISPATCH_PROFILES``.

    A lane or wave added to the SSOT later fails HERE, by name, instead of
    silently escaping every rule assertion in this file. Deliberately a FLOOR
    (superset) assertion -- extra shapes are always welcome.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    exercised_lanes = {
        argv[argv.index("--lane") + 1] for _, argv in _SHAPES if "--lane" in argv
    }
    exercised_waves = {
        argv[argv.index("--wave") + 1] if "--wave" in argv else "deliver"
        for _, argv in _SHAPES
    }
    missing_lanes = set(LANE_PROFILES) - exercised_lanes
    assert not missing_lanes, (
        f"lane(s) {sorted(missing_lanes)!r} exist in LANE_PROFILES but are not "
        f"exercised by this file's shape matrix (exercised: "
        f"{sorted(exercised_lanes)!r}) -- their dispatches would never be "
        "checked for the background-turn-close rule. Add a shape for each."
    )
    missing_waves = set(WAVE_DISPATCH_PROFILES) - exercised_waves
    assert not missing_waves, (
        f"wave(s) {sorted(missing_waves)!r} exist in WAVE_DISPATCH_PROFILES but "
        f"are not exercised by this file's shape matrix (exercised: "
        f"{sorted(exercised_waves)!r}). Add a shape for each."
    )


# ---------------------------------------------------------------------------
# THE BUG -- the rule must be present in the EXTRACTED TIMEOUT_INSTRUCTION
# section of every generated envelope. RED today for every shape.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", _SHAPE_PARAMS)
def test_timeout_instruction_forbids_ending_a_turn_on_a_background_job(
    argv: tuple[str, ...],
) -> None:
    """Every dispatch shape's ``# TIMEOUT_INSTRUCTION`` section must carry the
    background-turn-close rule.

    The section that tells a dispatched agent how to manage its own time and
    its own termination is the ONLY section where this rule is findable when it
    matters -- an agent about to close its turn is reading its termination
    contract, not scanning the whole envelope. RED today for every shape: none
    of the three ``_section_body`` branches mentions background jobs at all.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    body = _timeout_instruction_body(argv)
    missing = _missing_token_groups(body)
    assert not missing, (
        f"the generated '# {_SECTION}' section is missing the "
        "background-turn-close rule. A dispatched agent that backgrounds a long "
        "command and then ENDS ITS TURN waiting for the task-notification waits "
        "FOREVER -- the notification reaches the ORCHESTRATOR, never a "
        "dispatched agent -- and from outside it is indistinguishable from a "
        "slow agent, so nobody intervenes.\n"
        f"WHAT is missing (token group(s) with no match): {missing!r}\n"
        f"HOW to fix: append ONE shared module-level constant in "
        "src/des/cli/dispatch.py to each of the three TIMEOUT_INSTRUCTION "
        "branch bodies in _section_body -- never three copies of the prose -- "
        "saying in substance: if you need a long command's result, run it in "
        "the FOREGROUND in this turn or poll for it in the SAME turn; never end "
        "your turn waiting for a background job you started, because the "
        "notification reaches the orchestrator and never a dispatched agent.\n"
        f"argv={list(argv)!r}\n"
        f"generated {_SECTION} body={body!r}"
    )


@pytest.mark.parametrize("phase", sorted(dispatch._canonical_phase_values()))
def test_timeout_instruction_carries_the_rule_for_every_canonical_phase(
    phase: str,
) -> None:
    """PHASE-AXIS generality: the rule must reach EVERY phase ``des dispatch``
    can generate, sourced from the production SSOT
    ``dispatch._canonical_phase_values()`` (the same set argparse's ``--phase``
    choices resolve from) -- never a hand-copied phase list.

    A phase added to that SSOT later enters this leg's coverage automatically,
    with no edit here: that is what makes the CLASS closed rather than the
    reported instance patched. RED today for every phase.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    argv = _phase_argv(phase=phase, project_id=f"probe-bg-phase-{phase.lower()}")
    body = _timeout_instruction_body(argv)
    missing = _missing_token_groups(body)
    assert not missing, (
        f"`des dispatch --phase {phase}` generates a '# {_SECTION}' section with "
        f"no background-turn-close rule -- missing token group(s): {missing!r}. "
        "Every generable phase must carry it (see the shape-level test's HOW). "
        f"generated {_SECTION} body={body!r}"
    )


# ---------------------------------------------------------------------------
# SINGLE LOCUS -- the rule text must be BYTE-IDENTICAL across every shape,
# which is what one shared constant produces and three hand-written per-branch
# paraphrases do not. RED today.
# ---------------------------------------------------------------------------


def test_background_turn_close_rule_is_byte_identical_across_shapes() -> None:
    """The rule text shared by EVERY generated shape must itself carry the whole
    rule.

    Measured as the longest contiguous text present in every shape's
    ``# TIMEOUT_INSTRUCTION`` body. If the fix appends ONE shared constant, that
    shared text IS the rule and carries all five token groups. If instead each
    branch got its own paraphrase, the shared text degenerates to the incidental
    overlap and the token groups vanish from it -- which is precisely the drift
    this leg forbids, since three independently-worded copies are three things
    to keep in step.

    RED today: the longest text shared by all shapes is ``'\\nTarget ~60 turns'``,
    which carries no token group at all.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    bodies = [_timeout_instruction_body(argv) for _, argv in _SHAPES]
    shared = _longest_common_substring(bodies)
    missing = _missing_token_groups(shared)
    assert not missing, (
        "the text SHARED by every dispatch shape's "
        f"'# {_SECTION}' section does not carry the background-turn-close rule "
        f"-- missing token group(s): {missing!r}.\n"
        "WHY this matters: one shared module-level constant appended to each "
        "branch yields byte-identical rule text everywhere; three per-branch "
        "paraphrases yield three things that drift. HOW: define the rule ONCE "
        "in src/des/cli/dispatch.py and append that ONE name to each of the "
        "three TIMEOUT_INSTRUCTION branch bodies.\n"
        f"longest shared text was {shared!r}\n"
        "per-shape bodies="
        f"{dict(zip([s for s, _ in _SHAPES], bodies, strict=True))!r}"
    )


@pytest.mark.negative_at
def test_shared_rule_never_replaces_the_branch_specific_turn_budget() -> None:
    """NEGATIVE AT (no overcorrection): appending the shared rule must NEVER
    collapse the three branch bodies into one.

    Each branch's own turn-budget prose is role-specific and load-bearing -- the
    crafter's "room to seal, run static checks, and REPORT", the examiner's
    "STOP once you have exercised the real product surface", the authoring
    wave's "STOP once the wave's artifacts are authored". A fix that satisfied
    the single-locus leg by making every branch emit ONLY the shared rule would
    destroy that guidance while going green. GREEN today; must stay GREEN.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    bodies = {shape_id: _timeout_instruction_body(argv) for shape_id, argv in _SHAPES}
    shared = _longest_common_substring(list(bodies.values())).strip()
    collapsed = sorted(
        shape_id for shape_id, body in bodies.items() if body.strip() == shared
    )
    assert not collapsed, (
        f"NEGATIVE AT: shape(s) {collapsed!r} emit NOTHING BUT the text shared "
        "by every other shape -- their role-specific turn-budget guidance has "
        "been collapsed away. The background-turn-close rule is an ADDITION to "
        "each branch body, never a replacement for it. "
        f"shared text={shared!r}"
    )
    distinct_bodies = {body.strip() for body in bodies.values()}
    assert len(distinct_bodies) >= 3, (
        "NEGATIVE AT: the three TIMEOUT_INSTRUCTION branches "
        "(non-code-facing / crafter / authoring-wave) must remain "
        f"distinguishable -- only {len(distinct_bodies)} distinct body/bodies "
        f"were generated across {len(bodies)} shapes. bodies={bodies!r}"
    )


# ---------------------------------------------------------------------------
# VALIDATOR ACCEPTANCE -- an envelope its own validator refuses blocks every
# dispatch. GREEN today; must stay GREEN after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("argv", _SHAPE_PARAMS)
def test_generated_envelope_is_still_accepted_by_its_own_validator(
    argv: tuple[str, ...],
) -> None:
    """ROUND-TRIP: every shape's generated envelope must still be ACCEPTED by
    the REAL ``AtddPurePromptValidator`` after the rule is added.

    The system must never refuse its own generator's output -- an envelope its
    own PreToolUse validator rejects blocks EVERY dispatch of that shape, and
    that must not be discovered later, in production, by an operator whose
    dispatch will not start. GREEN today; must stay GREEN.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    envelope = _generate_envelope(argv)
    result = AtddPurePromptValidator().validate_prompt(envelope)
    assert result.status == "PASSED", (
        "the generator produced an envelope its OWN PreToolUse validator "
        f"REFUSES -- argv={list(argv)!r}, status={result.status}, "
        f"errors={result.errors!r}, recovery_guidance={result.recovery_guidance!r}"
    )
    assert result.task_invocation_allowed, (
        f"a generated envelope must stay invocable -- argv={list(argv)!r}, "
        f"errors={result.errors!r}"
    )


def test_atd_thin_auto_route_forbids_background_turn_close_on_focused_red() -> None:
    """DIRECT-ROUTE witness: nw-auto dispatches this agent via Agent,
    bypassing des-dispatch's TIMEOUT_INSTRUCTION -- the Thin Auto branch's own
    prose must carry the rule after its focused-RED sentence."""
    # covers: fix-dispatched-agent-background-job-never-wakes
    spec_path = _REPO_ROOT / "nWave" / "agents" / "nw-acceptance-designer.md"
    text = spec_path.read_text(encoding="utf-8")
    start = text.index("**Thin Auto M/L route (`nw-auto`)")
    end = text.index("**Human route:**", start)
    branch_after_red = text[start:end][
        text[start:end].index("observe the expected RED") :
    ]
    missing = _missing_token_groups(branch_after_red)
    assert not missing, (
        "Thin Auto branch missing background-turn-close rule after focused "
        f"RED: {missing!r} in {branch_after_red!r}"
    )


_LIFECYCLE_TOKEN_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("the long-running boundary notion", ("long-running", "long running")),
    (
        "the bounded-lifecycle/terminal-oracle requirement",
        ("bounded lifecycle", "terminal oracle"),
    ),
    ("the one-cycle seam preference", ("one-cycle", "one cycle")),
)


def test_atd_thin_auto_route_requires_bounded_lifecycle_for_long_running_boundaries() -> (
    None
):
    """Point-of-use witness (K4 ATD daemon regression): before materializing a
    CLI/management/service boundary, the Thin Auto branch must require
    inspecting it for long-running shape and giving any exercised long-running
    boundary a bounded lifecycle + terminal oracle, preferring the nearest
    one-cycle seam when the user property is one cycle."""
    # covers: fix-atd-daemon-lifecycle
    spec_path = _REPO_ROOT / "nWave" / "agents" / "nw-acceptance-designer.md"
    text = spec_path.read_text(encoding="utf-8")
    start = text.index("**Thin Auto M/L route (`nw-auto`)")
    end = text.index("**Human route:**", start)
    lowered = text[start:end].lower()
    missing = [
        name
        for name, alternatives in _LIFECYCLE_TOKEN_GROUPS
        if not any(alt in lowered for alt in alternatives)
    ]
    assert not missing, (
        f"Thin Auto branch missing the long-running-boundary lifecycle rule: {missing!r}"
    )


def test_mandatory_section_set_is_unchanged_by_the_fix() -> None:
    """FROZEN FLOOR: the atdd_pure mandatory-section set must not change.

    The cure is PROSE inside an existing section, never a new mandatory section
    (a 13th section would instantly invalidate every hand-authored and
    already-emitted envelope in flight). Pinned as an exact tuple so an added,
    removed or reordered section fails loudly here. GREEN today; must stay
    GREEN.
    """
    # covers: fix-dispatched-agent-background-job-never-wakes
    assert ATDD_PURE_MANDATORY_SECTIONS == (
        "DES_METADATA",
        "AGENT_IDENTITY",
        "SKILL_LOADING",
        "TASK_CONTEXT",
        "DESIGN_CONTEXT",
        "ATDD_PURE_PHASES",
        "QUALITY_GATES",
        "AT_COMPLETION_LEDGER",
        "RECORDING_INTEGRITY",
        "BOUNDARY_RULES",
        "TERMINATING_RUN",
        "TIMEOUT_INSTRUCTION",
    ), (
        "the atdd_pure mandatory-section set changed -- the background-turn-close "
        "rule must be PROSE APPENDED to the existing TIMEOUT_INSTRUCTION body, "
        "never a new mandatory section (which would invalidate every envelope "
        f"already in flight). got {ATDD_PURE_MANDATORY_SECTIONS!r}"
    )
    assert _SECTION in ATDD_PURE_MANDATORY_SECTIONS, (
        f"'{_SECTION}' -- the single common locus this whole file keys on -- is "
        "no longer a mandatory section; every assertion here would be vacuous."
    )
