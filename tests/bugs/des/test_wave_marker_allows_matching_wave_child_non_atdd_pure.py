"""Regression AT -- WAVE_MARKER_BYPASS wrongly denies a matching-wave child on a
non-atdd_pure wave floor (S2 branch, ``PreToolUseService._evaluate``/``validate``).

RCA (gate-core): ``src/des/application/pre_tool_use_service.py`` lines ~184-198
route ONLY atdd_pure dispatches through ``classify_atdd_pure_dispatch`` before the
classic wave-aware hinge (S2, ~206-241). For a NON-atdd_pure active wave (devops /
distill / design / discuss), an in-wave CHILD carrying
``<!-- DES-WAVE: <wave> -->`` (matching the active wave -- a partial-context
marker per ``carries_partial_wave_context``) is DENIED as ``WAVE_MARKER_BYPASS``,
demanding a ``DES-VALIDATION`` marker no producer generates for this shape (``des
dispatch`` supports ``--mode atdd_pure`` only; the wave-entry parent itself never
carried ``DES-VALIDATION``, only ``DES-WAVE``). The gate's own recovery ("copy
DES-VALIDATION from the parent") is impossible to satisfy. A child DECLARING its
OWN active wave is the opposite of a bypass -- ``DES-WAVE`` only ARMS enforcement
(never authorizes past it), so a matching declaration should be honoured, not
denied.

Fixed behaviour under test: an in-wave, non-entering child whose
``<!-- DES-WAVE: <wave> -->`` marker MATCHES the active non-atdd_pure wave is
ALLOWED. A MISMATCHED wave declaration, or a markerless-but-partial dispatch,
stays DENIED (the real bypass class) -- scenarios 1 vs 3 are the mechanical
discriminator: matching-wave allowed, mismatched-wave denied. The atdd_pure
dispatch path (routed earlier, before S2) is asserted unchanged.

Driving surface (Mandate-13, Layer-3 composition): the REAL
``des.application.pre_tool_use_service.PreToolUseService`` wired with the real
``DesMarkerParser`` + the real filesystem ``WaveActiveFilesystemStore`` (the exact
composition ``tests/des/acceptance/wave_dispatch_exemption_ssot/steps/
composition.py::_drive_pre_tool_use_at3`` already drives AT-3 through) -- no
decomposed private-predicate unit test, no direct-domain testing (Mandate-16).
The floor is seeded on the real filesystem via ``WaveActiveFilesystemStore.arm``;
the service reads it back via ``cwd()``-rooted ``.read()``, exactly as production.

Universe: ``HookDecision.action`` ("allow"|"block") + ``HookDecision.reason`` +
``HookDecision.recovery_suggestions`` -- the port-exposed observable surface, no
internal regex/dataclass field asserted.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driven_ports.wave_active_store import WaveActiveReader
from des.ports.driver_ports.pre_tool_use_port import (
    HookDecision,
    PreToolUseInput,
)


def _arm_floor(root: Path, wave: str, *, entering: bool) -> None:
    """Seed the real ``.nwave/wave-active/active.json`` floor for ``wave``."""
    store: WaveActiveReader = WaveActiveFilesystemStore()
    assert isinstance(store, WaveActiveFilesystemStore)
    store.arm(
        root,
        WaveActiveRecord(
            wave=wave,
            provenance=WaveProvenance.COMMAND,
            entry_pending=entering,
        ),
    )


def _dispatch(
    root: Path, prompt: str, *, subagent_type: str = "child", wave_entering: bool
) -> HookDecision:
    """Drive the REAL ``PreToolUseService`` over the seeded floor (cwd-rooted read,
    mirrors production + the wave_dispatch_exemption_ssot AT-3 composition)."""
    service = PreToolUseService(
        marker_parser=DesMarkerParser(),
        audit_writer=NullAuditLogWriter(),
        time_provider=SystemTimeProvider(),
        wave_active_reader=WaveActiveFilesystemStore(),
    )
    prev_cwd = Path.cwd()
    prev_env = os.environ.get("DES_PROJECT_DIR")
    try:
        os.chdir(root)
        # Mirror `root` into DES_PROJECT_DIR so `resolve_nwave_root()` (which the
        # service's `_read_active_wave()` now calls) resolves the SAME root this
        # helper armed the floor at, not the per-test isolation root the autouse
        # `_isolate_nwave_root` fixture set (tests/conftest.py).
        os.environ["DES_PROJECT_DIR"] = str(root)
        return service.validate(
            PreToolUseInput(
                prompt=prompt,
                subagent_type=subagent_type,
                wave_entering=wave_entering,
            )
        )
    finally:
        os.chdir(prev_cwd)
        if prev_env is None:
            os.environ.pop("DES_PROJECT_DIR", None)
        else:
            os.environ["DES_PROJECT_DIR"] = prev_env


# ---------------------------------------------------------------------------
# Scenario 1 -- matching DES-WAVE child on a non-atdd_pure wave is ALLOWED.
# TODAY (defect): denied WAVE_MARKER_BYPASS. This is the assertion expected
# to fail (RED) until the S2 branch is fixed to key on wave-MATCH.
# ---------------------------------------------------------------------------


def test_matching_devops_wave_marker_child_is_allowed(tmp_path: Path) -> None:
    _arm_floor(tmp_path, "devops", entering=False)
    prompt = "<!-- DES-WAVE: devops -->\nwork the devops wave"

    decision = _dispatch(tmp_path, prompt, wave_entering=False)

    assert decision.action == "allow", (
        "a child dispatch declaring the SAME wave as the active non-atdd_pure "
        "floor ('devops') must be ALLOWED -- DES-WAVE only ARMS enforcement, "
        "it is the opposite of a bypass signal. Observed: "
        f"action={decision.action!r} reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 2 (negative) -- markerless-but-partial child (a DES marker subset,
# no wave declaration) on a non-atdd_pure wave stays DENIED. Guards against
# opening a hole: the fix must key on wave-MATCH, not blanket-allow any
# partial-context dispatch.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_markerless_partial_context_child_still_denied(tmp_path: Path) -> None:
    _arm_floor(tmp_path, "devops", entering=False)
    # A DES marker SUBSET (DES-STEP-ID) with NO DES-WAVE declaration and NO
    # DES-VALIDATION -- carries_partial_wave_context=True via has_des_markers,
    # declared_wave=None.
    prompt = "<!-- DES-STEP-ID: 01-01 -->\nwork on something"

    decision = _dispatch(tmp_path, prompt, wave_entering=False)

    assert decision.action == "block", (
        "a child carrying a DES marker SUBSET with NO wave declaration and NO "
        "DES-VALIDATION is a genuine wave bypass and must stay DENIED. Observed: "
        f"action={decision.action!r} reason={decision.reason!r}"
    )
    assert "WAVE_MARKER_BYPASS" in (decision.reason or ""), (
        f"expected the WAVE_MARKER_BYPASS reason; observed reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 3 (negative, the mechanical discriminator) -- a MISMATCHED
# DES-WAVE declaration (child declares 'distill' while the floor is 'devops')
# stays DENIED. Matching-wave allowed (scenario 1) vs mismatched-wave denied
# (scenario 3) is the wave-spoof guard the fix must preserve.
# ---------------------------------------------------------------------------


@pytest.mark.negative_at
def test_mismatched_wave_marker_child_still_denied(tmp_path: Path) -> None:
    _arm_floor(tmp_path, "devops", entering=False)
    prompt = "<!-- DES-WAVE: distill -->\nwork on something else entirely"

    decision = _dispatch(tmp_path, prompt, wave_entering=False)

    assert decision.action == "block", (
        "a child declaring a DIFFERENT wave ('distill') than the active floor "
        "('devops') is a wave-spoof and must stay DENIED, never allowed by the "
        "fix that permits a MATCHING wave declaration. Observed: "
        f"action={decision.action!r} reason={decision.reason!r}"
    )
    assert "WAVE_MARKER_BYPASS" in (decision.reason or ""), (
        f"expected the WAVE_MARKER_BYPASS reason; observed reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 4 (negative) -- the atdd_pure dispatch path is unchanged: it
# is classified and routed BEFORE the S2 branch (line ~194-198) regardless
# of the active wave floor, so a valid atdd_pure marker set is allowed exactly
# as today, independent of the fix.
# ---------------------------------------------------------------------------


def test_atdd_pure_dispatch_still_routes_through_atdd_pure_validation(
    tmp_path: Path,
) -> None:
    _arm_floor(tmp_path, "devops", entering=False)
    prompt = (
        "<!-- DES-MODE: atdd_pure -->\n"
        "<!-- DES-PHASE: A_GREEN -->\n"
        "<!-- DES-SLICE: slice-01 -->\n"
        "work the slice"
    )

    decision = _dispatch(tmp_path, prompt, wave_entering=False)

    # No atdd_pure_validator wired here (mirrors production callers that omit
    # it) -- a 'valid' atdd_pure marker set allows immediately per
    # ``_validate_atdd_pure_dispatch``, UNTOUCHED by the S2 fix because
    # classification happens earlier and short-circuits before S2 is reached.
    assert decision.action == "allow", (
        "a valid atdd_pure dispatch (DES-MODE:atdd_pure + coherent "
        "DES-PHASE/DES-SLICE) must still route through atdd_pure validation and "
        "be allowed, unaffected by the S2 classic-wave-hinge fix. Observed: "
        f"action={decision.action!r} reason={decision.reason!r}"
    )


# ---------------------------------------------------------------------------
# Scenario 5 (negative) -- when a dispatch IS denied for a non-atdd_pure
# wave, the recovery text names an ACHIEVABLE remediation: carrying the
# ``<!-- DES-WAVE: <wave> -->`` marker -- never ONLY the impossible "copy
# DES-VALIDATION from the parent" (the parent itself never carries it for
# this dispatch shape).
# ---------------------------------------------------------------------------


def test_denied_dispatch_names_des_wave_marker_as_achievable_remediation(
    tmp_path: Path,
) -> None:
    _arm_floor(tmp_path, "devops", entering=False)
    prompt = "<!-- DES-STEP-ID: 01-01 -->\nwork on something"

    decision = _dispatch(tmp_path, prompt, wave_entering=False)

    assert decision.action == "block"
    recovery_text = " ".join(decision.recovery_suggestions or [])
    assert "DES-WAVE" in recovery_text, (
        "the block's recovery_suggestions must name carrying the "
        "'<!-- DES-WAVE: <wave> --> ' marker as an achievable remediation -- "
        "never ONLY the impossible 'copy DES-VALIDATION from the parent' "
        f"(the parent never carries it for this dispatch shape). Observed "
        f"recovery_suggestions={decision.recovery_suggestions!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
