"""Regression: refactor/find DES-MODE recognition must run BEFORE marker
completeness (bugfix-refactor-dispatch-mode-recognition-order).

RCA: ``PreToolUseService.validate``'s marker-completeness check (Step 3, keyed
off ``MarkerCompletenessPolicy``) ran BEFORE the refactor/find DES-MODE
recognition check (former Step 4c). ``MarkerCompletenessPolicy`` treats any
non-``atdd_pure`` mode as "classic" and demands ``DES-STEP-ID`` -- a marker a
refactor/find dispatch never carries (des-refactor-fixer-swarm slice-03 D8: "no
per-dispatch DES-EXEMPT hand-typed justification required"). So a
``DES-MODE: refactor`` / ``DES-MODE: find`` dispatch with no hand-typed
``DES-STEP-ID`` was refused ``DES_MARKERS_INCOMPLETE`` before the recognition
code that exists specifically to exempt it ever ran -- slice-03's entire
promised value was false.

Fix: move the refactor/find recognition check to run before the completeness
check, mirroring how atdd_pure recognition already runs earlier in the same
method.

Driving port: the real ``PreToolUseService`` wired through its PRODUCTION
composition (real ``DesMarkerParser`` + enforcement /
completeness policies, null I/O adapters) -- mirrors
``tests/des/refactor/test_slice_03_service_non_classic_routing.py``.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_enforcement_policy import DesEnforcementPolicy
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.marker_completeness_policy import MarkerCompletenessPolicy
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput


pytestmark = pytest.mark.unit


class _FixedTime:
    """Minimal deterministic TimeProvider double (null I/O) -- the service only
    calls ``now_utc().isoformat()`` when writing an audit event."""

    def now_utc(self) -> datetime:
        return datetime(2026, 7, 20, 12, 0, 0, tzinfo=timezone.utc)


def _build_gate() -> PreToolUseService:
    """Production composition with the real parser and routing policies,
    plus null audit/time adapters."""
    return PreToolUseService(
        marker_parser=DesMarkerParser(),
        audit_writer=NullAuditLogWriter(),
        time_provider=_FixedTime(),
        enforcement_policy=DesEnforcementPolicy(),
        completeness_policy=MarkerCompletenessPolicy(),
    )


def _dispatch_prompt(*, mode: str | None, step_id: str | None) -> str:
    """A dispatch prompt carrying DES-VALIDATION + DES-PROJECT-ID, an optional
    DES-MODE line, and an optional DES-STEP-ID line -- no DES-PHASE/DES-SLICE
    (a refactor/find dispatch is roadmap-free, mirrors the real `des dispatch
    --mode refactor` shape) and none of the nine classic mandatory sections.
    """
    lines = [
        "<!-- DES-VALIDATION : required -->",
        "<!-- DES-PROJECT-ID : bugfix-refactor-dispatch-mode-recognition-order -->",
    ]
    if mode is not None:
        lines.append(f"<!-- DES-MODE : {mode} -->")
    if step_id is not None:
        lines.append(f"<!-- DES-STEP-ID : {step_id} -->")
    lines += [
        "",
        "Drain the AD-37 tech-debt item.",
    ]
    return "\n".join(lines)


@pytest.mark.parametrize("mode", ["refactor", "find"])
def test_refactor_find_mode_dispatch_without_step_id_is_not_blocked_by_marker_completeness(
    mode: str,
) -> None:
    """covers: bugfix-refactor-dispatch-mode-recognition-order slice-01

    Given a `DES-MODE: refactor` / `find` dispatch with NO `DES-STEP-ID` (the
    real shape `des dispatch --mode refactor` emits -- no per-dispatch
    `DES-EXEMPT` hand-typed justification), When the production
    `PreToolUseService` validates it, Then it is ALLOWED (spine-recognized)
    rather than refused `DES_MARKERS_INCOMPLETE` for a step-id marker a
    refactor/find dispatch never carries.
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_dispatch_prompt(mode=mode, step_id=None))
    )

    assert decision.action == "allow", (
        f"a DES-MODE:{mode} dispatch with no DES-STEP-ID must be spine-"
        "recognized and allowed; it was blocked with reason "
        f"{decision.reason!r} -- i.e. the marker-completeness check ran "
        "before the refactor/find recognition check that exists to exempt it"
    )


def test_atdd_pure_mode_dispatch_without_complete_markers_still_fails_closed() -> None:
    """Control case (examiner-confirmed correct behavior, must stay unchanged):
    an atdd_pure dispatch missing its required markers (DES-PHASE / DES-SLICE)
    is still refused -- the reorder must not weaken atdd_pure enforcement.
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_dispatch_prompt(mode="atdd_pure", step_id=None))
    )

    assert decision.action == "block", (
        "an atdd_pure dispatch missing DES-PHASE/DES-SLICE must still be "
        f"blocked; got {decision.action!r} ({decision.reason!r})"
    )


def test_des_dispatch_with_no_mode_marker_is_refused_as_unresolved() -> None:
    """An otherwise complete DES dispatch without a mode terminates at the
    explicit unresolved-mode refusal, never at retired prompt validation.
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_dispatch_prompt(mode=None, step_id="slice-01"))
    )

    assert decision.action == "block", (
        "a DES dispatch with no DES-MODE must be "
        f"blocked; got {decision.action!r} ({decision.reason!r})"
    )
    assert "DISPATCH_MODE_UNRESOLVED" in (decision.reason or ""), (
        "an otherwise complete DES dispatch with no mode must terminate at the "
        "unresolved-mode refusal rather than a retired prompt validator; got "
        f"{decision.reason!r}"
    )


def test_unknown_des_mode_value_still_fails_closed_without_step_id() -> None:
    """Control case (examiner-confirmed correct behavior, must stay unchanged):
    an unrecognized DES-MODE value (neither atdd_pure/refactor/find/
    orchestrator) is not spine-recognized and still falls through to classic
    completeness enforcement, refused for missing DES-STEP-ID.
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_dispatch_prompt(mode="bogus-mode", step_id=None))
    )

    assert decision.action == "block", (
        "a dispatch with an unrecognized DES-MODE value must still be "
        f"blocked when DES-STEP-ID is missing; got {decision.action!r} "
        f"({decision.reason!r})"
    )
