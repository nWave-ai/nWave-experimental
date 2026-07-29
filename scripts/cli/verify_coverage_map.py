"""verify_coverage_map -- read-side gate CLI for the human sign-off.

F-DISTILL-HUMAN-SIGNOFF slice-03 + slice-04. The gate consumes the slice-01/02
output (a rendered + signed ``docs/feature/{id}/distill/coverage-map.md``) and
emits a verdict:

  * exit 0          -- accepted (structure OK, digest matches, trailer matches
                       if present).
  * exit 1 + ``StructuralIncomplete`` -- mandatory section missing or out of
                        order.
  * exit 1 + ``SignoffStale`` -- post-signoff body edit detected (the §5.3
                        canonical-content digest no longer matches the value
                        recorded in the ``## Signoff`` block / sidecar).
  * exit 1 + ``TrailerMismatch`` -- the commit-trailer file (if present)
                        diverges from the trailer the §6.1 projection re-derives
                        from the ``## Signoff`` block (slice-04).
  * exit 2 + ``MalformedInput`` -- coverage-map / manifest / ledger cannot be
                        parsed.

Subcommands:
  * ``verify --feature-root <path>``                 -- the gate verdict.
  * ``digest-golden-fixture --input <raw>``          -- §5.3 G4 cross-tree
                                                        canonicalization
                                                        conformance probe;
                                                        prints lowercase hex
                                                        sha256 to stdout.
  * ``emit-trailer --feature-root <path>``           -- §6.1 mechanical
                                                        projection of the
                                                        ``## Signoff`` block
                                                        onto the commit
                                                        trailer; also appends
                                                        a ``CoverageMapSignedOff``
                                                        record to the AT-
                                                        completion ledger
                                                        (slice-04).

The §5.3 canonicalization algorithm reproduced here is the SSOT of what the
verify gate computes; the composition root's reference implementation must
agree byte-for-byte (AT3 row f -- the golden-fixture probe).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

from des.adapters.driven.ledger.coverage_map_signoff_writer import (
    emit_trailer_from_signoff_block,
    write_coverage_map_signed_off,
)
from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.application.coverage_map_verify_service import (
    MANDATORY_SECTIONS_IN_ORDER as _MANDATORY_SECTIONS_IN_ORDER,
)
from des.cli.human_surface import Verdict, print_human_summary


# Slice-06 touchpoint dispatch table -- maps the CLI `--touchpoint` value to
# the AtCompletionLedger heartbeat-append method invoked on a passing verdict.
_TOUCHPOINT_HEARTBEAT_DISPATCH = {
    "distill_exit": "append_coverage_map_verified_at_distill_exit",
    "deliver_exit": "append_coverage_map_verified_at_deliver_exit",
}


def _emit_touchpoint_heartbeat(touchpoint: str, project_root: Path) -> None:
    """Append the per-touchpoint heartbeat record to the AT-completion ledger.

    Slice-06 hook-only wiring (Ale 2026-05-24 standing -- nwave-dev has NO
    sequencer / NO engine, ONLY hooks). The U4 SubagentStop enforcer is the
    consumer that turns a missing heartbeat into a feature-end block,
    mirroring the env-e2e + walking-skeleton 5th-sibling pattern.
    """
    method_name = _TOUCHPOINT_HEARTBEAT_DISPATCH[touchpoint]
    ledger = AtCompletionLedger(_DEFAULT_FEATURE_ID, project_root)
    getattr(ledger, method_name)()


# _MANDATORY_SECTIONS_IN_ORDER is imported above from
# des.application.coverage_map_verify_service -- techdebt.md's
# coverage-map-verify-cli-runtime-dup row: this CLI used to redefine the same
# tuple, which could silently drift from the ported service core.


# Refusal tokens -- the structured cause-of-refusal SSOT the CLI emits on
# stderr alongside the exit code. The exit code is the gate; the token is the
# named cause-of-refusal the future reader sees as WHY.
_TOKEN_STRUCTURAL_INCOMPLETE = "StructuralIncomplete"
_TOKEN_SIGNOFF_STALE = "SignoffStale"
_TOKEN_MALFORMED_INPUT = "MalformedInput"
_TOKEN_TRAILER_MISMATCH = "TrailerMismatch"
_TOKEN_SIGNOFF_MISSING = "SignoffMissing"
_TOKEN_OMISSION_DETECTED = "OmissionDetected"


# Slice-06 touchpoint vocabulary -- the `--touchpoint` flag accepts these two
# values; each value routes to its own heartbeat ledger event. The U4
# SubagentStop enforcer (and its verify_deliver_integrity CLI mirror) is the
# consumer that turns a missing heartbeat into a feature-end block.
_TOUCHPOINT_DISTILL_EXIT = "distill_exit"
_TOUCHPOINT_DELIVER_EXIT = "deliver_exit"


# Manifest domain-id schema pattern (anchored to nWave/schemas/component-manifest.schema.json).
_DOMAIN_ID_PATTERN = re.compile(r"^[a-z0-9-]+$")

# Pattern matching one ``@covers:<domain-id>`` tag on a Gherkin tag line (§4.1b).
_COVERS_TAG_PATTERN = re.compile(r"@covers:(\S+)")


# Default feature-id keyed by the AT-completion ledger writer (slice-04). The
# acceptance fixture's tmp_path feature root is feature-id-scoped via this
# constant; the production callers (hooks) supply the same id.
_DEFAULT_FEATURE_ID = "fix-distill-human-signoff"


# Repo-relative path to the Layer-1 omission-classes import (slice-05). The
# verify gate reads this file at verify time -- the class list is DATA, not
# code (cardinality-agnostic above N=1; an empty or unparseable file is
# MalformedInput exit 2, RC-G1 non-empty floor, §4.1a). JSON (stdlib) is the
# single representation -- no YAML, no drift surface (option E).
_DEFAULT_OMISSION_CLASSES_JSON_RELPATH = "nWave/data/omission-classes.json"


# Pattern matching the ``- reviewed-content-digest: <hex>`` line in the
# ``## Signoff`` block. Hex is lowercase per the §5.3 contract.
_DIGEST_LINE_PATTERN = re.compile(
    r"^-\s*reviewed-content-digest:\s*([0-9a-f]+)\s*$", re.MULTILINE
)


def _print_refusal(token: str, message: str) -> None:
    """Emit a structured refusal line + human-readable FAIL line on stderr."""
    print(f"verify_coverage_map: {token}: {message}", file=sys.stderr)
    print_human_summary(
        Verdict.FAIL,
        f"coverage-map verification failed ({token}): {message}",
    )


class _CoverageMapReadResult:
    """One read-classification of the coverage-map under inspection.

    Three disjoint shapes:
      * ``body`` -- the file exists and parsed as UTF-8 successfully.
      * ``ABSENT`` -- the file does not exist on disk (SignoffMissing exit 1).
      * ``MALFORMED`` -- the file exists but cannot be parsed as UTF-8
        (MalformedInput exit 2).
    The two refusal classes share no payload; they are sentinel singletons.
    """

    ABSENT = "absent"
    MALFORMED = "malformed"


def _read_coverage_map(coverage_map_path: Path) -> str | None:
    """Return the coverage-map body text, or ``None`` if it cannot be parsed.

    Backwards-compatible legacy entry point (kept for slice-03/04/05 call-
    sites that did not need to distinguish absent-vs-malformed). New
    slice-06 logic uses ``_classify_coverage_map_read`` instead.
    """
    classified = _classify_coverage_map_read(coverage_map_path)
    if classified in (_CoverageMapReadResult.ABSENT, _CoverageMapReadResult.MALFORMED):
        return None
    return classified


def _classify_coverage_map_read(coverage_map_path: Path) -> str:
    """Return the coverage-map body OR a sentinel from ``_CoverageMapReadResult``.

    Slice-06: the DISTILL-exit refusal token differs between
    ``ABSENT`` (SignoffMissing exit 1) and ``MALFORMED`` (MalformedInput
    exit 2). The caller routes to the appropriate refusal token.
    """
    if not coverage_map_path.is_file():
        return _CoverageMapReadResult.ABSENT
    try:
        return coverage_map_path.read_text(encoding="utf-8")
    except (FileNotFoundError, UnicodeDecodeError):
        return _CoverageMapReadResult.MALFORMED


def _check_structural_completeness(body: str) -> bool:
    """Return True iff every mandatory section is present and in fixed order."""
    last_index = -1
    for heading in _MANDATORY_SECTIONS_IN_ORDER:
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


def _load_omission_class_ids(omission_classes_path: Path) -> tuple[str, ...] | None:
    """Return the class-ids declared in `omission-classes.json`, or ``None``.

    ``None`` -- the file is absent, unreadable, or cannot be parsed as JSON
    with the expected `omission-classes:` list shape. The caller must treat
    ``None`` as `MalformedInput` exit 2 (RC-G1 non-empty floor, §4.1a).

    An empty list `[]` is parseable but returns an empty tuple -- the
    caller MUST refuse a zero-class file with `MalformedInput`, never a
    vacuous zero-class pass.
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
    """Extract the `omission-classes-attested:` list from the `## Signoff` block.

    Returns the class-ids the human attested, in document order. The list
    is parsed as a YAML sub-document so the shape contract is the same as
    the imported list -- `- <class-id>` bullets under the
    `omission-classes-attested:` key.

    Returns an empty tuple when the key is absent OR the value is an empty
    list. The caller distinguishes "absent" from "present-but-empty" via
    the presence of the `- omission-classes-attested:` line itself, which
    the slice-05 contract requires alongside any non-vacuous signoff.
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
            # Inline `[]` empty-list shape.
            tail = stripped.split(":", 1)[1].strip()
            in_attested = tail != "[]"
            continue
        if in_attested:
            if stripped.startswith("- "):
                attested.append(stripped[2:].strip())
                continue
            if stripped.startswith("-"):
                # Another top-level signoff field -- end of attested block.
                in_attested = False
    return tuple(attested)


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


def _commit_trailer_path(feature_root: Path) -> Path:
    """The mock commit-trailer file the verify gate compares against (slice-04)."""
    return feature_root / "distill" / "commit-trailer.txt"


def _default_omission_classes_path() -> Path:
    """Repo-rooted default path for `omission-classes.json`.

    Resolved relative to this file's location so the gate is portable
    across cwd (hook invocation context). Tests override via the
    `--omission-classes-json` CLI flag to a per-test substitute under
    tmp_path.
    """
    # scripts/cli/verify_coverage_map.py -> parents[2] = repo root.
    repo_root = Path(__file__).resolve().parents[2]
    return repo_root / _DEFAULT_OMISSION_CLASSES_JSON_RELPATH


def _verify(
    feature_root: Path,
    omission_classes_path: Path,
    touchpoint: str | None = None,
) -> int:
    """Run the verify-gate verdict pipeline; return the process exit code.

    Slice-06: when ``touchpoint`` is supplied (``distill_exit`` or
    ``deliver_exit``), the gate appends a heartbeat record to the AT-completion
    ledger on a passing verdict. The DELIVER-exit branch ALSO re-runs the
    anti-omission set-difference against the live `.feature` `@covers:` tags
    so an AT dropped during DELIVER (digest-invisible body change) is caught
    via ``OmissionDetected`` exit 1 (G2 second sensor, §6.4).
    """
    coverage_map_path = feature_root / "distill" / "coverage-map.md"
    classified = _classify_coverage_map_read(coverage_map_path)
    if classified == _CoverageMapReadResult.ABSENT:
        _print_refusal(
            _TOKEN_SIGNOFF_MISSING,
            f"coverage-map at {coverage_map_path} is absent -- the human "
            "signoff has not been recorded.",
        )
        return 1
    if classified == _CoverageMapReadResult.MALFORMED:
        _print_refusal(
            _TOKEN_MALFORMED_INPUT,
            f"coverage-map at {coverage_map_path} is present but not "
            "parseable as UTF-8.",
        )
        return 2
    body = classified
    if not _check_structural_completeness(body):
        _print_refusal(
            _TOKEN_STRUCTURAL_INCOMPLETE,
            "the coverage-map is missing a mandatory section or carries the "
            "mandatory sections out of fixed L1 order.",
        )
        return 1
    recorded = _extract_recorded_digest(body)
    if recorded is None:
        _print_refusal(
            _TOKEN_SIGNOFF_MISSING,
            f"coverage-map at {coverage_map_path} is present but the "
            "## Signoff block has no `reviewed-content-digest:` line -- "
            "the human signoff has not been recorded.",
        )
        return 1
    computed = _compute_canonical_digest(body)
    if computed != recorded:
        _print_refusal(
            _TOKEN_SIGNOFF_STALE,
            f"signed content has drifted from the recorded signoff digest -- "
            f"recomputed {computed} does not match recorded {recorded}.",
        )
        return 1
    # Slice-05: read the Layer-1 omission-classes import; RC-G1 non-empty
    # floor (§4.1a) -- an absent / unparseable / empty file is MalformedInput
    # exit 2, NEVER a vacuous zero-class pass. Then assert the `## Signoff`
    # block's `omission-classes-attested:` list covers every class-id
    # present in the import (cardinality-agnostic, N classes not 6).
    class_ids = _load_omission_class_ids(omission_classes_path)
    if class_ids is None:
        _print_refusal(
            _TOKEN_MALFORMED_INPUT,
            f"omission-classes file at {omission_classes_path} is absent, "
            f"unreadable, or not a parseable `omission-classes:` list.",
        )
        return 2
    if len(class_ids) == 0:
        _print_refusal(
            _TOKEN_MALFORMED_INPUT,
            f"omission-classes file at {omission_classes_path} declares zero "
            f"class-ids -- the RC-G1 non-empty floor refuses a vacuous "
            f"zero-class pass.",
        )
        return 2
    attested = _extract_attested_class_ids(body)
    missing = tuple(cid for cid in class_ids if cid not in attested)
    if missing:
        _print_refusal(
            _TOKEN_SIGNOFF_MISSING,
            f"the `## Signoff` block's `omission-classes-attested:` list "
            f"omits {len(missing)} class-id(s) present in "
            f"{omission_classes_path}: {', '.join(missing)}.",
        )
        return 1
    # Slice-04: when a commit-trailer file is present alongside the coverage-
    # map, the trailer it carries MUST match the §6.1 mechanical projection of
    # the ``## Signoff`` block. A divergent (hand-edited) trailer is refused
    # with ``TrailerMismatch`` exit 1. If no trailer file exists, the slice-03
    # contract is preserved (no trailer check).
    trailer_path = _commit_trailer_path(feature_root)
    if trailer_path.is_file():
        on_disk = trailer_path.read_text(encoding="utf-8").rstrip()
        projected = emit_trailer_from_signoff_block(coverage_map_path)
        if on_disk != projected:
            _print_refusal(
                _TOKEN_TRAILER_MISMATCH,
                f"commit trailer at {trailer_path} diverges from the §6.1 "
                f"projection of the ## Signoff block.",
            )
            return 1
    # Slice-06 G2 second sensor (DELIVER-exit only, §6.4): re-run the anti-
    # omission set-difference against the live `.feature` `@covers:` tags so
    # an AT dropped during DELIVER (a `.feature` AT-population change that
    # leaves the coverage-map body untouched -- digest-invisible) is caught
    # here. DISTILL-exit does NOT run this re-check; the post-DISTILL anti-
    # omission verdict is the responsibility of `derive_coverage_map`.
    if touchpoint == _TOUCHPOINT_DELIVER_EXIT:
        anti_omission_exit = _run_anti_omission_recheck(feature_root)
        if anti_omission_exit != 0:
            return anti_omission_exit
    # Slice-06 hook-only wiring: emit the per-touchpoint heartbeat on pass.
    # The U4 SubagentStop enforcer (and verify_deliver_integrity CLI mirror)
    # is the consumer that turns a missing heartbeat into a feature-end block.
    if touchpoint is not None:
        _emit_touchpoint_heartbeat(touchpoint, feature_root.parent)
    print_human_summary(
        Verdict.PASS,
        f"coverage-map at {coverage_map_path} verified",
    )
    return 0


def _run_anti_omission_recheck(feature_root: Path) -> int:
    """Slice-06 DELIVER-exit G2 sensor: re-run the anti-omission set-difference.

    Reads the live ``.feature`` ``@covers:`` tags + the component manifest
    ``unbounded-input-domains`` set; refuses with ``OmissionDetected`` exit 1
    when a manifest domain is no longer covered by any `@covers:` tag.

    The body-edit sensor (``SignoffStale``) catches coverage-map body edits;
    this re-run catches `.feature` AT-population changes -- two distinct
    sensors, two distinct exit names (§6.4 two-sensor contract).
    """
    manifest_path = feature_root / "design" / "component-manifest.yaml"
    if not manifest_path.is_file():
        # No manifest under the feature root -- nothing to anti-omission-check.
        # Treat as pass: the DISTILL-exit branch caught a missing manifest if
        # it mattered; here we are only re-checking ALREADY-signed coverage.
        return 0
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        _print_refusal(
            _TOKEN_MALFORMED_INPUT,
            f"component-manifest at {manifest_path} is absent or not "
            "parseable as YAML.",
        )
        return 2
    if not isinstance(manifest, dict):
        return 0  # An empty/scalar manifest -- nothing to check.
    if manifest.get("not-applicable"):
        # State-C not-applicable: no anti-omission re-check applies (§4.2).
        return 0
    entries = manifest.get("unbounded-input-domains") or []
    if not isinstance(entries, list):
        return 0
    manifest_domain_ids = {
        entry.get("id", "")
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    }
    if not manifest_domain_ids:
        return 0  # State-B empty-pending -- DISTILL-exit handled it.
    covered_ids = _scan_covers_tags(feature_root)
    uncovered = manifest_domain_ids - covered_ids
    if uncovered:
        _print_refusal(
            _TOKEN_OMISSION_DETECTED,
            f"DELIVER-exit anti-omission re-run: {len(uncovered)} manifest "
            f"domain(s) no longer covered by any `@covers:` tag -- an "
            f"acceptance scenario was dropped during DELIVER: "
            f"{', '.join(sorted(uncovered))}.",
        )
        return 1
    return 0


def _scan_covers_tags(feature_root: Path) -> set[str]:
    """Return the set of manifest domain-ids covered by `@covers:` tags.

    Mirrors the §4.1b binding from `derive_coverage_map._scan_covers_tags` --
    scan every `.feature` file under `feature_root`, emit only well-formed
    domain-ids (matching the manifest schema pattern). Malformed ids are
    silently skipped here (the slice-01/02 derive path is the place to fail-
    closed on malformed tags; this slice-06 re-check is only an omission
    detector).
    """
    covered: set[str] = set()
    # gherkin-scope: same `@covers:` colon-syntax as derive_coverage_map.py
    # (no pytest-side parser anywhere) -- see that module's marker.
    for feature_file in sorted(feature_root.rglob("*.feature")):
        try:
            lines = feature_file.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):
            continue
        for index, line in enumerate(lines):
            stripped = line.strip()
            if "@covers:" not in stripped:
                continue
            if not _is_scenario_tag_line(lines, index):
                continue
            for tag_id in _COVERS_TAG_PATTERN.findall(stripped):
                if _DOMAIN_ID_PATTERN.match(tag_id):
                    covered.add(tag_id)
    return covered


def _is_scenario_tag_line(lines: list[str], index: int) -> bool:
    """Return True iff the tag line at `index` precedes a `Scenario` keyword."""
    for following in lines[index + 1 :]:
        token = following.strip()
        if not token:
            continue
        if token.startswith("@"):
            continue
        return token.startswith("Scenario:") or token.startswith("Scenario Outline:")
    return False


def _digest_golden_fixture(input_path: Path) -> int:
    """Compute + print the §5.3 canonical-content digest for a golden fixture."""
    body = input_path.read_text(encoding="utf-8")
    digest = _compute_canonical_digest(body)
    print(digest)
    return 0


def _emit_trailer(feature_root: Path) -> int:
    """Print the §6.1 projected trailer + append a ``CoverageMapSignedOff`` record.

    Slice-04 driving port. The trailer is mechanically projected from the
    ``## Signoff`` block (NEVER hand-authored); the ledger record binds the
    block + the trailer + the ledger event to ONE identity (the §5.3 digest).
    """
    coverage_map_path = feature_root / "distill" / "coverage-map.md"
    trailer_line = emit_trailer_from_signoff_block(coverage_map_path)
    print(trailer_line)
    project_root = feature_root.parent
    write_coverage_map_signed_off(
        feature_id=_DEFAULT_FEATURE_ID,
        project_root=project_root,
        coverage_map_path=coverage_map_path,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry: dispatch to ``verify`` / ``digest-golden-fixture`` / ``emit-trailer``."""
    parser = argparse.ArgumentParser(
        prog="verify_coverage_map",
        description="Verify a signed coverage-map / probe canonicalization / emit trailer.",
    )
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    verify_parser = subparsers.add_parser(
        "verify", help="Verify a signed coverage-map at a feature root."
    )
    verify_parser.add_argument(
        "--feature-root",
        required=True,
        help="Path to docs/feature/{id}/ -- the feature project root.",
    )
    verify_parser.add_argument(
        "--omission-classes-json",
        required=False,
        default=None,
        help=(
            "Path to the Layer-1 `omission-classes.json` (slice-05). Defaults "
            "to `nWave/data/omission-classes.json` relative to the repo root."
        ),
    )
    verify_parser.add_argument(
        "--touchpoint",
        required=False,
        default=None,
        choices=(_TOUCHPOINT_DISTILL_EXIT, _TOUCHPOINT_DELIVER_EXIT),
        help=(
            "Slice-06: the touchpoint at which the gate is running. On a "
            "passing verdict the gate appends the per-touchpoint heartbeat "
            "record to the AT-completion ledger (CoverageMapVerifiedAtDistillExit "
            "or CoverageMapVerifiedAtDeliverExit). The DELIVER-exit branch "
            "ALSO re-runs the anti-omission set-difference (G2 second sensor)."
        ),
    )

    golden_parser = subparsers.add_parser(
        "digest-golden-fixture",
        help="Compute the §5.3 canonical-content digest for a raw input.",
    )
    golden_parser.add_argument(
        "--input",
        required=True,
        help="Path to the golden raw coverage-map body (without ## Signoff).",
    )

    emit_parser = subparsers.add_parser(
        "emit-trailer",
        help="Project the §6.1 commit trailer from the ## Signoff block and "
        "append a CoverageMapSignedOff ledger record.",
    )
    emit_parser.add_argument(
        "--feature-root",
        required=True,
        help="Path to docs/feature/{id}/ -- the feature project root.",
    )

    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.subcommand == "verify":
        omission_classes_path = (
            Path(args.omission_classes_json)
            if args.omission_classes_json is not None
            else _default_omission_classes_path()
        )
        return _verify(
            Path(args.feature_root),
            omission_classes_path,
            touchpoint=args.touchpoint,
        )
    if args.subcommand == "emit-trailer":
        return _emit_trailer(Path(args.feature_root))
    return _digest_golden_fixture(Path(args.input))


if __name__ == "__main__":  # pragma: no cover -- direct CLI invocation only
    sys.exit(main(sys.argv[1:]))
