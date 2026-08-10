"""Dense contract for the fail-closed docs-only CI classifier."""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ci.docs_only_classifier import _format_output, is_docs_only_change, main


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ci" / "docs_only_classifier.py"


class TestIsDocsOnlyChange:
    def test_empty_paths_is_not_docs_only(self) -> None:
        assert is_docs_only_change([]) is False

    def test_blank_path_is_not_docs_only(self) -> None:
        assert is_docs_only_change([""]) is False

    def test_docs_directory_with_no_filename_is_not_docs_only(self) -> None:
        assert is_docs_only_change(["docs/"]) is False

    def test_bare_docs_token_without_slash_is_not_docs_only(self) -> None:
        assert is_docs_only_change(["docs"]) is False

    def test_lookalike_prefix_is_not_docs_only(self) -> None:
        assert is_docs_only_change(["docsIGNORE/readme.md"]) is False

    def test_single_docs_file_is_docs_only(self) -> None:
        assert is_docs_only_change(["docs/product/roadmap.md"]) is True

    def test_multiple_docs_files_is_docs_only(self) -> None:
        assert (
            is_docs_only_change(
                ["docs/product/roadmap.md", "docs/feature/x/feature-delta.md"]
            )
            is True
        )

    def test_nested_docs_path_is_docs_only(self) -> None:
        assert is_docs_only_change(["docs/a/b/c/d.md"]) is True

    @pytest.mark.parametrize(
        "path",
        [
            ".github/workflows/ci.yml",  # workflow
            "pyproject.toml",  # config
            "uv.lock",  # dependency
            "tests/scripts/test_docs_link_report.py",  # test
            "src/des/domain/x.py",  # source
            "nWave/agents/nw-software-crafter.md",  # nWave asset
            "README.md",  # unknown/non-doc root file
        ],
    )
    def test_non_doc_category_fails_closed(self, path: str) -> None:
        assert is_docs_only_change([path]) is False

    def test_one_non_doc_path_among_many_docs_paths_fails_closed(self) -> None:
        assert (
            is_docs_only_change(["docs/product/roadmap.md", "src/des/domain/x.py"])
            is False
        )

    def test_one_blank_entry_among_docs_paths_fails_closed(self) -> None:
        assert is_docs_only_change(["docs/product/roadmap.md", ""]) is False


class TestFormatOutput:
    def test_true_formats_as_github_output_line(self) -> None:
        assert _format_output(True) == "docs_only=true"

    def test_false_formats_as_github_output_line(self) -> None:
        assert _format_output(False) == "docs_only=false"


class TestMain:
    def test_docs_only_diff_prints_true(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("docs/product/roadmap.md\n"))
        assert main([]) == 0
        assert capsys.readouterr().out == "docs_only=true\n"

    def test_mixed_diff_prints_false(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(
            sys, "stdin", io.StringIO("docs/product/roadmap.md\nsrc/des/x.py\n")
        )
        assert main([]) == 0
        assert capsys.readouterr().out == "docs_only=false\n"

    def test_empty_stdin_prints_false(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO(""))
        assert main([]) == 0
        assert capsys.readouterr().out == "docs_only=false\n"

    def test_always_exits_zero_even_on_full_run_classification(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(sys, "stdin", io.StringIO("garbage\n"))
        assert main([]) == 0


class TestCliSubprocessContract:
    def test_pipe_docs_only_diff_prints_expected_line(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input="docs/product/roadmap.md\ndocs/feature/x/feature-delta.md\n",
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        assert result.stdout == "docs_only=true\n"
        assert result.returncode == 0

    def test_pipe_mixed_diff_prints_expected_line(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            input="docs/product/roadmap.md\n.github/workflows/ci.yml\n",
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        assert result.stdout == "docs_only=false\n"
        assert result.returncode == 0
