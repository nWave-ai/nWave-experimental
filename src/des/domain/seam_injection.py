"""SeamInjectionPort -- the perturbation arm of the earned-verdict gate.

The seam-injection port breaks a NAMED dependency in a generated AT scaffold so
the perturbed run a verdict rests on actually took effect -- and refuses
(fail-safe) when the seam name cannot be resolved, so a seam that cannot be
named never silently leaves the real dependency in place while reporting a
perturbation that never happened.

Swap mechanism (GAP-2 resolution, DESIGN): env-driven **factory-lookup-by-name
at the seam** -- a bounded-change contract, NOT monkeypatch. The scaffold's
dependency at a seam is acquired through a single named indirection point;
``resolve_seam`` reads ``NWAVE_PERTURB`` from the environment, and when it equals
a manifest seam's ``id`` returns that seam's ``fault`` locator, else the ``real``
locator. The only mutation universe is the resolver's return value at the named
seam -- "the real dep was left untouched" is observable as "the resolver still
returns ``real``", with no interpreter-global side effect.

Seam shape (``nwave.seam_manifest.v1``): a declarative, language-neutral data
artifact co-located with the AT scaffold. It NAMES seams and their ``real`` /
``fault`` locators; it does not encode how a swap is performed. ``real`` /
``fault`` are OPAQUE locators -- meaningful only to the per-language adapter,
NEVER read by the target-blind verdict CORE.

LANGUAGE_BOUND: the ``real`` / ``fault`` locator interpretation + the
resolution-at-seam mechanism are language-specific (Python adapter #1: a dotted
locator returned by an env-driven factory lookup). The ``NWAVE_PERTURB`` channel
+ the neutral manifest declaration are language-neutral. The verdict CORE
(``des.domain.earned_verdict``) never imports this module -- target-blindness is
preserved.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


SEAM_MANIFEST_SCHEMA = "nwave.seam_manifest.v1"

# The environment channel that carries the seam id to perturb (frozen
# cross-tree contract -- the selector is the environment, uniformly across the
# CLI, the hook, and an SF sequencer).
PERTURB_ENV = "NWAVE_PERTURB"


class InjectionOutcome(str, Enum):
    """The observable outcome of one ``SeamInjectionPort.perturb`` call.

    PERTURBED -- the seam id matched a manifest seam and the seam now resolves
                 to that seam's ``fault`` locator (the swap took effect).
    ABSTAIN   -- the seam id matched no manifest seam; the port abstains
                 (reason ``no-nameable-seam``) and swaps nothing, never silently
                 reporting a perturbation that did not happen.
    """

    PERTURBED = "perturbed"
    ABSTAIN = "abstain"


class InjectionReason(str, Enum):
    """The fail-safe reason set iff the outcome is ABSTAIN."""

    NO_NAMEABLE_SEAM = "no-nameable-seam"


@dataclass(frozen=True)
class Seam:
    """One named perturbable seam declared in a ``nwave.seam_manifest.v1``.

    ``real`` / ``fault`` are OPAQUE locators interpreted only by the per-language
    adapter; the verdict CORE never reads them.
    """

    seam_id: str
    real: str
    fault: str


@dataclass(frozen=True)
class SeamManifest:
    """A parsed ``nwave.seam_manifest.v1`` -- the seams a scaffold exposes."""

    seams: tuple[Seam, ...]

    def named(self, seam_id: str) -> Seam | None:
        """Return the seam matching ``seam_id``, or ``None`` if not nameable."""
        for seam in self.seams:
            if seam.seam_id == seam_id:
                return seam
        return None


@dataclass(frozen=True)
class InjectionResult:
    """The port-exposed outcome of a perturbation (read-only of its own effect).

    ``resolved_impl`` is the OPAQUE locator the seam resolves to AFTER the call:
    the ``fault`` locator on PERTURBED, the ``real`` locator (or ``None`` when no
    seam is nameable) on ABSTAIN -- NEVER the ``fault`` locator on ABSTAIN.
    ``reason`` is set iff the outcome is ABSTAIN.
    """

    outcome: InjectionOutcome
    resolved_impl: str | None
    reason: InjectionReason | None


def resolve_seam(
    seam_id: str, manifest: SeamManifest, perturb: str | None
) -> str | None:
    """Resolve the locator the named seam binds to, given the perturb selector.

    Factory-lookup-by-name (the seam is a single named indirection point): when
    ``perturb`` selects this ``seam_id`` the seam binds to its ``fault`` locator,
    otherwise its ``real`` locator. A seam the manifest does not name binds to
    ``None`` -- the fail-safe no-nameable-seam path.
    """
    seam = manifest.named(seam_id)
    if seam is None:
        return None
    if perturb == seam.seam_id:
        return seam.fault
    return seam.real


def perturb(
    seam_id: str, manifest: SeamManifest, perturb_selector: str | None
) -> InjectionResult:
    """Perturb the named seam, or abstain fail-safe when it cannot be named.

    PERTURBED iff ``seam_id`` matches a manifest seam (the seam now resolves to
    its ``fault`` locator). ABSTAIN(no-nameable-seam) iff it matches no seam --
    the real dependency is left untouched (``resolved_impl`` is the ``real``
    locator or ``None``, never ``fault``).
    """
    resolved = resolve_seam(seam_id, manifest, perturb_selector)
    if resolved is None:
        return InjectionResult(
            outcome=InjectionOutcome.ABSTAIN,
            resolved_impl=None,
            reason=InjectionReason.NO_NAMEABLE_SEAM,
        )
    return InjectionResult(
        outcome=InjectionOutcome.PERTURBED,
        resolved_impl=resolved,
        reason=None,
    )


def manifest_from_payload(payload: dict[str, object]) -> SeamManifest:
    """Build a ``SeamManifest`` from a parsed ``nwave.seam_manifest.v1`` payload.

    Accepts both the canonical list shape (``seams: [{id, real, fault}, ...]``)
    and the slice-03 composition's stand-in mapping shape
    (``seams: {<id>: {real, fault}}``) -- the ATs read only the post-injection
    resolution, so either declaration shape yields the same nameable seams.
    """
    raw_seams = payload.get("seams", [])
    if isinstance(raw_seams, dict):
        return SeamManifest(
            seams=tuple(
                _seam_from_spec(str(seam_id), spec)
                for seam_id, spec in raw_seams.items()
                if isinstance(spec, dict)
            )
        )
    if isinstance(raw_seams, list):
        return SeamManifest(
            seams=tuple(
                _seam_from_spec(str(spec["id"]), spec)
                for spec in raw_seams
                if isinstance(spec, dict)
            )
        )
    return SeamManifest(seams=())


def _seam_from_spec(seam_id: str, spec: dict[object, object]) -> Seam:
    """Build a ``Seam`` from a manifest seam spec mapping (``real`` / ``fault``)."""
    return Seam(
        seam_id=seam_id,
        real=str(spec["real"]),
        fault=str(spec["fault"]),
    )
