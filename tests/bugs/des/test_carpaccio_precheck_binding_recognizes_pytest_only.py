"""Regression: `des carpaccio-precheck` must not warn "no scenario file is
bound" for a feature genuinely delivered via pytest-only ATs.

DEFECT (agnostic-at-discovery-ssot-repair, gap 4): `_check_binding`
(`src/des/cli/carpaccio_precheck.py`) resolves feature-AT binding through
`carpaccio_format._feature_tag_files` -- the Gherkin `.feature`-file resolver
-- ONLY. A feature delivered exclusively via head-comment-tagged pytest ATs
(no `.feature` file anywhere) always trips this check, producing a spurious
"no scenario file is bound to the feature ... add the file-level binding tag
@feature-<id> before the Feature: header of at least one .feature file"
diagnostic -- misleading advice for an author who has already correctly
authored pytest ATs. The pre-check returns advisory exit code 3 on this
violation, so the false positive is not cosmetic-only.

The fix composes the SAME agnostic resolvers ADR-AAD-001 and gap 1 of this
repair already trust (`feature_at_files.feature_tagged_test_files` /
`is_pytest_collectible`) as a second, OR-ed binding source -- no new
discovery mechanism.

Driving surface: `collect_violations` / `_check_binding` called directly,
in-process (Mandate-16 driving-port-only -- these are the SAME pure functions
`des carpaccio-precheck`'s CLI `main()` calls, module-direct per the file's
own docstring; no subprocess needed to pin this behaviour).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.carpaccio_precheck import _check_binding


_FEATURE_ID = "gap4-pytest-only-binding-probe"


def _write_pytest_only_at(project_dir: Path, feature_id: str) -> None:
    """A pytest-collectible AT head-tagged for `feature_id` -- no `.feature`
    file anywhere under `project_dir`."""
    scope_dir = project_dir / "tests" / "acceptance" / feature_id.replace("-", "_")
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "test_behaviour.py").write_text(
        f"# @feature-{feature_id}\n# @slice-01\n"
        "def test_behaviour():\n    assert True\n",
        encoding="utf-8",
    )


def test_pytest_only_feature_is_never_reported_unbound(tmp_path: Path) -> None:
    """POSITIVE (active-RED today): a feature delivered exclusively via a
    head-tagged pytest AT must NOT trip the "no scenario file is bound"
    violation."""
    project_dir = tmp_path / "pytest_only_repo"
    project_dir.mkdir(parents=True)
    _write_pytest_only_at(project_dir, _FEATURE_ID)

    violations = _check_binding(project_dir, _FEATURE_ID)

    assert violations == [], (
        "a feature delivered exclusively via a head-tagged pytest AT must "
        f"not be reported unbound -- got violations={violations!r}"
    )


@pytest.mark.negative_at
def test_genuinely_unbound_feature_still_reports_the_violation(
    tmp_path: Path,
) -> None:
    """NEGATIVE (invariance pin): a feature with NO AT of either kind must
    still trip the binding violation -- the fix widens WHAT counts as bound;
    it must never widen into accepting NOTHING."""
    project_dir = tmp_path / "genuinely_unbound_repo"
    project_dir.mkdir(parents=True)

    violations = _check_binding(project_dir, "gap4-genuinely-unbound-probe")

    assert len(violations) == 1
    assert "no scenario file is bound" in violations[0]
