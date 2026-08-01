"""Regression (GDP-6 false positive, sister friction #90): `des
verify-charter-filled`'s placeholder detector must reject only the KNOWN
scaffold tokens the `charter-scaffold` template actually emits inside the
two sections it verifies -- NOT every angle-bracketed span of prose.

Bug: ``_PLACEHOLDER_RE = re.compile(r"<[^>]+>")``
(``src/des/cli/verify_charter_filled.py:60``, consumed by ``_has_placeholder``
at line 84) treats ANY ``<...>`` span in the Preconditions / oracle section
body as a surviving scaffold placeholder. A charter whose PO wrote
legitimate, fully-filled prose that happens to use angle brackets as a
notation for a role/field name (e.g. "log in as the ``<developer>`` and
enter their ``<name>``") is bounced as still-hollow even though every
judgment section is genuinely filled. The PO had to rewrite the sentence
bracket-free to pass the gate -- the exact false positive this AT pins.

Grounded scaffold-token enumeration (SSOT: `nWave/templates/expectation-
charter.md`, the fenced block under `## Template`, as extracted by
`charter_scaffold._extract_template_skeleton` and left untouched by
`_fill_intent_section` -- which fills ONLY the `## Intent` body). Of that
skeleton, exactly the tokens landing inside the TWO sections
`verify_charter_filled._analyze_charter` actually inspects
(`## Preconditions` and `## Expected observations (oracle)`) are the
detector's real job:
  - Preconditions: ``<start recipe: how to run the system from a clean
    state, seed state>``
  - Oracle (positive line): ``<observable outcome, user language>``
  - Oracle (negative line): ``<negative: what must NOT happen>``
(The template also carries placeholder tokens in the title/ID line and the
`## Charter` section -- e.g. `EXP-<feature>-<n>`, `<who>`, `<area>`,
`<surface: browser/CLI/API>` -- but `_analyze_charter` never reads those
sections, so they are out of scope for this detector and this AT.)

Fix direction (not implemented here -- TEST ONLY, no production changes):
match only the three tokens above (or the template's exact scaffold
strings), not a blanket `<[^>]+>` sweep.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL `des.cli.verify_charter_filled.main(argv)`
CLI driver invoked in-process against a `tmp_path` charter file, stdout
captured via `capsys` -- same pattern as
`tests/des/unit/cli/test_verify_charter_filled.py` (the sibling suite this
AT's fixtures/driving-call mirror). The production module already exists
(this is a *behavior* bug, not a missing-module RED), so the import sits at
module top like the sibling suite -- the RED here is a semantic
`AssertionError` from a wrong PASS/FAIL verdict, never a collection error.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.cli.verify_charter_filled import main


#: A charter where EVERY judgment section is genuinely filled -- real start
#: recipe, real positive + negative oracle observations -- but the prose
#: legitimately uses angle brackets as a role/field notation
#: (`<developer>`, `<name>`). No scaffold placeholder token (the three
#: enumerated above) appears anywhere. This is the sister's exact repro
#: shape.
LEGITIMATE_PROSE_WITH_ANGLE_BRACKETS_CHARTER = """# A developer registers and sees their profile
ID: EXP-onboarding-1 . Spec rows: slice-01 · Persona: developer

## Intent
A developer registers an account and immediately sees their profile

## Preconditions
Register a new `<developer>` role account named `<name>` via the admin
console at `/admin/users/new`, then log in as that `<developer>`.

## Charter
Explore the onboarding flow to verify the profile page renders correctly.

## Expected observations (oracle)
- The profile page displays the `<developer>` role next to the `<name>`
  field for the newly registered account.
- Negative: the `<developer>` role and `<name>` field are NOT shown to an
  unauthenticated visitor browsing the same URL.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _charter_with_precondition_scaffold_token() -> str:
    """Preconditions still carries the REAL scaffold token verbatim; oracle
    is genuinely filled (positive + negative, no placeholders)."""
    return """# A developer registers and sees their profile
ID: EXP-onboarding-2 . Spec rows: R2 . Persona: developer

## Intent
A developer registers an account and immediately sees their profile

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore the onboarding flow to verify the profile page renders correctly.

## Expected observations (oracle)
- The profile page displays the developer's role next to their name.
- Negative: the role and name fields are NOT shown to an unauthenticated
  visitor browsing the same URL.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _charter_with_oracle_positive_scaffold_token() -> str:
    """Preconditions genuinely filled; oracle's POSITIVE line still carries
    the real scaffold token verbatim, negative line is real."""
    return """# A developer registers and sees their profile
ID: EXP-onboarding-3 . Spec rows: R3 . Persona: developer

## Intent
A developer registers an account and immediately sees their profile

## Preconditions
Register a new developer account named Jordan via the admin console at
`/admin/users/new`, then log in as that developer.

## Charter
Explore the onboarding flow to verify the profile page renders correctly.

## Expected observations (oracle)
- <observable outcome, user language>
- Negative: the role and name fields are NOT shown to an unauthenticated
  visitor browsing the same URL.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _charter_with_oracle_negative_scaffold_token() -> str:
    """Preconditions genuinely filled; oracle's positive line is real, but
    the NEGATIVE line still carries the real scaffold token verbatim (so it
    is neither a real negative observation nor placeholder-free)."""
    return """# A developer registers and sees their profile
ID: EXP-onboarding-4 . Spec rows: R4 . Persona: developer

## Intent
A developer registers an account and immediately sees their profile

## Preconditions
Register a new developer account named Jordan via the admin console at
`/admin/users/new`, then log in as that developer.

## Charter
Explore the onboarding flow to verify the profile page renders correctly.

## Expected observations (oracle)
- The profile page displays the developer's role next to their name.
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _invoke(charter_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict]:
    """The driving call every test uses: in-process `main()` (P2), stdout
    captured and parsed as the `--format json` contract token."""
    exit_code = main(["--charter", str(charter_path), "--format", "json"])
    captured = capsys.readouterr()
    return exit_code, json.loads(captured.out)


# ---------------------------------------------------------------------------
# POSITIVE -- RED today: legitimate prose using `<developer>` / `<name>` as
# a role/field notation must PASS. Today it is wrongly rejected because
# `_PLACEHOLDER_RE = <[^>]+>` treats those spans as surviving scaffold
# placeholders.
# ---------------------------------------------------------------------------


def test_legitimate_prose_with_angle_bracket_terms_is_reported_as_filled(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    charter_path = tmp_path / "a-developer-registers-and-sees-their-profile.md"
    charter_path.write_text(
        LEGITIMATE_PROSE_WITH_ANGLE_BRACKETS_CHARTER, encoding="utf-8"
    )

    exit_code, payload = _invoke(charter_path, capsys)

    assert exit_code == 0, (
        "false positive (GDP-6, sister friction #90): a charter with "
        "genuinely filled sections was rejected merely for containing "
        f"`<developer>`/`<name>` prose. Payload: {payload!r}"
    )
    assert payload["verdict"] == "PASS", payload
    assert payload["filled"] is True, payload
    assert payload["missing_sections"] == [], payload
    assert payload["has_negative_observation"] is True, payload


# ---------------------------------------------------------------------------
# NEGATIVE guard -- a charter still carrying a GENUINE scaffold token (one
# of the three enumerated above) must stay rejected. The fix must not
# blanket-allow all angle-bracketed content.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "make_charter_content",
    [
        pytest.param(
            _charter_with_precondition_scaffold_token,
            id="precondition_scaffold_token_survives",
        ),
        pytest.param(
            _charter_with_oracle_positive_scaffold_token,
            id="oracle_positive_scaffold_token_survives",
        ),
        pytest.param(
            _charter_with_oracle_negative_scaffold_token,
            id="oracle_negative_scaffold_token_survives",
        ),
    ],
)
def test_charter_with_genuine_scaffold_token_still_rejects_as_incomplete(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], make_charter_content
) -> None:
    charter_path = tmp_path / "a-developer-registers-and-sees-their-profile.md"
    charter_path.write_text(make_charter_content(), encoding="utf-8")

    exit_code, payload = _invoke(charter_path, capsys)

    assert exit_code != 0, payload
    assert payload["verdict"] != "PASS", payload
    assert payload["filled"] is not True, payload
