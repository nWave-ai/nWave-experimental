"""`des state` refuses a handover whose authority is not a DESIGN section locator.

An authority that points outside the repository ("/etc/passwd") or names a
whole file with no #anchor ("docs/brief.md") must never project design=bound
nor route to `des oracle`: the step answers the closed ADR-DES-003 §4 class C
block, HandoverMalformed -> Indeterminate, buys no turn and writes nothing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    nexts,
)


HANDOVER_REPAIR = (
    "delete .nwave/des/handover.json to re-elicit this Request from its "
    "durable authorities; the generated artifacts themselves are never removed"
)


@pytest.mark.parametrize("authority", ["/etc/passwd", "docs/brief.md"])
def test_state_refuses_an_authority_that_is_not_a_design_section_locator(
    root: Path, step, turns: Path, authority: str
) -> None:
    handover = root / ".nwave" / "des" / "handover.json"
    handover.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        {
            "request": "deliver",
            "values": [
                {"observation": "A", "dependencies": [], "authority": authority}
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    handover.write_bytes(raw)

    code, stdout, stderr = step("state", "--repo-root", str(root))

    shown = block(stdout, stderr)
    assert code != 0, stdout + stderr
    assert shown.get("DELIVERY-OUTCOME") == "Indeterminate", stdout + stderr
    assert shown.get("WHAT") == "HandoverMalformed", stdout + stderr
    assert shown.get("WHY") == (
        "value 1 authority is invalid: it is not a repository-relative DESIGN "
        f'section locator (path#heading): "{authority}"'
    ), stdout + stderr
    assert shown.get("HOW") == HANDOVER_REPAIR, stdout + stderr
    assert shown.get("TURNS-BOUGHT") == "0", stdout + stderr
    assert nexts(stdout) == [
        f"des state --repo-root {root.resolve()} -- after the HOW above"
    ], stdout + stderr
    for forbidden in ("design=bound", "des oracle", "Traceback"):
        assert forbidden not in stdout + stderr, stdout + stderr
    assert handover.read_bytes() == raw
    assert asked(turns) == []


def test_state_still_binds_a_valid_design_section_locator(
    root: Path, step, turns: Path
) -> None:
    """Positive control: a valid path#heading authority still projects design=bound.

    Section resolution is owned by later steps, so `des state` needs no
    section content to project the binding.
    """
    handover = root / ".nwave" / "des" / "handover.json"
    handover.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(
        {
            "request": "deliver",
            "values": [
                {
                    "observation": "A",
                    "dependencies": [],
                    "authority": "docs/brief.md#B",
                }
            ],
        },
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    handover.write_bytes(raw)

    code, stdout, stderr = step("state", "--repo-root", str(root))

    shown = block(stdout, stderr)
    assert code == 0, stdout + stderr
    assert shown.get("DELIVERY-OUTCOME") == "Success", stdout + stderr
    assert "design=bound" in (shown.get("VALUE-1") or ""), stdout + stderr
    assert "WHAT" not in shown, stdout + stderr
    assert "after the HOW above" not in stdout + stderr, stdout + stderr
    assert "Traceback" not in stdout + stderr, stdout + stderr
    assert handover.read_bytes() == raw
    assert asked(turns) == []
