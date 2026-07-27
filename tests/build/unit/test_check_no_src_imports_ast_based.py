"""Regression: check_no_src_imports must decide on a parsed IMPORT, never a
raw line substring.

OBSERVED (2026-07-26): `_check_no_src_imports` in
scripts/validation/validate_installed_wheel.py verified the installed wheel
never imports the pre-rewrite `src.des` path by scanning every line of every
installed .py file for the raw substrings `from src.des` / `import src.des`,
skipping only lines whose STRIPPED text starts with `#`. It did not parse the
file and did not recognize multi-line docstrings, so a line INSIDE a
triple-quoted docstring that merely QUOTES or DISCUSSES the banned import
(e.g. a migration-note docstring line reading "We used to import from
src.des directly; now we do not.") tripped a false FAIL -- reproduced by
direct execution of the per-line loop against that exact string.

This suite drives `check_no_src_imports` directly against a synthetic
site-packages tree (no wheel build, no venv -- fast/impacted only), unlike
the slow wheel-integration suite in tests/build/unit/test_install_smoke.py.
"""

from __future__ import annotations

from pathlib import Path

from scripts.validation.validate_installed_wheel import check_no_src_imports


def _write_package(
    tmp_path: Path, package_name: str, filename: str, content: str
) -> Path:
    package_dir = tmp_path / package_name
    package_dir.mkdir(parents=True, exist_ok=True)
    (package_dir / filename).write_text(content, encoding="utf-8")
    return tmp_path


class TestFalsePositiveOnDocstringMention:
    """A docstring merely quoting the banned import must not fail the check."""

    def test_docstring_mentioning_src_des_does_not_fail(self, tmp_path: Path) -> None:
        site_packages = _write_package(
            tmp_path,
            "des",
            "migration_note.py",
            '"""We used to import from src.des directly; now we do not."""\nx = 1\n',
        )
        result = check_no_src_imports(site_packages, "des")
        assert result.passed, (
            f"a docstring quoting the banned import must not fail: {result.message}"
        )

    def test_comment_mentioning_src_des_does_not_fail(self, tmp_path: Path) -> None:
        # "#"-prefixed lines were already exempted by the OLD substring scan
        # too -- pinned here so the AST rewrite does not regress it.
        site_packages = _write_package(
            tmp_path,
            "des",
            "note.py",
            "# there is no `import src.des` here\nx = 1\n",
        )
        result = check_no_src_imports(site_packages, "des")
        assert result.passed


class TestTruePositiveStillCaught:
    """A real `src.des` import must still fail the check (no false negative)."""

    def test_real_import_from_src_des_still_fails(self, tmp_path: Path) -> None:
        site_packages = _write_package(
            tmp_path,
            "des",
            "bad.py",
            "from src.des.application import orchestrator\n",
        )
        result = check_no_src_imports(site_packages, "des")
        assert not result.passed
        assert "bad.py" in result.message

    def test_real_bare_import_src_des_still_fails(self, tmp_path: Path) -> None:
        site_packages = _write_package(
            tmp_path,
            "des",
            "bad2.py",
            "import src.des.application\n",
        )
        result = check_no_src_imports(site_packages, "des")
        assert not result.passed
        assert "bad2.py" in result.message


class TestUnparseableFileDegradesToFailure:
    """A file that cannot be parsed must fail loudly, never silently skip."""

    def test_syntax_error_file_is_reported_as_failure_not_skipped(
        self, tmp_path: Path
    ) -> None:
        site_packages = _write_package(
            tmp_path,
            "des",
            "broken.py",
            "def(:::\n",
        )
        result = check_no_src_imports(site_packages, "des")
        assert not result.passed
        assert "broken.py" in result.message


class TestCleanPackagePasses:
    def test_clean_package_with_no_banned_import_passes(self, tmp_path: Path) -> None:
        site_packages = _write_package(
            tmp_path,
            "des",
            "clean.py",
            "from des.application import orchestrator\n",
        )
        result = check_no_src_imports(site_packages, "des")
        assert result.passed
