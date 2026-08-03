"""Pytest config for slice-01 of `unified-slice-progress-visualization`.

slice-01 wires `des mikado-board render --feature <id>` (CREATE_NEW,
`src/des/cli/mikado_board.py`) to a new pure projection
(`src/des/domain/slice_progress_projection.py`, CREATE_NEW) that reads ONLY
the Slice Plan's declared Status column -- no scheduling state, no declared
lanes yet (DESIGN Handoff: those land in slice-02).

No fixtures beyond the parent `tests/des/acceptance/conftest.py` autouse
probe silencer are needed -- the composition root builds its own tmp-rooted
repository + feature-delta fixtures per scenario (mirrors
`atdd_pure_declared_slice_dependency/conftest.py`).
"""

from __future__ import annotations
