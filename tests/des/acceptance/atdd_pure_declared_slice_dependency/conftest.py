"""Pytest config for slice-01 of `slice-dependency-declared` (mikado node D94).

slice-01 wires `resolve_predecessor_slice` into the M8 carpaccio-order check
(`des.adapters.drivers.hooks.carpaccio_intercept._carpaccio_order_block`) so a
declared `depends-on {slice-id}` Slice-Plan annotation is checked against the
DECLARED predecessor's ledger record instead of blindly `slice-(N-1)`'s.

No fixtures beyond the parent `tests/des/acceptance/conftest.py` autouse probe
silencer are needed -- the composition root builds its own tmp-rooted ledger
and feature-delta fixtures per scenario (mirrors
`atdd_pure_spine_hardening/conftest.py`).
"""

from __future__ import annotations
