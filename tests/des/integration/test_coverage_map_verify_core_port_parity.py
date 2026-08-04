"""Canonicalization-invariance + anti-laundering laws over the §5.3 digest core.

HISTORY (why this file exists, and why its scope narrowed): slice-04 of
oss-feature-end-emit-cli RELOCATED the §5.3 coverage-map verify core from the
upstream script ``scripts/cli/verify_coverage_map.py`` into
``src/des/application/coverage_map_verify_service`` (reuse-by-relocation,
DDD-8 / option (b)). At that point TWO independently maintained copies of the
core existed, and this file pinned PARITY between them -- the ported digest
equal to the upstream digest, and the two verify entry points agreeing on a
closed set of golden vectors.

AD-59 (ARCH_TECH_DEBT.md:527) then found the "two copies" premise itself was
the defect: the scripts/ copy was never boundary-forced (scripts/ already
legally imports from ``des.*``), so the two ~identical copies were folded --
the CLI now imports the §5.3 core's functions directly from
``des.application.coverage_map_verify_service`` (see
``tests/des/unit/cli/test_verify_coverage_map_shares_mandatory_sections.py``
for the object-identity pin proving the fold). Once there is exactly ONE core
object, "parity between the ported copy and the upstream copy" is a
tautology -- comparing a function to itself. The two tests that asserted
exactly that (``test_ported_digest_matches_upstream_for_any_body`` and
``test_ported_structural_and_digest_verdict_matches_upstream``) were DELETED
here as vacuous, not merely disabled: a docstring describing a parity that no
longer exists would teach the next reader a false contract.

What survives, and why it is NOT vacuous: two of the original four tests
state genuine laws about the §5.3 canonicalization algorithm itself, over the
now-single core -- they hold regardless of how many copies of the core exist,
because they never compared "ported" against "upstream" in the first place:

  1. **Canonicalization-invariance law** -- the digest is INVARIANT under the
     four §5.3-absorbed normalizations {LF-normalization, trailing-whitespace
     strip, blank-line collapse, feature-surface bullet reorder}. A body and
     its cosmetically-perturbed twin MUST hash identically.
  2. **Anti-laundering law** -- editing SIGNED content (the four mandatory
     sections excluding ``## Signoff``) MUST change the digest. You cannot
     alter what was signed without invalidating the signature.

Both are stated as universal laws over the unbounded coverage-map-body domain
via Hypothesis, not as fixed examples -- the falsifier-gate reasoning for a
pure layer-1/2 algorithm applies regardless of how many call sites the
algorithm has (nw-property-based-testing; Mandate 9: PBT full at layers 1-2).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from des.application import coverage_map_verify_service as _core


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


@settings(max_examples=60, deadline=400)
@given(body=_well_formed_coverage_map_body())
def test_ported_digest_invariant_under_canonicalized_perturbations(body: str) -> None:
    """The §5.3 digest is INVARIANT under the four canonicalization-absorbed
    normalizations.

    {LF-normalization, trailing-whitespace strip, blank-line collapse,
    feature-surface bullet reorder} are exactly the perturbations §5.3 absorbs --
    a body and its perturbed twin MUST yield the same canonical digest.
    """
    perturbed = _perturb_non_signed(body)
    assert _core._compute_canonical_digest(body) == _core._compute_canonical_digest(
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
    edited = body.replace(
        "## Feature surface declared\n",
        f"## Feature surface declared\n- {extra}-injected\n",
        1,
    )
    assert _core._compute_canonical_digest(body) != _core._compute_canonical_digest(
        edited
    )
