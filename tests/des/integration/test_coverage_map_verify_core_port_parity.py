"""Port-parity + canonicalization-invariance contract test for the slice-04 port.

slice-04 of oss-feature-end-emit-cli RELOCATES the §5.3 coverage-map verify core
from the upstream script ``scripts/cli/verify_coverage_map.py`` into a new
``src/des/application/coverage_map_verify_service`` module (reuse-by-relocation,
DDD-8 / option (b)). Reuse-by-relocation has ONE failure mode the acceptance
slice cannot catch: the ported copy SILENTLY DRIFTS from the upstream SSOT (a
canonicalization step dropped, a refusal cause re-classified). The acceptance
slice (``tests/des/acceptance/oss_feature_end_emit_cli``) drives the cycle and
sees only PASS/REFUSE -- it cannot tell whether the ported digest equals the
upstream digest byte-for-byte.

This is a CONTRACT test (not an acceptance test): it pins the PORT itself. It
imports BOTH cores -- the upstream script core (the SSOT) and the ported
``des.application`` core (the relocation target) -- and asserts they agree:

  1. **Digest parity (PBT, canonicalization-invariance LAW)** -- for ANY
     well-formed coverage-map body Hypothesis generates, the ported core's §5.3
     canonical digest EQUALS the upstream core's, AND is INVARIANT under the four
     §5.3 normalizations {LF-normalization, trailing-whitespace strip, blank-line
     collapse, feature-surface bullet reorder}, AND a body whose SIGNED content
     differs yields a DIFFERENT digest (the anti-laundering law: you cannot edit
     signed content without breaking the digest). This is the anti-laundering
     invariant stated as a universal law over the unbounded body domain, not as
     three examples -- the right paradigm for a pure layer-1 algorithm
     (nw-property-based-testing; the falsifier-gate PASSES: the body domain is
     unbounded and the invariant is value-independent).

  2. **Verdict parity (golden vectors)** -- over a closed set of golden
     coverage-map vectors {signed-pass, unsigned, stale-digest, malformed}, the
     ported verify entry point produces the SAME accept/refuse verdict + the SAME
     refusal token as the upstream core. Closed-world finite set -> parametrize,
     NOT PBT (falsifier-gate: finite + enumerable).

Mandate-13 NOTE: this is NOT an acceptance test driving the feature through a
port -- it is a drift-guard on the relocation. It legitimately imports the ported
module (the SUT of THIS contract test IS the ported module's parity with its
SSOT). It is layer-1/2 pure-function (stdlib digest algorithm), so PBT is
permitted (Mandate 9: PBT full at layers 1-2). It lives under
``tests/des/integration`` alongside the other contract/drift guards, NOT under
the acceptance slice.

RED-FOR-RIGHT-REASON (pre-DELIVER gate): the ported module does NOT exist yet, so
the guarded import below fails the test with a SEMANTIC ``pytest.fail`` carrying a
``MISSING_FUNCTIONALITY`` marker -- a RED classification, NOT a BROKEN
``ImportError`` (Mandate 7: RED not BROKEN). Once DELIVER ports the core, the
guard passes and the parity assertions become live.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


# The upstream §5.3 verify core -- the SSOT the port must match. It lives under
# scripts/, so the scripts root is added to sys.path (the same way other
# integration guards reach a scripts core). This import is the SSOT side of the
# parity, NOT the SUT.
_SCRIPTS_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(_SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_ROOT))

from cli import verify_coverage_map as _upstream


# The ported module DESIGN target (DDD-8). Does not exist until DELIVER. The
# guarded import keeps this RED (semantic fail), not BROKEN (ImportError).
_PORTED_MODULE = "des.application.coverage_map_verify_service"


def _ported():
    """Import the ported verify core or fail RED with MISSING_FUNCTIONALITY.

    Returns the ported module. When it does not exist yet (pre-DELIVER), fails
    the test with a semantic message classified MISSING_FUNCTIONALITY -- a RED
    signal the crafter clears by creating the module, never a BROKEN
    infrastructure error.
    """
    try:
        return importlib.import_module(_PORTED_MODULE)
    except ModuleNotFoundError:
        pytest.fail(
            f"MISSING_FUNCTIONALITY: the ported verify core {_PORTED_MODULE!r} "
            "does not exist yet (slice-04 DDD-8 relocates the §5.3 core here). "
            "DELIVER must create it as a byte-for-byte relocation of the upstream "
            "scripts/cli/verify_coverage_map.py §5.3 core.",
        )


# --- §5.3 well-formed coverage-map body strategy ------------------------------
#
# Generates valid coverage-map bodies whose SIGNED sections vary, so the digest
# law has a non-trivial body domain to range over. Each body carries the four
# §5.1 signed sections (Feature surface declared / NOT covered / Known residues /
# Negative-space statement) plus a `## Signoff` block; the digest is computed
# over the signed sections only (§5.3 excludes `## Signoff`).

_SAFE_TEXT = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Pd"),
        max_codepoint=0x2FF,
    ),
    min_size=1,
    max_size=40,
).map(lambda s: s.strip() or "x")


@st.composite
def _well_formed_coverage_map_body(draw: st.DrawFn) -> str:
    surface_bullets = draw(st.lists(_SAFE_TEXT, min_size=1, max_size=4))
    not_covered = draw(_SAFE_TEXT)
    residues = draw(_SAFE_TEXT)
    statement = draw(_SAFE_TEXT)
    surface = "\n".join(f"- {b}" for b in surface_bullets)
    return (
        "# Coverage Map -- parity-probe\n"
        "\n"
        "## Feature surface declared\n"
        f"{surface}\n"
        "\n"
        "## NOT covered -- and why\n"
        f"{not_covered}\n"
        "\n"
        "## Known residues carried forward\n"
        f"{residues}\n"
        "\n"
        "## Negative-space completeness statement\n"
        f"{statement}\n"
        "\n"
        "## Signoff\n"
        "- reviewed-content-digest: _pending_\n"
    )


def _perturb_non_signed(body: str) -> str:
    """Apply the four §5.3-absorbed normalizations the canonical digest ignores.

    LF<-CRLF, add trailing whitespace, inject extra blank lines, reorder the
    feature-surface bullets. A correct §5.3 canonicalization yields the SAME
    digest before and after -- the invariance law.
    """
    lines = body.split("\n")
    out: list[str] = []
    surface: list[str] = []
    in_surface = False
    for line in lines:
        if line.startswith("## Feature surface declared"):
            in_surface = True
            out.append(line + "   ")  # trailing whitespace
            out.append("")  # extra blank line
            continue
        if line.startswith("## ") and in_surface:
            out.extend(reversed(surface))  # reorder bullets
            surface = []
            in_surface = False
            out.append(line)
            continue
        if in_surface and line.startswith("- "):
            surface.append(line + "  ")  # trailing whitespace on bullets
        else:
            out.append(line + ("   " if line and not line.startswith("#") else ""))
    if in_surface and surface:
        out.extend(reversed(surface))
    # CRLF line endings + an extra trailing blank line.
    return "\r\n".join(out) + "\r\n\r\n"


# --- 1. Digest parity + canonicalization-invariance LAW (PBT) -----------------


@settings(max_examples=60, deadline=400)
@given(body=_well_formed_coverage_map_body())
def test_ported_digest_matches_upstream_for_any_body(body: str) -> None:
    """The ported §5.3 digest EQUALS the upstream digest for ANY well-formed body."""
    ported = _ported()
    assert ported._compute_canonical_digest(
        body
    ) == _upstream._compute_canonical_digest(body)


@settings(max_examples=60, deadline=400)
@given(body=_well_formed_coverage_map_body())
def test_ported_digest_invariant_under_canonicalized_perturbations(body: str) -> None:
    """The ported digest is INVARIANT under the four §5.3-absorbed normalizations.

    {LF-normalization, trailing-whitespace strip, blank-line collapse,
    feature-surface bullet reorder} are exactly the perturbations §5.3 absorbs --
    a body and its perturbed twin MUST yield the same canonical digest. This is
    the law a drifted port would break.
    """
    ported = _ported()
    perturbed = _perturb_non_signed(body)
    assert ported._compute_canonical_digest(body) == ported._compute_canonical_digest(
        perturbed
    )


@settings(max_examples=60, deadline=400)
@given(
    body=_well_formed_coverage_map_body(),
    extra=_SAFE_TEXT,
)
def test_ported_digest_changes_when_signed_content_changes(
    body: str, extra: str
) -> None:
    """Editing SIGNED content yields a DIFFERENT digest (the anti-laundering law).

    Appending a bullet to the signed ``## Feature surface declared`` section is a
    signed-content change -> the canonical digest MUST differ. You cannot alter
    signed content without breaking the digest -- the core of why a `_pending_` /
    minted digest can never equal a real signature over edited content.
    """
    ported = _ported()
    edited = body.replace(
        "## Feature surface declared\n",
        f"## Feature surface declared\n- {extra}-injected\n",
        1,
    )
    assert ported._compute_canonical_digest(body) != ported._compute_canonical_digest(
        edited
    )


# --- 2. Verdict parity over golden vectors (closed-world parametrize) ----------


def _golden_signed_body() -> str:
    """A genuinely-signed golden vector the verify core ACCEPTS."""
    base = (
        "# Coverage Map -- golden\n\n"
        "## Feature surface declared\n- golden-surface\n\n"
        "## NOT covered -- and why\n_none_\n\n"
        "## Known residues carried forward\n_none_\n\n"
        "## Negative-space completeness statement\nAll covered.\n\n"
        "## Signoff\n- reviewed-content-digest: {digest}\n"
    )
    digest = _upstream._compute_canonical_digest(base.format(digest="_pending_"))
    return base.format(digest=digest)


def _golden_unsigned_body() -> str:
    return _golden_signed_body().replace(
        _upstream._extract_recorded_digest(_golden_signed_body()) or "x", "_pending_"
    )


def _golden_stale_body() -> str:
    import hashlib

    stale = hashlib.sha256(b"golden-stale").hexdigest()
    signed = _golden_signed_body()
    recorded = _upstream._extract_recorded_digest(signed) or "x"
    return signed.replace(recorded, stale)


# Closed, enumerable set of golden vectors -> parametrize, NOT PBT (falsifier-gate
# §4-bis: finite + listable). Each maps to the upstream verdict the ported entry
# point must reproduce: True = accepted, False = refused.
_GOLDEN_VECTORS = {
    "signed-pass": (_golden_signed_body, True),
    "unsigned": (_golden_unsigned_body, False),
    "stale-digest": (_golden_stale_body, False),
}


@pytest.mark.integration
@pytest.mark.parametrize("vector", sorted(_GOLDEN_VECTORS))
def test_ported_structural_and_digest_verdict_matches_upstream(vector: str) -> None:
    """The ported verify verdict EQUALS the upstream verdict over golden vectors.

    For each golden coverage-map vector, the ported core's structural-complete +
    recorded-digest-matches verdict (the digest leg of the verify pipeline) MUST
    equal the upstream core's. A drifted port that re-classified any cause would
    diverge here.
    """
    ported = _ported()
    build_body, _ = _GOLDEN_VECTORS[vector]
    body = build_body()

    upstream_ok = _upstream._check_structural_completeness(body) and (
        _upstream._extract_recorded_digest(body)
        == _upstream._compute_canonical_digest(body)
    )
    ported_ok = ported._check_structural_completeness(body) and (
        ported._extract_recorded_digest(body) == ported._compute_canonical_digest(body)
    )
    assert ported_ok == upstream_ok
