# @feature-des-refactor-fixer-swarm
# @slice-03
"""Service-level non-classic routing -- des-refactor-fixer-swarm slice-03 (AT-11, D8).

@slice-03 @feature-des-refactor-fixer-swarm @driving_port
@contract-shape:pure-function.

Behavior (b) -- the PRODUCTION `PreToolUseService.validate` must RECOGNIZE a
`DES-MODE: refactor` (resp. `find`) dispatch as a fixer/finder dispatch and
allow it without any retired prompt-structure dependency.

Driving port: the real `PreToolUseService` wired through its PRODUCTION
composition (real `DesMarkerParser` + enforcement /
completeness policies, null I/O adapters) -- Pillar 3, mirrors the
`_build_gate` idiom in
`tests/des/acceptance/test_deliver_3phase_canon_gate.py`.

The preservation pair proves refactor/find remain executable while a DES
dispatch with no explicit mode remains refused.

covers: R-DES-REFACTOR-SLICE-03-SERVICE
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

from .domain_types import DispatchMode


pytestmark = pytest.mark.acceptance


class _FixedTime:
    """Minimal deterministic TimeProvider double (null I/O) -- the service only
    calls ``now_utc().isoformat()`` when writing an audit event."""

    def now_utc(self) -> datetime:
        return datetime(2026, 7, 19, 12, 0, 0, tzinfo=timezone.utc)


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


def _fixer_dispatch_prompt(mode: DispatchMode) -> str:
    """A fixer/finder-mode dispatch carrying DES-VALIDATION + DES-PROJECT-ID +
    DES-STEP-ID. ``DispatchMode.ABSENT`` omits the explicit mode for the
    preservation twin below.
    """
    lines = ["<!-- DES-VALIDATION : required -->"]
    if mode is not DispatchMode.ABSENT:
        lines.append(f"<!-- DES-MODE : {mode.value} -->")
    lines += [
        "<!-- DES-PROJECT-ID : des-refactor-fixer-swarm -->",
        "<!-- DES-STEP-ID : slice-03 -->",
        "",
        "Drain the AD-37 tech-debt item: route commit_slice.py's three",
        "raw-subprocess git call sites through the existing git_run seam.",
    ]
    return "\n".join(lines)


@pytest.mark.parametrize(
    "mode", [DispatchMode.REFACTOR, DispatchMode.FIND], ids=lambda m: m.value
)
def test_fixer_dispatch_is_recognized_without_retired_prompt_structure(
    mode: DispatchMode,
) -> None:
    """covers: R-DES-REFACTOR-SLICE-03-SERVICE

    Given a `DES-MODE: refactor` / `find` dispatch carrying its DES markers,
    When the production `PreToolUseService` validates it, Then it is ALLOWED
    without any retired prompt-structure dependency.

    CONTRACT_SHAPE: pure-function
    """
    gate = _build_gate()

    decision = gate.validate(PreToolUseInput(prompt=_fixer_dispatch_prompt(mode)))

    assert decision.action == "allow", (
        f"a DES-MODE:{mode.value} dispatch must be spine-recognized and allowed "
        "without retired prompt structure; it was blocked with reason "
        f"{decision.reason!r} (feature-delta D8 / AT-11)"
    )


def test_a_des_dispatch_without_mode_is_refused() -> None:
    """Preservation twin: only recognized modes are executable; a DES dispatch
    with no explicit mode remains refused.

    CONTRACT_SHAPE: pure-function
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_fixer_dispatch_prompt(DispatchMode.ABSENT))
    )

    assert decision.action == "block", (
        "a DES dispatch without an explicit mode must be blocked; got "
        f"{decision.action!r} ({decision.reason!r})"
    )
    assert "DISPATCH_MODE_UNRESOLVED" in (decision.reason or "")
