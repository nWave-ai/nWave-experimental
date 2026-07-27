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
