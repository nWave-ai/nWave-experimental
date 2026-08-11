"""Regression AT -- fix-dispatch-cannot-generate-feature-end-phases.

DEFECT (measured 2026-07-19, task #175, RCA in the dispatch instruction): the
atdd_pure dispatch GUARD -- ``carpaccio_intercept.py``'s
``AtddPurePhaseScopeIncoherent`` refusal -- names the legal feature-end-cycle
phase set as its OWN remedy, imported straight from the domain SSOT
``des.domain.atdd_pure_phases.FEATURE_END_PHASES``::

    f"phase ({' / '.join(sorted(FEATURE_END_PHASES))}) is the only kind "
    "that may carry scope 'feature-end'"

CORRECTED UNDERSTANDING (team-lead correction, Ale-ratified, post-authoring):
the disagreement between the guard's set and the generator's ``--phase``
``choices`` is NOT symmetric, and an earlier revision of this file wrongly
treated it as if it were. It runs in TWO OPPOSITE directions:

  * ``F_FINAL_REVIEW`` -- guard-legal, generator-missing. A REAL GAP: the
    feature-end deep code review has no generable dispatch. FIX = add it to
    the generator, routed to an agent that can READ CODE.
  * ``E_BATCH_REFACTOR`` -- guard-legal (today), generator-missing, and it
    SHOULD BE ABSENT FROM BOTH. Refactoring is REMOVED from the per-slice and
    feature-end cycles, superseded by the prefactoring lane (Ale-ratified).
    FIX = remove it from the GUARD's legal set, not add it to the generator.
    A fix that made ``E_BATCH_REFACTOR`` generable to satisfy a blanket
    "every guard-legal phase must be generable" property would RESURRECT a
    retired phase -- which is why that blanket property (an earlier revision
    of this file's ``test_every_guard_legal_feature_end_phase_is_generable``)
    was WRONG and is replaced below.

WHAT THIS FILE PINS: not "the two sets happen to contain the same strings
today" (a property satisfiable by hand-syncing two independently-maintained
literals -- the exact defect class under repair), but that the generator's
offered phases and the guard's legal phases are DERIVED FROM ONE SHARED
AUTHORITY (``des.domain.atdd_pure_phases.FEATURE_END_PHASES``), so a future
addition OR retirement is covered by construction, not by remembering to
edit two places:

  1. a structural identity check -- ``des.cli.dispatch`` and the guard
     reference the LITERAL SAME object (``is``, not ``==``);
  2. a live-derivation / propagation check -- monkeypatching the SSOT
     binding the generator already imports and observing the generator's
     ``--phase`` choices react IMMEDIATELY, with no other code change. A
     generator carrying its own hardcoded/copied choices list -- even one
     numerically synced to match the guard's set TODAY -- would NOT react to
     this patch, which is exactly the "two lists kept in sync" cheat this
     test is built to defeat;
  3. the CONCRETE post-retirement legal trio (``D_DISTILL``,
     ``FEATURE_END_EXAMINE``, ``F_FINAL_REVIEW``) must each be generable --
     derived as ``FEATURE_END_PHASES`` minus the one explicitly-named
     retirement, never a hand-typed trio;
  4. ``E_BATCH_REFACTOR`` must stay refused AND absent from the refusal's
     "choose from" alternatives forever (a retired phase named as a valid
     alternative is a resurrection invitation -- the same misleading-HOW
     class this whole feature is about);
  5. the "must route to a code-reading reviewer" assertion for
     ``F_FINAL_REVIEW`` is grounded in ``nWave/agents/nw-software-crafter-
     reviewer.md``'s own frontmatter, which names ``F_FINAL_REVIEW`` as one
     of its two ATDD-pure review phases (ADR-027) -- not an invented
     expectation;
  6. the existing negative controls drive the guard's own predicate
     (``classify_atdd_pure_dispatch``) directly on markers parsed from a
     REAL generated prompt, mirroring the established convention in
     ``tests/bugs/des/test_dispatch_validity_single_source.py``.

Driving surface (Mandate 2/16, driving-port-only, default IN-PROCESS): every
assertion drives the REAL ``des dispatch`` CLI entry in-process via
``tests/common/in_process_cli.run_cli_in_process`` (the in-process analogue
of ``python -m des.cli.__main__ dispatch ...``) against THIS checkout's real
``nWave/dispatch/atdd_pure.yaml`` SSOT -- no mocking of the prompt builder.
NO subprocess-e2e is spent here: this CLI already has an established
in-process driving convention across every sibling file in
``tests/bugs/des/test_dispatch_*.py`` (none forks a literal ``des dispatch``
subprocess), and the walking-skeleton budget for THIS feature is unneeded --
the two repro commands in the dispatch instruction were themselves run via
the real installed ``des`` console script during RCA (see task #175), which
already proved the console-script wiring; this file's job is to pin the
GENERATOR's OWN logic, which is faithfully reached in-process through its
real ``main()`` entry. The live-derivation check ALSO requires in-process
driving -- a subprocess would never see the monkeypatch.

RED-for-right-reason (current state, real semantic ``AssertionError``, never
an import/collection error):
  * the live-derivation/propagation check is RED -- today's ``--phase``
    choices never consult ``FEATURE_END_PHASES`` at all;
  * the post-retirement-trio property is RED for ``F_FINAL_REVIEW`` only
    (``D_DISTILL`` / ``FEATURE_END_EXAMINE`` are already enum-backed and
    already generable today);
  * the ``F_FINAL_REVIEW`` agent-routing check is RED (generation itself
    fails today);
  * the structural identity check and every negative control are GREEN
    today and must stay GREEN after the fix.

covers: fix-dispatch-cannot-generate-feature-end-phases
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from des.cli import dispatch
from des.domain import atdd_pure_phases
from des.domain.atdd_pure_phases import FEATURE_END_PHASES
from des.domain.des_marker_parser import DesMarkerParser, classify_atdd_pure_dispatch
from tests.common.delivery_contract_fixture import contract_args
from tests.common.in_process_cli import run_cli_in_process


# tests/bugs/des/<this file> -> parents[3] == checkout root (mirrors the
# established, CORRECT convention in
# tests/bugs/des/test_dispatch_distill_names_acceptance_designer.py).
_REPO_ROOT = Path(__file__).resolve().parents[3]

_PARSER = DesMarkerParser()

# A representative per-slice (non-feature-end) canonical phase -- used by the
# NEG control below. Deliberately NOT a FEATURE_END_PHASES member, so it
# must stay guard-rejected at scope 'feature-end' both before AND after the
# fix (the fix widens WHICH phases des dispatch can GENERATE; it must never
# widen WHICH phases the guard treats as feature-end-coherent).
_PER_SLICE_PHASE = "D_REFACTOR_COMMIT"

# The known-good --phase choices that exist TODAY, independent of this fix --
# used by a NEG control to assert the argparse refusal for a genuinely
# bogus phase name still names a real, non-empty valid set, both before and
# after the fix (the fix only ADDS to this set, never removes from it).
_PRE_FIX_KNOWN_CHOICES: tuple[str, ...] = (
    "A_GREEN",
    "C_REVIEWER_AUDIT",
    "D_REFACTOR_COMMIT",
    "D_DISTILL",
    "FEATURE_END_EXAMINE",
)

# The ONE explicitly-named retirement (Ale-ratified: refactoring is removed
# from the per-slice and feature-end cycles, superseded by the prefactoring
# lane). This is a factual, one-time correction -- naming the SPECIFIC word
# being retired is legitimate (a bugfix names its specific defect); it is
# NOT a hand-typed restatement of the general SSOT-derivation property below,
# which stays fully derived.
_RETIRED_FEATURE_END_PHASE = "E_BATCH_REFACTOR"

# The feature-end phases that MUST remain (or become) legal -- derived from
# the guard's own SSOT minus the one named retirement, never a hand-typed
# trio. Today this still evaluates to a set that (incorrectly) excludes
# nothing extra because E_BATCH_REFACTOR is still a live FEATURE_END_PHASES
# member pre-fix; the subtraction is what keeps this list honest once the
# guard's SSOT is corrected too.
_EXPECTED_LIVE_FEATURE_END_PHASES: tuple[str, ...] = tuple(
    sorted(FEATURE_END_PHASES - {_RETIRED_FEATURE_END_PHASE})
)

assert _EXPECTED_LIVE_FEATURE_END_PHASES, "fixture vacuous -- nothing to parametrize"
assert _RETIRED_FEATURE_END_PHASE not in _EXPECTED_LIVE_FEATURE_END_PHASES

_CHOOSE_FROM_RE = re.compile(r"\(choose from (.+?)\)")


def _choose_from_set(stderr: str) -> set[str]:
    """Extract the argparse '(choose from ...)' alternative set from stderr.

    Python's argparse has rendered this clause both quoted
    (``'A', 'B'``, seen on 3.12.3) and bare (``A, B``, seen on 3.12.13) across
    patch versions -- neither rendering is a stable contract, so this strips
    optional surrounding quotes per comma-separated token instead of assuming
    one form.
    """
    match = _CHOOSE_FROM_RE.search(stderr)
    assert match, (
        f"searched for pattern {_CHOOSE_FROM_RE.pattern!r} "
        "(an argparse '(choose from ...)' clause, quoted or bare -- "
        "argparse renders this differently across versions/environments) "
        f"in stderr={stderr!r}"
    )
    return {token.strip().strip("'") for token in match.group(1).split(",")}


def _run_dispatch(argv: list[str]) -> tuple[int, str, str]:
    """Drive the REAL `des dispatch` CLI in-process (Layer-2 default)."""
    return run_cli_in_process(["dispatch", *argv], cwd=_REPO_ROOT)


def _feature_end_argv(*, phase: str, project_id: str) -> list[str]:
    return [
        "--mode",
        "atdd_pure",
        "--project-id",
        project_id,
        "--slice",
        "feature-end",
        "--phase",
        phase,
        "--wave",
        "feature-end",
        "--intent",
        "X",
        *contract_args(_REPO_ROOT, seed=False),
    ]


def _agent_identity_line(stdout: str) -> str:
    """Extract the `Agent: ...` line following the `# AGENT_IDENTITY` header."""
    lines = stdout.splitlines()
    for index, line in enumerate(lines):
        if line.strip() == "# AGENT_IDENTITY":
            for following in lines[index + 1 :]:
                if following.startswith("Agent:"):
                    return following
            return ""
    return ""


# ---------------------------------------------------------------------------
# 1. STRUCTURAL SSOT INVARIANT -- des.cli.dispatch and the guard reference
#    the IDENTICAL FEATURE_END_PHASES object. One authority, two readers.
# ---------------------------------------------------------------------------


def test_generator_and_guard_reference_the_same_feature_end_phases_object() -> None:
    """`des.cli.dispatch` already imports `FEATURE_END_PHASES` (used today
    for the feature-end auto-slice-correct logic) -- it must be the SAME
    object the guard (`carpaccio_intercept.py`) consults, never a separately
    constructed (even if value-equal) collection. A copy reintroduces the
    two-lists-kept-in-sync defect this feature repairs.
    """
    assert dispatch.FEATURE_END_PHASES is atdd_pure_phases.FEATURE_END_PHASES, (
        "des.cli.dispatch.FEATURE_END_PHASES must be the SAME object as "
        "des.domain.atdd_pure_phases.FEATURE_END_PHASES (identity, not "
        "mere equality) -- one shared SSOT, not two synced copies."
    )


# ---------------------------------------------------------------------------
# 2. LIVE-DERIVATION PROOF -- the generator's --phase choices must react to
#    a patched FEATURE_END_PHASES SSOT at call time. This is what a
#    "two lists kept in sync" implementation CANNOT satisfy: hand-syncing
#    two literals to match TODAY'S values does not make the generator's
#    choices RESPOND to a live change in the guard's authority.
# ---------------------------------------------------------------------------


def test_generator_phase_choices_derive_live_from_feature_end_phases_ssot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RED today: the current `--phase` choices (`_canonical_phase_values()`)
    never consult `FEATURE_END_PHASES` at all, so a synthetic phase injected
    into that SSOT stays refused. After the fix, the generator's choices
    must be computed FROM the live binding at call time, so patching it
    immediately changes what is generable -- proof of derivation, not
    proof of two-numbers-matching-today.
    """
    synthetic_phase = "ZZZ_SYNTHETIC_FEATURE_END_PHASE_PROBE"
    monkeypatch.setattr(
        dispatch, "FEATURE_END_PHASES", frozenset({synthetic_phase, "D_DISTILL"})
    )

    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(phase=synthetic_phase, project_id="probe-ssot-propagation")
    )

    assert exit_code == 0, (
        "the generator's --phase choices must be LIVE-derived from the "
        "FEATURE_END_PHASES SSOT at call time -- patching that binding to "
        f"include {synthetic_phase!r} must make it immediately generable, "
        "with no other code change. A hardcoded or copied choices list "
        f"would still refuse it here. exit_code={exit_code}, "
        f"stdout={stdout!r}, stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# 3. THE CONCRETE POST-RETIREMENT PROPERTY -- every feature-end phase that
#    SHOULD remain legal (guard's SSOT minus the one named retirement) must
#    be generable. RED only for F_FINAL_REVIEW.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("phase", _EXPECTED_LIVE_FEATURE_END_PHASES)
def test_every_post_retirement_feature_end_phase_is_generable(phase: str) -> None:
    """A phase that remains guard-legal after E_BATCH_REFACTOR's retirement
    MUST be a phase `des dispatch` can actually GENERATE. RED today for
    `F_FINAL_REVIEW` (argparse `invalid choice`, exit_code == 2); GREEN for
    the two already-enum-backed members (`D_DISTILL`, `FEATURE_END_EXAMINE`).
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(phase=phase, project_id=f"probe-fe-{phase.lower()}")
    )

    assert exit_code == 0, (
        f"phase {phase!r} must remain legal (feature-end-coherent) after "
        "E_BATCH_REFACTOR's retirement, but `des dispatch --phase "
        f"{phase}` failed to generate a dispatch -- exit_code={exit_code}, "
        f"stderr={stderr!r}."
    )
    assert f"DES-PHASE : {phase}" in stdout or f"DES-PHASE: {phase}" in stdout, (
        f"des dispatch reported exit_code 0 for phase {phase!r} but the "
        f"generated prompt does not carry that phase in its DES-PHASE "
        f"marker -- stdout={stdout!r}"
    )


# ---------------------------------------------------------------------------
# 4. F_FINAL_REVIEW must route to a CODE-READING reviewer, never the
#    examiner (who has no source access by construction) and never the bare
#    implementing crafter.
# ---------------------------------------------------------------------------


def test_f_final_review_names_code_reading_reviewer_not_examiner() -> None:
    """`F_FINAL_REVIEW` is the feature-end deep code review (ADR-027) --
    `nWave/agents/nw-software-crafter-reviewer.md`'s own frontmatter names
    `F_FINAL_REVIEW` as one of its two ATDD-pure review phases. A dispatch
    naming ANY other agent for this phase is the same defect wearing a
    different mask: an agent structurally unable to perform the phase
    (the examiner cannot read source; the plain crafter never reviews).
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(phase="F_FINAL_REVIEW", project_id="probe-fe-review")
    )

    assert exit_code == 0, (
        "des dispatch --phase F_FINAL_REVIEW must succeed before its "
        f"AGENT_IDENTITY can even be inspected -- exit_code={exit_code}, "
        f"stderr={stderr!r}"
    )

    agent_identity_line = _agent_identity_line(stdout)

    assert "nw-software-crafter-reviewer" in agent_identity_line, (
        "F_FINAL_REVIEW must dispatch to 'nw-software-crafter-reviewer' -- "
        "the code-reading review agent ADR-027 assigns to this phase -- "
        f"got AGENT_IDENTITY line={agent_identity_line!r} from stdout="
        f"{stdout!r}"
    )
    assert "nw-user-examiner" not in agent_identity_line, (
        "F_FINAL_REVIEW must NOT dispatch to 'nw-user-examiner' -- that "
        "agent has no source/code access by construction and cannot "
        f"perform a code-reading review. got AGENT_IDENTITY line="
        f"{agent_identity_line!r}"
    )
    assert agent_identity_line.strip() != "Agent: nw-software-crafter", (
        "F_FINAL_REVIEW must NOT dispatch to the bare implementing crafter "
        "either -- it needs the REVIEWER agent, not the crafter that wrote "
        f"the code under review. got AGENT_IDENTITY line="
        f"{agent_identity_line!r}"
    )


# ---------------------------------------------------------------------------
# 5. NEGATIVE -- E_BATCH_REFACTOR is RETIRED. It must stay refused AND
#    absent from the refusal's "choose from" alternatives forever -- a
#    retired phase named as a valid alternative is a resurrection
#    invitation. Must be GREEN both before and after the fix.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_e_batch_refactor_stays_refused_and_absent_from_choose_from() -> None:
    """Refactoring is removed from the per-slice and feature-end cycles,
    superseded by the prefactoring lane (Ale-ratified). `E_BATCH_REFACTOR`
    must NEVER become generable, and the refusal must never list it as a
    valid alternative -- the same misleading-HOW class this whole feature
    is about, just pointed the OTHER direction (naming a phase that should
    not exist, instead of failing to name one that should).
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(
            phase=_RETIRED_FEATURE_END_PHASE, project_id="probe-fe-retired"
        )
    )

    assert exit_code == 2, (
        f"{_RETIRED_FEATURE_END_PHASE!r} is retired -- it must be refused "
        f"as an invalid choice, not generated -- got exit_code={exit_code}, "
        f"stdout={stdout!r}"
    )
    assert _RETIRED_FEATURE_END_PHASE not in _choose_from_set(stderr), (
        f"the refusal must NOT list {_RETIRED_FEATURE_END_PHASE!r} among "
        "the valid alternatives -- a retired phase named in a 'choose "
        f"from' line is a resurrection invitation. stderr={stderr!r}"
    )


# ---------------------------------------------------------------------------
# 6. NEGATIVE -- the guard must still refuse a per-slice phase carrying
#    feature-end scope. The fix widens WHICH phases the generator can
#    produce; it must never widen WHICH phases the guard treats as
#    feature-end-coherent.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_guard_still_refuses_per_slice_phase_at_feature_end_scope() -> None:
    """`D_REFACTOR_COMMIT` (a per-slice phase, never a `FEATURE_END_PHASES`
    member) combined with scope `feature-end` must stay guard-rejected --
    a no-overcorrection control that must be GREEN both before and after
    the fix.
    """
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(phase=_PER_SLICE_PHASE, project_id="probe-fe-per-slice")
    )
    assert exit_code == 0, (
        f"fixture problem, not the property under test: generating a "
        f"{_PER_SLICE_PHASE} dispatch at scope feature-end must itself "
        f"succeed (the guard, not the generator, is what rejects the "
        f"pair) -- exit_code={exit_code}, stderr={stderr!r}"
    )

    markers = _PARSER.parse(stdout)
    classification = classify_atdd_pure_dispatch(markers)

    assert classification == "defective", (
        f"phase={_PER_SLICE_PHASE!r} is NOT a FEATURE_END_PHASES member, so "
        "combining it with scope 'feature-end' must classify as "
        f"'defective' (ADR-028 D6) -- got {classification!r}. "
        f"markers={markers!r}"
    )


# ---------------------------------------------------------------------------
# 7. NEGATIVE -- a genuinely-invalid phase name must still be refused, and
#    the refusal must still name a real, non-empty valid set. A no-
#    overcorrection control: the fix only ADJUSTS the valid set (adds
#    F_FINAL_REVIEW, never re-adds E_BATCH_REFACTOR), it must never make an
#    unrecognised phase silently acceptable nor blank the refusal message.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_genuinely_invalid_phase_name_still_refused_naming_the_valid_set() -> None:
    exit_code, stdout, stderr = _run_dispatch(
        _feature_end_argv(phase="NOT_A_REAL_PHASE", project_id="probe-fe-bogus")
    )

    assert exit_code == 2, (
        "a genuinely-unrecognised --phase value must be refused as a usage "
        f"error (exit_code 2) both before and after the fix -- got "
        f"exit_code={exit_code}, stdout={stdout!r}, stderr={stderr!r}"
    )
    assert "invalid choice" in stderr, (
        "the refusal for an unrecognised --phase value must name the "
        f"problem as an invalid choice -- got stderr={stderr!r}"
    )
    for known_choice in _PRE_FIX_KNOWN_CHOICES:
        assert known_choice in stderr, (
            f"the refusal must still name {known_choice!r} as part of the "
            f"valid --phase set (the fix only ADJUSTS choices, never drops "
            f"one of these five) -- got stderr={stderr!r}"
        )
