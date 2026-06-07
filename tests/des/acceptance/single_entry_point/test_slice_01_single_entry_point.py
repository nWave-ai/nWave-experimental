"""slice-01 binder: single des entry point walking skeleton.

Walking-skeleton / wiring_e2e: drives the real `des` console-script end-to-
end via subprocess (Pillar 3 — app as in production). RED scaffold today:
`src/des/cli/__main__.py:main` raises AssertionError on every invocation
(scaffold marker `__SCAFFOLD__ = True`), so the 3 scenarios fail for the
right reason (semantic AssertionError, classified MISSING_FUNCTIONALITY by
the pre-DELIVER fail-for-right-reason gate).

DELIVER slice-01 GREEN replaces the dispatcher scaffold with the argparse
subparsers tree + lazy importlib delegation + pyproject `[project.scripts]`
collapse.
"""

from pytest_bdd import scenarios

from .steps.steps_slice_01 import *  # noqa: F403


scenarios("slice_01_single_entry_point_walking_skeleton.feature")
