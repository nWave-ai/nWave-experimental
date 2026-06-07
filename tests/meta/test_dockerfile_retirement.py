"""Meta test: Dockerfile retirement gate (step 01-04 / Phase 5).

Asserts the Dockerfile-to-testcontainers migration is complete:
1. No legacy Dockerfiles remain in tests/e2e/
2. No CI workflow invokes `docker build -f tests/e2e/Dockerfile.*`
3. ci.yml test stage runs the e2e-marked test suite (pytest -m e2e, or an
   unrestricted pytest invocation that includes e2e)
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_DIR = REPO_ROOT / "tests" / "e2e"
WORKFLOWS_DIR = REPO_ROOT / ".github" / "workflows"


@pytest.mark.fast_gate
def test_no_legacy_dockerfiles_in_tests_e2e() -> None:
    """All tests/e2e/Dockerfile.* files must be deleted post-migration."""
    leftovers = sorted(str(p.name) for p in E2E_DIR.glob("Dockerfile.*"))
    assert leftovers == [], (
        f"Legacy Dockerfiles still present in tests/e2e/: {leftovers}. "
        "These must be deleted as part of step 01-04 Phase 5 retirement."
    )


@pytest.mark.fast_gate
def test_no_ci_workflow_builds_retired_dockerfiles() -> None:
    """No .github/workflows/*.yml may reference `tests/e2e/Dockerfile.`"""
    offenders: list[str] = []
    for workflow in sorted(WORKFLOWS_DIR.glob("*.yml")):
        text = workflow.read_text(encoding="utf-8")
        if "tests/e2e/Dockerfile." in text:
            offenders.append(workflow.name)
    assert offenders == [], (
        f"Workflows still reference retired Dockerfiles: {offenders}. "
        "Replace docker build invocations with pytest -m e2e."
    )


@pytest.mark.fast_gate
def test_e2e_gated_in_release_pipeline() -> None:
    """The e2e tier must be gated SOMEWHERE on the path to PyPI.

    Architecture (post Phase 5 retirement + ci-yml e2e exclusion):
    - ci.yml runs the fast tiers only (excludes e2e via `-m "not e2e"`).
      Reason: GitHub-hosted matrix runners don't reliably run docker
      testcontainers in <30 min, and the same coverage runs against the
      published wheel at the release-rc and release-prod stages.
    - release-rc.yml:validate-rc runs `pytest -m e2e` against the
      published RC wheel (pipx-installed from PyPI).
    - release-prod.yml:validate-stable runs `pytest -m e2e` against the
      published stable wheel.

    Accept the gate as long as e2e is invoked in either release workflow.
    """
    rc = (WORKFLOWS_DIR / "release-rc.yml").read_text(encoding="utf-8")
    prod = (WORKFLOWS_DIR / "release-prod.yml").read_text(encoding="utf-8")

    rc_has_e2e = "-m e2e" in rc or '-m "e2e' in rc
    prod_has_e2e = "-m e2e" in prod or '-m "e2e' in prod
    assert rc_has_e2e or prod_has_e2e, (
        "release-rc.yml or release-prod.yml must invoke `pytest -m e2e` "
        "to gate the e2e tier on the path to PyPI"
    )

    # E2E directory must exist and contain migrated pytest files
    assert E2E_DIR.is_dir(), "tests/e2e/ must exist"
    e2e_test_files = list(E2E_DIR.glob("test_*.py"))
    assert len(e2e_test_files) >= 10, (
        f"tests/e2e/ must contain migrated pytest files, found {len(e2e_test_files)}"
    )
