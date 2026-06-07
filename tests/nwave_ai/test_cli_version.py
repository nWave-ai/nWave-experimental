"""Regression tests for `nwave-ai --version` flag.

Bug: rc2 shipped with `nwave-ai --version` returning "Unknown command:
--version" because the CLI dispatcher only matched the `version`
subcommand form. Standard CLI convention (PEP 440, click, argparse) is
to support both `--version` and `-V` as flag aliases. Fixed in
nwave_ai/cli.py:585-587 alongside the rc3 release.
"""

from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from nwave_ai.cli import main


def _invoke(args: list[str]) -> tuple[int, str, str]:
    """Invoke CLI main() with given args. Returns (exit_code, stdout, stderr)."""
    out, err = StringIO(), StringIO()
    with (
        patch("sys.argv", ["nwave-ai", *args]),
        patch("sys.stdout", out),
        patch("sys.stderr", err),
    ):
        code = main()
    return code, out.getvalue(), err.getvalue()


def test_long_flag_version() -> None:
    """`nwave-ai --version` exits 0 and prints version."""
    code, stdout, _ = _invoke(["--version"])
    assert code == 0
    assert "nwave-ai " in stdout


def test_short_flag_version() -> None:
    """`nwave-ai -V` exits 0 and prints version."""
    code, stdout, _ = _invoke(["-V"])
    assert code == 0
    assert "nwave-ai " in stdout


def test_subcommand_version_still_works() -> None:
    """`nwave-ai version` (subcommand form) keeps backward compatibility."""
    code, stdout, _ = _invoke(["version"])
    assert code == 0
    assert "nwave-ai " in stdout


def test_unknown_flag_rejected() -> None:
    """`nwave-ai --not-a-flag` returns non-zero with helpful error."""
    code, _, stderr = _invoke(["--not-a-flag"])
    assert code != 0
    assert "Unknown command" in stderr
