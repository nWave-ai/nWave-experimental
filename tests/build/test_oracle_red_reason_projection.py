"""Projection test for the "right-reason RED" GDP-9 line (K4 Run 13).

The CLI-level detection/refusal is covered by
`tests/des/unit/domain/test_oracle_execution_classifier.py`,
`tests/des/unit/cli/test_oracle_red_reason_refusal.py` and
`tests/des/acceptance/test_dispatch_oracle_red_reason.py`; this only proves
the agent-guidance wording landed in the right place.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACCEPTANCE_DESIGNER = ROOT / "nWave/agents/nw-acceptance-designer.md"


def test_acceptance_designer_asks_the_right_reason_question() -> None:
    text = ACCEPTANCE_DESIGNER.read_text(encoding="utf-8")
    compact = " ".join(text.split())

    assert (
        "Would this oracle pass once the feature exists, or does it fail "
        "for a reason the crafter cannot fix by implementing it" in compact
    )
    assert "K4 Run 13" in compact
    assert "`Model.check()`" in compact
    # Placed within RED_TO_GREEN step 5 (the oracle-write/read-back step),
    # right after the Run 10 splice-check sentence, before step 6.
    run10_index = text.index("K4 Run\n   10")
    right_reason_index = text.index("Would this oracle pass")
    step6_index = text.index("6. Before serializing any target's")
    assert run10_index < right_reason_index < step6_index
