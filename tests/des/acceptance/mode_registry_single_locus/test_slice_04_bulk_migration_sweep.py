"""pytest-bdd binding for mode-registry-single-locus slice-04.

Thin binding: registers the slice-04 scenarios and imports the step
vocabulary. No step definitions or business logic live here — the SSOT for
step bodies is `steps/steps_slice_04_bulk_migration_sweep.py` +
`steps/composition_slice_04.py`; the SSOT for the scenarios is the
`.feature` file (per the DISTILL mandate).

Slice-04 = the BULK application of the proven slice-01/02/03 patterns: the
two rendering cardinalities slice-02 routed here (empty conditional set /
many-skills list) land through the real docgen entry; the Layer-A
precondition is pinned AS DATA (zero naked mode literals outside GENERATED
regions / allow-markers across nWave/{skills,agents,tasks}); and the
deletion-safety ledger is honored — the eight DELETE-verdict prose-watchers
are gone, the three KEPT watchers still stand, and the staleness check
refuses drift on the formerly-guarded assets by name.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_04_bulk_migration_sweep import *


scenarios("slice-04-bulk-migration-sweep.feature")
