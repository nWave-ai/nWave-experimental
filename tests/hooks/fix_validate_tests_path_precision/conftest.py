"""pytest-bdd configuration for the fix-validate-tests-path-precision suite.

DISTILL-authored regression-pin (ADR-025 + Mandate 7 bugfix variant): the
production helper ``scripts.hooks.validate_tests.get_targeted_test_dirs``
already exists -- this is a bugfix, not a new feature. The scenarios are
authored to FAIL against the current buggy implementation (assertion mismatch
at the @then steps, NOT import error) and will GREEN after DELIVER ships the
capped-depth scoping fix.

There is no @xfail collection hook: per the pre-DELIVER fail-for-right-reason
gate, the scenarios MUST fail at the assertion layer with a MISSING_FUNCTIONALITY
classification (the bug exists in current code -- not setup error, not import
error). DELIVER's A_GREEN_ATS phase makes the scenarios pass by shipping the
1-line semantic change in ``get_targeted_test_dirs``.
"""

from __future__ import annotations
