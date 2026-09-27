"""Density resolver — shared utility per DDD-5 (lean-wave-documentation feature).

Pure-function domain helper. No I/O — caller passes an already-parsed dict.
Hexagonal: this module is a Tier-1 driving port at domain scope; filesystem
reads of `~/.nwave/config.json` live in caller adapters (CLI install,
wave-skill harness, doctor).

Per DDD-5 + D12 + Decision 4 (2026-04-28),
`resolve_density(global_config)` cascades:
    1. Explicit `documentation.density` override wins.
    2. Else `rigor.profile` mapping per D12 (lean -> lean+always-skip,
       standard/custom -> lean+ask-intelligent,
       thorough/exhaustive -> full+always-expand).
    3. Else hard default "lean" + "ask-intelligent" (fresh-install per
       Decision 4).

Provenance is reported on the returned Density value so consumers (telemetry,
doctor, audit) can explain *why* a given density is in effect without
re-running the cascade.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, get_args


DensityMode = Literal["lean", "full"]
ExpansionPromptMode = Literal[
    "ask", "always-skip", "always-expand", "smart", "ask-intelligent"
]


@dataclass(frozen=True)
class Density:
    """Resolved documentation-density decision.

    Immutable value object: density mode, expansion-prompt mode, and the
    provenance string that explains which cascade branch produced this result.

    Attributes:
        mode: "lean" or "full" (per DDD-5).
        expansion_prompt: "ask" | "always-skip" | "always-expand" |
            "smart" | "ask-intelligent" (the last one added per
            Decision 4 2026-04-28; scoped trigger-based menu).
        provenance: human-readable origin tag, e.g. "default",
            "explicit_override", "rigor.profile=thorough".
    """

    mode: DensityMode
    expansion_prompt: ExpansionPromptMode
    provenance: str


# D12 + Decision 4 mapping: rigor.profile -> Density (without provenance —
# set by caller). Returns (mode, expansion_prompt) tuple; provenance is
# composed at call site so the rigor profile name is preserved verbatim in
# the audit trail.
#
# Per Decision 4 (2026-04-28), `standard` and `custom` profiles use
# `ask-intelligent` (scoped trigger-based menu) instead of the broad `ask`
# menu. Trigger detection lives in the wave skill prose, not in this
# resolver.
_RIGOR_PROFILE_MAP: dict[str, tuple[DensityMode, ExpansionPromptMode]] = {
    "lean": ("lean", "always-skip"),
    "standard": ("lean", "ask-intelligent"),
    "thorough": ("full", "always-expand"),
    "exhaustive": ("full", "always-expand"),
    "custom": ("lean", "ask-intelligent"),
}


def _from_rigor_profile(profile: str) -> Density:
    """Map a rigor.profile name to its D12-defined Density.

    Raises ValueError on unknown profile names: density resolver does not
    silently default for invalid rigor configuration. Profile validation
    is owned by the rigor system upstream.
    """
    mapping = _RIGOR_PROFILE_MAP.get(profile)
    if mapping is None:
        raise ValueError(
            f"Unknown rigor.profile {profile!r}; "
            f"expected one of {sorted(_RIGOR_PROFILE_MAP)}."
        )
    mode, expansion_prompt = mapping
    return Density(
        mode=mode,
        expansion_prompt=expansion_prompt,
        provenance=f"rigor.profile={profile}",
    )


def _require_object(value: Any, *, field: str) -> dict[str, Any]:
    """Return ``value`` as a dict, or raise a useful ``ValueError``.

    A malformed JSON type for a config section (e.g. a list where an
    object is expected) must surface as a clear resolver-level ValueError,
    never as an ``AttributeError`` from a stray ``.get()`` deep in the
    cascade (V4-02).
    """
    if not isinstance(value, dict):
        raise ValueError(
            f"Invalid {field!r} config: expected a JSON object, got "
            f"{type(value).__name__}."
        )
    return value


def _validate_choice(value: str | None, *, field: str, legal: tuple[str, ...]) -> None:
    if value is not None and value not in legal:
        raise ValueError(f"Unknown {field} {value!r}; expected one of {sorted(legal)}.")


def resolve_density(global_config: dict[str, Any]) -> Density:
    """Return the active documentation density via the D12 cascade.

    Pure function. No I/O, no logging, no environment lookups. Caller is
    responsible for parsing `~/.nwave/config.json` and passing the
    resulting dict in.

    Cascade order (per DDD-5 + D12 + Decision 4):
        1. Explicit `documentation.density` override wins for the mode.
        2. Else `rigor.profile` D12 mapping decides the mode.
        3. Else fallback to "lean" — fresh-install hard default per
           Decision 4.
        Independently of which branch decided the mode, an explicit
        `documentation.expansion_prompt` always wins for the prompt
        (V4-02: previously dropped whenever density was omitted and the
        cascade fell through to the rigor-profile or hard-default branch).

    Args:
        global_config: Parsed contents of `~/.nwave/config.json`.
            May be empty (fresh install) or arbitrary user-shaped dict.

    Returns:
        Density value object capturing the resolved mode, expansion prompt,
        and provenance.

    Raises:
        ValueError: `rigor.profile` is unknown, `documentation.density` or
            `documentation.expansion_prompt` is not one of their legal
            values, or `documentation`/`rigor` is not a JSON object.
    """
    documentation = _require_object(
        global_config.get("documentation", {}), field="documentation"
    )
    rigor = _require_object(global_config.get("rigor", {}), field="rigor")

    explicit_mode = documentation.get("density")
    explicit_expansion_prompt = documentation.get("expansion_prompt")
    _validate_choice(
        explicit_mode, field="documentation.density", legal=get_args(DensityMode)
    )
    _validate_choice(
        explicit_expansion_prompt,
        field="documentation.expansion_prompt",
        legal=get_args(ExpansionPromptMode),
    )

    # Step 1: explicit density override wins for the mode.
    if explicit_mode is not None:
        return Density(
            mode=explicit_mode,
            expansion_prompt=explicit_expansion_prompt or "ask-intelligent",
            provenance="explicit_override",
        )

    # Step 2: rigor.profile inheritance per D12 decides the mode.
    rigor_profile = rigor.get("profile")
    if rigor_profile is not None:
        if not isinstance(rigor_profile, str):
            raise ValueError(
                f"Invalid rigor.profile: expected a string, got "
                f"{type(rigor_profile).__name__}."
            )
        base = _from_rigor_profile(rigor_profile)
    else:
        # Step 3: hard default — fresh install, no documentation, no rigor.
        # Per Decision 4 (2026-04-28), the fresh-install default is
        # ("lean", "ask-intelligent"): emit minimal Tier-1 baseline, then
        # show a scoped expansion menu only when triggers fire (the wave
        # skill prose owns trigger detection).
        base = Density(
            mode="lean", expansion_prompt="ask-intelligent", provenance="default"
        )

    # An explicit expansion_prompt is honored regardless of whether the
    # mode came from the rigor cascade or the hard default (V4-02).
    if explicit_expansion_prompt is not None:
        return Density(
            mode=base.mode,
            expansion_prompt=explicit_expansion_prompt,
            provenance=base.provenance,
        )
    return base
