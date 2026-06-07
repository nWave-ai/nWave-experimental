# Pending slices — single-entry-point consolidation

Slice-02 and slice-03 `.feature` files are parked here per the atdd-pure
per-slice DISTILL discipline (ADR-028). They are NOT collected by pytest in
this state (no `steps_slice_NN.py` binds them via `scenarios(...)`).

## Unpark protocol (per slice, when DELIVER starts that slice)

1. Move `slice_NN_<name>.feature` up one level into the parent directory.
2. Drop the `@pending` tag from the feature header.
3. Author `tests/des/acceptance/single_entry_point/steps/steps_slice_NN.py`
   binding the feature via `scenarios("../slice_NN_<name>.feature")`.
4. Extend `composition.py` with the slice-NN services the steps invoke
   (Mandate-12: step bodies stay ≤ 2 stmts; logic lives in composition).
5. Add the import to `conftest.py` so pytest-bdd discovers the steps.
6. Run the pre-DELIVER fail-for-the-right-reason gate (Mandate 7); only
   then DELIVER may proceed to GREEN.

## Why parked, not authored-and-skipped

Per `nw-at-completeness-check` § AT-set scope under `atdd_pure`: under
atdd-pure, the completeness gate is scoped to the entering slice. Authoring
slice-02 and slice-03 steps NOW would either (a) collect them as failing
tests today (wrong RED — they fail before slice-02's dispatcher registry
ships) or (b) require a global `@pytest.mark.skip` that masks the actual
implementation gap. Parking the `.feature` files preserves the contract
text + carpaccio-slice discipline + atdd-pure scope-narrowing.

## Coverage / completeness scope

The 15-item AT completeness checklist is run PER SLICE. Slice-01's 3 ATs are
the gated set for the entering slice; slice-02 and slice-03's ATs widen the
audit incrementally when their slices enter DELIVER. Each parked slice file
itself respects parametrize-collapse density (every subcommand enumerated
once per parametrize Examples table, NOT one scenario per subcommand).
