"""Regression (GDP-3): ``_carpaccio_reason`` must surface the gate's rich
what/why/how, not the bare event name.

Charter: ``docs/product/expectations/fix-gate-g-self-explains/`` sibling defect
-- same GDP-3 class, different call site.

Found in ``src/des/adapters/drivers/hooks/carpaccio_intercept.py``
``_carpaccio_reason(stdout)`` (line ~1168):

    reason = str(payload.get("event") or payload.get("error") or stdout.strip())

The gate CLI ALWAYS emits a bare ``event`` field (e.g.
``"ATReviewGateRejected"``), so the ``or`` short-circuits on ``event`` and the
rich ``error`` field (the self-explaining WHAT + "To fix: ..." HOW) and the
``instruction`` field are DROPPED every time, for every rejection. This
truncates the what/why/how at the exact reactive moment an Agent dispatch is
blocked by the hook -- a systemic defect: both the carpaccio AT-review gate
(``carpaccio_intercept.py`` line ~1089) and the wave-dispatch gate (line
~1064) route their block ``reason=`` through this same function.

The fix (crafter's job, NOT this test's): prefer ``error``/``instruction``
over the bare ``event``, mirroring what ``_readiness_reason`` (same module,
line ~1182) already does for the sibling readiness gate -- while still
degrading gracefully (unparseable / non-dict / missing rich fields -> fall
back to stdout or the bare event), never raising.

Driving surface: the function under test IS the composition-root's reason-
extraction seam (Layer 1 unit call on the seam itself is the correct level
here -- there is no higher driving port for a pure string-transform helper
than calling it directly; the gates that CONSUME it are exercised end-to-end
in the sibling suites ``test_carpaccio_at_review_rejection_self_explains_how.py``
and ``test_gate_g_verdict_self_explains_how_and_human_surface.py``).
"""

from __future__ import annotations

import json

import pytest

from des.adapters.drivers.hooks.carpaccio_intercept import _carpaccio_reason


_RICH_ERROR = (
    "AT-review gate rejected slice slice-01: no-scenarios-for-slice -- "
    "searched for a '.feature' file tagged '@feature-widget-checkout'. "
    "To fix: add/author a '.feature' file carrying the file-level tag "
    "'@feature-widget-checkout' with a scenario tagged @slice-01."
)
_RICH_INSTRUCTION = (
    "add/author a '.feature' file tagged '@feature-widget-checkout' with a "
    "scenario tagged @slice-01"
)
_REALISTIC_GATE_STDOUT = json.dumps(
    {
        "error": _RICH_ERROR,
        "event": "ATReviewGateRejected",
        "instruction": _RICH_INSTRUCTION,
        "reason": "no-scenarios-for-slice",
    }
)


def test_carpaccio_reason_surfaces_the_to_fix_how_not_just_the_bare_event() -> None:
    """POSITIVE AT (active-RED today, the bug): given a realistic gate JSON
    payload carrying BOTH the bare ``event`` and the rich ``error`` (which
    contains the actionable "To fix: ..." HOW) plus ``instruction``, the
    returned reason must CONTAIN the actionable HOW substring -- not merely
    the bare event name.

    FAILS today: current code returns exactly ``"ATReviewGateRejected"``,
    which contains neither "To fix" nor the instruction text -- a semantic
    AssertionError, not an import/collection error.
    """
    reason = _carpaccio_reason(_REALISTIC_GATE_STDOUT)

    assert "To fix" in reason or _RICH_INSTRUCTION in reason, (
        "the carpaccio reason must surface the gate's actionable HOW (the "
        "'error' field's \"To fix: ...\" clause and/or the 'instruction' "
        f"field) -- got the bare event name only: {reason!r}"
    )


def test_carpaccio_reason_carries_the_full_rich_content_alongside_identification() -> (
    None
):
    """POSITIVE AT: the returned reason must still IDENTIFY the failure (it
    may include the event name too) -- non-empty, and containing the
    error/instruction substance. Does NOT forbid the event name; requires the
    rich content ALSO be present.
    """
    reason = _carpaccio_reason(_REALISTIC_GATE_STDOUT)

    assert reason, "the carpaccio reason must be non-empty"
    assert _RICH_ERROR in reason or _RICH_INSTRUCTION in reason, (
        "the carpaccio reason must carry the rich 'error'/'instruction' "
        f"substance, not just an identifying token -- got: {reason!r}"
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "unparseable_stdout",
    [
        "boom not json",
        "",
        "   ",
        "{not: valid, json}",
    ],
)
def test_carpaccio_reason_does_not_raise_on_unparseable_stdout(
    unparseable_stdout: str,
) -> None:
    """NEGATIVE AT (degrade-loud, must stay green NOW and after the fix):
    unparseable / non-JSON stdout must never raise, and must return a
    non-empty fallback (the stripped stdout, or a sane default when stdout is
    itself empty/whitespace)."""
    reason = _carpaccio_reason(unparseable_stdout)

    assert isinstance(reason, str)
    assert reason, "must fall back to a non-empty default, never an empty string"


@pytest.mark.negative_at
def test_carpaccio_reason_falls_back_gracefully_when_only_event_is_present() -> None:
    """NEGATIVE AT (control -- graceful fallback path stays witnessed): a
    dict payload carrying ONLY ``event`` (no ``error``/``instruction``) still
    returns the event name -- the fallback path must not raise or produce an
    empty string when the rich fields are genuinely absent."""
    stdout = json.dumps({"event": "SomeBareEvent"})

    reason = _carpaccio_reason(stdout)

    assert reason == "SomeBareEvent"
