"""Regression -- `des verify-charter-filled` certifies the DESIGNATION (prose
sections non-empty), never the PROPERTY (does this charter ARM the examine
gate for its slice) -- GDP-8.

Defect (`defects.md`,
`verify-charter-filled-certifies-designation-not-arming-property`): measured
2026-07-30 by a sibling lane filling 5 charter scaffolds -- 4 of them
returned `des verify-charter-filled` -> `"verdict": "PASS"` while ALL 5
slices of the feature resolved `resolve_slice_charter` -> INDETERMINATE. The
gate never inspects the `ID:` line's `Spec rows:` field: it checks that the
oracle and start-recipe sections are non-empty and carry >=1 negative
observation, but never that the `Spec rows:` VALUE is in the vocabulary
`resolve_slice_charter` (`des.domain.expectation_charter_mapping`) actually
accepts (today: comma-separated `slice-NN` tokens, `_SLICE_ID_PATTERN`). A
charter can be certified FILLED and still fail to resolve to anything
downstream.

Two directions, both required (a fix that only adds the refusal and breaks
the existing PASS path is not a fix):
  - a charter whose prose is fully compiled but whose `Spec rows:` value is
    OUT OF VOCABULARY (or absent) must NOT be reported PASS/filled;
  - a charter whose prose is fully compiled AND whose `Spec rows:` value IS
    in vocabulary (a valid `slice-NN` token) must STILL be reported
    PASS/filled -- this is an ADDED check, not a replacement of the existing
    prose-completeness checks.

Scope note: the vocabulary this test validates against is the CURRENT
`resolve_slice_charter` grammar (`slice-NN` only) -- as of this test's
authoring, no lane has yet widened that grammar to admit the `bug-observable`
/ `brownfield-discovery` seed-mode identifiers (that is a separate, human-
routed grammar decision per `docs/feature/fix-charter-scaffold-placeholder-
scope/feature-delta.md` DD-2, explicitly out of scope here). This test
therefore does NOT hardcode those tokens as valid or invalid -- it only
asserts the CLOSED grammar `slice-NN` is accepted and a requirement-id-shaped
token (`R12`) is not, matching the exact shape the defect report measured.

Driving surface: `des.cli.verify_charter_filled.main(argv) -> int` invoked
IN-PROCESS against a `tmp_path` fixture charter file (same pattern as the
sibling suite `tests/des/unit/cli/test_verify_charter_filled.py`). The
production module already exists (this is a *behavior* gap, not a missing
module) -- RED here is a semantic `AssertionError` from a wrong PASS
verdict, never a collection error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


#: Fully-compiled prose (real start recipe, real oracle with a positive AND
#: a negative observation) -- the ONLY thing wrong with this charter is its
#: `Spec rows:` value: `R12` is a requirement-id-shaped token, not the
#: `slice-NN` grammar `resolve_slice_charter` accepts. This is the EXACT
#: shape the defect measured: prose complete, scope value out of vocabulary.
CHARTER_WITH_PROSE_FILLED_BUT_SPEC_ROWS_OUT_OF_VOCABULARY = """# A visitor books two seats and sees a countdown
ID: EXP-seat-booking-9 · Spec rows: R12 · Persona: visitor

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

#: The SAME prose, but `Spec rows:` is absent from the `ID:` line entirely --
#: the other shape `resolve_slice_charter` reports INDETERMINATE for ("no
#: `Spec rows:` mapping"), so this gate must not pass it either.
CHARTER_WITH_PROSE_FILLED_BUT_SPEC_ROWS_MISSING = """# A visitor books two seats and sees a countdown
ID: EXP-seat-booking-9 · Persona: visitor

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

#: The SAME prose again, this time with a `Spec rows:` value that IS in the
#: `slice-NN` vocabulary -- the negative-direction fixture: adding the new
#: check must NOT turn this into a false FAIL.
CHARTER_WITH_PROSE_FILLED_AND_SPEC_ROWS_VALID = """# A visitor books two seats and sees a countdown
ID: EXP-seat-booking-9 · Spec rows: slice-01 · Persona: visitor

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

#: A charter mapping to MULTIPLE valid slices at once (comma-separated) --
#: confirms the check validates every token, not just the first.
CHARTER_WITH_PROSE_FILLED_AND_MULTIPLE_VALID_SPEC_ROWS = (
    CHARTER_WITH_PROSE_FILLED_AND_SPEC_ROWS_VALID.replace(
        "Spec rows: slice-01", "Spec rows: slice-01, slice-02"
    )
)


def _invoke(charter_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()`, stdout
    captured and parsed as the `--format json` contract token."""
    from des.cli.verify_charter_filled import main

    exit_code = main(["--charter", str(charter_path), "--format", "json"])
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


@pytest.mark.negative_at
def test_prose_filled_but_spec_rows_out_of_vocabulary_is_never_reported_filled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative AT -- the exact shape the defect measured: prose sections
    fully compiled, `Spec rows:` value (`R12`) outside the resolver's
    `slice-NN` grammar. This must NOT be a PASS, no matter how complete the
    prose is -- a false 'ready' verdict here is precisely what let 4 charters
    through while their slices resolved INDETERMINATE downstream."""
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(
        CHARTER_WITH_PROSE_FILLED_BUT_SPEC_ROWS_OUT_OF_VOCABULARY, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert payload["verdict"] != "PASS", payload
    assert payload["filled"] is not True, payload
    assert exit_code != 0, payload
    joined_missing = " ".join(payload["missing_sections"]).lower()
    assert "spec rows" in joined_missing or "spec-rows" in joined_missing, (
        f"missing_sections must name the Spec rows scope problem, not just "
        f"the (here, fully-compiled) prose sections: {payload!r}"
    )
    assert "r12" in joined_missing, (
        f"the refusal must NAME the offending value (WHAT), not just say "
        f"'invalid': {payload!r}"
    )


@pytest.mark.negative_at
def test_prose_filled_but_spec_rows_missing_is_never_reported_filled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Negative AT -- the sibling shape: prose fully compiled, `Spec rows:`
    absent from the `ID:` line entirely. `resolve_slice_charter` reports
    INDETERMINATE ('no Spec rows: mapping') for this shape too, so this gate
    must not certify it FILLED either."""
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(
        CHARTER_WITH_PROSE_FILLED_BUT_SPEC_ROWS_MISSING, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert payload["verdict"] != "PASS", payload
    assert payload["filled"] is not True, payload
    assert exit_code != 0, payload


def test_prose_filled_and_spec_rows_valid_still_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The added check must not become a false negative: a charter whose
    `Spec rows:` value IS a valid `slice-NN` token, with fully-compiled
    prose, must still PASS exactly as before."""
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(
        CHARTER_WITH_PROSE_FILLED_AND_SPEC_ROWS_VALID, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert exit_code == 0, payload
    assert payload["verdict"] == "PASS", payload
    assert payload["filled"] is True, payload
    assert payload["missing_sections"] == [], payload
    assert payload["has_negative_observation"] is True, payload


def test_prose_filled_and_multiple_valid_spec_rows_still_passes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Multiple comma-separated valid `slice-NN` tokens must also PASS --
    the check validates the whole set, not just a single-token shortcut."""
    charter_path = tmp_path / "a-visitor-books-two-seats.md"
    charter_path.write_text(
        CHARTER_WITH_PROSE_FILLED_AND_MULTIPLE_VALID_SPEC_ROWS, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert exit_code == 0, payload
    assert payload["verdict"] == "PASS", payload
    assert payload["filled"] is True, payload
