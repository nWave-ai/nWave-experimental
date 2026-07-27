"""Acceptance tests for catalog completeness validation.

Scenarios covered (step 01-03):
  P0c-01: Uncatalogued agent fails validation
  P0c-02: All agents catalogued passes validation
  P0c-03: Reviewer agent with catalogued base passes validation
  P0c-04: Reviewer agent without catalogued base fails validation
  P0c-05: Catalog entry missing explicit public field fails validation
  P0c-06: Multiple uncatalogued agents listed in error message

Test Budget: 6 distinct behaviors x 2 = 12 max. Using 6 tests.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts.shared.agent_catalog import is_agent_on_disk_catalogued
from scripts.validation.validate_catalog_completeness import main


#: Repo root -- three parents up from this test file
#: (tests/build/acceptance/).
_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "validation" / "validate_catalog_completeness.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CATALOG_WITH_ALL = """\
agents:
  alpha:
    wave: DELIVER
    public: true
  beta:
    wave: DESIGN
    public: true
"""

CATALOG_ALPHA_ONLY = """\
agents:
  alpha:
    wave: DELIVER
    public: true
"""

CATALOG_FOO = """\
agents:
  foo:
    wave: DELIVER
    public: true
"""

CATALOG_MISSING_PUBLIC = """\
agents:
  baz:
    wave: DELIVER
    description: "Missing public field"
"""


@pytest.fixture()
def nwave_dir(tmp_path: Path) -> Path:
    """Create a temp nWave dir structure."""
    nwave = tmp_path / "nWave"
    nwave.mkdir()
    (nwave / "agents").mkdir()
    return nwave


# ---------------------------------------------------------------------------
# P0c-01: Uncatalogued agent fails validation
# ---------------------------------------------------------------------------


class TestUncataloguedAgentFails:
    """P0c-01: Uncatalogued agent fails validation."""

    def test_uncatalogued_agent_fails_validation(self, nwave_dir: Path) -> None:
        """Given agent 'nw-uncatalogued.md' not in catalog, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-uncatalogued.md").write_text("---\nname: uncatalogued\n---\n")

        result = main(nwave_dir)
        assert result == 1

        # Also verify via is_agent_on_disk_catalogued
        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-uncatalogued.md" in uncatalogued


# ---------------------------------------------------------------------------
# P0c-02: All agents catalogued passes validation
# ---------------------------------------------------------------------------


class TestAllCataloguedPasses:
    """P0c-02: All agents catalogued passes validation."""

    def test_all_agents_catalogued_passes_validation(self, nwave_dir: Path) -> None:
        """Given every agent file has a catalog entry with public field, validation passes."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_WITH_ALL)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-beta.md").write_text("---\nname: beta\n---\n")

        result = main(nwave_dir)
        assert result == 0


# ---------------------------------------------------------------------------
# P0c-03: Reviewer agent with catalogued base passes validation
# ---------------------------------------------------------------------------


class TestReviewerWithBasePasses:
    """P0c-03: Reviewer agent with catalogued base passes validation."""

    def test_reviewer_with_catalogued_base_passes(self, nwave_dir: Path) -> None:
        """Given 'nw-foo-reviewer.md' and 'foo' in catalog, validation passes."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_FOO)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-foo.md").write_text("---\nname: foo\n---\n")
        (agents_dir / "nw-foo-reviewer.md").write_text("---\nname: foo-reviewer\n---\n")

        result = main(nwave_dir)
        assert result == 0

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert not any("foo-reviewer" in u for u in uncatalogued)


# ---------------------------------------------------------------------------
# P0c-04: Reviewer agent without catalogued base fails validation
# ---------------------------------------------------------------------------


class TestReviewerWithoutBaseFails:
    """P0c-04: Reviewer agent without catalogued base fails validation."""

    def test_reviewer_without_catalogued_base_fails(self, nwave_dir: Path) -> None:
        """Given 'nw-bar-reviewer.md' and 'bar' NOT in catalog, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-bar-reviewer.md").write_text("---\nname: bar-reviewer\n---\n")

        result = main(nwave_dir)
        assert result == 1

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-bar-reviewer.md" in uncatalogued


# ---------------------------------------------------------------------------
# P0c-05: Catalog entry missing explicit public field fails validation
# ---------------------------------------------------------------------------


class TestMissingPublicFieldFails:
    """P0c-05: Catalog entry missing explicit public field fails validation."""

    def test_missing_public_field_fails_validation(self, nwave_dir: Path) -> None:
        """Given agent 'baz' registered without explicit public field, validation fails."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_MISSING_PUBLIC)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-baz.md").write_text("---\nname: baz\n---\n")

        result = main(nwave_dir)
        assert result == 1

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert any("missing public field" in u for u in uncatalogued)


# ---------------------------------------------------------------------------
# P0c-06: Multiple uncatalogued agents listed in error message
# ---------------------------------------------------------------------------


class TestMultipleUncataloguedListed:
    """P0c-06: Multiple uncatalogued agents listed in error message."""

    def test_multiple_uncatalogued_agents_listed(self, nwave_dir: Path) -> None:
        """Given two uncatalogued agents, both are listed in error output."""
        (nwave_dir / "framework-catalog.yaml").write_text(CATALOG_ALPHA_ONLY)
        agents_dir = nwave_dir / "agents"
        (agents_dir / "nw-alpha.md").write_text("---\nname: alpha\n---\n")
        (agents_dir / "nw-rogue-one.md").write_text("---\nname: rogue-one\n---\n")
        (agents_dir / "nw-rogue-two.md").write_text("---\nname: rogue-two\n---\n")

        uncatalogued = is_agent_on_disk_catalogued(agents_dir, nwave_dir)
        assert "nw-rogue-one.md" in uncatalogued
        assert "nw-rogue-two.md" in uncatalogued

        result = main(nwave_dir)
        assert result == 1


# ---------------------------------------------------------------------------
# Regression: the documented CLI invocation form must not crash
# (validate-catalog-completeness-not-in-ci-and-documented-invocation-crashes,
# techdebt.md)
# ---------------------------------------------------------------------------


def _bare_system_python() -> str | None:
    """Locate a real bare system interpreter -- NOT this project's own venv.

    This project's own `.venv` ships an editable install that copies the
    `scripts` package straight into its `site-packages` (verified via `ls
    .venv/lib/python3.12/site-packages/scripts`), so running the target
    script through `sys.executable` (even with `sys.path` scrubbed) cannot
    reproduce the defect -- `scripts` would still resolve. A genuine bare
    system `python3` (as a `language: system` pre-commit/CI hook actually
    uses, per the sibling `validate_yaml_files.py` module docstring) has
    neither the venv's site-packages nor the repo root on its default
    `sys.path`, which is the exact condition the module's own docstring
    invocation crashes under.

    `PATH` is filtered to drop any entry mentioning `.venv` before the
    lookup, so an activated venv shell does not shadow the real system
    interpreter.
    """
    filtered = os.pathsep.join(
        part
        for part in os.environ.get("PATH", "").split(os.pathsep)
        if ".venv" not in part
    )
    return shutil.which("python3", path=filtered)


_SYSTEM_PYTHON3 = _bare_system_python()


def _system_python3_has_pyyaml() -> bool:
    """Whether the resolved bare system python3 can `import yaml`.

    Orthogonal to the sys.path/ModuleNotFoundError defect this test class
    pins: PyYAML is a separate runtime dependency of
    `scripts.shared.agent_catalog` (see its own `_ensure_yaml()`), not
    something the bootstrap fix installs or is responsible for. A bare
    system python3 that lacks PyYAML (e.g. a clean CI runner image, as
    opposed to a dev machine's system Python with packages installed
    globally) is a real, distinct environment condition -- asserting full
    catalog-completeness output in that case would fail on the wrong axis.
    """
    if _SYSTEM_PYTHON3 is None:
        return False
    result = subprocess.run(
        [_SYSTEM_PYTHON3, "-c", "import yaml"],
        capture_output=True,
    )
    return result.returncode == 0


_SYSTEM_PYTHON3_HAS_PYYAML = _system_python3_has_pyyaml()


@pytest.mark.skipif(
    _SYSTEM_PYTHON3 is None,
    reason="no bare system python3 found outside this project's venv",
)
class TestDocumentedCliInvocationDoesNotCrash:
    """The module's own docstring instructs `python .../validate_catalog_
    completeness.py [nwave-dir]` -- invoked as a bare script, not `python -m
    scripts.validation...`. That form used to crash with
    `ModuleNotFoundError: No module named 'scripts'` because the absolute
    `from scripts.shared...` import requires the repo root on `sys.path`,
    which a bare script invocation never provides on its own.
    """

    def _run_as_bare_script(self) -> subprocess.CompletedProcess[str]:
        assert _SYSTEM_PYTHON3 is not None
        return subprocess.run(
            [_SYSTEM_PYTHON3, str(_SCRIPT)],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )

    def test_bare_script_invocation_does_not_raise_module_not_found(self) -> None:
        result = self._run_as_bare_script()

        assert "ModuleNotFoundError" not in result.stderr
        assert result.returncode in (0, 1)

    @pytest.mark.skipif(
        not _SYSTEM_PYTHON3_HAS_PYYAML,
        reason=(
            "bare system python3 lacks PyYAML, a separate dependency of "
            "scripts.shared.agent_catalog -- unrelated to the sys.path "
            "bootstrap this test class pins"
        ),
    )
    def test_bare_script_invocation_reports_catalog_completeness(self) -> None:
        result = self._run_as_bare_script()

        assert "Catalog completeness:" in result.stdout
