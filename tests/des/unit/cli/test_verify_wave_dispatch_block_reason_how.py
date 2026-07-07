"""Bugfix regression AT (GDP-3/GDP-4): the off-spine wave-dispatch guard's
BLOCK ``reason`` names WHAT + gestures at WHY but names no concrete,
actionable HOW.

Defect: ``decide_dispatch``'s no-signal BLOCK branch
(``src/des/domain/wave_dispatch_guard_policy.py::decide_dispatch``, the final
``return GuardDecision(verdict=GuardVerdict.BLOCK, ...)``) emits:

    "block: {subagent_type} dispatched off-spine with no DES-WAVE marker, no
    form-valid skip witness, and no valid session pre-grant -- refused
    (warn+ask: entering a wave off-spine is a human-conceded exception, never
    a silent default)"

This names WHAT (no marker / no witness / no pre-grant) and gestures at WHY
(a "human-conceded exception") but gives the operator no concrete
remediation -- no command to run, no marker syntax to embed. Per the standing
what-why-how rule
(``feedback_every_failure_explains_what_why_how_to_fix_2026_06_26``), every
failure surface must carry all three. The fix must route the operator to the
PRODUCING TOOL (``des dispatch --mode atdd_pure ...`` -- registered in
``src/des/cli/__main__.py`` as the ``dispatch`` subcommand, confirmed via
``des dispatch --help``: it renders a gate-valid prompt carrying a DES-WAVE
marker BY CONSTRUCTION) and/or name the exact ``<!-- DES-WAVE: <wave> -->``
marker syntax to embed by hand, and/or (if one exists) the session pre-grant
mechanism.

Driving surface (Mandate-13, Layer-3 composition): ``des.cli
.verify_wave_dispatch.main`` invoked IN-PROCESS -- the SAME production entry
point the ``dispatch.pre`` composition row calls (mirrors
``verify_readiness_pre_dispatch.py``'s convention). No subprocess fork,
stdout captured via ``capsys`` (Mandate-16 Driving-Port-Only: this IS the
composition-root driving port for this gate, not an internal-component
short-circuit).

Fix scope: this AT file only. Do NOT implement the fix here -- DISTILL
authors the regression AT, DELIVER (RED -> GREEN -> COMMIT) makes it pass.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_wave_dispatch import main


def _run_guard(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    *,
    prompt_text: str,
    session_id: str = "gdp-3-no-such-session",
) -> tuple[int, dict[str, object]]:
    """Drive ``des verify-wave-dispatch`` in-process; return (exit_code, payload).

    ``tmp_path`` is an empty repo root: no ``docs/feature/`` (no skip witness
    can exist), no ``.nwave/des/wave-skip-grant-*.json`` (no pre-grant can
    exist), no wave-active floor (the AT-3 collision branch cannot fire) --
    isolates the no-signal BLOCK / matching-marker ALLOW branches cleanly.
    """
    prompt_path = tmp_path / "dispatch-prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")
    exit_code = main(
        [
            "--subagent-type",
            "nw-acceptance-designer",
            "--prompt-path",
            str(prompt_path),
            "--repo-root",
            str(tmp_path),
            "--session-id",
            session_id,
        ]
    )
    stdout = capsys.readouterr().out.strip().splitlines()
    payload = json.loads(stdout[-1])
    return exit_code, payload


def test_off_spine_block_reason_names_a_concrete_how_to_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today, GDP-3/GDP-4): a wave-owner dispatched
    off-spine (no DES-WAVE marker, no witness, no pre-grant) is BLOCKED, and
    the block ``reason`` must name a concrete HOW -- the producing tool
    (``des dispatch``) and/or the marker syntax to embed
    (``<!-- DES-WAVE: <wave> -->``). Today's reason names neither string
    verbatim, so this fails for a genuine semantic AssertionError."""
    exit_code, payload = _run_guard(
        tmp_path,
        capsys,
        prompt_text="dispatch the acceptance designer, no marker anywhere here",
    )

    assert exit_code == 1, f"expected BLOCK (exit 1), got {exit_code}: {payload}"
    reason = payload["reason"]
    assert isinstance(reason, str)

    names_producing_tool = "des dispatch" in reason
    names_marker_syntax = "<!-- DES-WAVE:" in reason

    assert names_producing_tool or names_marker_syntax, (
        "off-spine BLOCK reason must name a concrete, actionable HOW: either "
        "the producing tool ('des dispatch') or the exact DES-WAVE marker "
        "syntax to embed ('<!-- DES-WAVE: <wave> -->') -- naming WHAT + "
        "gesturing at WHY is not enough (standing what-why-how rule). "
        f"Actual reason: {reason!r}"
    )


@pytest.mark.negative_at
def test_compliant_dispatch_is_never_blocked_by_the_how_fix(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (green today, stays green after the fix): a compliant
    on-spine dispatch (carries the matching DES-WAVE marker) is ALLOWED, and
    the allow-path reason emits no spurious HOW-routing text -- the fix must
    not leak the producing-tool / marker-syntax guidance onto the ALLOW path."""
    exit_code, payload = _run_guard(
        tmp_path,
        capsys,
        prompt_text="<!-- DES-WAVE: distill -->\ndispatch the acceptance designer",
    )

    assert exit_code == 0, f"expected ALLOW (exit 0), got {exit_code}: {payload}"
    reason = payload["reason"]
    assert isinstance(reason, str)
    assert "des dispatch" not in reason
    assert "<!-- DES-WAVE:" not in reason
