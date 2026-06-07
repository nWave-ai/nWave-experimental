"""
Unit tests for error formatting: NO_COLOR compliance and structured output.

Test Budget: 2 distinct behaviors x 2 = 4 unit tests max.

Behaviors:
  B1 - NO_COLOR env propagation: _isolated_env passes NO_COLOR through when set
  B2 - Validator stdout/stderr contain no ANSI escape when NO_COLOR=1

Driving port: nwave_ai.feature_delta.cli.validate_feature_delta_command (B2)
              tests.feature_delta.acceptance.conftest._isolated_env (B1)
"""

from __future__ import annotations

import io
import os
import re
from typing import TYPE_CHECKING
from unittest.mock import patch


if TYPE_CHECKING:
    from pathlib import Path


# ---------------------------------------------------------------------------
# B1 — _isolated_env propagates NO_COLOR when set in caller environment
# ---------------------------------------------------------------------------

_ANSI_RE = re.compile(r"\x1b\[")


def test_isolated_env_propagates_no_color_when_set(tmp_path: Path) -> None:
    """_isolated_env must include NO_COLOR in the subprocess env when caller has it."""
    from tests.feature_delta.acceptance.conftest import _isolated_env

    sandbox = tmp_path / "sandbox" / "repo"
    sandbox.mkdir(parents=True)

    with patch.dict(os.environ, {"NO_COLOR": "1"}):
        env = _isolated_env(sandbox)

    assert "NO_COLOR" in env, (
        "NO_COLOR must be forwarded to subprocess when set in caller environment"
    )
    assert env["NO_COLOR"] == "1"


def test_isolated_env_omits_no_color_when_absent(tmp_path: Path) -> None:
    """_isolated_env must NOT inject NO_COLOR when caller did not set it."""
    from tests.feature_delta.acceptance.conftest import _isolated_env

    sandbox = tmp_path / "sandbox" / "repo"
    sandbox.mkdir(parents=True)

    clean_env = {k: v for k, v in os.environ.items() if k != "NO_COLOR"}
    with patch.dict(os.environ, clean_env, clear=True):
        env = _isolated_env(sandbox)

    assert "NO_COLOR" not in env, (
        "NO_COLOR must not appear in subprocess env when caller did not set it"
    )


# ---------------------------------------------------------------------------
# B2 — Validator output contains no ANSI when NO_COLOR=1
# ---------------------------------------------------------------------------


def test_validator_human_output_has_no_ansi_with_no_color(tmp_path: Path) -> None:
    """validate_feature_delta_command must not emit ANSI escape codes when NO_COLOR=1."""
    from nwave_ai.feature_delta.cli import validate_feature_delta_command

    # Write a valid feature-delta so the validator produces [PASS] output
    delta = tmp_path / "feature-delta.md"
    delta.write_text(
        "# test\n\n## Wave: DISCUSS\n\n### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | trivial commitment | n/a | preserves trivial surface |\n",
        encoding="utf-8",
    )

    stderr_capture = io.StringIO()
    with patch.dict(os.environ, {"NO_COLOR": "1"}):
        with patch("sys.stderr", stderr_capture):
            validate_feature_delta_command(str(delta), mode="warn-only", fmt="human")

    output = stderr_capture.getvalue()
    assert not _ANSI_RE.search(output), (
        f"Expected no ANSI escape codes in stderr when NO_COLOR=1, got: {output!r}"
    )
