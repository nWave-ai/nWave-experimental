"""Wave-active domain value objects (slice-04, nwave-flow-v2-enforcement).

SHAPE per DESIGN feature-delta § "Wave: DESIGN / [REF] slice-04 code-design
(wave-active anchor)". Pure data; no I/O. The closed wave vocabulary (I1) is the
SSOT for "a member of the nWave waves", shared by the writer, the reader, and the
``WaveActiveRecord`` construction invariant.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


# The closed nWave wave vocabulary (I1). A record's ``wave`` MUST be a member;
# anything else is non-representable garbage. Shared SSOT for construction-time
# validation (here) and the reader's degrade-LOUD contract.
WAVE_VOCABULARY: frozenset[str] = frozenset(
    {"discuss", "design", "devops", "distill", "deliver", "feature-end"}
)


class WaveProvenance(str, Enum):
    """Closed set -- how a wave-active record came to exist (non-representable garbage).

    ``(str, Enum)`` is the repo-conformant, mypy-py3.10-compatible spelling of the
    design's ``StrEnum`` (mirrors ``ATDDPurePhase(str, Enum)``): the contract is
    the closed two-member set with lowercase string ``.value`` (``"command"`` /
    ``"inferred"``) -- identical observable behavior to ``StrEnum``.
    """

    COMMAND = "command"  # written from the literal /nw-<wave> at submission (strand-1)
    INFERRED = "inferred"  # written by the PreToolUse fallback (strand-2)


@dataclass(frozen=True)
class WaveActiveRecord:
    """The wave-active state value.

    INVARIANT I1: ``wave`` in the closed nWave wave vocabulary (enforced at
    construction -> raises ``ValueError``). INVARIANT I3: COMMAND provenance
    dominates INFERRED (a writer-side rule, enforced by ``WaveActiveWriter.arm``).
    INVARIANT I4 (slice-07c, floor v1.1): ``entry_pending=True`` is written ONLY
    by the COMMAND arm (the anchor, which deterministically saw the ``/nw-<wave>``
    literal -- F3). The gate side only READS and (post-allow) CLEARS it. On the
    floor JSON the key is OPTIONAL: omitted <=> False (mirrors ``scope``).
    INVARIANT I5 (RC3, floor v1.2, Ale 2026-06-26): ``armed_at`` is the Unix
    timestamp an INFERRED floor was armed -- written ONLY by ``arm_inferred``
    (the fallback strand). A COMMAND floor leaves it ``None`` (an explicit
    /nw-<wave> wave never expires). On the floor JSON the key is OPTIONAL:
    omitted <=> None (mirrors ``scope``). It feeds ``is_inferred_floor_expired``
    -- the read-side TTL that garbage-collects a stale INFERRED guess.
    """

    wave: str
    provenance: WaveProvenance
    scope: str | None = None
    entry_pending: bool = False
    armed_at: float | None = None

    def __post_init__(self) -> None:
        if self.wave not in WAVE_VOCABULARY:
            raise ValueError(
                f"wave={self.wave!r} is not a member of the closed nWave wave "
                f"vocabulary {sorted(WAVE_VOCABULARY)!r} (invariant I1)"
            )


@dataclass(frozen=True)
class NoWaveActive:
    """Explicit "no wave armed" -- the S1 floor, NOT an error and NOT a read failure.

    Distinct from ``committed_scope_port.Indeterminate`` (a degrade-LOUD read
    failure). ``NoWaveActive`` is the normal absent-state value.
    """


# RC3 (Ale 2026-06-26, experimental): an INFERRED floor that has sat armed past
# this TTL is a STALE GUESS -- garbage-collected on read so it stops blocking
# later dispatches. 30 minutes: long enough to never cut a real in-progress
# inferred wave, short enough to clear the cross-session / crashed / abandoned
# leftovers without a manual ``des wave-clear``.
INFERRED_FLOOR_TTL_SECONDS: float = 1800.0


def is_inferred_floor_expired(record: WaveActiveRecord, now: float) -> bool:
    """True iff an INFERRED floor has aged past the TTL (read-side GC).

    Removal-of-gating only, never addition: a COMMAND floor (an explicit
    /nw-<wave>) NEVER expires, and an INFERRED floor with no ``armed_at`` stamp
    (a legacy floor written before floor v1.2) has no TTL basis and is treated
    as live -- the TTL can only retire a guess it can prove is stale, never
    one it is unsure about.
    """
    if record.provenance is not WaveProvenance.INFERRED:
        return False
    if record.armed_at is None:
        return False
    return (now - record.armed_at) > INFERRED_FLOOR_TTL_SECONDS


def describe_wave_floor(
    record: WaveActiveRecord,
    *,
    floor_file: Path,
    project_root: Path,
    now: float,
) -> str:
    """Describe an armed floor so a reader can JUDGE and LOCATE it (pure, no I/O).

    SSOT for "what does this floor mean" -- shared by the REFUSAL path
    (``PreToolUseService._describe_wave_floor``, which re-reads the record on
    the rare block path) and the ADVISORY path (``des dispatch``'s proactive
    heads-up, defect-2 docs/mikado/EXECUTION-SSOT-des-optimization.md), so the
    two surfaces describe the SAME floor identically instead of drifting into
    two hand-maintained prose copies.

    Names the floor file's absolute PATH and the resolved project ROOT (the
    gate/generator already read both to reach its decision -- restating them
    costs nothing and saves the reader an investigation, defect-3), plus --
    for an INFERRED floor -- the CONCRETE signal it was deduced from
    (``arm_inferred`` is its only writer: a wave-declaring dispatch's
    ``<!-- DES-WAVE: <wave> -->`` marker landing on an empty floor). "inferred"
    alone is a label, not an antecedent.
    """
    parts = [
        f"wave '{record.wave}', provenance {record.provenance.value}",
        f"floor file: {floor_file}",
        f"project root: {project_root}",
    ]
    if record.provenance is WaveProvenance.INFERRED:
        parts.append(
            "inferred means: no dispatch DECLARED this wave -- a prior "
            f"dispatch's <!-- DES-WAVE: {record.wave} --> marker landed on an "
            "empty floor and arm_inferred armed it by itself (the fallback "
            "strand, the only writer of INFERRED provenance)"
        )
    if record.armed_at is None:
        parts.append("armed with NO timestamp, so its age cannot be checked")
    else:
        age = now - record.armed_at
        parts.append(f"armed {age / 60:.1f} min ago")
        if record.provenance is WaveProvenance.INFERRED:
            remaining = INFERRED_FLOOR_TTL_SECONDS - age
            parts.append(
                "an INFERRED floor expires by itself after "
                f"{INFERRED_FLOOR_TTL_SECONDS / 60:.0f} min "
                + (
                    f"-- {remaining / 60:.1f} min remain, so WAITING clears it "
                    "without disarming anything"
                    if remaining > 0
                    else "-- it is already past that, so it is genuinely stale"
                )
            )
    return "; ".join(parts) + "."
