"""Regression: `nwave-ai --help` must list every command main() dispatches.

Bug: `_print_usage()`'s printed command list omitted three commands the
same file's dispatch table actually implements and routes
(`validate-feature-delta`, `extract-gherkin`, `migrate-feature`) --
documented in docs/reference/cli.md, but invisible to a user running
`nwave-ai --help`, the in-tool discovery surface.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

import pytest
from nwave_ai.cli import main


def _invoke(args: list[str]) -> tuple[int, str, str]:
    out, err = StringIO(), StringIO()
    with (
        patch("sys.argv", ["nwave-ai", *args]),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
    ):
        code = main()
    return code, out.getvalue(), err.getvalue()


def test_help_text_lists_validate_feature_delta_extract_gherkin_migrate_feature() -> (
    None
):
    """The three real, routed, publicly-documented commands must all appear
    in `nwave-ai --help`'s printed command list."""
    code, stdout, _ = _invoke(["--help"])
    assert code == 0
    assert "validate-feature-delta" in stdout
    assert "extract-gherkin" in stdout
    assert "migrate-feature" in stdout


@pytest.mark.parametrize(
    ("argv", "expect_zero"),
    [
        (["project", "enable", "--help"], True),
        (["project", "enable", "-h"], True),
        (["project", "disable", "--help"], True),
        (["project", "disable", "-h"], True),
        (["project", "--help"], True),
        (["project", "-h"], True),
        (["project"], False),
        (["project", "bogus"], False),
        (["project", "enable", "--bogus"], False),
        (["project", "enable", "extra"], False),
        (["project", "disable", "extra"], False),
        (["project", "enable", "--yes", "extra"], False),
    ],
)
def test_project_help_and_malformed_args_never_mutate_cwd(
    argv: list[str], expect_zero: bool, tmp_path, monkeypatch
) -> None:
    """`project enable|disable --help`/`-h` and any unknown option or extra
    positional must print usage and never create `.nwave/` or `.gitignore`
    in cwd -- only an exact `enable`/`disable` action (with optional
    `--yes`) may write, and it must never silently swallow trailing args."""
    monkeypatch.chdir(tmp_path)
    code, stdout, stderr = _invoke(argv)
    if expect_zero:
        assert code == 0
        assert "Usage: nwave-ai project" in stdout
    else:
        assert code != 0
        assert "Usage: nwave-ai project" in stderr
    assert not (tmp_path / ".nwave").exists()
    assert not (tmp_path / ".gitignore").exists()
