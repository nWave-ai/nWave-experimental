"""dormant_seam -- the pure dormant-seam detector (DESIGN D-1, Reuse R2).

slice-01 of oss-dormant-seam-gate -- THE walking-skeleton detector. A *dormant
seam* is a net-new effectful public symbol with NO resolved production call-site
(DISCUSS D4 witness contract). This module is the PURE FUNCTIONAL CORE (DDD-4 /
principle 12): ``detect(...) -> DormantSeamVerdict`` is return-only, mutates
nothing, reads no live internal, performs NO I/O and imports NO git/subprocess --
and, per ADR-TEST-002 D-A, no ``ast``. It names abstract capabilities (a symbol's
identity, the set of resolved call-site identities) the composition-root CLI
realizes; the AST walk + the delta read + the call-site resolution all live in the
imperative shell.

The binding-resolved cross-product shape REUSES the
``detect_per_plugin_capability_conformance`` pattern
(``registry_conformance.py``, DESIGN Reuse R1): the detector consumes
fully-resolved plain-data surfaces (a symbol's module-qualified identity and the
set of call-site target identities -- resolved bindings, not bare names), so an
entry-point-dispatched symbol whose binding was resolved into a call-site is NOT
flagged (slice-03), and a name-collision does NOT false-negate (slice-03) --
because the CLI hands resolved identities, not strings. slice-01 exercises only
the syntactic call-site join; the resolution precision is slice-03's concern, but
the detector's plain-data contract is already binding-resolved by construction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


# escape (b) discriminator: how an otherwise-dormant seam was honestly cleared.
# Mirrors ``SeamEscape.DORMANT_OK_MARKER`` -- recorded so a reader sees WHY a seam
# left the flagged set (never a silent suppression).
_DORMANT_OK_ESCAPE = "dormant-ok"


@dataclass(frozen=True)
class EffectfulSymbol:
    """A net-new effectful public symbol the detector evaluates (plain data).

    ``identity`` -- the symbol's module-qualified identity (a resolved binding,
    e.g. ``des.probe_dormant_module.absorb_ready_refs``), the join key against the
    call-site set. ``name`` -- the bare public symbol name reported in the warning
    (e.g. ``absorb_ready_refs``). The detector never parses either; the CLI
    supplies them already resolved.
    """

    identity: str
    name: str


@dataclass(frozen=True)
class DormantSeam:
    """A flagged dormant seam in the verdict (port-exposed observable).

    ``symbol`` -- the bare public symbol name to name in the loud warning.
    ``identity`` -- the resolved module-qualified identity, for the machine-
    readable verdict surface. ``kind`` -- the dormant-semantics token binding the
    name to the DORMANT verdict (so a warn-every-net-new-symbol gate with no
    call-site join cannot satisfy the AT's semantics check).
    """

    symbol: str
    identity: str
    kind: str = "dormant-no-call-site"


@dataclass(frozen=True)
class SeamEscapeRecord:
    """An auditable record of an otherwise-dormant seam honestly cleared (D-4).

    The never-silent contract: a ``# dormant-ok: <F-id>`` owned-residue marker
    does NOT vanish the seam, it converts it into an AUDITABLE owned residue. The
    record names BOTH the symbol identity and the owning F-id, plus ``escaped_via``
    so a reader sees WHY the seam left the flagged set -- never a silent suppression.

    ``symbol`` -- the bare public symbol name. ``identity`` -- the resolved
    module-qualified identity. ``f_id`` -- the owning residue F-id the marker
    names (free text, carried verbatim). ``escaped_via`` -- the escape kind token
    (``dormant-ok``).
    """

    symbol: str
    identity: str
    f_id: str
    escaped_via: str = _DORMANT_OK_ESCAPE


@dataclass(frozen=True)
class DormantSeamVerdict:
    """The detector's port-exposed result (DDD aggregate, frozen VO).

    ``dormant_symbols`` -- every net-new effectful symbol with no resolved
                           production call-site AND no owned-residue marker, in
                           input order (empty == clean).
    ``escapes``         -- every otherwise-dormant seam cleared by an owned-residue
                           marker, recorded with its owning F-id (escape b).
    ``flagged``         -- True iff >= 1 dormant seam was found (the recall signal).
    """

    dormant_symbols: tuple[DormantSeam, ...]
    escapes: tuple[SeamEscapeRecord, ...] = ()

    @property
    def flagged(self) -> bool:
        return bool(self.dormant_symbols)


def detect(
    net_new_symbols: Iterable[EffectfulSymbol],
    resolved_call_site_identities: Iterable[str],
    owned_residue_markers: Mapping[str, str] | None = None,
) -> DormantSeamVerdict:
    """Flag every net-new effectful symbol with no resolved production call-site.

    ``net_new_symbols`` is the feature's net-new effectful public-symbol surface
    (the CLI derived it from the changed-files delta cross AST-detected effectful
    public defs). ``resolved_call_site_identities`` is the set of symbol
    identities a production call-site (outside the symbol's own defining module
    and ``tests/**``) resolves to -- INCLUDING entry-point / registry / DI wiring
    the composition root resolved into call-sites (so an indirectly-wired symbol
    has a resolved identity here and is NOT flagged). ``owned_residue_markers``
    maps a symbol identity to the F-id of its ``# dormant-ok: <F-id>`` marker
    (escape b) -- the CLI line-scanned the def lines; the detector decides
    clear-vs-warn and emits the escape record from this plain data.

    PURE over its arguments (DDD-D2 / principle 12): a symbol is DORMANT iff its
    module-qualified ``identity`` is absent from the resolved call-site set AND it
    carries no owned-residue marker. The join is on resolved identity, never the
    bare name. An owned-residue marker on an OTHERWISE-dormant symbol (no
    call-site) clears it and is RECORDED in ``escapes`` (never-silent); a marker
    on an already-called symbol records NOTHING (it was never flagged -- a spurious
    record would be a false-positive suppression report).
    """
    called = frozenset(resolved_call_site_identities)
    markers = owned_residue_markers or {}
    dormant: list[DormantSeam] = []
    escapes: list[SeamEscapeRecord] = []
    for symbol in net_new_symbols:
        if symbol.identity in called:
            continue
        marker_f_id = markers.get(symbol.identity)
        if marker_f_id is not None:
            escapes.append(
                SeamEscapeRecord(
                    symbol=symbol.name,
                    identity=symbol.identity,
                    f_id=marker_f_id,
                )
            )
            continue
        dormant.append(DormantSeam(symbol=symbol.name, identity=symbol.identity))
    return DormantSeamVerdict(dormant_symbols=tuple(dormant), escapes=tuple(escapes))


__all__ = [
    "DormantSeam",
    "DormantSeamVerdict",
    "EffectfulSymbol",
    "SeamEscapeRecord",
    "detect",
]
