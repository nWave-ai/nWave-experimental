"""The adapter-capability-registry SSOT (ADR-TEST-002 D-C).

slice-02 ships the FULL per-language adapter contract on top of the slice-01
SKELETON. Mirrors the ``error_codes._REGISTRY`` register-decorator pattern for
in-repo consistency.

slice-01 (shipped, MUST stay green) gave the registry its register-protocol
seam: the two capabilities the M1 rule consumes plus ``requires_capabilities``.
slice-02 (this slice) fleshes the ``Capability`` enum out to the complete
9-capability set (ADR-TEST-002 D-C) and adds the ``CapabilityRegistry`` catalog
— the ONE SSOT a methodology maintainer reads to learn EXACTLY what every
per-language AST adapter must implement, plus a mechanical conformance check
(does a given adapter implement every required capability?).

slice-12 (drift-guard self-conformance) dropped the two registered-but-unrealized
members (``string_literals_in_call`` + ``parametrize_arg_source``: no real-adapter
method, no consuming rule) so the catalog enumerates exactly the capabilities the
gates need — SSOT honesty restored (ADR-TEST-002 D-C).

The slice-01 surface (``FUNCTIONS_WITH_DECORATOR``, ``IMPORTS_IN_FUNCTION``,
``_REGISTRY``, ``requires_capabilities``) is preserved verbatim — slice-02 only
ADDS (the genericità single-checklist requirement, Ale Decision B). Per the
dispatch contract: the registry DECLARES the full 9-capability surface; the
Python reference adapter need only implement the capabilities the gates SO FAR
consume — completeness of the SSOT is independent of any single adapter's
coverage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypeVar


if TYPE_CHECKING:
    from collections.abc import Callable


T = TypeVar("T")


class Capability(Enum):
    """Named AST capabilities a per-language adapter must implement.

    The COMPLETE 9-capability contract of ADR-TEST-002 D-C — the SSOT a
    new-language implementer reads. Each member names an abstract, pure query
    over an opaque parsed-tree handle (the rule layer never names a parser API).

    The first two members are the slice-01 skeleton (preserved verbatim; the M1
    driving-port-boundary rule consumes them). The remaining seven are the full
    contract every gate-family the shipped gates need (slice-12 dropped the two
    dead members that no rule consumed and no adapter realized).
    """

    # -- slice-01 skeleton (M1 driving-port-boundary rule; MUST stay) ----------
    FUNCTIONS_WITH_DECORATOR = "functions_with_decorator"
    IMPORTS_IN_FUNCTION = "imports_in_function"

    # -- slice-02 full contract (ADR-TEST-002 D-C, capabilities 3-9) -----------
    IMPORTS_IN_MODULE = "imports_in_module"
    CALLS_IN_FUNCTION = "calls_in_function"
    MARKER_DECORATORS = "marker_decorators"
    SPAWN_SHAPE_IN_BODY = "spawn_shape_in_body"
    KEYWORD_ARG_NAMES = "keyword_arg_names"
    ASSIGNMENTS_CONSTRUCTING_TYPE = "assignments_constructing_type"
    LAYER_OF_FILE = "layer_of_file"


# ===========================================================================
# slice-01 register-protocol seam (SHIPPED — implemented, MUST stay green)
# ===========================================================================

_REGISTRY: dict[str, frozenset[Capability]] = {}


def requires_capabilities(*capabilities: Capability) -> Callable[[T], T]:
    """Declarative annotation: a gate-rule registers the capabilities it consumes
    into the SSOT at import time (the running validation of D-A).

    Mirrors the ``error_codes._register`` idiom: the target is recorded and
    returned unchanged. The registry key is the target's fully-qualified name
    (``module:qualname``) so each registering rule is addressable.
    """
    consumed = frozenset(capabilities)

    def _decorator(target: T) -> T:
        _REGISTRY[_registry_key(target)] = consumed
        return target

    return _decorator


def _registry_key(target: object) -> str:
    module = getattr(target, "__module__", "?")
    qualname = getattr(target, "__qualname__", repr(target))
    return f"{module}:{qualname}"


# ===========================================================================
# slice-02 catalog + conformance surface (RED SCAFFOLD — implemented by DELIVER)
# ===========================================================================


@dataclass(frozen=True)
class ConformanceVerdict:
    """The port-exposed result of checking an adapter against the SSOT contract.

    ``missing`` — the capabilities the adapter was required to cover but does not
                  implement (empty == conformant). Names the gaps so a
                  new-language implementer sees exactly what is left to build.
    ``conformant`` (derived) — True iff ``missing`` is empty, i.e. the adapter
                  implements every capability it was required to cover.
    """

    missing: tuple[Capability, ...]

    @property
    def conformant(self) -> bool:
        return not self.missing


class CapabilityRegistry:
    """The ONE SSOT catalog enumerating the full per-language adapter contract.

    The methodology maintainer reads this catalog to learn EXACTLY which AST
    capabilities every adapter must implement (ADR-TEST-002 D-C, Ale Decision B
    — the single-checklist requirement). A registry that omits a capability some
    gate consumes is INCOMPLETE (fail-closed): ``required_capabilities`` is the
    union of the declared contract and everything any registered rule consumes,
    so a gate can never quietly depend on a capability the catalog does not name.

    The catalog is the full ``Capability`` enum; conformance is structural over
    an adapter's callable method names.
    """

    def required_capabilities(self) -> frozenset[Capability]:
        """The complete capability contract every per-language adapter must cover.

        The SSOT checklist: the union of the declared 9-capability contract and
        every capability any ``@requires_capabilities``-registered rule consumes.
        Fail-closed — a gate consuming a capability absent from this set makes
        the registry incomplete, which the slice-02 self-AT detects. Because the
        declared contract is the full ``Capability`` enum and every registered
        capability is an enum member, that union is exactly the enum.
        """
        return frozenset(Capability).union(*_REGISTRY.values())

    def check_conformance(
        self, adapter: object, *, required: frozenset[Capability]
    ) -> ConformanceVerdict:
        """Verify ``adapter`` implements every capability in ``required``.

        Conformance is structural: an adapter covers a capability iff it exposes
        a callable method named for that capability's value. Returns a
        ``ConformanceVerdict`` naming any missing capabilities — the gaps a
        new-language implementer must still build, ordered by the contract's
        canonical enum order for a stable, reviewable report.
        """
        missing = tuple(
            capability
            for capability in Capability
            if capability in required and not self._adapter_covers(adapter, capability)
        )
        return ConformanceVerdict(missing=missing)

    @staticmethod
    def _adapter_covers(adapter: object, capability: Capability) -> bool:
        method = getattr(adapter, capability.value, None)
        return callable(method)


def build_registry() -> CapabilityRegistry:
    """Composition-root entry — the SSOT catalog the gates and adapters read."""
    return CapabilityRegistry()
