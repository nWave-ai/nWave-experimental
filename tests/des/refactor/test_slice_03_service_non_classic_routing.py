# @feature-des-refactor-fixer-swarm
# @slice-03
"""Service-level non-classic routing -- des-refactor-fixer-swarm slice-03 (AT-11, D8).

@slice-03 @feature-des-refactor-fixer-swarm @driving_port
@contract-shape:pure-function.

Behavior (b) -- the PRODUCTION `PreToolUseService.validate` must RECOGNIZE a
`DES-MODE: refactor` (resp. `find`) dispatch as a fixer/finder dispatch and NOT
force it through the classic Step-5 nine-mandatory-section prompt-structure
validation a markerless-classic crafter dispatch receives (feature-delta D8:
"no per-dispatch DES-EXEMPT ... NOT forced through the classic-dispatch
completeness check").

Driving port: the real `PreToolUseService` wired through its PRODUCTION
composition (real `DesMarkerParser` + `TemplateValidator` + enforcement /
completeness policies, null I/O adapters) -- Pillar 3, mirrors the
`_build_gate` idiom in
`tests/des/acceptance/test_deliver_3phase_canon_gate.py`.

RED-not-BROKEN (no production scaffold needed here): on CURRENT code a refactor
dispatch carrying DES-VALIDATION + DES-PROJECT-ID + DES-STEP-ID but none of the
nine classic sections (a) passes marker-completeness (classic branch, both
identifiers present), (b) is NOT routed to the atdd_pure validator
(`mode != atdd_pure` -> `classify_atdd_pure_dispatch` == 'absent'), and so (c)
falls through to Step 5's classic `TemplateValidator`, which BLOCKS it for the
missing sections -- the exact "forced through the classic completeness check"
failure. The assertion pins the DESIRED post-slice outcome (ALLOW), so it fails
RED on current code for a genuine business reason (block != allow), never a
collection/import error. A_GREEN widens `validate` to recognize the two new
classifier verdicts and allow such a dispatch.

covers: R-DES-REFACTOR-SLICE-03-SERVICE
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.application.pre_tool_use_service import PreToolUseService
from des.application.validator import TemplateValidator
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
    """Production composition of the DES PreToolUse gate with null I/O adapters
    (real parser / validator / enforcement / completeness policies)."""
    return PreToolUseService(
        marker_parser=DesMarkerParser(),
        prompt_validator=TemplateValidator(),
        audit_writer=NullAuditLogWriter(),
        time_provider=_FixedTime(),
        enforcement_policy=DesEnforcementPolicy(),
        completeness_policy=MarkerCompletenessPolicy(),
    )


def _fixer_dispatch_prompt(mode: DispatchMode) -> str:
    """A fixer/finder-mode dispatch carrying DES-VALIDATION + DES-PROJECT-ID +
    DES-STEP-ID (so it clears marker completeness and REACHES Step 5) but NONE of
    the nine classic mandatory sections -- the exact shape the classic
    ``TemplateValidator`` blocks on current code.

    ``DispatchMode.ABSENT`` omits the DES-MODE line -> a markerless classic
    dispatch (the preservation twin below).
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
def test_fixer_dispatch_is_recognized_not_forced_through_classic_completeness(
    mode: DispatchMode,
) -> None:
    """covers: R-DES-REFACTOR-SLICE-03-SERVICE

    Given a `DES-MODE: refactor` / `find` dispatch carrying its DES markers but
    NONE of the nine classic mandatory sections, When the production
    `PreToolUseService` validates it, Then it is ALLOWED (spine-recognized as a
    fixer/finder dispatch) -- never blocked for lacking the classic sections a
    markerless crafter dispatch is held to.

    CONTRACT_SHAPE: pure-function
    """
    gate = _build_gate()

    decision = gate.validate(PreToolUseInput(prompt=_fixer_dispatch_prompt(mode)))

    assert decision.action == "allow", (
        f"a DES-MODE:{mode.value} dispatch must be spine-recognized and allowed "
        "without the nine classic mandatory sections; it was blocked with reason "
        f"{decision.reason!r} -- i.e. forced through the classic-dispatch "
        "completeness check (feature-delta D8 / AT-11)"
    )


def test_a_markerless_classic_dispatch_never_bypasses_the_classic_sections() -> None:
    """Preservation twin (negative oracle): a CLASSIC dispatch (no DES-MODE) that
    lacks the nine mandatory sections must STILL be blocked -- the slice-03
    widening recognizes refactor/find ONLY, it must not blanket-exempt every
    dispatch from the classic completeness check. Expected GREEN both BEFORE and
    AFTER A_GREEN (leak-guard companion to the RED pins above).

    CONTRACT_SHAPE: pure-function
    """
    gate = _build_gate()

    decision = gate.validate(
        PreToolUseInput(prompt=_fixer_dispatch_prompt(DispatchMode.ABSENT))
    )

    assert decision.action == "block", (
        "a markerless classic dispatch lacking the nine mandatory sections must "
        f"still be blocked -- the widening is refactor/find-only; got "
        f"{decision.action!r} ({decision.reason!r})"
    )
