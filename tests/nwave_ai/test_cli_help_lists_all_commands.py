"""Regression tests for the public ``nwave-ai`` discovery surface."""

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


def test_help_text_omits_retired_feature_delta_commands() -> None:
    """The direct cutover must not advertise the retired carrier family."""
    code, stdout, _ = _invoke(["--help"])
    assert code == 0
    for command in (
        "sync",
        "validate-feature-delta",
        "extract-gherkin",
        "migrate-feature",
    ):
        assert command not in stdout


@pytest.mark.parametrize(
    "command",
    ["sync", "validate-feature-delta", "extract-gherkin", "migrate-feature"],
)
def test_retired_feature_delta_commands_are_not_dispatched(command: str) -> None:
    code, _, stderr = _invoke([command])
    assert code == 1
    assert f"Unknown command: {command}" in stderr


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
