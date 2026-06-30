"""Domain types for the algebra-projections-enforced slice-04 acceptance slice.

DISCUSS slice-04 ("the maintainer sees the coherence-hook fire on DISTILL and
DELIVER prose, not only DISCUSS") + DESIGN Point 5 (the 4 prose loci + the 4
`_MIGRATED` rows) + Reuse Analysis row `_MIGRATED` (Mandate-12 criterion 1).

Every domain noun used in the Gherkin is expressed once here as a typed enum or
NewType. Step bodies and the composition service consume these typed parameters —
no raw ``str`` where a domain enum exists, no control flow in step bodies.

slice-04 reuses the §17 ``GateVerdict`` closed-token contract verbatim — the
coherence gate emits the SAME five-token verdict envelope every other §17 producer
emits. The slice-specific data is (a) the set of wave prose loci the hook must
cover and (b) the prose-mutation shapes the error paths arm.
"""

from __future__ import annotations

from enum import Enum


__all__ = [
    "COHERENCE_VERDICT_BY_PHRASE",
    "MIGRATED_PROSE_LOCI",
    "PROSE_ARMING_BY_PHRASE",
    "CoherenceVerdict",
    "MigratedWave",
    "ProseLocus",
    "ProseMutation",
]


# -- the §17 GateVerdict closed token set the coherence gate emits ----------------
# Reused verbatim (SSOT: src/des/cli/verify_wave_contract_coherence.py GateVerdict).
# slice-04 asserts on `pass` (the migrated prose is coherent) and `fail` (a mutated
# pointer is drift). The gate also emits `indeterminate` on an unreadable registry;
# slice-04 does not arm that (it is slice-05's fail-closed boundary).
class CoherenceVerdict(str, Enum):
    """The closed verdict token the ``verify-wave-contract-coherence`` gate returns."""

    PASS = "pass"
    FAIL = "fail"
    INDETERMINATE = "indeterminate"


# -- the migrated waves slice-04 extends the hook to cover -----------------------
class MigratedWave(str, Enum):
    """A wave whose prose loci the coherence-hook ``_MIGRATED`` tuple must cover.

    DISCUSS is the slice-02 worked example (already in ``_MIGRATED``). slice-04 adds
    DISTILL + DELIVER. Each migrated wave contributes TWO prose loci (a task locus
    and a skill locus), mirroring the DISCUSS 2-locus pattern.
    """

    DISCUSS = "discuss"
    DISTILL = "distill"
    DELIVER = "deliver"


# -- the four prose loci slice-04 wires the pointers into ------------------------
# (wave, repo-relative path) — the exact rows DESIGN Point 5 enumerates for the
# ``_MIGRATED`` extension. DISCUSS rows are the slice-02 baseline (already present);
# the DISTILL + DELIVER rows are slice-04's net-new additions. The hook AT asserts
# the hook covers EXACTLY these (no distill/deliver locus is silently uncovered).
MIGRATED_PROSE_LOCI: tuple[tuple[MigratedWave, str], ...] = (
    (MigratedWave.DISCUSS, "nWave/tasks/nw/discuss.md"),
    (MigratedWave.DISCUSS, "nWave/skills/nw-discuss/SKILL.md"),
    (MigratedWave.DISTILL, "nWave/tasks/nw/distill.md"),
    (MigratedWave.DISTILL, "nWave/skills/nw-distill/SKILL.md"),
    (MigratedWave.DELIVER, "nWave/tasks/nw/deliver.md"),
    (MigratedWave.DELIVER, "nWave/skills/nw-deliver/SKILL.md"),
)

# The four NET-NEW slice-04 loci (the distill + deliver subset of MIGRATED_PROSE_LOCI).
SLICE_04_NEW_LOCI: tuple[tuple[MigratedWave, str], ...] = tuple(
    row for row in MIGRATED_PROSE_LOCI if row[0] is not MigratedWave.DISCUSS
)


class ProseLocus(str, Enum):
    """A single wave-prose file the coherence gate is driven against (typed lookup)."""

    DISTILL_TASK = "nWave/tasks/nw/distill.md"
    DISTILL_SKILL = "nWave/skills/nw-distill/SKILL.md"
    DELIVER_TASK = "nWave/tasks/nw/deliver.md"
    DELIVER_SKILL = "nWave/skills/nw-deliver/SKILL.md"

    @property
    def wave(self) -> MigratedWave:
        """The wave this locus belongs to (distill or deliver)."""
        return MigratedWave.DISTILL if "distill" in self.value else MigratedWave.DELIVER


class ProseMutation(str, Enum):
    """How a scenario presents the wave prose to the gate.

    PRISTINE -- the prose exactly as the real repo carries it. This is the only
                presentation slice-04 arms: slice-04 is a PURE coverage EXTENSION,
                so the happy path drives the REAL distill/deliver locus (active-RED
                until DELIVER adds the pointer + scrubs the bare gate_ids). The
                generic gate invariant "a perturbed pointer -> fail" is already
                green at HEAD and is NOT this slice's scope, so no mutation
                presentation is armed here.
    """

    PRISTINE = "pristine"


# -- Gherkin-phrase -> typed-value lookups (Mandate-12 criterion 3) --------------
# Each step body is a single typed lookup + a single composition call, no branching.
# The Given uses ONE full-phrase placeholder (the whole "<wave> wave prose ..."
# clause) mapping to a (wave, mutation) pair, so a single typed lookup arms both —
# pytest-bdd's parsers.parse cannot split two greedy placeholders unambiguously.

PROSE_ARMING_BY_PHRASE: dict[str, tuple[MigratedWave, ProseMutation]] = {
    "the distill wave prose as the repository carries it": (
        MigratedWave.DISTILL,
        ProseMutation.PRISTINE,
    ),
    "the deliver wave prose as the repository carries it": (
        MigratedWave.DELIVER,
        ProseMutation.PRISTINE,
    ),
}

COHERENCE_VERDICT_BY_PHRASE: dict[str, CoherenceVerdict] = {
    "clears the coherence check": CoherenceVerdict.PASS,
}
