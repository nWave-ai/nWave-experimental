"""pytest-bdd configuration for fix-d1-human-readable-gate-surfaces ATs.

ATDD-pure carpaccio: slice-01 (walking skeleton) wires the human-readable
surface helper to ONE gate CLI (``des.cli.run_contract_gate``) as proof-of-
pattern. Subsequent slices extend to the other 8 D1 gates without revisiting
the helper itself.

The driving-port helper (``src/des/cli/human_surface.py``) is a RED scaffold
on master — its ``print_human_summary`` entry raises ``AssertionError`` so the
slice-01 ATs FAIL for the right reason (missing functionality, Mandate 7)
rather than erroring on a broken import. The ``run_contract_gate`` extension
that imports + calls the helper is authored during the DELIVER A_GREEN_ATS
phase; on master the helper module exists as a scaffold and the gate has not
yet adopted it.

No xfail rewrite hook: under atdd_pure the slice's scenarios go GREEN when
the slice lands. The carpaccio DELIVER spine unskips per slice.
"""

from __future__ import annotations
