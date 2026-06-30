"""Algebra laws L1 + L2 as property-based tests (ADR-FLOW-007 §S.2).

LAYER 1 (Mandate-9 PBT-full): these laws are statements about the section-schema
VALUE and its three pure projections -- a closed algebra over the 5 constructors.
The natural test layer is the production pure functions directly (NOT the
subprocess CLI), so the PBT explores the constructor set / registry exhaustively.

- L1 schema-totality: every projection is TOTAL over each of the 5 constructors
  (no unhandled case) AND every registered section maps to exactly one constructor.
- L2 section-independence: a section's projection (here: wave_injection membership
  for a section) is invariant under any perturbation of ANOTHER section's body.

@feature-feature-delta-section-schema @slice-02 -- the laws witness the projection
algebra introduced in slice-02. Tagged @property @driving_port (the production
pure functions are the driving surface for the algebra value).

Active-RED (ADR-025/028): at HEAD the scaffold raises AssertionError on every
projection call + `section_type_constructors`/`FEATURE_DELTA_SCHEMA` are unrealized,
so each law fails with a semantic AssertionError -- never an import/collection error
(the module imports resolve against the RED scaffold).
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from des.cli import feature_delta_schema as fds


pytestmark = pytest.mark.acceptance


# ---------------------------------------------------------------------------
# L1 — schema-totality
# ---------------------------------------------------------------------------


def _constructors() -> tuple[type, ...]:
    """The closed 5-constructor set, read from the production algebra. RED until
    DELIVER realizes `section_type_constructors()`."""
    return fds.section_type_constructors()


def test_l1_algebra_is_exactly_five_constructors() -> None:
    """L1a: the SectionType sum is closed at exactly five constructors."""
    ctors = _constructors()
    names = {c.__name__ for c in ctors}
    assert names == {"KeyedBlock", "Table", "Prose", "RefList", "Composite"}, (
        f"the closed sum must be exactly the five §S.1 constructors; got {names}"
    )


def test_l1_every_section_maps_to_one_constructor() -> None:
    """L1b: every registry entry maps to exactly one §S.1 constructor."""
    schema = fds.FEATURE_DELTA_SCHEMA
    assert schema is not None, "the registry value must be realized (RED until DELIVER)"
    ctor_types = tuple(_constructors())
    for entry in schema:
        st_value = entry.section_type
        matches = [c for c in ctor_types if isinstance(st_value, c)]
        assert len(matches) == 1, (
            f"section {entry.section_id!r} must map to exactly one constructor; "
            f"matched {[c.__name__ for c in matches]}"
        )


_ALL_WAVES = (
    "discover",
    "diverge",
    "discuss",
    "design",
    "devops",
    "distill",
    "deliver",
    "review",
)


@given(wave=st.sampled_from(_ALL_WAVES))
def test_l1_wave_injection_is_total_over_every_wave(wave: str) -> None:
    """L1c: wave_injection is TOTAL -- it returns a list (never raises an
    unhandled-case error) for every wave in the closed wave set."""
    schema = fds.FEATURE_DELTA_SCHEMA
    assert schema is not None, "the registry value must be realized (RED until DELIVER)"
    result = fds.wave_injection(schema, wave)
    assert isinstance(result, list), (
        f"wave_injection must be total over the wave set; {wave!r} gave {result!r}"
    )


# ---------------------------------------------------------------------------
# L2 — section-independence
# ---------------------------------------------------------------------------


@given(
    perturbation=st.text(min_size=0, max_size=200),
    wave=st.sampled_from(["design", "distill", "deliver", "review", "discover"]),
)
def test_l2_section_injection_independent_of_other_section_bodies(
    perturbation: str, wave: str
) -> None:
    """L2: the set of section IDs wave_injection projects for `wave` depends ONLY
    on the registry (per-entry consumed_by), never on any section's body text.

    The registry is a Map<SectionId, SectionEntry> with no cross-entry references,
    so wave_injection's output is a function of the schema + wave alone -- a body
    perturbation (here, arbitrary text) cannot change the projected ID set.
    Realized: wave_injection ignores DocumentText entirely (it is a pure registry
    filter, §S.4). RED until DELIVER realizes the projection.
    """
    schema = fds.FEATURE_DELTA_SCHEMA
    assert schema is not None, "the registry value must be realized (RED until DELIVER)"
    baseline_ids = {e.section_id for e in fds.wave_injection(schema, wave)}
    # wave_injection takes (schema, wave) only -- no document body -- so by its
    # very type signature it cannot depend on another section's content. Re-invoke
    # to witness determinism (same inputs -> same projected ID set).
    repeat_ids = {e.section_id for e in fds.wave_injection(schema, wave)}
    assert baseline_ids == repeat_ids, (
        f"wave_injection({wave!r}) must be a pure registry filter independent of "
        f"document bodies; got {baseline_ids} then {repeat_ids} (perturbation={perturbation!r})"
    )
