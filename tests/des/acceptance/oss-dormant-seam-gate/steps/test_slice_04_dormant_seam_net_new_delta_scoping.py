"""pytest-bdd binding for the dormant-seam gate net-new-delta scoping (slice-04).

Driving port: the production ``des dormant-seam-gate`` composition-root CLI,
invoked as a subprocess black box (Mandate-13 driving-port-only, Layer 3
subprocess). Step bodies delegate to the slice-04 composition root
(``composition_slice_04.py``); no production module is imported-and-called at the
step boundary, and no business logic lives in a step body (Mandate-12: each body
is a single delegation).

The ``scenarios(...)`` call binds every scenario in the slice-04 ``.feature`` via
the RELATIVE path from this steps/ module -- the proven-collecting form. Every step
decorator's literal text is UNIQUE within this feature directory (S1
step-text-uniqueness invariant): slice-04 phrases its Given / When / Then literals
("delta-scoped dormant-seam gate", the pre-existing / discrimination / modified-file
Givens, the "delta-scoped gate exits with code zero" Then) so they do NOT collide
with slice-01/02/03's step literals in the same directory -- no global-registry
shadowing.

RED-for-right-reason / GREEN-on-author: the shipped slice-01/02/03 production
ALREADY scopes to the net-new delta -- ``GitChangedSymbolAdapter`` uses
``git diff --diff-filter=A`` (added files only) and ``_parse_added_src_modules``
parses ONLY files in that delta -- so a base-committed (pre-existing) symbol is
never parsed and never flagged, and a modified-file's net-new symbol is below the
added-FILE floor. slice-04 is therefore a GREEN-ON-AUTHOR regression PIN: it pins
the no-retroactive-blast safety property (DISCUSS D3) and resolves OQ-1 to the
added-FILE granularity, both already satisfied by the shipped delta -- no
production change is required. The PIN guards the property against a future
regression. The discrimination scenario's net-new flag is the KPI-1 non-vacuity
control (scoping is NOT vacuously flag-nothing).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_04 import DormantSeamScopingComposition


scenarios("../slice-04-dormant-seam-net-new-delta-scoping.feature")


@pytest.fixture
def scoping_composition() -> DormantSeamScopingComposition:
    return DormantSeamScopingComposition()


# --- Given -------------------------------------------------------------------


@given(
    "a dormant effectful seam that already existed on the static tree before this change"
)
def given_pre_existing_seam(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.given_pre_existing_static_tree_seam()


@given(
    "a net-new dormant seam alongside a pre-existing dormant seam already on the static tree"
)
def given_net_new_alongside_pre_existing(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.given_net_new_alongside_pre_existing_seam()


@given(
    "a net-new dormant symbol added to a file that already existed on the static tree"
)
def given_modified_file_add(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.given_net_new_symbol_in_modified_file()


# --- When --------------------------------------------------------------------


@when("the developer runs the delta-scoped dormant-seam gate at GREEN-phase")
def when_runs_delta_scoped_gate(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.when_developer_runs_the_gate()


# --- Then --------------------------------------------------------------------


@then("the gate leaves the pre-existing static-tree seam unflagged and unnamed")
def then_pre_existing_unflagged(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.then_pre_existing_seam_unflagged()


@then(
    "the gate flags only the net-new seam and leaves the pre-existing seam out of scope"
)
def then_only_net_new_flagged(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.then_only_net_new_flagged_pre_existing_out_of_scope()


@then("the gate names the net-new seam in its loud warning")
def then_net_new_named(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.then_net_new_seam_named_in_warning()


@then(
    "the gate leaves the modified-file symbol out of scope at the added-file granularity floor"
)
def then_modified_file_out_of_scope(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.then_modified_file_symbol_out_of_scope()


@then("the delta-scoped gate exits with code zero")
def then_delta_scoped_exits_zero(
    scoping_composition: DormantSeamScopingComposition,
) -> None:
    scoping_composition.then_exits_zero()
