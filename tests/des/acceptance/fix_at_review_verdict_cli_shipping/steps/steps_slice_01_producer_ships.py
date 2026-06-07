"""Step definitions for slice-01 — the recorder ships to an installed instance.

Mandate-12 criterion 3: every step body is a typed lookup plus one composition
call (no control flow, no inline business logic). The composition root
(composition.py) is the single source of truth for behaviour.

S1 (step-text uniqueness): every literal step string here is unique within the
feature directory — slice-02 uses distinct literals (see
steps_slice_02_installed_operator.py).
"""

from __future__ import annotations

import pytest
from pytest_bdd import given, then, when

from .composition import ShimSet, ShippingComposition, recorder_stem
from .domain_types import RecorderModule


@pytest.fixture()
def shipping(tmp_path, request) -> ShippingComposition:
    """Production-wired composition root anchored at the real repo root.

    slice-01 drives the real source tree + frozen floor (repo-relative); the
    installed_root is a tmp_path sandbox unused by slice-01 scenarios.
    """
    repo_root = request.config.rootpath
    return ShippingComposition(repo_dir=repo_root, installed_root=tmp_path)


# --- Given --------------------------------------------------------------------


@given(
    "the install discovers every canonical recorder from the source tree it ships from",
    target_fixture="discovered_shims",
)
def given_install_discovers_recorders(shipping: ShippingComposition) -> ShimSet:
    return shipping.discover_shipped_recorders()


@given(
    "an installed-shape runtime where the recorder lives in the canonical recorder namespace"
)
def given_installed_shape_runtime(shipping: ShippingComposition) -> None:
    return None


@given(
    "the frozen ship-floor that the install guarantees never to drop",
    target_fixture="ship_floor",
)
def given_frozen_ship_floor(shipping: ShippingComposition) -> frozenset[str]:
    return shipping.frozen_ship_floor()


# --- When ---------------------------------------------------------------------


@when(
    "the operator lists the recorders that will ship to an installed instance",
    target_fixture="shipped_set",
)
def when_operator_lists_shipped_recorders(discovered_shims: ShimSet) -> ShimSet:
    return discovered_shims


@when(
    "the operator loads the AT-review verdict recorder from that namespace",
    target_fixture="import_result",
)
def when_operator_loads_recorder(shipping: ShippingComposition):
    return shipping.load_recorder_from_installed_namespace()


@when(
    "the operator inspects the frozen ship-floor",
    target_fixture="inspected_floor",
)
def when_operator_inspects_floor(ship_floor: frozenset[str]) -> frozenset[str]:
    return ship_floor


# --- Then ---------------------------------------------------------------------


@then("the AT-review verdict recorder is among the recorders that will ship")
def then_recorder_among_shipped(shipped_set: ShimSet) -> None:
    assert recorder_stem(RecorderModule.AT_REVIEW_VERDICT) in shipped_set.stems


@then("no other shipped recorder is dropped")
def then_no_other_recorder_dropped(shipped_set: ShimSet) -> None:
    assert recorder_stem(RecorderModule.CARPACCIO_SLICE_GATE) in shipped_set.stems


@then("the recorder loads without error")
def then_recorder_loads_without_error(import_result) -> None:
    assert import_result.exit_code == 0, import_result.stderr


@then("the AT-review verdict recorder is named in the frozen ship-floor")
def then_recorder_named_in_floor(inspected_floor: frozenset[str]) -> None:
    assert recorder_stem(RecorderModule.AT_REVIEW_VERDICT) in inspected_floor
