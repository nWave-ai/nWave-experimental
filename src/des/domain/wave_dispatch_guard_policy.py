"""Wave-dispatch guard policy (f-nonbypassable-attestation slice-05, DDD-8/9).

A pure domain policy that decides whether an Agent/Task dispatch ENTERS a wave
on-spine (recognized) or off-spine (a silent default the flow-v2 incident
exploited one level up from per-commit bypass). The guard runs as PRODUCTION
RUNTIME enforcement in the DES runtime (`des.cli.verify_wave_dispatch` is the
thin gate over this policy), NOT the hand-placed personal hook under the
developer home dir (which has no repo source -- DDD-8).

The policy owns three net-new load-bearing seams (D11 / DDD-8/9):

  1. ``WAVE_OWNERS`` -- the wave->owner map. A dispatch of one of these
     subagent_types WITHOUT the matching ``DES-WAVE: <wave>`` marker is off-spine
     wave entry. Reviewers are deliberately ABSENT (they are §22.0 controls,
     never wave-authoring -- their dispatch is always allowed).
  2. ``DISPATCH_GUARD_VOCABULARY`` -- the policy's OWN closed vocabulary of the 7
     wave tokens it protects (§22.0 H-1). DISTINCT from the ledger
     ``wave_active.WAVE_VOCABULARY`` (which excludes discover/diverge because
     they emit no wave-active record). The guard protects DISCOVER/DIVERGE too,
     so it declares its own set rather than importing the ledger vocab.
  3. ``_wave_skip_witness_present(content, wave)`` -- the wave-parametric
     skip-witness FORM check (generalizes the DESIGN-only
     ``_design_skip_witness_present`` on the readiness gate). FORM-only (canonical
     heading + non-empty rationale): the guard CANNOT verify source-authorship of
     plain markdown -- that is review-enforced (the fourth honest limit, AT-A8).

REUSE: the ``DES-WAVE`` marker regex is the SHIPPED
``des_marker_parser._WAVE_PATTERN`` (no second marker parser). The skip-witness
FORM check generalizes the readiness gate's predicate (one FORM implementation,
parameterized by wave).

Pure stdlib (``re`` / ``json`` / ``time`` / ``pathlib``) + ``des_marker_parser``;
no scripts.* / tests.* imports (F-D-09).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from des.domain.des_marker_parser import DesMarkerParser


if TYPE_CHECKING:
    from pathlib import Path

    from des.domain.wave_active import WaveActiveRecord


# --- the wave->owner map + the policy-owned vocabulary (DDD-8, §22.0 H-1) ----

# subagent_type -> the DES-WAVE token its on-spine dispatch carries. Owners only;
# reviewers are §22.0 controls (never wave-authoring) so they are ABSENT from the
# map and always allowed. nw-platform-architect owns BOTH design (infra) + devops;
# either marker is on-spine (the dual-ownership check accepts both tokens).
# NB: declared WITHOUT a type annotation so the arch-test AST reader
# (`test_arch_wave_dispatch_guard_owner_map.py::_literal_assignment`, which walks
# `ast.Assign` nodes only) reads the literal map as DATA. An annotated assignment
# is an `ast.AnnAssign` the reader does not see.
WAVE_OWNERS = {
    "nw-product-discoverer": "discover",
    "nw-diverger": "diverge",
    "nw-product-owner": "discuss",
    "nw-solution-architect": "design",
    "nw-ddd-architect": "design",
    "nw-system-designer": "design",
    "nw-acceptance-designer": "distill",
    "nw-platform-architect": "design",
}

# The platform architect's second on-spine wave -- DEVOPS. The DESIGN token is in
# WAVE_OWNERS above; DEVOPS is the dual-ownership second token.
_PLATFORM_ARCHITECT = "nw-platform-architect"
_PLATFORM_ARCHITECT_WAVES: frozenset[str] = frozenset({"design", "devops"})

# The policy's OWN closed vocabulary (§22.0 H-1) -- the 7 wave tokens it protects,
# INCLUDING discover/diverge the ledger WAVE_VOCABULARY deliberately excludes.
# Bare assignment (no annotation) so the arch-test AST reader sees the
# `frozenset({...})` literal call.
DISPATCH_GUARD_VOCABULARY = frozenset(
    {"discover", "diverge", "discuss", "design", "devops", "distill", "deliver"}
)

_WAVE_SKIP_HEADING_TEMPLATE = "## Wave: {wave} / [REF] Wave Skipped"


class GuardVerdict(Enum):
    """The wave-dispatch-guard decision projected onto exit codes (CT-8/9/10).

    Mirrors ``verify_readiness_pre_dispatch``'s convention: 0 ALLOW / 1 BLOCK;
    argparse reserves 2 for malformed-input (§22.0 H-2).
    """

    ALLOW = 0
    BLOCK = 1


@dataclass(frozen=True)
class GuardDecision:
    """The policy's decision: the verdict + the recognized on-spine signal name.

    ``recognized_signal`` names WHY an ALLOW was conceded (the matching DES-WAVE
    marker / a form-valid skip witness / a valid session pre-grant) so an ALLOW is
    a RECOGNIZED decision, never a silent exemption (anti-vacuous-pass). It is
    None for an exempt reviewer (the one legitimately-invariant ALLOW) and for a
    BLOCK.
    """

    verdict: GuardVerdict
    reason: str
    recognized_signal: str | None = None


def _wave_owner_for(subagent_type: str) -> str | None:
    """The owner's on-spine wave token, or None when the subagent is not an owner.

    A non-owner (a reviewer or anything outside the map) returns None -> the gate
    exempts it (always ALLOW).
    """
    return WAVE_OWNERS.get(subagent_type)


def _marker_is_on_spine(prompt: str, owner_wave: str, subagent_type: str) -> bool:
    """True when the prompt carries a DES-WAVE marker matching the owner's wave.

    Reuses the SHIPPED ``des_marker_parser._WAVE_PATTERN`` (no second parser). The
    platform architect owns BOTH design + devops, so either token is on-spine for
    it; every other owner matches its single wave token.
    """
    match = DesMarkerParser._WAVE_PATTERN.search(prompt)
    if match is None:
        return False
    declared = match.group(1)
    if subagent_type == _PLATFORM_ARCHITECT:
        return declared in _PLATFORM_ARCHITECT_WAVES
    return declared == owner_wave


def _has_design_ownership_envelope(prompt: str) -> bool:
    """Return whether a marked architect DESIGN prompt owns its gate inputs.

    The feature id comes from the prompt's own DES marker, so copied ownership
    prose for a different feature is malformed rather than silently accepted.
    """
    feature_id = DesMarkerParser().parse(prompt).project_id
    if feature_id is None:
        return False
    ownership = (
        f"nw-solution-architect owns docs/feature/{feature_id}/feature-delta.md "
        "canonical DESIGN sections `## Reuse Analysis` and "
        "`## Prefactoring Assessment`."
    )
    return (
        ownership in prompt
        and "Standalone design documents never substitute for feature-delta.md."
        in prompt
        and "Before handoff, run `des verify-readiness-pre-dispatch`." in prompt
    )


def _wave_skip_witness_present(content: str, wave: str) -> bool:
    """True iff a ``## Wave: <wave> / [REF] Wave Skipped`` heading carries a
    non-empty rationale body (DDD-9 wave-parametric FORM check).

    Generalizes ``verify_readiness_pre_dispatch._design_skip_witness_present`` to
    ANY wave. The witness is valid only when the canonical heading is followed by
    at least one non-blank, non-``##`` line before the next ``##`` heading. A bare
    heading (immediately followed by another ``##`` heading or end-of-file) is NOT
    a valid witness -- the rationale is empty.

    FORM-only (the fourth honest limit, AT-A8): it verifies the FORM, NOT the
    source-authorship of the rationale -- the guard cannot prove a human wrote
    plain markdown; that is review-enforced.
    """
    heading = _WAVE_SKIP_HEADING_TEMPLATE.format(wave=wave)
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.strip() != heading:
            continue
        for body in lines[idx + 1 :]:
            stripped = body.strip()
            if stripped.startswith("##"):
                break
            if stripped:
                return True
        return False
    return False


def _feature_delta_witness_present(repo_root: Path, owner_wave: str) -> bool:
    """Scan ``docs/feature/*/feature-delta.md`` for a form-valid wave-skip witness.

    The witness heading uses the UPPER-CASE wave name (``## Wave: DESIGN / ...``)
    while the marker token is lower-case (``design``); the FORM check is driven
    with the upper-cased wave. Any one feature-delta carrying a form-valid witness
    for this wave concedes the off-spine dispatch.
    """
    feature_dir = repo_root / "docs" / "feature"
    if not feature_dir.is_dir():
        return False
    witness_wave = owner_wave.upper()
    for delta in feature_dir.rglob("feature-delta.md"):
        try:
            content = delta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if _wave_skip_witness_present(content, witness_wave):
            return True
    return False


def _valid_pre_grant_present(repo_root: Path, session_id: str) -> bool:
    """True when a non-expired session-scoped pre-grant exists (DDD-9 night-autonomy).

    Reads ``.nwave/des/wave-skip-grant-{session_id}.json``. A grant is valid when
    its ``expires_at`` is still in the future. A TTL-elapsed grant reads as ABSENT
    (the off-spine dispatch stays BLOCKED). A malformed/unreadable grant is treated
    as absent (fail-closed for the skip-authorization -- no false-allow).
    """
    grant = repo_root / ".nwave" / "des" / f"wave-skip-grant-{session_id}.json"
    if not grant.is_file():
        return False
    try:
        record = json.loads(grant.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    expires_at = record.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False
    return expires_at > time.time()


def _is_at3_collision(
    *,
    prompt: str,
    owner_wave: str,
    active_floor: WaveActiveRecord | None,
) -> bool:
    """True for the AT-3 matching-wave collision case (DDD-1 SSOT reuse).

    Mirrors the canonical predicate ``PreToolUseService`` applies (the
    ``markers.wave is not None and markers.carries_partial_wave_context and not
    wave_entering`` hinge): an ACTIVE wave floor for THIS owner's wave whose
    ``entry_pending`` is cleared (a non-entering, in-wave dispatch) + a prompt
    carrying PARTIAL wave context (a ``DES-*`` marker -- including ``DES-WAVE``
    but NOT the required ``DES-VALIDATION`` marker). The active wave + the
    wave-entering signal both come from the floor reader AT-3 uses (never
    self-reported); ``carries_partial_wave_context`` is the SAME ``DesMarkers``
    property AT-3 reads. A matching DES-WAVE marker reads as on-spine to the
    floor-blind cascade below; this collision is detected so the branch can
    ALLOW it explicitly (agreeing with AT-3's own ALLOW, per Ale's 2026-07-16
    re-reconcile onto ALLOW -- a child declaring its OWN active wave is a
    legitimate wave-membership declaration, the OPPOSITE of a bypass), rather
    than falling through to the identical ALLOW below by accident.
    """
    if active_floor is None or active_floor.wave != owner_wave:
        return False
    if active_floor.entry_pending:
        return False
    markers = DesMarkerParser().parse(prompt)
    return markers.carries_partial_wave_context


def decide_dispatch(
    *,
    subagent_type: str,
    prompt: str,
    repo_root: Path,
    session_id: str,
    active_floor: WaveActiveRecord | None = None,
) -> GuardDecision:
    """Decide whether an Agent/Task dispatch enters its wave on-spine.

    The decision cascade (DDD-8/9, re-reconciled onto ALLOW 2026-07-16):
      * a non-owner (reviewer / anything outside WAVE_OWNERS) -> ALLOW (exempt).
      * the AT-3 matching-wave collision case (active floor for this wave +
        non-entering partial-marker in-wave dispatch) -> ALLOW (agrees with
        PreToolUse AT-3's own ALLOW -- a child declaring its OWN active wave is
        a legitimate wave-membership declaration, not a bypass).
      * a wave-owner carrying the matching DES-WAVE marker -> ALLOW (on-spine).
      * a marker-less wave-owner with a form-valid skip witness -> ALLOW (witness).
      * a marker-less wave-owner with a valid session pre-grant -> ALLOW (grant).
      * a marker-less wave-owner with no recognized signal -> BLOCK (warn+ask).

    ``active_floor`` is the wave-active record the CLI driver reads (via the same
    ``WaveActiveReader`` store AT-3 uses) and threads in as pure data; None when no
    floor is armed or no reader is wired (the legacy floor-blind behaviour). The
    collision branch is ADDITIVE -- it fires ONLY for the case AT-3 already
    allows, leaving every existing ALLOW path intact (DDD-2), and now emits the
    SAME ALLOW explicitly (rather than relying on fallthrough) so the reason
    names the matching-wave signal.
    """
    owner_wave = _wave_owner_for(subagent_type)
    if owner_wave is None:
        return GuardDecision(
            verdict=GuardVerdict.ALLOW,
            reason=f"allow: {subagent_type} is not a wave-owner (exempt control)",
        )

    if _is_at3_collision(
        prompt=prompt, owner_wave=owner_wave, active_floor=active_floor
    ):
        return GuardDecision(
            verdict=GuardVerdict.ALLOW,
            reason=(
                f"allow: the '{owner_wave}' wave floor is active and this "
                f"{subagent_type} sub-dispatch declares the SAME wave via its "
                "DES-WAVE marker while NOT entering the wave -- a child "
                "declaring its own active wave is a legitimate wave-membership "
                "declaration (DES-WAVE only ARMS enforcement, it is the "
                "opposite of a bypass); verify-wave-dispatch agrees with the "
                "PreToolUse AT-3 floor check's own ALLOW (one exemption SSOT, "
                "2026-07-16 re-reconcile)."
            ),
            recognized_signal="des-wave",
        )

    if _marker_is_on_spine(prompt, owner_wave, subagent_type):
        if (
            subagent_type == "nw-solution-architect"
            and owner_wave == "design"
            and not _has_design_ownership_envelope(prompt)
        ):
            return GuardDecision(
                verdict=GuardVerdict.BLOCK,
                reason=(
                    "block: WHAT: the nw-solution-architect DESIGN prompt lacks "
                    "the canonical feature-delta ownership/readiness envelope; "
                    "WHY: `## Reuse Analysis` and `## Prefactoring Assessment` "
                    "must be owned in feature-delta.md before the readiness gate "
                    "can be trusted; HOW: regenerate the prompt with `des dispatch` "
                    "instead of hand-authoring it."
                ),
            )
        return GuardDecision(
            verdict=GuardVerdict.ALLOW,
            reason=f"allow: on-spine DES-WAVE marker recognized for {subagent_type}",
            recognized_signal="des-wave",
        )

    if _feature_delta_witness_present(repo_root, owner_wave):
        return GuardDecision(
            verdict=GuardVerdict.ALLOW,
            reason="allow: form-valid wave-skip witness recognized (human-authorized)",
            recognized_signal="witness",
        )

    if _valid_pre_grant_present(repo_root, session_id):
        return GuardDecision(
            verdict=GuardVerdict.ALLOW,
            reason="allow: valid session pre-grant recognized (human-authorized)",
            recognized_signal="pre-grant",
        )

    return GuardDecision(
        verdict=GuardVerdict.BLOCK,
        reason=(
            f"block: {subagent_type} dispatched off-spine with no DES-WAVE marker, "
            "no form-valid skip witness, and no valid session pre-grant -- refused "
            "(warn+ask: entering a wave off-spine is a human-conceded exception, "
            "never a silent default). To proceed: run `des dispatch --mode "
            "atdd_pure --project-id <id> --slice <slice> --phase <phase>` (the "
            "producing tool -- emits a gate-valid dispatch carrying the "
            f"`<!-- DES-WAVE: {owner_wave} -->` marker by construction), or embed "
            f"`<!-- DES-WAVE: {owner_wave} -->` in the prompt yourself, or route "
            f"through `/nw-{owner_wave}`."
        ),
    )
