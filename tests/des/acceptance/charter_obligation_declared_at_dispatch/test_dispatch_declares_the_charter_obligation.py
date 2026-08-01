# @feature-charter-obligation-declared-at-dispatch
"""ATs -- the dispatch DECLARES the charter obligation as a durable fact.

Feature `charter-obligation-declared-at-dispatch`, Slice Plan row 1 (keystone):
"When I start a piece of work, the system tells me right there whether this
work owes an expectation charter, instead of leaving me to remember."

CONTRACT_SHAPE: bounded-change (declared mutation set = one appended ledger
line per dispatch; the rendered envelope and the exit code are UNCHANGED).

Driving surface: the production `des` CLI EDGE. The single `@walking_skeleton`
below forks a REAL interpreter; every other scenario drives the same EDGE
IN-PROCESS (L2 default). No production internal is imported for its behaviour,
so a failure here is a semantic `AssertionError` about an observable artifact
(a record on disk, a stream, an exit code), never a collection error.

ACTIVE-RED TODAY. `LaneProfile` (`src/des/domain/lane_profile.py:38-48`) has no
`charter_obligation` field and `des dispatch` appends nothing to the examine
ledger, so every assertion below fails on the observable, for the right reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.des.acceptance.charter_obligation_declared_at_dispatch.composition import (
    FEATURE_ID,
    dispatch,
    dispatch_argv_for_subprocess,
    emitted_events,
    event_named,
    ledger_for,
    provision_project,
    run_des_subprocess,
)
from tests.des.acceptance.charter_obligation_declared_at_dispatch.domain_types import (
    CHARTER_OBLIGATION_EVENT,
    CHARTER_WORD,
    LANE_OBLIGATIONS,
    UNWRITABLE_EVENT,
    CharterObligation,
    charter_lines,
    declared_obligation,
    line_stating,
    operator_visible,
    read_obligation_records,
)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    return provision_project(tmp_path / "project")


# ---------------------------------------------------------------------------
# WALKING SKELETON -- the ONE subprocess-e2e scenario for this whole FEATURE
# ---------------------------------------------------------------------------


@pytest.mark.walking_skeleton
def test_operator_starting_work_is_told_on_disk_that_it_owes_a_charter(
    project: Path,
) -> None:
    """@walking_skeleton @driving_port @real-io

    The operator types the real command in a real terminal; the system answers
    with a DURABLE fact keyed to that piece of work, readable afterwards by
    anything that joins on `(feature_id, slice_id)`.

    DIRECT-SURFACE: the paying user consumes the CLI itself -- there is no
    packaged, installed or assembled artifact between the producer and the
    consumer, so Artifact Lineage Closure reduces to the real fork below.
    """
    # covers: R1
    slice_id = "slice-01"
    argv = dispatch_argv_for_subprocess(project, slice_id, "bugfix")

    completed = run_des_subprocess(*argv, cwd=project)

    ledger = ledger_for(project)
    assert ledger.is_file(), (
        "a REAL `des dispatch` fork left NO examine ledger at "
        f"{ledger} -- the obligation was never made durable, so nothing "
        "downstream can be told this work owes a charter. "
        f"exit={completed.returncode}, stderr={completed.stderr[-800:]!r}"
    )
    records = read_obligation_records(ledger)
    assert records, (
        f"the ledger at {ledger} carries no {CHARTER_OBLIGATION_EVENT!r} "
        f"record; its lines were {ledger.read_text(encoding='utf-8')!r}"
    )
    record = records[-1]
    assert record.get("feature_id") == FEATURE_ID, record
    assert record.get("slice_id") == slice_id, (
        "the record must be keyed on the SAME (feature_id, slice_id) pair "
        "`_latest_examine_verdict` already indexes on (commit_slice.py:"
        f"825-827), else the join cannot be made: {record!r}"
    )
    assert record.get("obligation") == CharterObligation.REQUIRED.value, (
        "the `bugfix` lane already declares at_requirement=REQUIRED "
        f"(lane_profile.py:113); the record says {record.get('obligation')!r}"
    )


# ---------------------------------------------------------------------------
# The obligation is READ OFF the operator's declared lane (DDD-2)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("lane", "expected"),
    [(lane, obligation.value) for lane, obligation in sorted(LANE_OBLIGATIONS.items())],
    ids=sorted(LANE_OBLIGATIONS),
)
def test_the_declared_lane_decides_the_obligation(
    project: Path, lane: str, expected: str
) -> None:
    """@driving_port @real-io

    The lane is ALREADY the operator's declaration of the kind of work; the
    obligation is read as a consequence of it, never asked as a second
    question (D-3: cost on the operator for a question already answered).
    """
    # covers: R2
    slice_id = "slice-01"
    exit_code, stdout, stderr = dispatch(project, slice_id, lane=lane)

    observed = declared_obligation(ledger_for(project), slice_id)
    assert observed == expected, (
        f"`des dispatch --lane {lane}` declared {observed!r}; the lane's own "
        f"LANE_PROFILES row says the obligation is {expected!r}. "
        f"exit={exit_code}, stderr={stderr[-600:]!r}, stdout_head={stdout[:200]!r}"
    )


def test_a_dispatch_that_names_no_lane_mints_the_third_state_explicitly(
    project: Path,
) -> None:
    """@driving_port @real-io

    THE THIRD STATE, minted at declaration time. `--lane` is optional
    (`dispatch.py:1359-1364`), so the default dispatch resolves NO LaneProfile.
    That case must be WRITTEN DOWN as INDETERMINATE, not left as an absence for
    a downstream reader to interpret -- an unwritten third state cannot reach
    the aggregate (GDP-8 arity corollary).
    """
    # covers: R3
    slice_id = "slice-02"
    exit_code, _stdout, stderr = dispatch(project, slice_id, lane=None)

    observed = declared_obligation(ledger_for(project), slice_id)
    assert observed == CharterObligation.INDETERMINATE.value, (
        "a lane-less dispatch must DECLARE INDETERMINATE; it declared "
        f"{observed!r}. An unminted third state is invisible to the "
        f"end-of-feature count. exit={exit_code}, stderr={stderr[-600:]!r}"
    )


# ---------------------------------------------------------------------------
# NEGATIVE -- the gate must NOT fire, and an absence must NOT be a declaration
# ---------------------------------------------------------------------------


def test_never_dispatched_work_carries_no_declaration_and_is_not_exempt(
    project: Path,
) -> None:
    """@driving_port @real-io

    THE DISCRIMINATOR, stated at its source. Work that never went through a
    dispatch has NO record. `declared_obligation` returns `None` -- which is
    not a value of `CharterObligation` and must never be coerced into one.
    Absence-read-as-a-negative-declaration is the silent-wrong this feature
    exists to kill, so the absence is pinned here as a first-class observation.
    """
    # covers: R4
    dispatch(project, "slice-01", lane="bugfix")

    undeclared = declared_obligation(ledger_for(project), "slice-99")
    assert undeclared is None, (
        "a slice that was NEVER dispatched must read as 'no declaration', not "
        f"as a declared value; it read {undeclared!r}"
    )
    assert undeclared != CharterObligation.EXEMPT.value, (
        "'never declared' must never be collapsed into 'declared EXEMPT' -- "
        "that collapse IS the two-valued defect this feature removes from "
        "`_examine_gate_armed` (commit_slice.py:723-736)"
    )


def test_a_blank_exemption_reason_is_refused_and_leaves_no_half_declaration(
    project: Path,
) -> None:
    """@driving_port @real-io @error

    NEGATIVE. `--charter-exemption ""` is an absence wearing a declaration's
    clothes (feature-delta `[REF] Driving Ports`, row 3). It is refused with
    exit 2 -- and, the half that a refusal alone would not prove, it leaves NO
    record behind: a rejected declaration that still wrote a line would grant
    silently what the refusal denied loudly.
    """
    # covers: R5
    slice_id = "slice-01"
    exit_code, _stdout, stderr = dispatch(
        project, slice_id, lane="bugfix", extra=("--charter-exemption", "")
    )

    assert exit_code == 2, (
        "a blank `--charter-exemption` reason must exit 2 (usage error); got "
        f"exit={exit_code}, stderr={stderr[-600:]!r}"
    )
    assert "unrecognized arguments" not in stderr, (
        "argparse rejecting an UNKNOWN flag is a different refusal from "
        "rejecting a BLANK reason, and must never be mistaken for it -- that "
        "mistake would let this AT pass while the flag does not exist. "
        f"stderr={stderr[-600:]!r}"
    )
    assert "charter-exemption" in stderr and "reason" in stderr.lower(), (
        "the refusal must NAME the flag and say a reason is required; an "
        "operator cannot act on a refusal that names neither. "
        f"stderr={stderr[-600:]!r}"
    )
    assert declared_obligation(ledger_for(project), slice_id) is None, (
        "the refused dispatch still wrote an obligation record -- a refusal "
        "that leaves its effect behind is not a refusal"
    )


def test_an_unwritable_ledger_is_loud_and_never_takes_down_the_dispatch(
    project: Path,
) -> None:
    """@driving_port @real-io @infrastructure-failure

    NEGATIVE / fault injection. The ledger path is occupied by a DIRECTORY, so
    the append cannot succeed. The failure is announced LOUD (naming the path
    and the OSError) and the dispatch's exit code and envelope are UNCHANGED --
    a telemetry write must never take down the dispatch that is the operator's
    only way forward (GDP-6: degrade LOUD, never degrade-refuse-everything).
    """
    # covers: R6
    slice_id = "slice-01"
    healthy_project = provision_project(project.parent / "healthy")
    healthy_exit, healthy_out, _ = dispatch(healthy_project, slice_id, lane="bugfix")

    blocked = ledger_for(project)
    blocked.parent.mkdir(parents=True, exist_ok=True)
    blocked.mkdir()

    exit_code, stdout, stderr = dispatch(project, slice_id, lane="bugfix")

    assert exit_code == healthy_exit, (
        "an unwritable ledger changed the dispatch's exit code "
        f"({exit_code} vs {healthy_exit} on a healthy ledger) -- the telemetry "
        "write took down the dispatch"
    )
    assert "# DES_METADATA" in stdout and "# TASK_CONTEXT" in stdout, (
        "an unwritable ledger suppressed the rendered envelope; the operator's "
        "only way forward must be unaffected by a telemetry failure. "
        f"healthy envelope had {len(healthy_out)} chars, this one "
        f"{len(stdout)}: {stdout[:400]!r}"
    )
    loud = f"{stderr}\n{json.dumps(emitted_events(stdout, stderr))}"
    assert UNWRITABLE_EVENT in loud, (
        f"the failed append was SILENT: {UNWRITABLE_EVENT!r} appears nowhere "
        f"in the emitted streams. stderr={stderr[-800:]!r}"
    )
    assert str(blocked) in loud, (
        "the loud failure must NAME the path it could not write "
        f"({blocked}); the operator cannot act on an unnamed path. "
        f"stderr={stderr[-800:]!r}"
    )


def test_an_authoring_wave_dispatch_declares_no_obligation_and_still_succeeds(
    project: Path,
) -> None:
    """@driving_port @real-io

    OQ-5, DECIDED HERE rather than left to fall out of control flow. The
    obligation write sits after lane/wave resolution, so an AUTHORING-wave
    dispatch (`runs_tests=False`, `dispatch.py:1709-1711`) passes through it
    too. DISTILL's decision: an authoring wave produces no committable slice,
    so it declares NOTHING -- and that absence is the undeclared state
    (INDETERMINATE at the aggregate), never a silent EXEMPT.
    """
    # covers: R7
    slice_id = "feature-end"
    exit_code, _stdout, stderr = dispatch(project, slice_id, wave="distill", phase=None)

    assert exit_code == 0, (
        "the OQ-5 decision must not break an authoring-wave dispatch; "
        f"exit={exit_code}, stderr={stderr[-600:]!r}"
    )
    assert declared_obligation(ledger_for(project), slice_id) is None, (
        "an authoring-wave dispatch wrote an obligation record; it produces "
        "no committable slice, so there is no obligation to declare"
    )


def test_a_concurrent_partial_line_never_masquerades_as_a_missing_declaration(
    project: Path,
) -> None:
    """@driving_port @real-io @error

    NEGATIVE / robustness. The design reuses the examine ledger's EXISTING
    malformed-line tolerance (`commit_slice.py:818-822`) rather than
    re-deriving it. A truncated line from a concurrent writer must be skipped,
    leaving a real declaration on a later line still readable.
    """
    # covers: R1
    slice_id = "slice-01"
    ledger = ledger_for(project)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text('{"event": "CharterObligationDecl', encoding="utf-8")

    dispatch(project, slice_id, lane="bugfix")

    assert declared_obligation(ledger, slice_id) == CharterObligation.REQUIRED.value, (
        "a partial line from a concurrent writer swallowed the real "
        f"declaration; ledger reads {ledger.read_text(encoding='utf-8')!r}"
    )


def test_the_declaration_records_who_declared_it_and_how(project: Path) -> None:
    """@driving_port @real-io

    GDP-3 omission corollary: a record naming a state without naming what it
    was derived FROM hands the reader an investigation the producer had already
    finished. The record must carry the lane it was read off, so an operator
    reading the aggregate later can tell WHY a slice landed in its bucket.
    """
    # covers: R2
    slice_id = "slice-01"
    exit_code, stdout, stderr = dispatch(project, slice_id, lane="prefactoring")

    records = read_obligation_records(ledger_for(project))
    assert records, (
        f"no declaration to inspect. exit={exit_code}, stderr={stderr[-600:]!r}, "
        f"stdout_head={stdout[:200]!r}"
    )
    record = records[-1]
    assert record.get("lane") == "prefactoring", (
        "the record must name the lane the obligation was read off (its "
        f"antecedent), else 'EXEMPT' is a label with no reason: {record!r}"
    )
    assert event_named([record], CHARTER_OBLIGATION_EVENT) is not None, record


# ---------------------------------------------------------------------------
# THE OPERATOR-VISIBLE SURFACE -- a different proposition from the record
#
# Everything above asserts the RECORD EXISTS ON DISK. The charter promises THE
# OPERATOR IS TOLD ("the system tells me right there whether this work owes an
# expectation charter, instead of leaving me to remember"). Those are two
# propositions; only the first was tested, which is why the AT file went green
# while the examiner returned FAIL on the same slice with: "I ran the dispatch
# nine different ways and never once saw the word 'charter' on my screen."
#
# The record ATs above STAY. These ADD the surface the charter actually
# promised. They assert on the operator-visible stream, never on the ledger.
# ---------------------------------------------------------------------------


def test_the_operator_is_told_on_screen_that_this_work_owes_a_charter(
    project: Path,
) -> None:
    """@driving_port @real-io

    The charter's first oracle row: dispatching work whose obligation is
    REQUIRED prints, plainly and up front, that this work OWES a charter --
    before any implementation is described. A record in
    `.nwave/telemetry/examine/<feature>.jsonl` that the CLI never names is
    precisely the "buried" the charter's negative row forbids.

    And the telling must be ACTIONABLE: the HOW invokes the PRODUCING TOOL
    (GDP-4), so the operator is never left to hunt for the command.
    """
    # covers: R18
    slice_id = "slice-01"
    _exit_code, stdout, stderr = dispatch(project, slice_id, lane="bugfix")

    assert charter_lines(stdout, stderr), (
        "the operator was never told anything about a charter: the word "
        f"{CHARTER_WORD!r} appears on NO operator-visible line. The obligation "
        "may be on disk, but the charter promises the operator is TOLD. "
        f"screen={operator_visible(stdout, stderr)[-1500:]!r}"
    )
    told = line_stating(stdout, stderr, CHARTER_WORD, "REQUIRED")
    assert told is not None, (
        "no operator-visible line states that this work's charter obligation "
        f"is REQUIRED. charter lines seen: {charter_lines(stdout, stderr)!r}"
    )
    scaffold_line = line_stating(stdout, stderr, "des charter-scaffold")
    assert scaffold_line is not None, (
        "being told an obligation exists without being handed the command that "
        "discharges it leaves the operator to hunt (GDP-4: the HOW invokes the "
        f"PRODUCING TOOL). charter lines: {charter_lines(stdout, stderr)!r}"
    )
    assert FEATURE_ID in operator_visible(stdout, stderr), (
        "the printed command must carry THIS feature's id already filled in -- "
        "a command the operator must still edit is not a command they were "
        f"handed. screen={operator_visible(stdout, stderr)[-1500:]!r}"
    )


def test_the_operator_is_told_on_screen_that_this_work_owes_nothing_and_why(
    project: Path,
) -> None:
    """@driving_port @real-io

    The charter's second oracle row: work whose obligation is EXEMPT prints,
    plainly and up front, that it does NOT owe a charter, WITH the reason --
    "so the operator is never left wondering". A bare "EXEMPT" with no
    antecedent is a label, not a reason (GDP-3 omission corollary): the
    dispatch already holds the lane it read the obligation off, so withholding
    it hands the operator an investigation the producer had already finished.
    """
    # covers: R19
    slice_id = "slice-01"
    _exit_code, stdout, stderr = dispatch(project, slice_id, lane="prefactoring")

    told = line_stating(stdout, stderr, CHARTER_WORD, "EXEMPT")
    assert told is not None, (
        "no operator-visible line states that this work is EXEMPT from the "
        "charter obligation -- the operator is left to work it out from the "
        f"Slice Plan by hand. charter lines: {charter_lines(stdout, stderr)!r}, "
        f"screen={operator_visible(stdout, stderr)[-1500:]!r}"
    )
    assert "prefactoring" in told.lower(), (
        "the EXEMPT statement must name the ANTECEDENT it was read off (the "
        f"declared lane), else it is a label with no reason: {told!r}"
    )


def test_an_operator_supplied_exemption_reason_is_shown_back_on_screen(
    project: Path,
) -> None:
    """@driving_port @real-io

    Same oracle row, the other antecedent. When the operator supplies
    `--charter-exemption "<reason>"`, THAT text is the reason -- and it must
    come back on screen, so the operator can see the system understood the
    declaration it just accepted (and catch a mistyped one immediately, not at
    commit time).
    """
    # covers: R19
    slice_id = "slice-01"
    reason = "purely internal lock race, no operator-observable surface"
    _exit_code, stdout, stderr = dispatch(
        project, slice_id, lane="bugfix", extra=("--charter-exemption", reason)
    )

    told = line_stating(stdout, stderr, CHARTER_WORD, "EXEMPT")
    assert told is not None, (
        "an accepted `--charter-exemption` was never stated back to the "
        f"operator. charter lines: {charter_lines(stdout, stderr)!r}"
    )
    assert reason in operator_visible(stdout, stderr), (
        "the operator's own exemption reason must be shown back VERBATIM -- a "
        "declaration accepted silently cannot be checked by the person who "
        f"made it. screen={operator_visible(stdout, stderr)[-1500:]!r}"
    )


def test_the_third_state_is_stated_loud_on_screen_not_only_in_the_ledger(
    project: Path,
) -> None:
    """@driving_port @real-io

    THE THIRD STATE, at the surface. A lane-less dispatch resolves
    INDETERMINATE -- nobody could tell whether this work is user-visible. That
    is precisely the state the operator most needs to see, because it is the
    one nobody decided, and burying it is the silent-wrong this feature exists
    to remove (GDP-8 arity corollary: the third value must reach the surface
    the reader actually reads, never collapse into pass/empty).

    It must ALSO not be dressed up as a clearance: an operator told nothing, or
    told "no charter needed", cannot tell "we decided you owe none" from "we
    could not tell".
    """
    # covers: R20
    slice_id = "slice-02"
    _exit_code, stdout, stderr = dispatch(project, slice_id, lane=None)

    told = line_stating(stdout, stderr, CHARTER_WORD, "INDETERMINATE")
    assert told is not None, (
        "the undeclarable third state never reached the operator's screen. "
        "The ledger records it; the operator is told nothing, so the state is "
        f"invisible exactly where it matters. charter lines: "
        f"{charter_lines(stdout, stderr)!r}, "
        f"screen={operator_visible(stdout, stderr)[-1500:]!r}"
    )
    assert line_stating(stdout, stderr, CHARTER_WORD, "EXEMPT") is None, (
        "the INDETERMINATE state must not be reported as EXEMPT -- 'we could "
        "not tell' and 'we decided none is owed' are different answers, and "
        f"collapsing them is the defect. line seen: {told!r}"
    )


def test_exempt_work_is_never_told_it_owes_a_charter(project: Path) -> None:
    """@driving_port @real-io

    NEGATIVE, made NON-VACUOUS. The charter's second negative row: an
    `@infrastructure`/`@prefactoring`-class slice is never told it owes a
    charter (a false-positive obligation sends the operator off to write one
    nobody wants).

    Today this negative passes only VACUOUSLY -- nothing about charters is
    printed at all, so there is no false positive available to catch, and a
    negative that cannot fail is not evidence. The POSITIVE CONTROL below
    closes that: the same run must also carry the EXEMPT statement, so the
    absence of the REQUIRED statement is a real discrimination rather than the
    absence of any output whatsoever.
    """
    # covers: R21
    slice_id = "slice-01"
    _exit_code, stdout, stderr = dispatch(project, slice_id, lane="prefactoring")

    # POSITIVE CONTROL -- proves the surface is speaking at all.
    assert line_stating(stdout, stderr, CHARTER_WORD, "EXEMPT") is not None, (
        "VACUOUS NEGATIVE: nothing is said about the charter obligation on "
        "this run, so 'never told it owes one' holds only because the surface "
        "is silent. The control must speak before its absence means anything. "
        f"charter lines: {charter_lines(stdout, stderr)!r}"
    )
    # THE NEGATIVE ITSELF -- now discriminating.
    assert line_stating(stdout, stderr, CHARTER_WORD, "REQUIRED") is None, (
        "EXEMPT work was told it OWES a charter -- a false-positive obligation "
        f"that sends the operator to write one nobody wants. charter lines: "
        f"{charter_lines(stdout, stderr)!r}"
    )
    assert line_stating(stdout, stderr, "des charter-scaffold") is None, (
        "EXEMPT work was handed the charter-producing command; being given the "
        "cure implies the disease. "
        f"charter lines: {charter_lines(stdout, stderr)!r}"
    )


@pytest.mark.parametrize(
    "lane",
    [None, "bugfix", "prefactoring", "charter"],
    ids=["no-lane", "bugfix", "prefactoring", "charter"],
)
def test_a_declaration_written_to_the_ledger_is_never_left_unsaid_on_screen(
    project: Path, lane: str | None
) -> None:
    """@driving_port @real-io

    The charter's FIRST negative row, stated as the joint condition it really
    is: "dispatching any slice never leaves the charter-obligation question
    unanswered or buried -- the operator is never forced to open the
    feature-delta or the Slice Plan by hand".

    So the two propositions are BOUND: whenever a `CharterObligationDeclared`
    record is written, the same invocation must also SAY it. Asserting either
    half alone is what let a green suite coexist with a FAIL verdict --
    on-disk-and-unsaid is the exact shape of "buried". Parametrized across
    every lane (and the lane-less default) so no route out of the dispatch can
    write silently.
    """
    # covers: R22
    slice_id = "slice-01"
    _exit_code, stdout, stderr = dispatch(project, slice_id, lane=lane)

    recorded = declared_obligation(ledger_for(project), slice_id)
    if recorded is None:
        pytest.skip("no declaration written for this lane -- nothing to bind")
    assert line_stating(stdout, stderr, CHARTER_WORD, recorded) is not None, (
        f"a {recorded!r} obligation was written to "
        f"{ledger_for(project)} and never stated on screen. A ledger file the "
        "CLI does not name IS buried: the operator would have to know the "
        "path, know the record name, and go read it. "
        f"charter lines: {charter_lines(stdout, stderr)!r}"
    )
