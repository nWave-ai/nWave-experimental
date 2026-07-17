"""Regression -- ``des verify-negative-at --all-critical`` conflates TWO
distinct refusal causes into ONE byte-identical message (GDP-3 violation).

RCA: docs/feature/fix-verify-negative-at-two-causes/deliver/rca.md.
Feature-delta: docs/feature/fix-verify-negative-at-two-causes/feature-delta.md.

``--all-critical`` (commit 7031d5df8) is a caller-declares-criticality
escape hatch that lets a scope exist with ZERO scannable AT tokens at all
(a prose file, a doc, a genuinely empty module) -- a case the original
2-state model (covered / presence-only-weak) never anticipated, because
under the mark-based path a critical scope always had >=1 scannable case
by construction. Today both causes emit the SAME "presence-only coverage /
add a negative AT" refusal:

  (a) genuine presence-only -- the file HAS real ATs but none is negative
      (correct advice: add a negative AT); and
  (b) zero-scannable -- the file has NO test-declaration tokens at all
      (misleading: there is nothing to "add a negative AT" TO; the real
      problem is the wrong file/scope was pointed at).

Bug observable (the oracle, message-only -- decision/exit UNCHANGED for
both causes): a zero-scannable scope must get a message that does NOT use
the "presence-only" / "add a negative AT" wording and DOES name the real
cause (no scannable AT surface / check the file-scope), while a genuine
presence-only scope keeps the existing "add a negative AT" wording. Both
still refuse (exit 1); a scope with a genuine negative AT still passes
(exit 0).

Driving surface (Mandate-13/16 driving-port-only, Layer 3 in-process
default): the REAL ``des verify-negative-at`` CLI entry (``main()``),
captured via ``capsys`` -- the bug is the shape of the JSON payload the CLI
emits, so the CLI is the faithful driving port. Fixture idiom mirrored from
``tests/des/unit/cli/test_verify_negative_at.py`` (``_first_event``,
``--test-file``/``--all-critical`` invocation shape) -- reused, not
duplicated logic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_negative_at import main


# A file with a REAL, presence-only critical AT -- case (a), unchanged.
_PRESENCE_ONLY_PY = """\
def test_seat_hold_is_created():
    result = {"hold": "abc123"}
    assert result["hold"] is not None
"""

# A file with a genuine negative AT alongside the presence-only one --
# regression pin: the scope still passes (exit 0) either way.
_HAS_NEGATIVE_PY = _PRESENCE_ONLY_PY + (
    "\n\n"
    "def test_unrelated_input_does_not_trigger_a_second_hold():\n"
    "    holds = [{'id': 1}]\n"
    "    assert len(holds) == 1\n"
)

# Pure prose -- ZERO test-declaration tokens (no def/fn/func/function, no
# test()/it()/describe() calls). Case (b): nothing to scan at all.
_ZERO_SCANNABLE_PROSE = """\
Booking notes

This document describes the booking workflow used by the team. There is
no automated coverage here -- QA signs off manually after each release.
See the runbook for the manual checklist.
"""

_PRESENCE_ONLY_WORDING = "presence-only"


def _first_event(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    out: dict[str, object] = json.loads(capsys.readouterr().out.splitlines()[0])
    return out


def _flatten_scope_text(event: dict[str, object]) -> str:
    """All human-readable text on a NegativeAtRefused payload, lowercased --
    top-level what/why/how plus every offending scope's what/why/how."""
    parts = [
        str(event.get("what", "")),
        str(event.get("why", "")),
        str(event.get("how", "")),
    ]
    scopes = event.get("scopes", [])
    assert isinstance(scopes, list)
    for scope in scopes:
        assert isinstance(scope, dict)
        parts.append(str(scope.get("what", "")))
        parts.append(str(scope.get("why", "")))
        parts.append(str(scope.get("how", "")))
    return " ".join(parts).lower()


def test_zero_scannable_scope_is_not_mislabeled_presence_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """BUG observable, NEGATIVE proof: a --all-critical scope with ZERO
    scannable AT tokens must NOT get the "presence-only" / "add a negative
    AT" wording -- there is nothing to add a negative assertion TO. The
    real cause (no scannable AT surface in this file/scope -- wrong
    file/dir was pointed at) must be named instead. Exit code (refusal)
    is unchanged -- this pins the MESSAGE only.
    """
    prose_file = tmp_path / "booking-notes.md"
    prose_file.write_text(_ZERO_SCANNABLE_PROSE)

    exit_code = main(["--test-file", str(prose_file), "--all-critical"])

    assert exit_code == 1  # decision/exit unchanged (RCA non-goal)
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtRefused"

    text = _flatten_scope_text(event)
    assert _PRESENCE_ONLY_WORDING not in text, (
        "zero-scannable scope (no test-declaration tokens found) must NOT "
        f"be mislabeled with 'presence-only' wording -- got: {text!r}"
    )
    assert "add a negative" not in text and "add an at asserting" not in text, (
        "zero-scannable scope must not tell the operator to add a negative "
        f"AT to a scope that has no ATs at all -- got: {text!r}"
    )
    assert any(
        phrase in text
        for phrase in ("no scannable", "zero scannable", "no test-declaration")
    ), (
        "zero-scannable scope must name the REAL cause (no scannable AT "
        f"surface / check the file-scope) -- got: {text!r}"
    )


def test_presence_only_scope_still_gets_add_negative_at_wording(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """REGRESSION pin, case (a) unchanged: a --all-critical scope with a
    REAL, presence-only AT keeps the existing "add a negative AT" advice
    and still refuses (exit 1). The fix must NOT weaken this genuine
    enforcement while fixing the zero-scannable mislabeling above.
    """
    test_file = tmp_path / "test_seat_hold.py"
    test_file.write_text(_PRESENCE_ONLY_PY)

    exit_code = main(["--test-file", str(test_file), "--all-critical"])

    assert exit_code == 1
    event = _first_event(capsys)
    assert event["event"] == "NegativeAtRefused"
    text = _flatten_scope_text(event)
    assert _PRESENCE_ONLY_WORDING in text or "add an at asserting" in text, (
        "genuine presence-only scope must keep naming presence-only "
        f"coverage / the add-a-negative-AT remedy -- got: {text!r}"
    )


def test_negative_at_present_still_passes_regardless_of_all_critical(
    tmp_path: Path,
) -> None:
    """REGRESSION pin: a scope carrying a genuine negative AT is unaffected
    by this fix -- it never rejects, with or without --all-critical."""
    test_file = tmp_path / "test_seat_hold.py"
    test_file.write_text(_HAS_NEGATIVE_PY)

    assert main(["--test-file", str(test_file), "--all-critical"]) == 0
    assert main(["--test-file", str(test_file)]) == 0
