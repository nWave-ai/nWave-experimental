"""pytest fixtures for the atdd_pure 3-phase-count reduction ATs.

The `scenarios(...)` binding lives in the test module (sibling-suite
convention), not here — pytest collects `test_*.py`, not `conftest.py`. This
conftest holds only shared fixtures.
"""

from __future__ import annotations
