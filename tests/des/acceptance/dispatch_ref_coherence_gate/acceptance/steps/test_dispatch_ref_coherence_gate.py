"""pytest-bdd binding for dispatch-template-ssot-reconciliation slice-04
(dispatch-ref coherence gate).

Driving surface (Core Principle 7 -- in-process DEFAULT, subprocess RESERVED to
one @walking_skeleton per command): AT-1 (@walking_skeleton) and AT-6
(git-absent-from-PATH) drive the REAL ``des verify-dispatch-ref-coherence``
subcommand as a Layer-3 subprocess through the shipped ``des`` dispatcher; every
other scenario drives the REAL ``verify_dispatch_ref_coherence.main(argv)``
entry directly in-process (Layer 2), no interpreter fork. Both surfaces are
implemented in ``composition_dispatch_ref_coherence.py`` -- see its module
docstring for the full per-channel RED-reason statement. Step bodies delegate
to the composition root; no business logic in step bodies (Mandate-12).

Active-RED scaffold (atdd_pure -- NOT @skip): each scenario is RED until DELIVER
ships ``src/des/cli/verify_dispatch_ref_coherence.py`` + its
``_SubcommandRow`` registration in ``src/des/cli/__main__.py``. At HEAD:
  * the two subprocess scenarios (AT-1, AT-6) see the dispatcher reject the
    unknown subcommand at argv-parse time (``invalid choice``, exit 2) -- no
    verdict token is printed;
  * the in-process scenarios (AT-2, both AT-3 variants, AT-4, AT-4b, AT-5) see a
    lazy ``from des.cli.verify_dispatch_ref_coherence import main`` raise
    ``ModuleNotFoundError`` INSIDE the When call (never at collection time).
Either way ``verdict`` is None -> every Then fires the SAME semantic
AssertionError naming the missing gate module, never a collection / import /
setup error.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_dispatch_ref_coherence import DispatchRefCoherenceComposition
from .domain_types import DispatchRefVerdict


scenarios("../dispatch-ref-coherence-gate.feature")


@pytest.fixture
def gate(tmp_path: Path) -> DispatchRefCoherenceComposition:
    return DispatchRefCoherenceComposition(tmp_path=tmp_path)


# --- Given -------------------------------------------------------------------


@given(
    "a skill file carrying a valid dispatch-ref pointer with zero inline restatement"
)
def given_skill_valid_pointer_zero_restatement(
    gate: DispatchRefCoherenceComposition,
) -> None:
    gate.given_skill_with_valid_pointer_zero_restatement()


@given("a skill file carrying no dispatch-ref pointer")
def given_skill_no_pointer(gate: DispatchRefCoherenceComposition) -> None:
    gate.given_skill_with_no_pointer()


@given("a skill file carrying a dispatch-ref pointer naming an unresolvable lane")
def given_skill_unresolvable_lane(gate: DispatchRefCoherenceComposition) -> None:
    gate.given_skill_with_unresolvable_lane()


@given("a skill file carrying a dispatch-ref pointer naming an unresolvable mode")
def given_skill_unresolvable_mode(gate: DispatchRefCoherenceComposition) -> None:
    gate.given_skill_with_unresolvable_mode()


@given(
    "a skill file carrying a valid dispatch-ref pointer that also inline-restates "
    "dispatch section bodies"
)
def given_skill_valid_pointer_with_restatement(
    gate: DispatchRefCoherenceComposition,
) -> None:
    gate.given_skill_with_valid_pointer_and_inline_restatement()


@given(
    "a skill file carrying a valid dispatch-ref pointer that mentions exactly "
    "one dispatch section id"
)
def given_skill_valid_pointer_with_single_mention(
    gate: DispatchRefCoherenceComposition,
) -> None:
    gate.given_skill_with_valid_pointer_and_single_section_mention()


@given("a skill file path that does not exist on disk")
def given_skill_path_absent(gate: DispatchRefCoherenceComposition) -> None:
    gate.given_skill_path_that_does_not_exist()


@given("a process environment where no git executable is reachable on PATH")
def given_no_git_on_path(gate: DispatchRefCoherenceComposition) -> None:
    gate.given_no_git_reachable_on_path()


# --- When ----------------------------------------------------------------------


@when(
    "the maintainer runs the installed des verify-dispatch-ref-coherence command "
    "over that skill file"
)
def when_maintainer_runs_gate_via_installed_command(
    gate: DispatchRefCoherenceComposition,
) -> None:
    """AT-1 (@walking_skeleton) + AT-6 (git-boundary) -- subprocess, RESERVED."""
    gate.when_maintainer_runs_dispatch_ref_coherence_gate_via_installed_command()


@when("the maintainer runs the dispatch-ref coherence gate over that skill file")
def when_maintainer_runs_gate_in_process(
    gate: DispatchRefCoherenceComposition,
) -> None:
    """Every other scenario -- in-process (Layer 2), the DEFAULT surface."""
    gate.when_maintainer_runs_dispatch_ref_coherence_gate_in_process()


# --- Then ------------------------------------------------------------------------


@then("the dispatch-ref coherence gate emits the PASS verdict")
def then_gate_emits_pass(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_gate_emits_verdict(DispatchRefVerdict.PASS)


@then("the dispatch-ref coherence gate emits the FAIL verdict")
def then_gate_emits_fail(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_gate_emits_verdict(DispatchRefVerdict.FAIL)


@then("the dispatch-ref coherence gate emits the INDETERMINATE verdict")
def then_gate_emits_indeterminate(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_gate_emits_verdict(DispatchRefVerdict.INDETERMINATE)


@then(
    "the failure diagnostic explains the missing pointer, why it matters, and "
    "how to fix it by running des dispatch"
)
def then_missing_pointer_diagnostic(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_missing_pointer_diagnostic_is_self_explaining()


@then(
    "the failure diagnostic names the unresolvable lane, why it matters, and "
    "how to fix it by running des dispatch"
)
def then_unresolvable_lane_diagnostic(
    gate: DispatchRefCoherenceComposition,
) -> None:
    gate.then_unresolvable_lane_diagnostic_is_self_explaining()


@then(
    "the failure diagnostic names the unresolvable mode, why it matters, and "
    "how to fix it by running des dispatch"
)
def then_unresolvable_mode_diagnostic(
    gate: DispatchRefCoherenceComposition,
) -> None:
    gate.then_unresolvable_mode_diagnostic_is_self_explaining()


@then(
    "the failure diagnostic names the restated section body, why it matters, "
    "and how to fix it by running des dispatch"
)
def then_restatement_diagnostic(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_restatement_diagnostic_is_self_explaining()


@then("the indeterminate diagnostic names the missing skill file")
def then_indeterminate_diagnostic(gate: DispatchRefCoherenceComposition) -> None:
    gate.then_indeterminate_diagnostic_names_missing_skill_file()
