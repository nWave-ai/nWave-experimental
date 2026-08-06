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


# The twin-identity regression that stood here was DELETED 2026-08-06, on its own
# instruction. It reproduced the defect by importing this module under the second
# `src.des` identity, and asserted that identity existed -- so it could only pass
# while the tree still permitted the condition. It no longer does: independent
# review established the dual identity is an artefact of the pytest path, not a
# supported runtime topology (no production module imports the `src`-prefixed
# name, and the installer rewrites it away), and the two test files that reached
# for it were converted. `tests/meta/test_no_test_imports_the_src_prefixed_package.py`
# now guards the CAUSE for every module in the tree rather than this symptom in
# one of them.
#
# What survives, and why it is not now ceremony: `resolve_phase` still RETURNS
# its third outcome instead of raising. That is better design independently of
# import topology -- an unrecognised name is an expected result, not an
# exceptional one -- and the four properties above are what pin it.
