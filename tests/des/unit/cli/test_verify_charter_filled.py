"""AT -- `des verify-charter-filled` (charter-scaffold feature, slice-02).

The backstop gate that closes the loop slice-01 opened: slice-01
(`des charter-scaffold`) PRODUCES a charter scaffold; this gate VERIFIES a
charter is actually FILLED (not just scaffolded-and-forgotten) before an
operator trusts it or lets it arm a downstream EXAMINE.

covers: slice-02 of docs/feature/charter-scaffold/feature-delta.md

A charter is FILLED iff every judgment section the scaffold left as a TODO
placeholder has been replaced by real content:
  (a) the oracle section is non-empty AND carries >=1 negative observation
      (a "the wrong output is NOT produced" line);
  (b) the start-recipe (Preconditions) section is non-empty;
  (c) no residual scaffold TODO/placeholder markers remain in either
      judgment section.
Verdicts: PASS (filled), FAIL (present-but-hollow -- names EACH still-TODO
section), INDETERMINATE (unreadable/malformed path -- missing file, empty
file, directory -- LOUD what/why/how, never a bare traceback, never a false
PASS). stdout token (``--format json``):
``{charter, filled, missing_sections, has_negative_observation, verdict,
detail}``.

RED reason (P1-P4 in-process active-RED, `nw-distill-red-scaffolding`):
`src/des/cli/verify_charter_filled.py` does not exist yet. Module-level
imports name ONLY stable, already-shipped entries -- NEVER the absent SUT
module (P1). Each test lazily imports `main` from
`des.cli.verify_charter_filled` INSIDE its body via `_invoke` (P3); the
resulting `ModuleNotFoundError` is a runtime exception raised WITHIN the
test's own call stack, not a collection-time error -- collection stays
green, and each test fails for a semantic reason once the module ships (P4).

Driving surface: `des.cli.verify_charter_filled.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture charter file (composition-root
driving port -- Mandate 16, driving-port-only boundary). No subprocess fork.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: A charter with EVERY judgment section genuinely filled: a real start
#: recipe, a real oracle with both a positive AND a negative observation.
#: No `<...>` placeholder tokens anywhere.
FILLED_CHARTER = """# A visitor books two seats and sees a countdown
ID: EXP-seat-booking-1 . Spec rows: slice-01 · Persona: visitor

## Intent
A visitor books two seats and sees a live countdown while payment is pending

## Preconditions
Start the booking service locally (`des serve --seed demo-seats`), open the
browser to /booking/theatre-42, and select 2 adjacent seats in the front row.

## Charter
Explore the booking flow to verify the countdown timer appears and holds.

## Expected observations (oracle)
- After selecting 2 seats and clicking "Hold", a visible countdown timer
  starts at 10:00 and ticks down every second.
- Negative: the held seats are NOT released back to the public pool while
  the countdown is still running.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""

#: A charter that is present but HOLLOW -- exactly what `charter-scaffold`
#: produces before a human fills it in. Intent is written out (as a fresh
#: scaffold would carry it, pre-filled from the Value statement), but the
#: oracle and start-recipe sections still carry the literal scaffold
#: placeholder tokens.
HOLLOW_CHARTER = """# A visitor books two seats and sees a countdown
ID: EXP-seat-booking-1 . Spec rows: R1 . Persona: visitor

## Intent
A visitor books two seats and sees a live countdown while payment is pending

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""

#: A charter where the start-recipe AND the Charter/Intent sections are
#: genuinely filled and the oracle has a real POSITIVE observation -- but
#: zero negative observations. The feature's own premise (per the charter
#: oracle: "the >=1-negative-observation check" is part of the gate) says
#: this must NOT be silently treated as filled.
ORACLE_MISSING_NEGATIVE_OBSERVATION_CHARTER = """# A visitor cancels a held seat before payment
ID: EXP-seat-booking-2 . Spec rows: R2 . Persona: visitor

## Intent
A visitor cancels a held seat before payment and the seat returns to the pool

## Preconditions
Start the booking service locally (`des serve --seed demo-seats`), hold a
seat as visitor A, then open a second session as visitor B.

## Charter
Explore the cancellation flow to verify the seat becomes available again.

## Expected observations (oracle)
- After visitor A cancels the hold, visitor B can immediately select the
  same seat.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _invoke(charter_path: Path, capsys) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()` (P2), stdout
    captured and parsed as the `--format json` contract token."""
    from des.cli.verify_charter_filled import main

    exit_code = main(
        [
            "--charter",
            str(charter_path),
            "--format",
            "json",
        ]
    )
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


def test_filled_charter_is_reported_as_filled_and_ready(tmp_path: Path, capsys) -> None:
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(FILLED_CHARTER, encoding="utf-8")

    exit_code, payload = _invoke(charter_path, capsys)

    # "you're good to go" -- not just a bare exit code: a plain-language
    # verdict token an operator recognizes, and it's the FILLED verdict, not
    # a generic pass-through.
    assert exit_code == 0
    assert payload["filled"] is True
    assert payload["verdict"] == "PASS"
    assert payload["missing_sections"] == []
    assert payload["has_negative_observation"] is True


def test_hollow_charter_names_each_still_incomplete_section(
    tmp_path: Path, capsys
) -> None:
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(HOLLOW_CHARTER, encoding="utf-8")

    exit_code, payload = _invoke(charter_path, capsys)

    # Not just a generic "invalid" verdict -- naming WHICH sections are
    # still TODO, so an operator knows exactly what to fill next.
    assert exit_code != 0
    assert payload["filled"] is False
    assert payload["verdict"] == "FAIL"
    joined_missing = " ".join(payload["missing_sections"])
    assert "oracle" in joined_missing
    assert "start-recipe" in joined_missing


@pytest.mark.negative_at
def test_hollow_charter_is_never_reported_as_filled(tmp_path: Path, capsys) -> None:
    """Negative AT: a false 'ready' verdict is the exact failure this
    command exists to prevent -- a HOLLOW charter must NOT be reported as
    filled/ready under any circumstance."""
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(HOLLOW_CHARTER, encoding="utf-8")

    _, payload = _invoke(charter_path, capsys)

    assert payload["filled"] is not True
    assert payload["verdict"] != "PASS"


@pytest.mark.negative_at
def test_oracle_with_no_negative_observation_is_not_silently_reported_filled(
    tmp_path: Path, capsys
) -> None:
    """Negative AT: an oracle with a positive observation but ZERO negative
    observations is not truly FILLED per this feature's own premise -- the
    operator relying on the tool must be TOLD (a visible FAIL / has_negative
    _observation: false), never silently passed with exit 0."""
    charter_path = tmp_path / "a-visitor-cancels-a-held-seat.md"
    charter_path.write_text(
        ORACLE_MISSING_NEGATIVE_OBSERVATION_CHARTER, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert payload["has_negative_observation"] is False
    assert payload["filled"] is not True
    assert payload["verdict"] != "PASS"
    assert exit_code != 0


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "make_charter_path",
    [
        pytest.param(
            lambda tmp_path: tmp_path / "does-not-exist.md",
            id="missing_file",
        ),
        pytest.param(
            lambda tmp_path: _write_empty(tmp_path / "empty-charter.md"),
            id="empty_file",
        ),
        pytest.param(
            lambda tmp_path: _mkdir(tmp_path / "a-directory-not-a-file"),
            id="directory_path",
        ),
    ],
)
def test_unreadable_charter_paths_never_crash_with_a_bare_traceback(
    tmp_path: Path, capsys, make_charter_path
) -> None:
    """Negative AT: whatever the command reports on a missing file, an
    unreadable/empty file, or a directory path, it reports a CLEAR message
    -- never a bare, unhandled traceback -- and it never silently passes."""
    charter_path = make_charter_path(tmp_path)

    exit_code, payload = _invoke(charter_path, capsys)

    assert exit_code != 0
    assert payload["verdict"] == "INDETERMINATE"
    assert payload["filled"] is not True
    # LOUD: a non-empty, human-readable explanation -- never a bare code.
    assert payload["detail"]
    assert str(charter_path) in payload["detail"] or "charter" in payload["detail"]


def _write_empty(path: Path) -> Path:
    path.write_text("", encoding="utf-8")
    return path


def _mkdir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
