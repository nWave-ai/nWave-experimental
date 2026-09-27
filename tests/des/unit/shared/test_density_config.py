"""Unit tests for density resolver — pure function, port-to-port at domain scope.

Driving port: `resolve_density(global_config: dict) -> Density`.
The function signature IS the public interface; calling it directly is correct
port-to-port testing per nw-tdd-methodology + nw-fp-principles.

Per Decision 4 (2026-04-28), the fresh-install hard default is now
`ask-intelligent` (scoped trigger-based menu) instead of the broader `ask`
menu. The wave skill prose owns trigger detection.

Coverage (per task spec):
  1. Empty dict -> lean default + provenance="default" + ask-intelligent
  2. Explicit documentation.density="full" -> full + provenance="explicit_override"
  3. rigor.profile="thorough" only -> full + provenance="rigor.profile=thorough"
  4. Explicit + rigor both -> explicit wins (override beats inheritance)
  5. Unknown rigor profile -> ValueError (strict; profile validation is upstream)
  6. rigor.profile="standard" -> lean+ask-intelligent (Decision 4)
"""

from __future__ import annotations

import pytest

from scripts.shared.density_config import Density, resolve_density


def test_empty_config_returns_lean_default() -> None:
    """Fresh-install path: no documentation, no rigor -> hard default.

    Per Decision 4 (2026-04-28), hard default is lean + ask-intelligent.
    """
    result = resolve_density({})
    assert result == Density(
        mode="lean", expansion_prompt="ask-intelligent", provenance="default"
    )


def test_explicit_documentation_density_full_wins() -> None:
    """Step-1 cascade: explicit override wins over everything else.

    Per Decision 4, the fallback expansion_prompt for an explicit-density
    override that does not set its own expansion_prompt is now
    "ask-intelligent" (was "ask").
    """
    config = {"documentation": {"density": "full"}}
    result = resolve_density(config)
    assert result == Density(
        mode="full",
        expansion_prompt="ask-intelligent",  # default per Decision 4
        provenance="explicit_override",
    )


def test_rigor_profile_standard_yields_lean_ask_intelligent() -> None:
    """Decision 4: standard profile maps to lean + ask-intelligent."""
    config = {"rigor": {"profile": "standard"}}
    result = resolve_density(config)
    assert result == Density(
        mode="lean",
        expansion_prompt="ask-intelligent",
        provenance="rigor.profile=standard",
    )


def test_rigor_profile_thorough_yields_full_density() -> None:
    """Step-2 cascade: rigor.profile inheritance (D12 mapping)."""
    config = {"rigor": {"profile": "thorough"}}
    result = resolve_density(config)
    assert result == Density(
        mode="full",
        expansion_prompt="always-expand",
        provenance="rigor.profile=thorough",
    )


def test_explicit_override_beats_rigor_profile() -> None:
    """Cascade priority: explicit override beats rigor.profile inheritance."""
    config = {
        "documentation": {"density": "lean", "expansion_prompt": "always-skip"},
        "rigor": {"profile": "thorough"},  # would yield "full" if used
    }
    result = resolve_density(config)
    assert result == Density(
        mode="lean",
        expansion_prompt="always-skip",
        provenance="explicit_override",
    )


def test_unknown_rigor_profile_raises_value_error() -> None:
    """Strict: unknown rigor profile signals upstream config invariant violation."""
    config = {"rigor": {"profile": "ludicrous"}}
    with pytest.raises(ValueError, match="ludicrous"):
        resolve_density(config)


# --- V4-02: explicit expansion_prompt with density omitted; invalid values ---


@pytest.mark.parametrize(
    ("expansion_prompt", "expected_mode", "expected_provenance"),
    [
        ("ask", "lean", "default"),
        ("always-skip", "lean", "default"),
        ("always-expand", "lean", "default"),
        ("smart", "lean", "default"),
        ("ask-intelligent", "lean", "default"),
    ],
)
def test_explicit_expansion_prompt_is_respected_with_default_density(
    expansion_prompt: str, expected_mode: str, expected_provenance: str
) -> None:
    """All five legal expansion_prompt values are honored even when
    documentation.density is omitted (V4-02): the bug silently dropped an
    explicit expansion_prompt whenever the cascade fell through to the
    rigor-profile or hard-default branch instead of the explicit-override
    branch.
    """
    config = {"documentation": {"expansion_prompt": expansion_prompt}}
    result = resolve_density(config)
    assert result.mode == expected_mode
    assert result.expansion_prompt == expansion_prompt


def test_explicit_expansion_prompt_is_respected_with_inherited_rigor_density() -> None:
    """Explicit expansion_prompt overrides the rigor-profile's own mapped
    expansion_prompt while still inheriting the rigor-mapped density mode.
    """
    config = {
        "rigor": {"profile": "thorough"},
        "documentation": {"expansion_prompt": "always-skip"},
    }
    result = resolve_density(config)
    assert result.mode == "full"  # inherited from rigor.profile=thorough
    assert result.expansion_prompt == "always-skip"  # explicit wins


def test_invalid_density_mode_raises_value_error_not_attribute_error() -> None:
    config = {"documentation": {"density": "extreme"}}
    with pytest.raises(ValueError, match="extreme"):
        resolve_density(config)


def test_invalid_expansion_prompt_raises_value_error_not_attribute_error() -> None:
    config = {"documentation": {"density": "lean", "expansion_prompt": "yolo"}}
    with pytest.raises(ValueError, match="yolo"):
        resolve_density(config)


def test_malformed_documentation_section_raises_value_error_not_attribute_error() -> (
    None
):
    """A malformed JSON type (e.g. a list instead of an object) for
    ``documentation`` must not crash with AttributeError deep in ``.get()``.
    """
    config = {"documentation": ["not", "an", "object"]}
    with pytest.raises(ValueError):
        resolve_density(config)


def test_malformed_rigor_section_raises_value_error_not_attribute_error() -> None:
    config = {"rigor": "not-an-object"}
    with pytest.raises(ValueError):
        resolve_density(config)


# --- rigor.profile boundary-type handling: unhashable / wrong-shaped values ---


@pytest.mark.parametrize(
    "bad_profile",
    [[], {}, True, False, ["lean"], {"name": "lean"}],
)
def test_non_string_rigor_profile_raises_value_error_not_type_error(
    bad_profile: object,
) -> None:
    """A non-string `rigor.profile` (list/dict/bool) must surface as a
    resolver-level ValueError, never as a TypeError from an unhashable-type
    dict lookup deep in `_from_rigor_profile` (`resolve_density({'rigor':
    {'profile': []}})` previously raised `TypeError: unhashable type: 'list'`).
    """
    config = {"rigor": {"profile": bad_profile}}
    with pytest.raises(ValueError):
        resolve_density(config)


@pytest.mark.parametrize(
    "legal_profile",
    ["lean", "standard", "thorough", "exhaustive", "custom"],
)
def test_current_legal_rigor_profiles_still_resolve(legal_profile: str) -> None:
    """All current legal string profiles keep resolving without error."""
    config = {"rigor": {"profile": legal_profile}}
    result = resolve_density(config)
    assert result.provenance == f"rigor.profile={legal_profile}"


def test_explicit_density_precedence_over_malformed_rigor_profile() -> None:
    """Explicit `documentation.density` wins even when the unused
    lower-priority `rigor.profile` is malformed (unhashable list): the
    malformed rigor.profile must not decide the density nor raise, because
    it is never consulted once the explicit override applies.
    """
    config = {
        "documentation": {"density": "full"},
        "rigor": {"profile": []},
    }
    result = resolve_density(config)
    assert result.mode == "full"
    assert result.provenance == "explicit_override"
