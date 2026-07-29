"""Regression AT -- an INFERRED wave floor must NOT veto (widened, 2026-07-29).

RCA part 1 (Ale, 2026-07-29, first fix same day): a `deliver`-wave
sub-dispatch was refused `WAVE_MARKER_BYPASS` by a floor whose OWN
diagnostic said it armed itself (``arm_inferred``, the fallback strand, off
a stray ``<!-- DES-WAVE: deliver -->`` marker landing on an empty floor --
nobody DECLARED the wave) and was already 31.6 minutes old against its own
30-minute (``INFERRED_FLOOR_TTL_SECONDS``) TTL. The gate had already
computed the floor was stale and vetoed anyway. The first fix made ONLY
that combination (INFERRED + past its own TTL) skip the veto.

RCA part 2 (Ale, same day, measured + authorized widening): a sibling lane
measured `des wave-clear` reasons across this machine's project history --
479 unique clear events, 48 naming an INFERRED floor as the reason for
clearing, ZERO describing the floor having caught a real bypass (every one
described a self-armed or spurious floor: a completed wave's residue, an
unrelated parallel lane, the operator's own prior dispatch). The one hit
resembling a protective outcome across all 479 names the OPPOSITE
("reviewer dispatches incorrectly blocked"). Separately, the TTL-gated exit
from part 1 was itself unreliable: ``arm_inferred`` re-arms on ANY
wave-marker dispatch landing on an empty floor, so a passer-by could
restart the 30-minute clock before it ever elapsed -- "wait for the TTL"
does not reliably self-heal. Ale authorized widening the skip from
"INFERRED + expired" to "INFERRED, regardless of age" on this evidence.

``src/des/domain/wave_active.py::is_inferred_floor_expired`` still exists
and is still used by the OTHER readers of this floor (``arm_inferred``'s
re-arm check, ``dispatch.py``'s proactive advisory, ``verify_wave_
dispatch.py``'s AT-3 collision read) for their own TTL-based purposes
(re-arming, display, collision detection) -- this widening touches ONLY the
veto path in ``PreToolUseService``, which no longer consults the TTL at
all: it keys purely on ``WaveProvenance``.

Fixed behaviour under test: the S2 hinge decides on the DECLARED property
(provenance alone, GDP-8), not the wave name and not the floor's age. Four
cells:

  1. INFERRED + fresh    -> ALLOW (advisory `warning`) -- THE WIDENING.
     Previously this cell still vetoed; now provenance alone decides.
  2. INFERRED + expired  -> ALLOW (advisory `warning`) -- unchanged from
     the part-1 fix (a strict subset of cell 1's condition).
  3. COMMAND  + "expired"-> unchanged, still DENIED (a COMMAND floor never
     expires -- ``armed_at`` stays ``None``, I5 -- and is never diverted by
     provenance either: this is the regression guard against the widening
     going too far).
  4. matching DES-WAVE declaration on an INFERRED floor -> unchanged,
     ALLOWED by the pre-existing S2a branch (asserts the fix does not need
     to touch that branch; also proves S2a is still reached BEFORE the
     provenance check, since it is the same allow either way).

Driving surface (Mandate-13, Layer-3 composition): the REAL
``PreToolUseService`` wired with the real ``DesMarkerParser`` + the real
filesystem ``WaveActiveFilesystemStore`` -- mirrors
``test_wave_marker_allows_matching_wave_child_non_atdd_pure.py``'s
composition exactly (no decomposed private-predicate unit test, no
direct-domain testing, Mandate-16). The floor is seeded on the real
filesystem via ``WaveActiveFilesystemStore.arm`` with an explicit
``armed_at`` in the past, so the TTL math runs for real -- no fake clock.

Universe: ``HookDecision.action`` + ``HookDecision.reason`` +
``HookDecision.warning`` -- the port-exposed observable surface.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.driven.logging.null_audit_log_writer import NullAuditLogWriter
from des.adapters.driven.time.system_time import SystemTimeProvider
from des.application.pre_tool_use_service import PreToolUseService
from des.domain.des_marker_parser import DesMarkerParser
from des.domain.wave_active import (
    INFERRED_FLOOR_TTL_SECONDS,
    WaveActiveRecord,
    WaveProvenance,
)
from des.ports.driven_ports.wave_active_store import WaveActiveReader
from des.ports.driver_ports.pre_tool_use_port import HookDecision, PreToolUseInput
from des.ports.driver_ports.validator_port import ValidationResult, ValidatorPort


class _AllowAllValidator(ValidatorPort):
    """Trivial classic prompt validator -- never reached by the S2 collision path,
    wired only to satisfy the required constructor argument."""

    def validate_prompt(self, prompt: str) -> ValidationResult:
        return ValidationResult(errors=[], task_invocation_allowed=True)


def _arm_floor(
    root: Path,
    wave: str,
    *,
    provenance: WaveProvenance,
    armed_at: float | None,
) -> None:
    """Seed the real ``.nwave/wave-active/active.json`` floor directly."""
    store: WaveActiveReader = WaveActiveFilesystemStore()
    assert isinstance(store, WaveActiveFilesystemStore)
    store.arm(
        root,
        WaveActiveRecord(
            wave=wave,
            provenance=provenance,
            entry_pending=False,
            armed_at=armed_at,
        ),
    )


def _dispatch(root: Path, prompt: str, *, subagent_type: str = "child") -> HookDecision:
    """Drive the REAL ``PreToolUseService`` over the seeded floor (cwd-rooted read,
    mirrors production + the matching-wave-child regression test's composition)."""
    service = PreToolUseService(
        marker_parser=DesMarkerParser(),
        prompt_validator=_AllowAllValidator(),
        audit_writer=NullAuditLogWriter(),
        time_provider=SystemTimeProvider(),
        wave_active_reader=WaveActiveFilesystemStore(),
    )
    prev_cwd = Path.cwd()
    prev_env = os.environ.get("DES_PROJECT_DIR")
    try:
        os.chdir(root)
        os.environ["DES_PROJECT_DIR"] = str(root)
        return service.validate(
            PreToolUseInput(
                prompt=prompt,
                subagent_type=subagent_type,
                wave_entering=False,
            )
        )
    finally:
        os.chdir(prev_cwd)
        if prev_env is None:
            os.environ.pop("DES_PROJECT_DIR", None)
        else:
            os.environ["DES_PROJECT_DIR"] = prev_env


# A DES marker SUBSET (no DES-WAVE) -- carries_partial_wave_context=True,
# declared_wave=None. The exact shape the reported defect hit: partial
# context, no matching declaration, so S2 is reached.
_PARTIAL_CONTEXT_PROMPT = "<!-- DES-STEP-ID: 01-01 -->\nread-only tech-debt sweep"


def _assert_inferred_advisory(decision: HookDecision) -> None:
    """Shared shape check for the allow+warning cells (1 and 2)."""
    assert decision.action == "allow", (
        "an INFERRED floor must not veto, regardless of its age -- provenance "
        f"alone decides (GDP-8). Observed: action={decision.action!r} "
        f"reason={decision.reason!r}"
    )
    assert decision.warning is not None and "INFERRED" in decision.warning, (
        "the allow must carry a self-explaining warning naming the INFERRED "
        f"provenance (GDP-6, never a silent pass). Observed warning={decision.warning!r}"
    )


# ---------------------------------------------------------------------------
# Cell 1 (THE WIDENING) -- INFERRED and still WELL WITHIN its own TTL ->
# ALLOWED with an advisory warning. Before this fix this cell still vetoed.
# ---------------------------------------------------------------------------


def test_fresh_inferred_floor_no_longer_vetoes(tmp_path: Path) -> None:
    fresh_armed_at = time.time() - 60.0  # 1 min old, well inside the 30-min TTL
    _arm_floor(
        tmp_path,
        "deliver",
        provenance=WaveProvenance.INFERRED,
        armed_at=fresh_armed_at,
    )

    decision = _dispatch(tmp_path, _PARTIAL_CONTEXT_PROMPT)

    _assert_inferred_advisory(decision)


# ---------------------------------------------------------------------------
# Cell 2 -- INFERRED and past its own TTL -> unchanged, still ALLOWED.
# ---------------------------------------------------------------------------


def test_expired_inferred_floor_still_allows(tmp_path: Path) -> None:
    stale_armed_at = time.time() - INFERRED_FLOOR_TTL_SECONDS - 120.0  # 32 min old
    _arm_floor(
        tmp_path,
        "deliver",
        provenance=WaveProvenance.INFERRED,
        armed_at=stale_armed_at,
    )

    decision = _dispatch(tmp_path, _PARTIAL_CONTEXT_PROMPT)

    _assert_inferred_advisory(decision)


# ---------------------------------------------------------------------------
# Cell 3 (regression guard) -- a DECLARED (COMMAND) floor never expires
# (armed_at stays None, I5) and is never diverted by provenance -> still
# DENIED regardless of how long it has sat armed.
# ---------------------------------------------------------------------------


def test_declared_command_floor_never_expires_and_still_vetoes(tmp_path: Path) -> None:
    _arm_floor(
        tmp_path,
        "deliver",
        provenance=WaveProvenance.COMMAND,
        armed_at=None,
    )

    decision = _dispatch(tmp_path, _PARTIAL_CONTEXT_PROMPT)

    assert decision.action == "block", (
        "a DECLARED (COMMAND) floor must NEVER expire and must keep vetoing -- "
        "the widening applies ONLY to INFERRED provenance, never to a "
        f"human/anchor-declared wave. Observed: action={decision.action!r} "
        f"reason={decision.reason!r}"
    )
    assert "WAVE_MARKER_BYPASS" in (decision.reason or "")


# ---------------------------------------------------------------------------
# Cell 4 (negative) -- a matching DES-WAVE declaration on an INFERRED floor
# is still allowed by the PRE-EXISTING S2a branch, reached (and returning)
# BEFORE the provenance check below it.
# ---------------------------------------------------------------------------


def test_matching_wave_declaration_still_allowed_on_inferred_floor(
    tmp_path: Path,
) -> None:
    fresh_armed_at = time.time() - 60.0
    _arm_floor(
        tmp_path,
        "deliver",
        provenance=WaveProvenance.INFERRED,
        armed_at=fresh_armed_at,
    )
    prompt = "<!-- DES-WAVE: deliver -->\nwork the deliver wave"

    decision = _dispatch(tmp_path, prompt)

    assert decision.action == "allow"
    # S2a's own allow() carries no warning -- unlike the S2-inferred-advisory
    # branch below it. Asserting warning is None proves S2a fired FIRST and
    # returned early, rather than merely falling through to the (also-allow)
    # advisory branch, which would make this assertion pass for the wrong
    # reason.
    assert decision.warning is None, (
        "a matching DES-WAVE declaration must be allowed by S2a's plain "
        "allow() (no warning) -- a non-None warning means this fell through "
        f"to the advisory branch instead. Observed warning={decision.warning!r}"
    )
