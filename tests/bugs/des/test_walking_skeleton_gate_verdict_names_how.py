"""Regression (GDP-3): the walking-skeleton gate's FAIL verdict must carry a
`how` field naming the remediation, not only `diagnostic` (WHAT/WHY, no HOW).

Charter: ``docs/product/expectations/fix-walking-skeleton-gate-verdict-names-how/
the-fail-verdict-names-how-to-fix-the-tier.md``.

Found in ``src/des/domain/gate_outcome.py``:
  * ``GateOutcome.facet_failure`` (:101) and ``GateOutcome.at_failure`` (:112)
    -- both FAIL factories carry a ``diagnostic`` (the cause) but no ``how``
    (the remediation). ``GateOutcome`` (:77, frozen dataclass) has no ``how``
    field at all.
  * ``src/des/cli/walking_skeleton_gate.py`` ``_emit`` (:280) -- builds the
    JSON verdict payload ``{event, verdict, tier_of_record, reason,
    diagnostic, facet?}``; no ``how`` key is ever emitted.

The fix direction (charter, NOT implemented here): add an optional
``how: str = ""`` field to ``GateOutcome``; populate it in ``facet_failure``
(facet-specific, keyed on ``FacetViolation``) and ``at_failure`` (green-the-AT
remediation); surface it in ``_emit`` ONLY when non-empty.

CRITICAL CONSTRAINT (preserved, do NOT change): the check stays intact -- a
red AT / facet violation is STILL a FAIL (``exit_code == 1``); PASS /
NOT_APPLICABLE stay clean -- no spurious ``how``.

Driving surface (deviation from the sibling GDP-3 regression ATs, justified
below): the DOMAIN unit surface (`GateOutcome` factories) plus the CLI's own
`_emit`, NOT `main()` in-process. `main()`'s only path to a real FAIL verdict
runs through `BuildDistArtifactBuilder` + `PipTargetInstaller` -- a real
`scripts/build_dist.py` build followed by a real `pip install --target`
subprocess against a temp prefix -- constructed inline at :337-340 with no
injection seam to substitute fakes. Driving a message-shape regression AT
through an actual package build/install is exactly the too-heavy/fragile case
that justifies falling back to the domain surface. This AT instead drives the
two REAL surfaces the defect actually lives in: (1) `GateOutcome`'s
FAIL/PASS/NOT_APPLICABLE factories -- the domain surface the `how` field is
added to -- and (2) `_emit` itself, the exact function the charter names as
building the JSON payload with no `how` key, capturing its real `print()`
output via `capsys` -- the identical code path `main()` calls at :349.
"""

from __future__ import annotations

import json

import pytest

from des.cli.walking_skeleton_gate import _emit
from des.domain.gate_outcome import FacetViolation, GateOutcome, GateTier


def _emitted_payload(
    outcome: GateOutcome, capsys: pytest.CaptureFixture[str]
) -> dict[str, object]:
    """Drive the REAL `_emit` (the exact function `main()` calls at :349),
    capturing its single-line JSON stdout payload via `capsys`.
    """
    _emit(outcome)
    stdout = capsys.readouterr().out
    lines = [ln for ln in stdout.splitlines() if ln.strip().startswith("{")]
    assert lines, f"expected a JSON payload line on stdout, got: {stdout!r}"
    payload: dict[str, object] = json.loads(lines[-1])
    return payload


_FACET_HOW_TOKENS: tuple[tuple[FacetViolation, str], ...] = (
    (FacetViolation.ENTRY_POINT_ABSENT, "staged prefix"),
    (FacetViolation.NO_SUBPROCESS, "subprocess"),
    (FacetViolation.RESOLVED_OUTSIDE, "installed"),
    (FacetViolation.NO_TRANSFORM, "transform"),
)


# ===========================================================================
# POSITIVE ATs -- active-RED today
# ===========================================================================


@pytest.mark.parametrize(
    "facet,expected_token",
    _FACET_HOW_TOKENS,
    ids=[facet.value for facet, _ in _FACET_HOW_TOKENS],
)
def test_facet_failure_names_a_facet_specific_how(
    facet: FacetViolation, expected_token: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """A D6 facet violation is STILL a FAIL (unchanged, floor intact) -- and
    the outcome must ALSO carry a `how` naming a remediation matched to the
    violated facet. Today `GateOutcome` has no `how` field:
    `getattr(outcome, "how", "")` is ``""`` for every facet -- RED for the
    right reason (a semantic assertion on the absent `how`, not an
    AttributeError crash).
    """
    outcome = GateOutcome.facet_failure(GateTier.T1, facet, "fixture diagnostic")

    # Floor intact -- already true today, must stay true after the fix.
    assert outcome.verdict.value == "fail"
    assert outcome.exit_code == 1
    assert outcome.facet_violation is facet

    # HOW -- MISSING today (GateOutcome carries no `how` field/attribute).
    how = getattr(outcome, "how", "")
    assert how, (
        f"a facet_failure({facet.value}) outcome must carry a `how` field "
        f"naming a remediation matched to the violated facet -- got how={how!r}"
    )
    assert expected_token in how.lower(), (
        f"the `how` for facet {facet.value} must name '{expected_token}' -- "
        f"got how={how!r}"
    )

    payload = _emitted_payload(outcome, capsys)
    assert payload.get("verdict") == "fail", payload
    assert payload.get("facet") == facet.value, payload
    emitted_how = payload.get("how")
    assert emitted_how, (
        f"the emitted JSON verdict for a facet_failure({facet.value}) must "
        f"carry a `how` key -- payload carries none: {payload!r}"
    )
    assert expected_token in str(emitted_how).lower(), payload


def test_at_failure_names_a_green_the_at_how(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A red `@walking-skeleton` AT is STILL a FAIL (unchanged, floor intact)
    -- and the outcome must ALSO carry a `how` instructing to green the AT at
    its tier of record. Today `GateOutcome.at_failure` sets no `how` -- RED
    for the right reason.
    """
    outcome = GateOutcome.at_failure(
        GateTier.T1, "the walking-skeleton acceptance test ran red"
    )

    assert outcome.verdict.value == "fail"
    assert outcome.exit_code == 1
    assert outcome.facet_violation is None

    how = getattr(outcome, "how", "")
    assert how, (
        "an at_failure outcome must carry a `how` field instructing to green "
        f"the @walking-skeleton AT at its tier of record -- got how={how!r}"
    )
    assert "green" in how.lower() and (
        "walking-skeleton" in how.lower() or "walking skeleton" in how.lower()
    ), (
        "the `how` for at_failure must name greening the walking-skeleton AT "
        f"-- got how={how!r}"
    )

    payload = _emitted_payload(outcome, capsys)
    assert payload.get("verdict") == "fail", payload
    assert "facet" not in payload, payload
    emitted_how = payload.get("how")
    assert emitted_how, (
        "the emitted JSON verdict for an at_failure must carry a `how` key "
        f"-- payload carries none: {payload!r}"
    )


# ===========================================================================
# NEGATIVE ATs -- control, green today AND after the fix
# ===========================================================================


@pytest.mark.negative_at
def test_passed_verdict_never_carries_a_how(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A PASS outcome carries NO `how` -- the remediation belongs only to the
    FAIL path, never leaking into a clean verdict. Must stay green both
    BEFORE and AFTER the fix.
    """
    outcome = GateOutcome.passed(GateTier.T1)

    assert outcome.verdict.value == "pass"
    assert outcome.exit_code == 0
    assert not getattr(outcome, "how", ""), (
        "a passed() outcome must never carry a `how`: got "
        f"how={getattr(outcome, 'how', '')!r}"
    )

    payload = _emitted_payload(outcome, capsys)
    assert payload.get("verdict") == "pass", payload
    assert "how" not in payload, (
        f"a PASS verdict must never carry a spurious `how` field: {payload!r}"
    )


@pytest.mark.negative_at
def test_not_applicable_verdict_never_carries_a_how(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A NOT_APPLICABLE outcome carries NO `how` -- same clean-path guarantee
    as PASS. Must stay green both BEFORE and AFTER the fix.
    """
    outcome = GateOutcome.not_applicable("justified non-installable feature")

    assert outcome.verdict.value == "not_applicable"
    assert outcome.exit_code == 0
    assert not getattr(outcome, "how", ""), (
        "a not_applicable() outcome must never carry a `how`: got "
        f"how={getattr(outcome, 'how', '')!r}"
    )

    payload = _emitted_payload(outcome, capsys)
    assert payload.get("verdict") == "not_applicable", payload
    assert "how" not in payload, (
        f"a NOT_APPLICABLE verdict must never carry a spurious `how` field: {payload!r}"
    )
