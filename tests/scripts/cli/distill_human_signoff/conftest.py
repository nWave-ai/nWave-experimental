"""pytest-bdd configuration for the fix-distill-human-signoff AT set.

ATDD-pure carpaccio: six slice feature files (01, 02, 03, 04, 05, 06). Slices
01-05 live in this collected `tests/` tree. Slice 06 remains PARKED under
`docs/feature/fix-distill-human-signoff/distill/pending-slices/` per the
F-CARPACCIO-FUTURE-SLICE-SCAFFOLD-BLOCKS-COMMIT workaround and move-back when
the DELIVER loop reaches the touchpoint-wiring slice.

The driving-port CLI (``scripts/cli/derive_coverage_map.py``) is a RED
scaffold on master -- its entry point raises ``AssertionError`` (RED: missing
functionality, Mandate 7), so scenarios FAIL for the right reason rather than
erroring on a broken import. The substrate
(``scripts/cli/resolve_manifest_state.py``,
``scripts/cli/validate_component_manifest.py``,
``nWave/schemas/component-manifest.schema.json``) is already landed via
`F-DESIGN-COMPONENT-MANIFEST` slices 01-03.

No xfail rewrite hook: under atdd_pure each slice's scenarios go GREEN when
its slice lands. The carpaccio DELIVER spine unskips per slice; on master the
slice-01 set is RED-for-the-right-reason, which is the intended pre-DELIVER
state per ADR-025.
"""

from __future__ import annotations
