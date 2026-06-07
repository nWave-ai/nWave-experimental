"""Shared genuinely-signed coverage-map fixture builder (slice-03 + slice-04).

The §5.3 canonical-digest reproduction + the signed coverage-map body were first
authored in ``composition_slice_04.py`` to stage a GENUINELY human-signed
coverage-map the cycle's REAL ported verify core PASSES. slice-03's amended
scenario-1 (post-slice-04 gating collision, RATIFIED Ale option A, 2026-06-03)
needs the SAME genuinely-signed artifact so the now-mandatory coverage-map leg
PASSES and the cycle reaches a full 6-record SUCCESS. Rather than DUPLICATE the
§5.3 reproduction, both slices import this single shared builder (DRY; the §5.3
algorithm lives in exactly one test-infrastructure module).

HONESTY DISCIPLINE (load-bearing, identical to slice-04's): the signed digest is
a function of the coverage-map BODY under the §5.3 canonicalization. This builder
reproduces the §5.3 7-step canonicalization (stdlib ``hashlib`` + ``re`` only --
the same algorithm the ported core runs) and records the GENUINE digest it
computes over the body it just wrote. A minted constant / ``_pending_`` digest
cannot equal the real canonicalization, so the fixture is genuinely-signed by
construction -- never a fake the real verify would reject. This is TEST
INFRASTRUCTURE (staging a genuinely-signed artifact); the SUT is the cycle,
driven only through the real ``des feature-end run`` subprocess.

The omission-class attestation is read from the Layer-1 SSOT
(``nWave/data/omission-classes.json``) so the fixture stays in lock-step when the
class list grows (no hardcoded id list to rot).
"""

from __future__ import annotations

import hashlib
from pathlib import Path


# THIS file lives at
# tests/des/acceptance/oss_feature_end_emit_cli/steps/signed_coverage_map.py ->
# 5 parents up is the repo root; the omission-class SSOT lives under it.
_REPO_ROOT = Path(__file__).resolve().parents[5]


# The §5.1 mandatory section headings in fixed L1 order -- the structural check
# the ported verify core asserts present + ordered. The four SIGNED sections are
# everything before ``## Signoff`` (the digest is canonicalized over these).
_MANDATORY_SECTIONS_IN_ORDER: tuple[str, ...] = (
    "## Feature surface declared",
    "## NOT covered -- and why",
    "## Known residues carried forward",
    "## Negative-space completeness statement",
    "## Signoff",
)


def write_signed_coverage_map(feature_dir: Path, feature_id: str) -> None:
    """Write a GENUINELY human-signed ``distill/coverage-map.md`` under feature_dir.

    The ``## Signoff`` block carries a REAL ``reviewed-content-digest`` -- the
    genuine §5.3 canonical digest computed over the four signed sections (NOT
    ``_pending_``, NOT a minted constant) -- and attests every omission-class-id
    from the Layer-1 SSOT. The ported verify core's structural + digest +
    attestation checks all pass, so the cycle's coverage-map verify leg PASSES
    and appends both ``CoverageMapVerifiedAt{Distill,Deliver}Exit`` records on a
    REAL pass.
    """
    distill_dir = feature_dir / "distill"
    distill_dir.mkdir(parents=True, exist_ok=True)

    full_attestation = "\n".join(f"  - {cid}" for cid in _load_omission_class_ids())
    # Render once with ``_pending_`` to compute the genuine §5.3 digest over the
    # fixed signed sections, then render again with that digest recorded.
    digest = _compute_canonical_digest(
        _coverage_map_body(feature_id, "_pending_", full_attestation)
    )
    (distill_dir / "coverage-map.md").write_text(
        _coverage_map_body(feature_id, digest, full_attestation), encoding="utf-8"
    )


def write_unsigned_coverage_map(feature_dir: Path, feature_id: str) -> None:
    """Write a genuinely UNSIGNED ``distill/coverage-map.md`` under feature_dir.

    The ``## Signoff`` block carries the producer's ``_pending_`` digest -- the
    only thing the automated producer renders; no human signed. The body is
    otherwise structurally complete (same four signed sections + a present
    ``## Signoff`` block) so the ported verify core refuses on the SIGNATURE
    (``SignoffMissing`` -- the digest-line regex rejects ``_pending_``), NOT on a
    missing-block / structural error. This stages the divergence-pair PARTNER of
    ``write_signed_coverage_map``: a stub that always-emits the coverage-map
    records cannot pass a scenario built on this unsigned artifact.
    """
    distill_dir = feature_dir / "distill"
    distill_dir.mkdir(parents=True, exist_ok=True)
    full_attestation = "\n".join(f"  - {cid}" for cid in _load_omission_class_ids())
    (distill_dir / "coverage-map.md").write_text(
        _coverage_map_body(feature_id, "_pending_", full_attestation),
        encoding="utf-8",
    )


def _load_omission_class_ids() -> list[str]:
    """Read the omission-class ids the signoff must attest from the Layer-1 SSOT.

    The ported verify core asserts the ``## Signoff`` block's
    ``omission-classes-attested:`` list covers every class-id present in
    ``nWave/data/omission-classes.json`` (cardinality-agnostic). The honest signed
    fixture attests exactly that set -- read from the SSOT so the fixture stays in
    lock-step when the class list grows (no hardcoded id list to rot).
    """
    import json  # stdlib: the omission-classes SSOT is JSON (option E)

    document = json.loads(
        (_REPO_ROOT / "nWave" / "data" / "omission-classes.json").read_text(
            encoding="utf-8"
        )
    )
    return [entry["id"] for entry in document["omission-classes"]]


def _signed_sections(feature_id: str) -> str:
    """The four FIXED §5.1 signed sections (everything before ``## Signoff``)."""
    return (
        f"# Coverage Map -- {feature_id}\n"
        "\n"
        "## Feature surface declared\n"
        "- the-feature-end-cycle-runs-the-real-coverage-map-verify\n"
        "\n"
        "## NOT covered -- and why\n"
        "_all declared surface is covered_\n"
        "\n"
        "## Known residues carried forward\n"
        "_none_\n"
        "\n"
        "## Negative-space completeness statement\n"
        "Every manifest domain is covered or listed as uncovered on its "
        "dimension row.\n"
        "\n"
    )


def _coverage_map_body(feature_id: str, digest: str, attested_block: str) -> str:
    """Render the coverage-map body with the given signoff digest + attestation."""
    return _signed_sections(feature_id) + (
        "## Signoff\n"
        "- name: Ale\n"
        "- date: 2026-06-03\n"
        f"- reviewed-content-digest: {digest}\n"
        "- role: human-signer\n"
        "- omission-classes-attested:\n"
        f"{attested_block}\n"
    )


# --- §5.3 canonicalization (test-harness copy, stdlib only) ------------------
#
# Reproduces the §5.3 7-step canonicalization the ported verify core runs
# (scripts/cli/verify_coverage_map.py:361-380 -> ported to
# src/des/application/coverage_map_verify_service), stdlib hashlib only. The
# fixture builder uses it to record a GENUINE digest over the signed body it
# writes -- the honest-signed fixture's digest matches the body by construction.
# This is TEST INFRASTRUCTURE (staging a genuinely-signed artifact), not the SUT.


def _select_signed_sections(body: str) -> str:
    """Return the four signed sections concatenated in L1 order (exclude Signoff)."""
    chunks: dict[str, str] = {}
    current_heading: str | None = None
    buffer: list[str] = []
    for line in body.split("\n"):
        if line.startswith("## "):
            if current_heading is not None:
                chunks[current_heading] = "\n".join(buffer)
            current_heading = line.rstrip()
            buffer = [current_heading]
        else:
            buffer.append(line)
    if current_heading is not None:
        chunks[current_heading] = "\n".join(buffer)
    signed = _MANDATORY_SECTIONS_IN_ORDER[:-1]  # exclude ## Signoff
    return "\n".join(chunks.get(heading, "") for heading in signed)


def _sort_feature_surface_lines(selected: str) -> str:
    """Sort domain bullet lines under ``## Feature surface declared``."""
    out_lines: list[str] = []
    in_feature_surface = False
    feature_surface_bullets: list[str] = []
    for line in selected.split("\n"):
        if line.startswith("## Feature surface declared"):
            in_feature_surface = True
            out_lines.append(line)
            continue
        if line.startswith("## ") and in_feature_surface:
            out_lines.extend(sorted(feature_surface_bullets))
            feature_surface_bullets = []
            in_feature_surface = False
            out_lines.append(line)
            continue
        if in_feature_surface and line.startswith("- "):
            feature_surface_bullets.append(line)
        else:
            out_lines.append(line)
    if in_feature_surface and feature_surface_bullets:
        out_lines.extend(sorted(feature_surface_bullets))
    return "\n".join(out_lines)


def _collapse_blank_runs(text: str) -> str:
    """Collapse blank-line runs to one; strip leading + trailing blank lines."""
    collapsed: list[str] = []
    prev_blank = False
    for line in text.split("\n"):
        if line == "":
            if not prev_blank:
                collapsed.append(line)
            prev_blank = True
        else:
            collapsed.append(line)
            prev_blank = False
    while collapsed and collapsed[0] == "":
        collapsed.pop(0)
    while collapsed and collapsed[-1] == "":
        collapsed.pop()
    return "\n".join(collapsed)


def _compute_canonical_digest(body: str) -> str:
    """§5.3 canonicalization: select signed sections + normalize + sha256."""
    selected = _select_signed_sections(body)
    selected = selected.replace("\r\n", "\n").replace("\r", "\n")
    selected = "\n".join(line.rstrip(" \t") for line in selected.split("\n"))
    selected = _collapse_blank_runs(selected)
    selected = _sort_feature_surface_lines(selected)
    return hashlib.sha256(selected.encode("utf-8")).hexdigest()


__all__ = ["write_signed_coverage_map", "write_unsigned_coverage_map"]
