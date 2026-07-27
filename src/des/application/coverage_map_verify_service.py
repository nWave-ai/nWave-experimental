"""coverage_map_verify_service -- the §5.3 coverage-map verify core, ported.

slice-04 of oss-feature-end-emit-cli (option (b) RATIFIED, Ale 2026-06-03;
DDD-8). A reuse-by-RELOCATION of the pure §5.3 coverage-map verify core from the
upstream ``scripts/cli/verify_coverage_map.py`` into ``src/des/application`` so
the feature-end-cycle use-case can run the verify IN-PROCESS (no subprocess) at
its coverage-map leg.

WHY A COPY, NOT AN IMPORT (F-D-09): ``scripts/`` is present in the dev checkout
but ABSENT from the installed ``des`` package -- a ``from scripts...`` import in
shipped ``src/des`` code is a load-time ``ImportError`` on the target machine
(``tests/build/test_des_no_dev_root_imports.py`` is the mechanical guard). So the
pure functions are COPIED here byte-for-byte. The
``tests/des/integration/test_coverage_map_verify_core_port_parity.py`` contract
test pins the relocation faithful: the ported digest EQUALS the upstream digest
for any body, is invariant under the four §5.3 normalizations, and the verdict
parity matches over the golden vectors. Drift the canonicalization and the
contract test reds -- the drift-guard working as designed.

PARAMETERIZED, NOT HARDWIRED: the upstream gate hardwired ``_DEFAULT_FEATURE_ID``
for its ledger writes. This port performs NO ledger write (the feature-end cycle
owns the heartbeat appends) and resolves the omission-classes SSOT from a
``repo_root`` parameter, so there is no feature-id constant here.

Pure Python: ``hashlib`` + ``re`` + ``json`` + ``pathlib`` only -- all stdlib,
no external imports (the omission-classes SSOT is parsed with stdlib ``json`` so
the bundled DES runtime carries zero forbidden external imports), no git, no
subprocess, no ``sys.executable``. NEVER ``scripts.*``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path


# The four §5.1 mandatory section headings plus ``## Signoff``, in fixed L1
# order. The structural check asserts every heading is present and in this
# order; the digest is computed over the first four (excluding ``## Signoff``).
#
# PUBLIC (no leading underscore): the upstream CLI ``scripts/cli/
# verify_coverage_map.py`` imports this tuple rather than repeating it --
# techdebt.md's coverage-map-verify-cli-runtime-dup row. Both callers must
# see the SAME object, or a change to one silently stops matching the other.
MANDATORY_SECTIONS_IN_ORDER: tuple[str, ...] = (
    "## Feature surface declared",
    "## NOT covered -- and why",
    "## Known residues carried forward",
    "## Negative-space completeness statement",
    "## Signoff",
)


# Repo-relative path to the Layer-1 omission-classes SSOT. The verify core
# reads this file at verify time -- the class list is DATA, not code
# (cardinality-agnostic above N=1; an empty or unparseable file is a refusal,
# RC-G1 non-empty floor, §4.1a). JSON (stdlib) is the single representation --
# no YAML, no drift surface (option E, Ale-ratified 2026-06-03).
_OMISSION_CLASSES_JSON_RELPATH = "nWave/data/omission-classes.json"


def _default_omission_classes_path() -> Path:
    """Resolve the shipped omission-classes SSOT relative to THIS package.

    The omission-classes list is a SHIPPED DATA RESOURCE (``nWave/data/``), NOT
    a per-feature artifact -- the human attests the same SSOT for every feature.
    The upstream gate resolved it relative to the SCRIPT's repo root
    (``verify_coverage_map.py:_default_omission_classes_path``,
    ``Path(__file__).resolve().parents[2]``), NOT relative to the feature root
    under verification. This port preserves that semantics: the SSOT is found
    next to the package, not under the (tmp) repo being verified.

    This module lives at ``src/des/application/coverage_map_verify_service.py``;
    ``parents[3]`` is the repo root where ``nWave/data/`` sits in the dev
    checkout, and the installed layout ships the same ``nWave/`` tree alongside.
    """
    repo_root = Path(__file__).resolve().parents[3]
    return repo_root / _OMISSION_CLASSES_JSON_RELPATH


# Pattern matching the ``- reviewed-content-digest: <hex>`` line in the
# ``## Signoff`` block. Hex is lowercase per the §5.3 contract.
_DIGEST_LINE_PATTERN = re.compile(
    r"^-\s*reviewed-content-digest:\s*([0-9a-f]+)\s*$", re.MULTILINE
)


# Refusal cause tokens -- the named cause-of-refusal a reader sees as WHY. These
# mirror the upstream tokens so the verdict parity stays observable.
_TOKEN_STRUCTURAL_INCOMPLETE = "StructuralIncomplete"
_TOKEN_SIGNOFF_STALE = "SignoffStale"
_TOKEN_MALFORMED_INPUT = "MalformedInput"
_TOKEN_SIGNOFF_MISSING = "SignoffMissing"


@dataclass(frozen=True)
class CoverageMapVerified:
    """The coverage-map passed the §5.3 verify: structure + digest + attestation."""


@dataclass(frozen=True)
class CoverageMapRefused:
    """The coverage-map failed the §5.3 verify; ``token`` names the refusal cause."""

    token: str
    message: str


def _check_structural_completeness(body: str) -> bool:
    """Return True iff every mandatory section is present and in fixed order."""
    last_index = -1
    for heading in MANDATORY_SECTIONS_IN_ORDER:
        idx = body.find(heading)
        if idx < 0 or idx <= last_index:
            return False
        last_index = idx
    return True


def _extract_recorded_digest(body: str) -> str | None:
    """Return the recorded digest hex from the ``## Signoff`` block, or None."""
    match = _DIGEST_LINE_PATTERN.search(body)
    if match is None:
        return None
    return match.group(1)


def _select_signed_sections(body: str) -> str:
    """Return the four signed sections concatenated in L1 order.

    Excludes ``## Signoff`` (cannot digest the field carrying the digest).
    Headings of unknown sections are dropped silently.
    """
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
    signed = MANDATORY_SECTIONS_IN_ORDER[:-1]  # exclude ## Signoff
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
    """§5.3 canonicalization: select signed sections + normalize + sha256.

    7-step ordered sequence:
      1. Select the four signed sections (exclude ``## Signoff``).
      2. Normalize line endings to LF.
      3. Strip trailing whitespace on every line.
      4. Collapse blank-line runs to a single blank line; strip leading
         and trailing blank lines.
      5. Sort domain lines under ``## Feature surface declared`` byte-wise
         ascending; other sections preserve order (after 2-4 normalization).
      6. Encode UTF-8 (no BOM).
      7. SHA256, lowercase hex.
    """
    selected = _select_signed_sections(body)
    selected = selected.replace("\r\n", "\n").replace("\r", "\n")
    selected = "\n".join(line.rstrip(" \t") for line in selected.split("\n"))
    selected = _collapse_blank_runs(selected)
    selected = _sort_feature_surface_lines(selected)
    return hashlib.sha256(selected.encode("utf-8")).hexdigest()


def _load_omission_class_ids(omission_classes_path: Path) -> tuple[str, ...] | None:
    """Return the class-ids declared in ``omission-classes.json``, or ``None``.

    ``None`` -- the file is absent, unreadable, or cannot be parsed as JSON
    with the expected ``omission-classes:`` list shape. The caller must treat
    ``None`` as a refusal (RC-G1 non-empty floor, §4.1a). An empty list ``[]``
    is parseable but returns an empty tuple -- the caller MUST refuse a
    zero-class file, never a vacuous zero-class pass.
    """
    if not omission_classes_path.is_file():
        return None
    try:
        text = omission_classes_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(document, dict):
        return None
    classes = document.get("omission-classes")
    if not isinstance(classes, list):
        return None
    ids: list[str] = []
    for entry in classes:
        if not isinstance(entry, dict):
            return None
        class_id = entry.get("id")
        if not isinstance(class_id, str) or not class_id.strip():
            return None
        ids.append(class_id)
    return tuple(ids)


def _extract_attested_class_ids(body: str) -> tuple[str, ...]:
    """Extract the ``omission-classes-attested:`` list from the ``## Signoff`` block.

    Returns the class-ids the human attested, in document order. Returns an
    empty tuple when the key is absent OR the value is an empty list.
    """
    in_signoff = False
    in_attested = False
    attested: list[str] = []
    for raw in body.split("\n"):
        line = raw.rstrip()
        if line.startswith("## Signoff"):
            in_signoff = True
            continue
        if line.startswith("## ") and in_signoff:
            in_signoff = False
            in_attested = False
            continue
        if not in_signoff:
            continue
        stripped = line.strip()
        if stripped.startswith("- omission-classes-attested:"):
            tail = stripped.split(":", 1)[1].strip()
            # Inline `[]` empty-list shape ends the attested block immediately;
            # any other tail opens it for the following `- <class-id>` bullets.
            in_attested = tail != "[]"
            continue
        if in_attested:
            if stripped.startswith("- "):
                attested.append(stripped[2:].strip())
                continue
            if stripped.startswith("-"):
                in_attested = False
    return tuple(attested)


def _read_coverage_map_body(coverage_map_path: Path) -> str | None:
    """Return the coverage-map body text, or ``None`` if it cannot be read.

    ``None`` covers both an absent file and a file whose bytes are not valid
    UTF-8 (a malformed coverage-map). The caller maps ``None`` to the
    appropriate refusal token.
    """
    if not coverage_map_path.is_file():
        return None
    try:
        return coverage_map_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return None


def verify_coverage_map(
    *,
    feature_root: Path,
    omission_classes_path: Path | None = None,
) -> CoverageMapVerified | CoverageMapRefused:
    """Run the §5.3 coverage-map verify; accept iff structure + digest + attestation.

    Reads ``{feature_root}/distill/coverage-map.md`` and the Layer-1
    omission-classes SSOT (``nWave/data/omission-classes.json`` resolved next to
    the package by default, override via ``omission_classes_path``), then runs
    the verify pipeline in-process:

      * absent / non-UTF-8 file  -> ``CoverageMapRefused`` (SignoffMissing /
        MalformedInput);
      * mandatory section missing or out of order -> StructuralIncomplete;
      * no ``reviewed-content-digest:`` line (``_pending_`` placeholder included,
        which the hex regex rejects) -> SignoffMissing;
      * recorded digest != recomputed §5.3 canonical digest -> SignoffStale;
      * omission-classes SSOT absent / empty / unparseable -> MalformedInput;
      * a class-id present in the SSOT not attested in ``## Signoff`` ->
        SignoffMissing;
      * otherwise -> ``CoverageMapVerified``.

    Pure: no ledger write, no subprocess, no git. The feature-end cycle owns
    the heartbeat appends on a verified verdict.
    """
    coverage_map_path = feature_root / "distill" / "coverage-map.md"
    if not coverage_map_path.is_file():
        return CoverageMapRefused(
            _TOKEN_SIGNOFF_MISSING,
            f"coverage-map at {coverage_map_path} is absent -- the human "
            "signoff has not been recorded.",
        )
    body = _read_coverage_map_body(coverage_map_path)
    if body is None:
        return CoverageMapRefused(
            _TOKEN_MALFORMED_INPUT,
            f"coverage-map at {coverage_map_path} is present but not "
            "parseable as UTF-8.",
        )
    if not _check_structural_completeness(body):
        return CoverageMapRefused(
            _TOKEN_STRUCTURAL_INCOMPLETE,
            "the coverage-map is missing a mandatory section or carries the "
            "mandatory sections out of fixed L1 order.",
        )
    recorded = _extract_recorded_digest(body)
    if recorded is None:
        return CoverageMapRefused(
            _TOKEN_SIGNOFF_MISSING,
            f"coverage-map at {coverage_map_path} is present but the "
            "## Signoff block has no `reviewed-content-digest:` line -- "
            "the human signoff has not been recorded.",
        )
    computed = _compute_canonical_digest(body)
    if computed != recorded:
        return CoverageMapRefused(
            _TOKEN_SIGNOFF_STALE,
            f"signed content has drifted from the recorded signoff digest -- "
            f"recomputed {computed} does not match recorded {recorded}.",
        )
    resolved_omission_path = (
        omission_classes_path
        if omission_classes_path is not None
        else _default_omission_classes_path()
    )
    class_ids = _load_omission_class_ids(resolved_omission_path)
    if not class_ids:
        return CoverageMapRefused(
            _TOKEN_MALFORMED_INPUT,
            f"omission-classes file at {resolved_omission_path} is absent, "
            "unreadable, empty, or not a parseable `omission-classes:` list "
            "-- the RC-G1 non-empty floor refuses a vacuous zero-class pass.",
        )
    attested = _extract_attested_class_ids(body)
    missing = tuple(cid for cid in class_ids if cid not in attested)
    if missing:
        return CoverageMapRefused(
            _TOKEN_SIGNOFF_MISSING,
            f"the `## Signoff` block's `omission-classes-attested:` list "
            f"omits {len(missing)} class-id(s) present in "
            f"{resolved_omission_path}: {', '.join(missing)}.",
        )
    return CoverageMapVerified()


__all__ = [
    "CoverageMapRefused",
    "CoverageMapVerified",
    "verify_coverage_map",
]
