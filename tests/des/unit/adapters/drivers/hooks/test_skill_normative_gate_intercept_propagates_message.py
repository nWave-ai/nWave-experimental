"""Regression -- the skill-normative gate intercept must not discard the
subprocess's own diagnostic.

Hook-audit fix 2026-07-29 (Difetto C, GDP-3 omission). `_run_skill_gate_subprocess`
captures `des skill-normative-gate`'s real stdout/stderr (`des_spawn(...,
capture_output=True, text=True, ...)`), but the subprocess's stdout already NAMES
the failing clause(s) -- `skill_normative_gate.py::_render` prints
`"FAIL: N failing clause(s)\\n{clause.render() ...}"`, and each clause's
`render()` names the skill, the clause id, the absent marker text, WHY, and HOW.
The pre-fix `_evaluate_skill_normative_intercept` discarded all of that and
reported only `"skill-normative gate vetoed the skill edit (gate exit N)"` --
the fact was already in scope (the subprocess had already produced it) and the
hook silently dropped it, forcing the operator to re-run the gate by hand to
learn what this call already knew.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.drivers.hooks import pre_write_handler
from des.adapters.drivers.hooks.hook_protocol import STDERR_CAPTURE_MAX_CHARS


if TYPE_CHECKING:
    import pytest


_SKILL_PATH = "nWave/skills/some-skill/SKILL.md"


def _fake_completed(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["des", "skill-normative-gate"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def test_block_reason_propagates_the_gates_own_clause_naming_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FAIL gate run's stdout (which names the clause) must reach the reason."""
    distinctive_output = (
        "FAIL: 1 failing clause(s)\n"
        "nw-example-skill — protocol-driver:assert-shipped-artifact: marker "
        "'artifact the SUT actually shipped' is absent. WHY: this is a "
        "normative clause — the skill must state it. HOW: add the marker "
        "back to nWave/skills/nw-example-skill/SKILL.md"
    )
    monkeypatch.setattr(
        pre_write_handler,
        "_run_skill_gate_subprocess",
        lambda: _fake_completed(1, stdout=distinctive_output),
    )

    result = pre_write_handler._evaluate_skill_normative_intercept(_SKILL_PATH)

    assert result is not None
    assert result["decision"] == "block"
    assert "protocol-driver:assert-shipped-artifact" in result["reason"], (
        "the gate's own clause-naming stdout must reach the block reason, not "
        f"just the bare exit code; got:\n{result['reason']}"
    )
    assert "marker" in result["reason"] and "absent" in result["reason"]


def test_block_reason_truncates_long_gate_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pathologically long gate stdout is capped, never unbounded in the body."""
    huge_output = "X" * (STDERR_CAPTURE_MAX_CHARS * 3)
    monkeypatch.setattr(
        pre_write_handler,
        "_run_skill_gate_subprocess",
        lambda: _fake_completed(1, stdout=huge_output),
    )

    result = pre_write_handler._evaluate_skill_normative_intercept(_SKILL_PATH)

    assert result is not None
    assert len(result["reason"]) <= STDERR_CAPTURE_MAX_CHARS + 200


def test_block_reason_degrades_gracefully_when_gate_prints_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A FAIL exit with empty stdout still names the exit code, no silent gap."""
    monkeypatch.setattr(
        pre_write_handler,
        "_run_skill_gate_subprocess",
        lambda: _fake_completed(1, stdout=""),
    )

    result = pre_write_handler._evaluate_skill_normative_intercept(_SKILL_PATH)

    assert result is not None
    assert result["decision"] == "block"
    assert "gate exit 1" in result["reason"]
    assert "no gate output captured" in result["reason"]


def test_passing_gate_still_allows_the_edit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A PASS (exit 0) run is unaffected by the propagation fix -- still allows."""
    monkeypatch.setattr(
        pre_write_handler,
        "_run_skill_gate_subprocess",
        lambda: _fake_completed(0, stdout="PASS: 0 failing clauses"),
    )

    assert pre_write_handler._evaluate_skill_normative_intercept(_SKILL_PATH) is None


def test_non_skill_tree_path_is_not_the_intercepts_concern() -> None:
    """A path outside nWave/skills/** never even reaches the subprocess."""
    assert (
        pre_write_handler._evaluate_skill_normative_intercept("src/des/foo.py") is None
    )
