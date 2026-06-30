"""Typed domain vocabulary for fix-wave-bypass-recovery-truthful ATs (JOB-019).

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum / frozen value, so the composition
methods consume typed parameters (no raw ``str`` where an enum exists). These
types are TEST-LOCAL -- they never import production code; the ATs drive the SUT
only through composition-root driving ports (Mandate-13).

Two slices, two surfaces, one shared vocabulary:
  * slice-01 (truthful recovery) -- the REAL ``PreToolUseService.validate`` via
    the production composition root; the observable is
    ``HookDecision.recovery_suggestions`` on a WAVE_MARKER_BYPASS block.
  * slice-02 (sanctioned clear) -- the REAL ``des wave-clear`` subcommand via
    subprocess; the observables are exit code + the floor file + the audit log.
"""

from __future__ import annotations

from enum import Enum


class GateDecision(Enum):
    """The observable spine hook decision surface (allow vs block)."""

    ALLOW = "allow"
    BLOCK = "block"


# The seven literal marker keys in ``_DES_MARKER_KEY`` (the SSOT set whose
# presence sets ``has_des_markers=True``). slice-01 item-1 of the corrected
# recovery MUST reference at least one of these AND following it (a prompt
# carrying that marker) yields ``has_des_markers=True``. DES-WAVE is DELIBERATELY
# absent (Constraint 4: the wave-DECLARATION marker is NOT in the completeness
# set; the recovery must point at the REAL set, never make DES-WAVE satisfy it).
DES_MARKER_KEYS: tuple[str, ...] = (
    "DES-VALIDATION",
    "DES-MODE",
    "DES-PHASE",
    "DES-SLICE",
    "DES-PROJECT-ID",
    "DES-STEP-ID",
    "DES-PROJECT-ROOT",
)

# The literal sanctioned stale-floor clear command slice-01 item-2 MUST name (the
# OB-A=A2 decision). A bare "DES-WAVE" instruction is NOT a sanctioned-clear
# reference -- the phantom A3-class item that today loops the LLM.
SANCTIONED_CLEAR_COMMAND: str = "des wave-clear"

# The phantom the corrected recovery MUST NOT contain: an instruction that adding
# the bare wave-DECLARATION makes the dispatch wave-entering. ``wave_entering`` is
# floor-state (entry_pending), never prompt-settable -- so this is the untruthful
# (verified-impossible) action the A3-class defect proposes.
PHANTOM_WAVE_ENTERING_PHRASE: str = "wave-entering"


class FloorState(Enum):
    """The wave-active floor precondition states slice-02 drives the clear over.

    Each value steers the REAL ``WaveActiveReader.read`` down one of its three
    degrade-LOUD classifications -- the C2 state machine the clear command must
    handle (record / NoWaveActive / Indeterminate).
    """

    # A days-old `{"wave":"distill","provenance":"inferred"}` floor: a record is
    # present -> the clear removes it (exit 0, loud + audited), and the next
    # legitimate dispatch no longer sees WAVE_MARKER_BYPASS.
    STALE_INFERRED_RECORD = "STALE_INFERRED_RECORD"
    # No floor file -> NoWaveActive -> no-op SUCCESS (idempotent), still audited.
    ABSENT = "ABSENT"
    # A corrupt / unreadable floor -> Indeterminate -> degrade-LOUD: refuse,
    # exit 1, audited; NEVER a fabricated success.
    CORRUPT = "CORRUPT"


class ClearOutcome(Enum):
    """The observable exit-code contract of ``des wave-clear`` per floor state.

    The seam the AT drives ON (the operator-visible exit code the command ships),
    never a line number. Values are the literal process exit codes the DESIGN
    `des wave-clear` CLI contract table pins.
    """

    CLEARED = 0  # floor present -> removed, loud + audited
    NOOP_SUCCESS = 0  # floor absent -> idempotent no-op, audited
    INDETERMINATE = 1  # corrupt floor -> degrade-LOUD refuse, audited
    USAGE_ERROR = 2  # --reason absent -> argparse usage error, no floor touched
