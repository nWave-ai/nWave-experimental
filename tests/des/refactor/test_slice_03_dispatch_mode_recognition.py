# @feature-des-refactor-fixer-swarm
# @slice-03
"""Dispatch-mode recognition -- des-refactor-fixer-swarm slice-03 (AT-11, D8).

@slice-03 @feature-des-refactor-fixer-swarm @driving_port
@contract-shape:pure-function.

Value statement (feature-delta Slice Plan slice-03): "A fixer/finder-mode
dispatch is spine-recognized via `DES-MODE: refactor` / `DES-MODE: find` -- no
per-dispatch `DES-EXEMPT` hand-typed justification required, and the dispatch is
NOT forced through the classic-dispatch completeness check a markerless crafter
dispatch receives."

Behavior (a) -- pure-function classifier recognition (layer 1-2). The driving
port is the two new sibling classifiers `classify_refactor_dispatch` /
`classify_find_dispatch` in `des.domain.des_marker_parser`, which mirror the
shipped `classify_atdd_pure_dispatch`. Max-density parametrized decision table
over {refactor, find, atdd_pure, orchestrator, absent} x expected-verdict for
BOTH classifiers -- NOT a swarm of example ATs
(feedback_ats_max_pbt_parametrize_density). The parse-then-classify round-trip
reuses the SHIPPED `DesMarkerParser` + `_MODE_PATTERN` grammar verbatim
(feature-delta Test Reuse AT-11: EXTEND the existing dispatch-marker recognition
idiom, ZERO new marker syntax).

RED-scaffold note: `classify_refactor_dispatch` / `classify_find_dispatch` are
`__SCAFFOLD__` stubs raising AssertionError (MISSING_FUNCTIONALITY) -- so every
row below COLLECTS and fails RED for the right reason (impl missing), never
BROKEN (ImportError). A_GREEN replaces the stub bodies with the real two-way
(valid / absent) rule; it does NOT re-author this AT.

covers: R-DES-REFACTOR-SLICE-03-CLASSIFIER
"""

from __future__ import annotations

import pytest

from des.domain.des_marker_parser import (
    DesMarkerParser,
    DesMarkers,
    classify_find_dispatch,
    classify_refactor_dispatch,
)

from .domain_types import DispatchMode, RecognitionVerdict


pytestmark = pytest.mark.acceptance


def _markers_for(mode: DispatchMode) -> DesMarkers:
    """Parse a real dispatch prompt carrying the given DES-MODE via the SHIPPED
    production parser -- the driving-port round-trip, never a hand-built
    ``DesMarkers`` (Pillar 3: exercise the real ``_MODE_PATTERN`` grammar).

    ``DispatchMode.ABSENT`` omits the DES-MODE line entirely so the parser sees
    ``mode=None`` -- the classic-dispatch case.
    """
    lines = ["<!-- DES-VALIDATION : required -->"]
    if mode is not DispatchMode.ABSENT:
        lines.append(f"<!-- DES-MODE : {mode.value} -->")
    return DesMarkerParser().parse("\n".join(lines))


# Decision tables. The refactor classifier recognizes ONLY refactor mode; the
# find classifier recognizes ONLY find mode; every other / absent mode is
# 'absent'. Neither table carries a DEFECTIVE row -- a well-formed fixer/finder
# dispatch is never classified 'defective' (proved by construction: the expected
# column is drawn only from {VALID, ABSENT}).
_REFACTOR_TABLE = [
    (DispatchMode.REFACTOR, RecognitionVerdict.VALID),
    (DispatchMode.FIND, RecognitionVerdict.ABSENT),
    (DispatchMode.ATDD_PURE, RecognitionVerdict.ABSENT),
    (DispatchMode.ORCHESTRATOR, RecognitionVerdict.ABSENT),
    (DispatchMode.ABSENT, RecognitionVerdict.ABSENT),
]
_FIND_TABLE = [
    (DispatchMode.FIND, RecognitionVerdict.VALID),
    (DispatchMode.REFACTOR, RecognitionVerdict.ABSENT),
    (DispatchMode.ATDD_PURE, RecognitionVerdict.ABSENT),
    (DispatchMode.ORCHESTRATOR, RecognitionVerdict.ABSENT),
    (DispatchMode.ABSENT, RecognitionVerdict.ABSENT),
]


@pytest.mark.parametrize(("mode", "expected"), _REFACTOR_TABLE, ids=lambda v: v.value)
def test_classify_refactor_dispatch_recognizes_only_refactor_mode(
    mode: DispatchMode, expected: RecognitionVerdict
) -> None:
    """covers: R-DES-REFACTOR-SLICE-03-CLASSIFIER

    Given a dispatch carrying `DES-MODE: <mode>`, When
    `classify_refactor_dispatch` classifies it, Then a refactor-mode dispatch is
    `valid` (spine-recognized) and every other / absent mode is `absent` --
    never `defective` for a well-formed dispatch.

    CONTRACT_SHAPE: pure-function
    """
    verdict = classify_refactor_dispatch(_markers_for(mode))

    assert verdict == expected.value, (
        f"classify_refactor_dispatch({mode.value!r}) must be {expected.value!r} "
        f"(refactor-mode -> spine-recognized 'valid', anything else 'absent'); "
        f"got {verdict!r}"
    )


@pytest.mark.parametrize(("mode", "expected"), _FIND_TABLE, ids=lambda v: v.value)
def test_classify_find_dispatch_recognizes_only_find_mode(
    mode: DispatchMode, expected: RecognitionVerdict
) -> None:
    """covers: R-DES-REFACTOR-SLICE-03-CLASSIFIER

    Given a dispatch carrying `DES-MODE: <mode>`, When `classify_find_dispatch`
    classifies it, Then a find-mode dispatch is `valid` (spine-recognized) and
    every other / absent mode is `absent` -- never `defective` for a well-formed
    dispatch.

    CONTRACT_SHAPE: pure-function
    """
    verdict = classify_find_dispatch(_markers_for(mode))

    assert verdict == expected.value, (
        f"classify_find_dispatch({mode.value!r}) must be {expected.value!r} "
        f"(find-mode -> spine-recognized 'valid', anything else 'absent'); "
        f"got {verdict!r}"
    )


def test_a_cross_mode_dispatch_is_never_recognized_as_valid() -> None:
    """covers: R-DES-REFACTOR-SLICE-03-CLASSIFIER

    Negative oracle: the refactor classifier must NEVER return `valid` for a
    find-mode dispatch, and the find classifier must NEVER return `valid` for a
    refactor-mode dispatch -- the two swarm modes are not interchangeable. Makes
    the "wrong output is not produced" assertion (implied by the recognition
    tables' ABSENT rows) explicit for the negative-AT evidence gate.

    CONTRACT_SHAPE: pure-function
    """
    refactor_on_find = classify_refactor_dispatch(_markers_for(DispatchMode.FIND))
    find_on_refactor = classify_find_dispatch(_markers_for(DispatchMode.REFACTOR))

    assert refactor_on_find != RecognitionVerdict.VALID.value, (
        "the refactor classifier must never recognize a find-mode dispatch as "
        f"'valid'; got {refactor_on_find!r}"
    )
    assert find_on_refactor != RecognitionVerdict.VALID.value, (
        "the find classifier must never recognize a refactor-mode dispatch as "
        f"'valid'; got {find_on_refactor!r}"
    )
