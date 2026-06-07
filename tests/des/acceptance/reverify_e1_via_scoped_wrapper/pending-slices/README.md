# Pending slice ATs

Parked acceptance tests for slices not yet entered. Each `.feature` here
becomes live in its slice's DELIVER wave by being moved up to the suite
root and bound by a matching `test_slice_NN_*.py` (the binder mirrors the
slice-01 pattern in this same directory's parent).

This directory is NOT discovered by pytest (no `__init__.py`, no binder,
no `scenarios()` call) -- the files are reviewable spec but not executable
until the slice owns them.

## Contents

- `slice_02_reverify_uses_scoped_wrapper.feature` -- slice-02:
  - AT-(a) cross-feature-collision (**THE MISSED DECISION-TABLE ROW R4**).
  - AT-(b) single-feature regression-guard for the 10 existing reverify
    ATs (parametrize-collapsed with AT-(a) at slice-02 entry, reviewer's
    call per DESIGN open question).
