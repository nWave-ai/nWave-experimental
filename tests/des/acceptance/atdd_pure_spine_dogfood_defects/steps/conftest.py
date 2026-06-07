"""Pytest config for fix-atdd-pure-spine-dogfood-defects acceptance tests.

The slice ATs are RED scaffolds -- the production fixes do not exist yet. They
are collected `xfail` so the suite stays GREEN overall while DELIVER's
A_GREEN_ATS turns each slice green.

============================================================================
DELIVER HANDOFF -- xfail removal is PER-SLICE and MECHANICAL (review HIGH 3)
============================================================================
`_RED_SLICES` below is the closed set of slices whose ATs are still RED. When
DELIVER's A_GREEN_ATS delivers a slice, it MUST remove that slice's tag from
`_RED_SLICES` (one-line edit) -- it does NOT touch any other slice.

Removing the tag un-marks that slice's ATs: they then run UNMARKED and MUST be
observed GREEN before the slice is declared done. Critically, slice-02's
no-regression rows (the per-slice dispatches in slice-02 AT(1)) are `xfail`
ONLY while `slice-02` is in `_RED_SLICES`; once removed they run unmarked, so a
genuine GREEN is GREEN -- never silently absorbed as an `xpass`. A row that
passed today is therefore NOT indistinguishable from a broken one: it is
visible as a real GREEN the moment its slice leaves `_RED_SLICES`.

`strict=False` is retained ONLY for the in-flight RED window: while a slice is
RED, some of its rows (e.g. slice-02 no-regression rows already holding on
master) legitimately xpass and must not error the run. The mechanical safety
net is the per-slice removal -- once delivered, the slice runs unmarked and a
regression reds the suite honestly.

slice-00's AT(3) is a RED probe authored to be run, observed, then closed by
DELIVER -- slice-00 is in `_RED_SLICES` until slice-00 lands.

Run `pytest --runxfail` to see the RED detail of every still-marked slice.
"""

from __future__ import annotations

import pytest


# The closed set of slices still in RED. DELIVER's A_GREEN_ATS removes a slice
# tag from this set -- and ONLY that tag -- when it delivers the slice. This is
# the mechanical per-slice xfail-removal handoff (review HIGH 3).
_RED_SLICES: set[str] = set()


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark a slice's scenarios as RED scaffolds (xfail) only while it is RED.

    A scenario is xfail-marked iff its `@slice-NN` tag is still in
    `_RED_SLICES`. DELIVER removes a tag as it greens that slice -- the slice's
    ATs then run UNMARKED and must be observed GREEN. `strict=False` covers the
    in-flight RED window where a no-regression row may already xpass on master.
    """
    red_scaffold = pytest.mark.xfail(
        reason="RED scaffold -- DELIVER A_GREEN_ATS turns this green",
        strict=False,
    )
    for item in items:
        if any(tag in item.keywords for tag in _RED_SLICES):
            item.add_marker(red_scaffold)
