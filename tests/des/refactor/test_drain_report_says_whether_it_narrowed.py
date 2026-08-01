# @feature-impacted-test-selector-arity-fix
# @slice-01
"""A maintainer reading a drain report can tell "I narrowed" from "I could
not narrow" -- feature impacted-test-selector-arity-fix, slice-01.

Runtime behaviour is DELIBERATELY UNCHANGED by this slice (the whole tree is
still what actually runs where it ran before) -- these scenarios change only
what is OBSERVABLE: ``ImpactedTestSelection`` carries the three-valued
``SelectionOutcome``, the shipped selector answers ``INDETERMINATE`` with a
named cause when there is nothing to narrow against, and
``DrainResult.test_target_scope`` (plus the new ``selection_reason``) is
DERIVED from the selector's actual answer rather than assigned the constant
``"fast+impacted"`` at all three call sites (``drain_one``'s success path,
``drain_batch``'s success path, and ``_refused``).

Layer 3 composition (in-process, L2 default) for every scenario except the
one ``@walking_skeleton`` -- drives ``RefactorDrainService.drain_one`` /
``.drain_batch`` directly with the real production adapters (Pillar 3),
never a re-forked interpreter. ``ImpactedTestSelectorPort`` is driven by
BOTH treatments deliberately (DISTILL WS Strategy): the REAL
``HeuristicImpactedTestSelectorAdapter`` in scenarios 3 and 6 (what does the
shipped selector answer), and the configured ``SelectorAnsweringOutcome``
stand-in in scenarios 2, 4, 5 (what does the drain DO with a given answer) --
neither alone is sufficient.

RED-scaffold note: ``SelectionOutcome`` and ``ImpactedTestSelection.outcome``/
``.reason`` exist (port scaffold, vocabulary only, no law -- see
``__SCAFFOLD__`` in ``impacted_test_selector_port.py``), but nothing in
``RefactorDrainService``/``DrainResult``/``des.cli.refactor`` reads or
derives from them yet (Finding 2: the selection is computed then discarded
one line later). Every scenario below therefore currently fails at its
OBSERVABLE assertion -- an ``AssertionError`` comparing what the drain
reported against what this slice requires it to report -- never at an
import/collection/fixture error. That is the correct RED classification
(MISSING_FUNCTIONALITY) for a scaffolded-but-not-yet-derived vertical slice.
"""

from __future__ import annotations

import pytest

from des.ports.driven_ports.impacted_test_selector_port import SelectionOutcome

from .composition import RefactorSwarmComposition
from .doubles import SelectorAnsweringOutcome


pytestmark = pytest.mark.acceptance

#: Local re-declaration of the production constant this slice retires as the
#: UNCONDITIONAL answer (``refactor_drain_service.py:87``) -- same pattern
#: the sibling ``test_tests_red_and_exception_exits_clean_up_worktree.py``
#: already uses for ``_TESTS_RED_REASON``: a literal used ONLY to prove it is
#: no longer what gets reported, never re-imported as the thing under test.
_TEST_SCOPE_FAST_IMPACTED = "fast+impacted"

#: Every valid outcome token, read off the typed enum (never re-typed) -- the
#: same "read off the enum, never re-typed" convention
#: ``composition.py:_fixer_verdict_line`` already documents for entry-gate
#: verdicts.
_ALL_OUTCOME_TOKENS = tuple(outcome.value for outcome in SelectionOutcome)

#: Local re-declaration of the production refusal-reason literal
#: (``refactor_drain_service.py:101``) -- same reuse pattern
#: ``test_tests_red_and_exception_exits_clean_up_worktree.py`` already uses;
#: a literal used to prove the SAME refusal still fires, never re-imported
#: as the thing under test.
_TESTS_RED_REASON = "MergeBlockedTestsRed"


def test_maintainer_reads_in_the_terminal_whether_the_drain_narrowed(tmp_path):
    """@walking_skeleton @driving_port @real-io -- covers R6.

    Given a real hermetic repo with one pending item and a well-behaved
    fixer, When the maintainer runs the REAL installed ``des refactor`` CLI
    (Layer 1 subprocess -- the one walking-skeleton for this feature), Then
    the terminal report names WHICH of the three things the real selector's
    answer was -- never only the bare "Drained 1 item: ... -> merged" line
    today's ``_report`` prints, which carries no scope information at all.
    """
    # covers: R6
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    result = composition.run_refactor_cli_subprocess(
        agent_cmd=composition.agent_cmd_that_makes_a_benign_real_change()
    )

    assert result.exit_code == 0, (
        f"a benign fix must still merge exactly as before this slice; "
        f"exit_code={result.exit_code!r}, stderr={result.stderr!r}"
    )
    assert any(token in result.stdout for token in _ALL_OUTCOME_TOKENS), (
        "a maintainer reading the terminal report must be able to tell "
        "WHICH of narrowed/not_narrowable/indeterminate the drain's "
        f"selection was; got stdout={result.stdout!r} (none of "
        f"{_ALL_OUTCOME_TOKENS!r} appear anywhere in it)"
    )


def test_the_reported_scope_is_derived_from_the_answer_the_selector_gave(tmp_path):
    """@driving_port @real-io -- covers R3, R4.

    CT-1, the oracle that makes this slice falsifiable: two drain runs whose
    selector answered DIFFERENTLY must report DIFFERENT
    ``test_target_scope`` values. No constant can satisfy both assertions at
    once -- today's unconditional ``"fast+impacted"`` fails this test on the
    second drain no matter which one runs first.
    """
    # covers: R3
    # covers: R4
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()

    composition.seed_pile_item(item_id="TD-001")
    narrowed_report = composition.observe_reported_scope(
        selector=SelectorAnsweringOutcome(
            outcome=SelectionOutcome.NARROWED,
            reason="importers of the changed module",
            narrowed=True,
        ),
    )

    composition.seed_pile_item(item_id="TD-002")
    not_narrowable_report = composition.observe_reported_scope(
        selector=SelectorAnsweringOutcome(
            outcome=SelectionOutcome.NOT_NARROWABLE,
            reason="the changed root conftest.py is imported everywhere",
            narrowed=False,
        ),
    )

    assert (
        narrowed_report.test_target_scope != not_narrowable_report.test_target_scope
    ), (
        "two drain runs whose selector answered DIFFERENTLY (NARROWED vs "
        "NOT_NARROWABLE) must report DIFFERENT test_target_scope values "
        f"(CT-1); got the SAME value {narrowed_report.test_target_scope!r} "
        "for both -- a hard-coded scope string satisfies neither run"
    )


def test_the_shipped_selector_answers_indeterminate_when_no_change_set_arrives(
    tmp_path,
):
    """@driving_port @real-io -- covers R1, R2, R4.

    Given a real drain whose agent makes NO tracked change to the worktree
    (the harness default -- nothing for the REAL selector to narrow
    against), When the item drains with the REAL
    ``HeuristicImpactedTestSelectorAdapter`` wired in, Then the shipped
    selector's answer is reported as INDETERMINATE with a reason naming the
    missing input -- never silently folded into the unconditional
    ``"fast+impacted"`` constant, AND never the SAME reason a genuinely
    different real-selector answer (NOT_NARROWABLE) reports.

    CT-2, added after review (2026-08-01): the first version of this
    scenario asserted only ``selection_reason is not None`` and
    ``!= "fast+impacted"`` -- an implementation that relabels ALL THREE of
    the real adapter's fallback sites uniformly as NOT_NARROWABLE, never
    emitting INDETERMINATE at all, would satisfy that version (and every
    other scenario in this file) while still collapsing the three-valued
    outcome back into two. This version puts the REAL adapter's two
    non-``NARROWED`` answers side by side -- (a) no tracked change at all
    (this scenario's own arrangement, the INDETERMINATE cause) vs (b) a
    REAL tracked change the heuristic finds no candidate test directory for
    (this hermetic repo has no ``tests/`` directory at all -- the
    NOT_NARROWABLE cause, reached via
    ``agent_cmd_that_makes_a_benign_real_change``) -- and asserts the two
    reported reasons DIFFER from each other, not merely from the retired
    constant.

    Reachability note, made explicit rather than left implicit (review
    finding): as production code stands today,
    ``RefactorDrainService._run_tests`` (``refactor_drain_service.py:739``)
    returns ``_UNOBSERVED_PLACEHOLDER_RUN`` BEFORE calling
    ``select()`` at all whenever ``changed_paths`` is empty -- so the real
    adapter's own INDETERMINATE branch (``tsunami_impacted_test_selector_
    adapter.py:154``, "no changed_paths") is UNREACHABLE from THIS
    scenario's arrangement via any current call site. This scenario's first
    assertion is on the AGGREGATE's observable report, not on whether
    ``select()`` was literally invoked for the no-change-set leg -- DELIVER
    must therefore either (a) call ``select()`` for reporting purposes on
    that early-return leg too, without necessarily spawning pytest
    (preserving R7's unchanged-runtime-behaviour requirement), or (b)
    synthesize the INDETERMINATE outcome+reason at the
    ``_run_tests``/``drain_one`` level directly for this specific
    "no changed_paths supplied at all" case, without consulting the
    adapter. Either satisfies this scenario; DISTILL does not prescribe
    which -- that choice belongs to DELIVER.
    """
    # covers: R1
    # covers: R2
    # covers: R4
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()

    composition.seed_pile_item(item_id="TD-001")
    no_change_result = composition.run_drain_one_item()

    composition.seed_pile_item(item_id="TD-002")
    real_change_result = composition.run_drain_one_item(
        agent_cmd=composition.agent_cmd_that_makes_a_benign_real_change()
    )

    no_change_reason = getattr(no_change_result, "selection_reason", None)
    real_change_reason = getattr(real_change_result, "selection_reason", None)

    assert no_change_reason is not None, (
        "R1/R2: a drain whose agent made no tracked change must report WHY "
        "the shipped selector could not narrow (e.g. 'no change set was "
        "supplied') via DrainResult.selection_reason -- got "
        f"{no_change_reason!r} (the field is still absent/unpopulated on "
        "DrainResult); see this scenario's reachability note re the "
        "_run_tests early-return"
    )
    assert real_change_reason is not None, (
        "R1: a drain whose agent made a real tracked change the heuristic "
        "cannot narrow (NOT_NARROWABLE) must ALSO report WHY via "
        f"DrainResult.selection_reason -- got {real_change_reason!r}"
    )
    assert no_change_result.test_target_scope != _TEST_SCOPE_FAST_IMPACTED, (
        "R1: the real selector's INDETERMINATE answer must not be reported "
        f"as the unconditional {_TEST_SCOPE_FAST_IMPACTED!r} constant; got "
        f"test_target_scope={no_change_result.test_target_scope!r}"
    )
    assert no_change_reason != real_change_reason, (
        "CT-2/R4: NOT_NARROWABLE and INDETERMINATE must be distinguishable "
        "at the aggregate -- an implementation that relabels every "
        "non-NARROWED fallback uniformly (e.g. always NOT_NARROWABLE, "
        "never INDETERMINATE) would satisfy every OTHER assertion in this "
        f"file yet fail THIS one; got the SAME reason {no_change_reason!r} "
        "for both a no-change-set drain and a real-change-the-heuristic-"
        "cannot-narrow drain"
    )
    assert no_change_result.test_target_scope != real_change_result.test_target_scope, (
        "CT-1/CT-2/R4, the residual review finding: the two REAL-selector "
        "answers must differ in the SCOPE they report, not only in the "
        "prose reason string -- an implementation that assigns INDETERMINATE "
        "and NOT_NARROWABLE the SAME test_target_scope while writing a "
        "different selection_reason for each would satisfy the reason-only "
        "assertion above yet still collapse the tri-state on the exact "
        "field CT-1/CT-2 are defined over; got the SAME "
        f"test_target_scope={no_change_result.test_target_scope!r} for both "
        "a no-change-set (INDETERMINATE) drain and a real-change-the-"
        "heuristic-cannot-narrow (NOT_NARROWABLE) drain"
    )


def test_an_outcome_without_a_cause_is_never_reported(tmp_path):
    """@driving_port @real-io @error @negative -- covers R8.

    CT-3's arrangement, reached through the REAL driving port: a selector
    answering a non-``NARROWED`` outcome with an EMPTY reason must never
    reach a rendered, successfully-drained report. The drain must refuse
    loudly instead -- whether by a graceful refusal ``DrainResult`` or by
    the causeless construction raising and the drain's own
    ``except BaseException: cleanup; raise`` propagating it (``ScopeReport``
    represents either shape identically; see its docstring).
    """
    # covers: R8
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    report = composition.observe_reported_scope(
        selector=SelectorAnsweringOutcome(
            outcome=SelectionOutcome.NOT_NARROWABLE, reason="", narrowed=False
        ),
    )

    assert not report.drained, (
        "CT-3: a NOT_NARROWABLE outcome constructed with an EMPTY reason "
        "must never reach a rendered, successfully-drained report -- the "
        "drain must refuse loudly instead; got drained=True, "
        f"test_target_scope={report.test_target_scope!r}"
    )


@pytest.mark.parametrize("reporting_path", ["single-item", "batch"])
def test_every_reporting_path_derives_the_scope_it_reports(tmp_path, reporting_path):
    """@driving_port @real-io -- covers R5.

    No reporting path keeps the constant: the single-item success path
    (``drain_one``) and the batch success path (``drain_batch``) must BOTH
    derive their reported reason from the selector's OWN configured answer,
    never the literal ``"fast+impacted"`` every path assigns unconditionally
    today.
    """
    # covers: R5
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()

    configured_reason = "importers of the changed module"
    selector = SelectorAnsweringOutcome(
        outcome=SelectionOutcome.NARROWED, reason=configured_reason, narrowed=True
    )

    if reporting_path == "single-item":
        # ``observe_reported_scope``'s default agent_cmd makes a real,
        # tracked change to test_toy.py, so it must already exist and be
        # tracked -- unlike the batch path below, which fixes each item's
        # OWN new file and needs no pre-existing toy test.
        composition.seed_toy_passing_test()
        composition.seed_pile_item(item_id="TD-001")
        reports = (composition.observe_reported_scope(selector=selector),)
    else:
        # Deliberately NO seed_toy_passing_test() here: two concurrently
        # merged items BOTH really executing pytest against the SAME toy
        # test file each produce a worktree-path-embedded __pycache__ .pyc
        # whose content differs per worktree -- a genuine merge conflict on
        # THIS harness's own bytecode artifact, orthogonal to what this
        # scenario verifies. Zero test files means zero bytecode to
        # conflict over (precedent:
        # test_disjoint_items_drain_concurrently_each_in_its_own_worktree_
        # and_venv in test_slice_02_concurrent_drain.py drains successfully
        # the same way, with no toy test seeded either).
        composition.seed_disjoint_pile_items(("TD-001", "TD-002"))
        reports = composition.observe_reported_scope_for_batch(selector=selector)

    assert reports, f"no ScopeReport observed for reporting_path={reporting_path!r}"
    for report in reports:
        assert report.selection_reason == configured_reason, (
            f"R5 ({reporting_path}): every reporting path must derive its "
            "reported reason from the selector's OWN answer, never the "
            f"constant; got selection_reason={report.selection_reason!r}, "
            f"expected {configured_reason!r}"
        )


@pytest.mark.parametrize("agent_kind", ["benign", "breaks-the-suite"])
def test_a_drain_that_could_not_narrow_still_runs_the_tests_it_ran_before(
    tmp_path, agent_kind
):
    """@driving_port @real-io @error -- covers R7, R3.

    R7's negative oracle, the presidio a visibility-only slice most needs:
    Given the REAL selector (this hermetic repo has no ``tests/`` directory,
    so it cannot narrow either agent's change), When the item drains with a
    benign fix vs a suite-breaking fix, Then the drain's VERDICT (merged vs
    refused-for-tests-red) is EXACTLY the one it produced before this slice
    -- this slice changes only what is OBSERVABLE about the selection, never
    which tests actually ran or what they decided. AND (R3) the per-item
    gate must still report WHY the selector reached its scope, not merely
    the constant, on BOTH the success and the refusal path.
    """
    # covers: R7
    # covers: R3
    composition = RefactorSwarmComposition(tmp_path)
    composition.init_git_repo()
    composition.seed_toy_passing_test()
    composition.seed_pile_item(item_id="TD-001")

    if agent_kind == "benign":
        agent_cmd = composition.agent_cmd_that_makes_a_benign_real_change()
    else:
        agent_cmd = (
            composition.agent_cmd_that_breaks_the_test_suite_after_passing_entry_gate()
        )

    result = composition.run_drain_one_item(agent_cmd=agent_cmd)

    if agent_kind == "benign":
        assert result.merged is True, (
            "R7: a benign fix must still merge exactly as it did before "
            f"this slice; got merged={result.merged!r}, "
            f"refusal_reason={result.refusal_reason!r}"
        )
    else:
        assert result.merge_blocked_reason == _TESTS_RED_REASON, (
            "R7: a suite-breaking fix must still be refused for the SAME "
            f"reason as before this slice; got "
            f"merge_blocked_reason={result.merge_blocked_reason!r}, "
            f"expected {_TESTS_RED_REASON!r}"
        )

    assert getattr(result, "selection_reason", None) is not None, (
        "R3: the per-item gate must report WHY the selector reached its "
        "scope, not merely the constant, on this "
        f"{agent_kind!r} path -- selection_reason is still absent from "
        f"DrainResult (got {getattr(result, 'selection_reason', 'MISSING')!r})"
    )
