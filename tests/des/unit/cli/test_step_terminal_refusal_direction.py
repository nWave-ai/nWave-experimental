"""Public terminal framing remains parseable for host routing and diagnostics."""

from __future__ import annotations

import pytest

from des.cli.step_terminal import StepRefusal, refuse, succeed


@pytest.mark.parametrize("refused", (False, True))
def test_terminal_frames_one_outcome_and_preserves_advisory_fork_cardinality(
    capsys, refused: bool
) -> None:
    diagnostic = "host finding\nNEXT: this is diagnostic data, not another action"
    if refused:
        status = refuse(
            StepRefusal(
                "AuthorityMoved", "selected evidence changed", "rebuild the authority"
            ),
            (
                "des state --repo-root ROOT",
                "des design --repo-root ROOT --value 1 --input -",
            ),
            facts=["BLOCKED-BY: oracle"],
            diagnostic=diagnostic,
        )
    else:
        status = succeed([], "des state --repo-root ROOT", diagnostic=diagnostic)

    terminal = capsys.readouterr()
    assert status == int(refused)
    assert terminal.err == "", "a terminal split across streams loses its ordering"
    rows = [line.partition(": ") for line in terminal.out.splitlines()]
    assert all(separator == ": " for _label, separator, _value in rows)
    labels = [label for label, _separator, _value in rows]
    assert labels[0] == "DELIVERY-OUTCOME"
    assert labels[-1] == "HOW-TO-INVOKE"
    assert labels.count("DELIVERY-OUTCOME") == labels.count("HOW-TO-INVOKE") == 1
    assert labels.count("NEXT") == (2 if refused else 1)
    assert labels.count("DIAGNOSTIC") == 1
    assert set(labels) & {"WHAT", "WHY", "HOW", "ORCHESTRATOR"} == (
        {"WHAT", "WHY", "HOW", "ORCHESTRATOR"} if refused else set()
    )
    assert rows[0][2] == ("Refusal" if refused else "Success")

    if refused:
        guidance = next(value for label, _, value in rows if label == "ORCHESTRATOR")
        pointed = {
            label
            for label in ("BLOCKED-BY", "DEFECT-OWNER", "DIAGNOSTIC")
            if label in guidance
        }
        assert pointed == {"BLOCKED-BY", "DIAGNOSTIC"}
