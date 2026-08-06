"""The law that closes the escaping-exception class in `resolve_phase`.

`resolve_phase` used to signal its third outcome -- an unrecognised name -- by
raising `UnknownPhaseName`, which the only caller caught one line below the call.
CI observed that exception propagating out of `des.cli.phases._resolve` from the
line INSIDE its own `try`, with the matching `except` on the next line: an
`except` matches on class IDENTITY, and where the same package is reachable by
more than one path that identity is not guaranteed.

Returning all three outcomes removes the coupling. These properties pin that:
if the function never raises, no `except` can fail to match it, whatever the
import topology.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from des.domain.atdd_pure_phases import (
    CANONICAL_PHASES,
    LEGACY_PHASE_ALIASES,
    PhaseResolution,
    PhaseResolutionKind,
    resolve_phase,
)


_SETTINGS = settings(max_examples=300, deadline=None)

#: Arbitrary operator input, plus the vocabularies that must resolve, so the
#: generator reaches all three outcomes rather than only the unknown one.
_ANY_NAME = st.one_of(
    st.text(max_size=40),
    st.sampled_from(sorted(CANONICAL_PHASES)),
    st.sampled_from(sorted(LEGACY_PHASE_ALIASES)),
)


@_SETTINGS
@given(name=_ANY_NAME)
def test_resolve_phase_never_raises(name: str) -> None:
    """Totality: every string maps to an outcome, none escapes as an exception.

    This is the whole point of the contract change. It is asserted over
    arbitrary input, not over a curated list, because the defect it closes was
    triggered by an unrecognised name -- the case a curated list omits.
    """
    resolution = resolve_phase(name)

    assert isinstance(resolution, PhaseResolution)
    assert resolution.requested == name


@_SETTINGS
@given(name=_ANY_NAME)
def test_only_a_canonical_outcome_carries_a_phase(name: str) -> None:
    """Construction: the illegal combinations are unrepresentable.

    A ROUTING or UNKNOWN outcome carrying a phase would be a silent map to a
    wrong phase -- the exact thing the typed-error contract existed to prevent.
    """
    resolution = resolve_phase(name)

    if resolution.kind is PhaseResolutionKind.CANONICAL:
        assert resolution.canonical in CANONICAL_PHASES
    else:
        assert resolution.canonical is None


@_SETTINGS
@given(name=st.sampled_from(sorted(CANONICAL_PHASES)))
def test_a_canonical_name_resolves_to_itself(name: str) -> None:
    """Idempotence on the canonical vocabulary: resolution is a no-op there."""
    resolution = resolve_phase(name)

    assert resolution.kind is PhaseResolutionKind.CANONICAL
    assert resolution.canonical == name


@_SETTINGS
@given(name=st.sampled_from(sorted(CANONICAL_PHASES)))
def test_resolution_is_stable_under_case_and_separator_noise(name: str) -> None:
    """Metamorphic: normalisation the operator can reasonably expect.

    A name typed lowercase or with hyphens is the same request, so it must reach
    the same outcome -- otherwise the CLI refuses input it plainly understands.
    """
    noisy = name.lower().replace("_", "-")

    assert resolve_phase(noisy).canonical == resolve_phase(name).canonical


def test_the_outcome_discriminates_across_a_second_module_identity() -> None:
    """The law that the FIRST version of this contract change got wrong.

    Returning the outcome removes the `except` identity coupling only if callers
    ask the OUTCOME. The first attempt had the CLI branch on
    `resolution.kind is PhaseResolutionKind.UNKNOWN` -- an identity comparison on
    an enum member, which is the same coupling in new syntax. CI caught it as an
    unknown phase ACCEPTED with exit 0.

    This pins the difference. The same source file is importable under a second
    module name in this tree, producing distinct class and enum objects; a
    resolution built by one side must still be discriminated correctly by the
    property, while the cross-module enum comparison is shown to be exactly the
    unreliable thing.
    """
    import src.des.domain.atdd_pure_phases as twin

    from des.domain.atdd_pure_phases import PhaseResolutionKind as CanonicalKind

    assert twin.PhaseResolutionKind is not CanonicalKind, (
        "this repository no longer exposes the same module under two identities, "
        "so this regression can no longer be reproduced -- if that is deliberate, "
        "delete this test with the reason; do not weaken it"
    )

    twin_resolution = twin.resolve_phase("TOTALLY_BOGUS_PHASE")

    # What a caller must rely on: the outcome answers about itself.
    assert twin_resolution.is_unknown is True
    assert twin_resolution.is_routing is False
    assert twin_resolution.is_canonical is False

    # What a caller must NOT rely on, demonstrated rather than asserted in prose:
    # the cross-module identity comparison answers False for the TRUE case.
    assert (twin_resolution.kind is CanonicalKind.UNKNOWN) is False
