"""`des state` refuses a handover nested too deep to parse, as a closed block.

A handover.json nested 5000 or more levels deep must answer the closed
Indeterminate block naming HandoverMalformed -- never a RecursionError
traceback -- and must leave the handover bytes untouched.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    asked,
    block,
    nexts,
)


DEPTH = 5000

WHY = ".nwave/des/handover.json is malformed: JSON nesting is too deep to parse"
HOW = (
    "delete .nwave/des/handover.json to re-elicit this Request from its "
    "durable authorities; the generated artifacts themselves are never removed"
)


@pytest.mark.parametrize(
    "nested",
    [
        pytest.param(b"[" * DEPTH + b"]" * DEPTH, id="array"),
        pytest.param(b'{"a":' * DEPTH + b"0" + b"}" * DEPTH, id="object"),
    ],
)
def test_state_refuses_a_handover_nested_too_deep(
    root: Path, step, turns: Path, nested: bytes
) -> None:
    handover = root / ".nwave" / "des" / "handover.json"
    handover.parent.mkdir(parents=True, exist_ok=True)
    handover.write_bytes(nested)

    code, stdout, stderr = step("state", "--repo-root", str(root))

    fields = block(stdout, stderr)
    assert code != 0
    assert fields.get("DELIVERY-OUTCOME") == "Indeterminate"
    assert fields.get("WHAT") == "HandoverMalformed"
    assert fields.get("WHY") == WHY
    assert fields.get("HOW") == HOW
    assert fields.get("TURNS-BOUGHT") == "0"
    assert nexts(stdout) == [
        f"des state --repo-root {root.resolve()} -- after the HOW above"
    ]
    assert "Traceback" not in stdout + stderr
    assert "RecursionError" not in stdout + stderr
    assert handover.read_bytes() == nested
    assert asked(turns) == []
