"""The terminal speaks to the orchestrator, and shows evidence it never reads.

WHAT THIS FILE STOPPED ASSERTING, and where those properties went. Six
scenarios drove `orchestrator_line`, which composed the move a WHOLE-Request
run left open from its disposition and from whether a durable value graph
survived THAT RUN. Both facts are quantified over the totality of a Request's
run, so ADR-DES-003 Section 11 sorts them to the composer, and they were
retired with `des dispatch`.

A STEP still prints an `ORCHESTRATOR` row, and it is a different observation
with a different home: Section 3's G5 DERIVES it from the primitive rows the
one invocation actually printed -- `TURNS-BOUGHT`, `ROLE`, `DIAGNOSTIC`,
`BLOCKED-BY`, `DEFECT-OWNER`. That law is asserted on
`des.cli.step_terminal.orchestrator_line` in
`tests/des/unit/cli/test_step_terminal_refusal_direction.py` and in
`tests/des/acceptance/steps_for_the_orchestrator/test_a_terminal_names_only_lines_it_carries.py`,
which is why removing the composed one costs no coverage.
"""

from __future__ import annotations

import json

from des.domain.orchestrator_terminal import (
    DIAGNOSTIC_CHARACTER_LIMIT,
    NO_ROLE_TURN,
    diagnostic_line,
)


def test_the_diagnostic_travels_verbatim_and_decodes_back_to_itself() -> None:
    diagnostic = 'Request carries three values; ordered as "a", then b, then c.'

    line = diagnostic_line(diagnostic)

    assert json.loads(line[len("DIAGNOSTIC: ") :]) == diagnostic


def test_a_multi_line_diagnostic_stays_exactly_one_line() -> None:
    """A record read line by line cannot have a field that becomes three."""
    diagnostic = "first finding\nsecond finding\nthird finding"

    line = diagnostic_line(diagnostic)

    assert "\n" not in line
    assert json.loads(line[len("DIAGNOSTIC: ") :]) == diagnostic


def test_no_role_turn_is_stated_never_left_blank() -> None:
    assert json.loads(diagnostic_line(None)[len("DIAGNOSTIC: ") :]) == NO_ROLE_TURN


def test_a_runaway_diagnostic_is_cut_and_says_how_much_it_dropped() -> None:
    diagnostic = "x" * (DIAGNOSTIC_CHARACTER_LIMIT + 137)

    shown = json.loads(diagnostic_line(diagnostic)[len("DIAGNOSTIC: ") :])

    assert shown.startswith("x" * DIAGNOSTIC_CHARACTER_LIMIT)
    assert shown.endswith("[TRUNCATED: 137 more characters]")


def test_a_diagnostic_at_the_limit_is_not_truncated() -> None:
    diagnostic = "x" * DIAGNOSTIC_CHARACTER_LIMIT

    assert json.loads(diagnostic_line(diagnostic)[len("DIAGNOSTIC: ") :]) == diagnostic
