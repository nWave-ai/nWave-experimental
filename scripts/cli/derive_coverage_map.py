"""Coverage-map renderer CLI.

F-DISTILL-HUMAN-SIGNOFF slices 01-02. Reads a feature's DESIGN component
manifest (``docs/feature/{id}/design/component-manifest.yaml``) and the
feature's ``.feature`` files; renders
``docs/feature/{id}/distill/[slice-NN/]coverage-map.md`` -- the human-readable
synthesis of the 15-item completeness audit the acceptance designer signs.

Driving-port contract (the SSOT slice-02 / slice-03 / slice-05 consume):

* exit ``0`` -- coverage-map rendered to the canonical path with all mandatory
  L1 §5.1 sections in order, the four mandatory dimension rows in
  ``## NOT covered -- and why``, and uncovered manifest domains routed to
  the correct dimension row via their ``canonical-category`` enum
* exit ``1`` -- the renderer refuses for a non-malformed reason: slice-02
  ``OmissionDetected`` (designer-attested not-covered list silently drops a
  manifest domain), ``CoverageMapOverCap`` (more than CAP=7 uncovered manifest
  domains), ``SignoffMissing`` (§4.2 ``not-applicable`` manifest without the
  ``manifest-not-applicable-attested:`` signoff line). Slice-04a will add
  ``TrailerMismatch``.
* exit ``2`` -- ``MalformedInput``: a ``@covers:<domain-id>`` whose ``<domain-id>``
  does not match the manifest schema pattern ``^[a-z0-9-]+$``

On any exit-1 refusal the renderer MUST NOT emit ``coverage-map.md`` -- the
refusal paths are fail-closed (no artefact written, structured cause token on
stderr).

Invocable as ``python -m scripts.cli.derive_coverage_map --feature-root <path>``.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml


# Canonical-category -> coverage-dimension row mapping (§5.1 §4.1a partition).
# The four dimension rows in ``## NOT covered -- and why`` are coarse buckets;
# each manifest entry's ``canonical-category`` enum (C2/C5/C6/C7) routes the
# domain to one row.
_DIMENSION_BY_CATEGORY: dict[str, str] = {
    "C2": "behavioural",
    "C5": "process",
    "C6": "other",
    "C7": "environmental",
}

# The four mandatory dimension rows, in fixed order (§5.1).
_DIMENSIONS_IN_ORDER: tuple[str, ...] = (
    "environmental",
    "behavioural",
    "process",
    "other",
)

# Manifest ``id:`` schema pattern (anchored to nWave/schemas/component-manifest.schema.json).
_DOMAIN_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")

# Pattern matching one ``@covers:<domain-id>`` tag on a Gherkin tag line.
# Greedy non-whitespace after the ``@covers:`` keyword so a malformed id is
# captured intact (validated separately against ``_DOMAIN_ID_PATTERN``).
_COVERS_TAG_PATTERN = re.compile(r"@covers:(\S+)")

# Slice-02: lean cap on the not-covered surface. A coverage-map a human cannot
# evaluate in one sitting is itself a defect signal (§5.4 / §6.3 step 3a). The
# producer refuses with ``CoverageMapOverCap`` when (manifest \\ @covers:-tagged)
# exceeds this count.
_CAP: int = 7

# Slice-02 refusal token literals (the structured cause-of-refusal SSOT the
# CLI emits on stderr alongside exit 1). The exit code is the gate; the token
# is the named cause-of-refusal -- the future reader sees WHY.
_TOKEN_OMISSION_DETECTED = "OmissionDetected"
_TOKEN_COVERAGE_MAP_OVER_CAP = "CoverageMapOverCap"
_TOKEN_SIGNOFF_MISSING = "SignoffMissing"

# Slice-02: marker line a human signoff must carry for a §4.2 not-applicable
# manifest to render a degenerate coverage-map (fail-functional, not fail-skip).
_NOT_APPLICABLE_ATTESTED_KEY = "manifest-not-applicable-attested:"


def _read_manifest(feature_root: Path) -> dict | None:
    """Return the parsed component-manifest YAML, or None if absent."""
    manifest_path = feature_root / "design" / "component-manifest.yaml"
    if not manifest_path.is_file():
        return None
    return yaml.safe_load(manifest_path.read_text(encoding="utf-8"))


def _collect_manifest_domains(
    manifest: dict,
) -> list[tuple[str, str]]:
    """Return [(domain-id, dimension)] for every ``unbounded-input-domains`` entry.

    The dimension is the §5.1 partition row computed from the entry's
    ``canonical-category`` enum (C2/C5/C6/C7) via ``_DIMENSION_BY_CATEGORY``.
    """
    entries = manifest.get("unbounded-input-domains") or []
    domains: list[tuple[str, str]] = []
    for entry in entries:
        domain_id = entry.get("id", "")
        category = entry.get("canonical-category", "")
        dimension = _DIMENSION_BY_CATEGORY.get(category, "other")
        domains.append((domain_id, dimension))
    return domains


def _scan_covers_tags(feature_root: Path) -> tuple[set[str], list[str]]:
    """Scan every ``.feature`` file under ``feature_root`` for ``@covers:`` tags.

    Returns ``(covered_domain_ids, malformed_ids)``. The §4.1b binding:

    * A ``@covers:`` tag on a ``Feature:`` line is IGNORED -- only the
      scenario tag line (the line directly above ``Scenario:`` /
      ``Scenario Outline:``) binds a domain to an AT.
    * A ``Scenario Outline`` covers its domain once regardless of how many
      ``Examples:`` rows expand from it (coverage is binary per domain).
    * Multiple ``@covers:`` tags may share one tag line (whitespace-separated).
    * A ``@covers:<domain-id>`` whose ``<domain-id>`` does not match
      ``^[a-z0-9-]+$`` is malformed -- returned in ``malformed_ids`` so the
      caller can fail-closed with exit 2 (``MalformedInput``).
    """
    covered: set[str] = set()
    malformed: list[str] = []
    for feature_file in sorted(feature_root.rglob("*.feature")):
        lines = feature_file.read_text(encoding="utf-8").splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if "@covers:" not in stripped:
                continue
            # A tag line binds to the next non-blank, non-tag line. If that
            # next line begins with ``Feature:`` the tag is on the Feature
            # line and must be ignored per §4.1b placement rule.
            if not _is_scenario_tag_line(lines, index):
                continue
            for tag_id in _COVERS_TAG_PATTERN.findall(stripped):
                if _DOMAIN_ID_PATTERN.match(tag_id):
                    covered.add(tag_id)
                else:
                    malformed.append(tag_id)
    return covered, malformed


def _is_scenario_tag_line(lines: list[str], index: int) -> bool:
    """Return True iff the tag line at ``index`` precedes a ``Scenario`` keyword.

    Tag lines that precede the ``Feature:`` keyword are ignored per §4.1b
    (a feature-level tag is too coarse to bind a specific AT to a domain).
    """
    for following in lines[index + 1 :]:
        token = following.strip()
        if not token:
            continue
        if token.startswith("@"):
            # Another tag line -- keep walking until we find a keyword.
            continue
        return token.startswith("Scenario:") or token.startswith("Scenario Outline:")
    return False


def _render_feature_surface(domains: list[tuple[str, str]]) -> str:
    """Render the ``## Feature surface declared`` section body.

    One line per declared manifest domain; domain-id + dimension annotation.
    """
    if not domains:
        return "_no declared domains_\n"
    lines = []
    for domain_id, dimension in sorted(domains):
        lines.append(f"- `{domain_id}` ({dimension})")
    return "\n".join(lines) + "\n"


def _render_not_covered_table(
    uncovered_by_dimension: dict[str, list[str]],
) -> str:
    """Render the ``## NOT covered -- and why`` Markdown table.

    The four mandatory dimension rows are ALWAYS present in fixed order; a
    dimension with nothing uncovered carries the literal ``none`` -- it is
    never omitted (§5.1 -- the present-but-empty row is the structural device
    that makes an omission visible).
    """
    header = (
        "| Dimension | What is NOT covered | Why accepted | Residue? owner+bound |\n"
        "|-----------|---------------------|--------------|----------------------|\n"
    )
    rows = []
    for dimension in _DIMENSIONS_IN_ORDER:
        uncovered = uncovered_by_dimension.get(dimension, [])
        if not uncovered:
            cell = "none"
            why = "fully covered"
        else:
            cell = ", ".join(f"`{did}`" for did in sorted(uncovered))
            why = "_ATD attestation pending_"
        rows.append(f"| {dimension} | {cell} | {why} | no |")
    return header + "\n".join(rows) + "\n"


def _render_coverage_map(
    feature_id: str,
    domains: list[tuple[str, str]],
    covered_ids: set[str],
) -> str:
    """Render the full coverage-map Markdown body (§5.1 mandatory section set)."""
    uncovered_by_dimension: dict[str, list[str]] = {
        dimension: [] for dimension in _DIMENSIONS_IN_ORDER
    }
    for domain_id, dimension in domains:
        if domain_id not in covered_ids:
            uncovered_by_dimension[dimension].append(domain_id)

    feature_surface = _render_feature_surface(domains)
    not_covered_table = _render_not_covered_table(uncovered_by_dimension)
    return (
        f"# Coverage Map -- {feature_id}\n"
        "\n"
        "## Feature surface declared\n"
        f"{feature_surface}\n"
        "## NOT covered -- and why\n"
        f"{not_covered_table}\n"
        "## Known residues carried forward\n"
        "_none_\n"
        "\n"
        "## Negative-space completeness statement\n"
        "The four dimension rows above jointly exhaust the declared surface; "
        "every manifest domain is either covered by an `@covers:` tag or "
        "listed as uncovered on its dimension row.\n"
        "\n"
        "## Signoff\n"
        "- name: _pending_\n"
        "- date: _pending_\n"
        "- reviewed-content-digest: _pending_\n"
        "- role: _pending_\n"
    )


def _infer_feature_id(feature_root: Path, manifest: dict | None) -> str:
    """Resolve the feature identifier (manifest ``feature-id:`` or dirname)."""
    if manifest:
        manifest_id = manifest.get("feature-id")
        if isinstance(manifest_id, str) and manifest_id:
            return manifest_id
    return feature_root.name


def _read_attestation_listed_ids(feature_root: Path) -> set[str] | None:
    """Return the designer-attested not-covered domain-id set, or None if absent.

    Slice-02 step 3 (§4 / §6.3): the renderer reads
    ``distill/not-covered-attestation.md`` as the designer's SSOT for "what is
    not covered". When the file is absent, the renderer auto-lists every
    uncovered manifest domain (slice-01 fallback -- no anti-omission check
    fires). When the file is present, the renderer compares the attested set
    against (manifest \\ @covers:-tagged); any uncovered manifest domain
    missing from the attested set is the silent drop the §4 step-2 check
    refuses with ``OmissionDetected``.

    The file format is human-readable Markdown -- the listed domain ids are
    bullet items (``- <domain-id>``). The parser is deliberately lenient:
    it extracts any token following ``- `` on a single line.
    """
    attestation_path = feature_root / "distill" / "not-covered-attestation.md"
    if not attestation_path.is_file():
        return None
    listed: set[str] = set()
    for raw_line in attestation_path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("- "):
            continue
        token = stripped[2:].strip()
        # Skip any token carrying a colon (an attestation header / key line).
        if ":" in token:
            continue
        listed.add(token)
    return listed


def _signoff_has_not_applicable_attestation(feature_root: Path) -> bool:
    """Return True iff the human signoff carries the §4.2 attestation line.

    The line is the new mandatory ``## Signoff`` field added by §4.2:
    ``manifest-not-applicable-attested: <human> <date>``. Its presence is
    the proof the human looked at -- and co-signed -- the not-applicable
    judgment (neither brick nor bypass). An absent signoff file is treated
    as "no attestation" -- the §4.2 contract refuses fail-closed (no two-gate
    bypass).
    """
    signoff_path = feature_root / "distill" / "signoff.md"
    if not signoff_path.is_file():
        return False
    return _NOT_APPLICABLE_ATTESTED_KEY in signoff_path.read_text(encoding="utf-8")


def _render_not_applicable_coverage_map(
    feature_id: str, not_applicable_rationale: str
) -> str:
    """Render the §4.2 degenerate coverage-map.

    Carries the verbatim ``not-applicable`` marker text + rationale on the
    feature-surface section, the four mandatory dimension-rows each ``none``,
    and a Signoff block that refers the human attestation to ``signoff.md``
    -- the producer does NOT mint the attestation line itself; it only emits
    the artefact the human has already attested.
    """
    not_covered_table = _render_not_covered_table(
        {dimension: [] for dimension in _DIMENSIONS_IN_ORDER}
    )
    return (
        f"# Coverage Map -- {feature_id}\n"
        "\n"
        "## Feature surface declared\n"
        f"not-applicable: {not_applicable_rationale}\n"
        "\n"
        "## NOT covered -- and why\n"
        f"{not_covered_table}\n"
        "## Known residues carried forward\n"
        "_none_\n"
        "\n"
        "## Negative-space completeness statement\n"
        "This feature carries the `not-applicable` marker (§4.2 fail-functional "
        "branch); the human signoff attests the marker is a genuine "
        "finite-SUT / legacy claim, not an omission dodge.\n"
        "\n"
        "## Signoff\n"
        "- see signoff.md (carries `manifest-not-applicable-attested:` per §4.2)\n"
    )


def _print_refusal(token: str, message: str) -> None:
    """Emit a structured refusal line on stderr (exit-code-paired with caller)."""
    print(f"derive_coverage_map: {token}: {message}", file=sys.stderr)


def _write_coverage_map(distill_dir: Path, body: str) -> None:
    """Write the coverage-map artefact to its canonical distill path."""
    distill_dir.mkdir(parents=True, exist_ok=True)
    (distill_dir / "coverage-map.md").write_text(body, encoding="utf-8")


def _handle_not_applicable_branch(
    feature_root: Path,
    manifest: dict,
    feature_id: str,
    distill_dir: Path,
) -> int | None:
    """§4.2 not-applicable branch (slice-02 step 0).

    Returns the process exit code when the manifest carries the
    ``not-applicable:`` marker; ``None`` when the manifest is on the normal
    anti-omission path (caller continues).
    """
    not_applicable_rationale = manifest.get("not-applicable")
    if not (isinstance(not_applicable_rationale, str) and not_applicable_rationale):
        return None
    if not _signoff_has_not_applicable_attestation(feature_root):
        _print_refusal(
            _TOKEN_SIGNOFF_MISSING,
            "the manifest carries `not-applicable:` but the human signoff "
            f"({feature_root / 'distill' / 'signoff.md'}) is absent or missing "
            f"the `{_NOT_APPLICABLE_ATTESTED_KEY}` line.",
        )
        return 1
    body = _render_not_applicable_coverage_map(feature_id, not_applicable_rationale)
    _write_coverage_map(distill_dir, body)
    return 0


def _check_cap(uncovered_ids: set[str]) -> int | None:
    """§6.3 step 3a -- refuse a coverage-map whose not-covered surface > CAP."""
    if len(uncovered_ids) <= _CAP:
        return None
    _print_refusal(
        _TOKEN_COVERAGE_MAP_OVER_CAP,
        f"{len(uncovered_ids)} uncovered manifest domains exceed the lean cap "
        f"of {_CAP}; a human cannot evaluate this surface in one sitting -- "
        "shrink the surface or split the feature.",
    )
    return 1


def _check_anti_omission(feature_root: Path, uncovered_ids: set[str]) -> int | None:
    """§4 step 2 / §6.3 step 3 -- refuse a designer attestation that silently
    drops an uncovered manifest domain. No attestation file -> slice-01
    fallback (caller auto-lists every uncovered domain)."""
    attested_ids = _read_attestation_listed_ids(feature_root)
    if attested_ids is None:
        return None
    dropped = uncovered_ids - attested_ids
    if not dropped:
        return None
    _print_refusal(
        _TOKEN_OMISSION_DETECTED,
        "the designer's not-covered attestation silently drops manifest "
        f"domain(s) {sorted(dropped)!r}; every uncovered manifest domain "
        "MUST appear in the attestation file or in `@covers:` tags.",
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    """Render the coverage-map for one feature; return the process exit code."""
    parser = argparse.ArgumentParser(
        prog="derive_coverage_map",
        description="Render docs/feature/{id}/distill/coverage-map.md.",
    )
    parser.add_argument(
        "--feature-root",
        required=True,
        help="Path to docs/feature/{id}/ -- the feature project root.",
    )
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    feature_root = Path(args.feature_root)
    manifest = _read_manifest(feature_root) or {}
    feature_id = _infer_feature_id(feature_root, manifest)
    distill_dir = feature_root / "distill"

    # Step 0 (§4.2 not-applicable branch).
    not_applicable_exit = _handle_not_applicable_branch(
        feature_root, manifest, feature_id, distill_dir
    )
    if not_applicable_exit is not None:
        return not_applicable_exit

    domains = _collect_manifest_domains(manifest)
    covered_ids, malformed_ids = _scan_covers_tags(feature_root)
    if malformed_ids:
        _print_refusal(
            "MalformedInput",
            "malformed @covers: domain-id(s): "
            + ", ".join(repr(mid) for mid in malformed_ids),
        )
        return 2

    uncovered_ids = {
        domain_id for domain_id, _ in domains if domain_id not in covered_ids
    }

    # Step 3a (CAP) then step 3 (anti-omission) -- both fail-closed,
    # NO artefact emitted on refusal.
    cap_exit = _check_cap(uncovered_ids)
    if cap_exit is not None:
        return cap_exit
    omission_exit = _check_anti_omission(feature_root, uncovered_ids)
    if omission_exit is not None:
        return omission_exit

    body = _render_coverage_map(feature_id, domains, covered_ids)
    _write_coverage_map(distill_dir, body)
    return 0


if __name__ == "__main__":  # pragma: no cover -- direct CLI invocation only
    sys.exit(main(sys.argv[1:]))
