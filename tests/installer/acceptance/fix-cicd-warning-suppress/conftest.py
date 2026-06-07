"""pytest-bdd configuration for the fix-cicd-warning-suppress AT set.

Slice-01 (pytest-warning-filter) scope: drive a real `pipenv run pytest`
subprocess against a KNOWN-NOISY pytest-bdd test file in the repo (slice-02
of the spine-ledger-gate-v2 feature carries 9+ unregistered custom marks)
and assert ZERO `PytestUnknownMarkWarning` instances + ≥80% stdout-volume
reduction post-fix.

The conftest sits at the feature root (sibling of the .feature file)
mirroring the codex-empirical-e2e-support + fix-hmac-bootstrap-installer +
atdd-spine-ledger-enforcement-gate-v2 precedent — avoids a pytest plugin-
name collision with sibling features that also carry a steps/conftest.py.

No per-test environment isolation is needed for slice-01 — the SUT is a
read-only pytest invocation against an existing test file. The composition
fixture rooted at `tmp_path` captures stdout via subprocess.run.

RED-for-the-right-reason: the production fix
(`pyproject.toml[tool.pytest.ini_options].filterwarnings` entry suppressing
`PytestUnknownMarkWarning`) does NOT exist yet. The composition fixture
invokes the real pytest subprocess; with no filter in place, the captured
stdout contains 9 `PytestUnknownMarkWarning` occurrences for the slice-02
target file. AT-1's `assert_zero_unknown_mark_warnings` and AT-2's
`assert_output_volume_reduction_at_least_eighty_percent` both fire
AssertionError on the first `Then` step. That is the correct RED: the
assertion fires because the warnings filter is unimplemented, not because
of an import error or fixture setup bug.
"""

from __future__ import annotations
