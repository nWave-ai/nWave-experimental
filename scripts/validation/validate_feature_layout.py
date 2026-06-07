"""validate_feature_layout — lean-wave feature directory layout validator.

Per Recommendation 2 (lean-wave doc audit, 2026-04-28). The lean-wave
contract (D1-D5 of feature `lean-wave-documentation`) declares ONE
narrative file per feature: `docs/feature/{feature-id}/feature-delta.md`.
Multi-file legacy layouts (`discuss/`, `design/`, `distill/`, `deliver/`
subdirs with several `.md` files each) are deprecated. Machine companions
(parseable YAML/JSON, executable `.feature` files, BDD step modules) are
allowed; arbitrary loose markdown files are NOT.

CLI contract:
- `python scripts/validation/validate_feature_layout.py <docs/feature/...>`
- Exit 0 on a conforming feature tree (or empty tree).
- Exit 1 on offenders, listing each path with its canonical alternative.
- Exit 2 on usage error.

Architecture (functional split):
- Pure core: `validate_feature_layout(file_paths)` accepts a flat list of
  paths and returns a `LayoutResult`. No I/O.
- Thin filesystem wrapper: `walk_feature_tree(root)` enumerates files
  under `docs/feature/`. Returns paths only.
- CLI shell: `main(argv)` resolves arguments, calls the wrapper + pure
  core, prints diagnostics, returns the exit code.

The validator is layout-only — content validation lives in
`validate_feature_delta.py` (D2 schema) and `validate_ssot_propagation.py`
(R3 back-propagation contract).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Domain types — pure data carriers
# ---------------------------------------------------------------------------


#: Single canonical narrative file name per Recommendation 1.
NARRATIVE_FILE: str = "feature-delta.md"

#: File extensions allowed unconditionally (machine-parseable companions).
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".json", ".yaml", ".yml", ".feature"})

#: Subdirectory names allowed under `docs/feature/{feature-id}/`. Paths
#: rooted at any of these are exempt from the "no extra .md" rule because
#: they carry executable Gherkin steps, slice briefs, spike notes, or
#: bugfix RCAs (each with their own contract).
ALLOWED_SUBDIRS: frozenset[str] = frozenset({"steps", "slices", "spike", "bugfix"})


class LayoutOffender(NamedTuple):
    """A path that violates the lean-wave layout contract."""

    path: str
    reason: str
    canonical_alternative: str


class LayoutResult(NamedTuple):
    """Outcome of validating a feature tree."""

    is_valid: bool
    offenders: list[LayoutOffender]
    feature_count: int


# ---------------------------------------------------------------------------
# Pure core
# ---------------------------------------------------------------------------


def _classify_path(rel_path: str) -> LayoutOffender | None:
    """Classify one feature-relative path. Pure.

    Args:
        rel_path: path relative to a feature root (e.g. `feature-delta.md`,
            `discuss/user-stories.md`, `slices/slice-01-foo.md`,
            `environments.yaml`). Forward-slash separated.

    Returns:
        None if the path conforms to the contract; an Offender otherwise.
    """
    parts = rel_path.split("/")

    # Top-level narrative file is always allowed.
    if rel_path == NARRATIVE_FILE:
        return None

    # Allowed subdirs (steps/, slices/, spike/, bugfix/) — anything inside is
    # allowed without further inspection. Each subdir has its own contract.
    if len(parts) >= 2 and parts[0] in ALLOWED_SUBDIRS:
        return None

    # Machine artifacts at any depth are allowed by extension.
    suffix = Path(rel_path).suffix.lower()
    if suffix in ALLOWED_EXTENSIONS:
        return None

    # Special-case: legacy wave-grouping subdirs (`discuss/`, `design/`,
    # `distill/`, `deliver/`, `discover/`, `devops/`). Any markdown inside
    # those is a legacy-output offender — narrate that explicitly.
    legacy_wave_dirs: frozenset[str] = frozenset(
        {"discuss", "design", "distill", "deliver", "discover", "devops"}
    )
    if len(parts) >= 2 and parts[0] in legacy_wave_dirs:
        return LayoutOffender(
            path=rel_path,
            reason=(
                f"legacy multi-file output under `{parts[0]}/` "
                "(deprecated by Recommendation 1)"
            ),
            canonical_alternative=(
                f"merge into feature-delta.md as "
                f"`## Wave: {parts[0].upper()} / [REF] <Section>`"
            ),
        )

    # Loose top-level markdown files (e.g. wave-decisions.md, dor-validation.md).
    if rel_path.endswith(".md"):
        return LayoutOffender(
            path=rel_path,
            reason="loose markdown file outside feature-delta.md",
            canonical_alternative=(
                "merge into feature-delta.md as `## Wave: <NAME> / [REF] <Section>`"
            ),
        )

    # Anything else (unknown extension, no extension) is flagged so it
    # gets a human review — this includes accidentally-committed binaries.
    return LayoutOffender(
        path=rel_path,
        reason="unrecognised file (not narrative, not machine artifact)",
        canonical_alternative=(
            "delete or move under steps/, slices/, spike/, or bugfix/"
        ),
    )


def validate_feature_layout(
    feature_paths: list[tuple[str, list[str]]],
) -> LayoutResult:
    """Validate a list of (feature_id, relative_paths) pairs. Pure.

    Args:
        feature_paths: list of `(feature_id, [rel_path, ...])` tuples. Each
            inner list is the set of files (relative to that feature's
            root) discovered by the filesystem walker.

    Returns:
        LayoutResult with `is_valid` true iff zero offenders were found.
    """
    offenders: list[LayoutOffender] = []
    for feature_id, rel_paths in feature_paths:
        for rel_path in rel_paths:
            offender = _classify_path(rel_path)
            if offender is None:
                continue
            offenders.append(
                LayoutOffender(
                    path=f"{feature_id}/{offender.path}",
                    reason=offender.reason,
                    canonical_alternative=offender.canonical_alternative,
                )
            )
    return LayoutResult(
        is_valid=not offenders,
        offenders=offenders,
        feature_count=len(feature_paths),
    )


# ---------------------------------------------------------------------------
# Thin filesystem wrapper
# ---------------------------------------------------------------------------


def walk_feature_tree(root: Path) -> list[tuple[str, list[str]]]:
    """Enumerate `(feature_id, [rel_path, ...])` pairs under `root`.

    Each immediate subdirectory of `root` is a feature; the rel_paths are
    forward-slash-relative to that feature's directory.

    Args:
        root: typically `docs/feature/`.

    Returns:
        Sorted list of `(feature_id, sorted_rel_paths)` tuples.
    """
    if not root.is_dir():
        return []
    out: list[tuple[str, list[str]]] = []
    for feature_dir in sorted(root.iterdir()):
        if not feature_dir.is_dir():
            continue
        rel_paths: list[str] = []
        for entry in sorted(feature_dir.rglob("*")):
            if not entry.is_file():
                continue
            rel = entry.relative_to(feature_dir).as_posix()
            rel_paths.append(rel)
        out.append((feature_dir.name, rel_paths))
    return out


# ---------------------------------------------------------------------------
# CLI shell
# ---------------------------------------------------------------------------


def _format_failure(result: LayoutResult) -> str:
    lines = [
        f"Feature layout invalid: {len(result.offenders)} offending path(s) "
        f"across {result.feature_count} feature(s).",
        "",
    ]
    for off in result.offenders:
        lines.append(f"  {off.path}")
        lines.append(f"    reason: {off.reason}")
        lines.append(f"    fix:    {off.canonical_alternative}")
    return "\n".join(lines)


def _format_success(result: LayoutResult) -> str:
    return (
        f"Feature layout valid. {result.feature_count} feature(s) checked, "
        "zero layout offenders."
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: `python validate_feature_layout.py [--soft] <feature-root>`.

    Args:
        argv: optional argument list (defaults to `sys.argv[1:]`).

    Returns:
        0 on a valid tree (or `--soft` mode regardless), 1 on offenders in
        strict mode, 2 on usage error.

    The `--soft` flag emits the same diagnostics but always exits 0. Used
    by the pre-commit hook during the soft-warn rollout window — promote
    the hook to strict mode (drop `--soft`) after one stable release.
    """
    args = sys.argv[1:] if argv is None else argv
    soft = False
    positional: list[str] = []
    for arg in args:
        if arg == "--soft":
            soft = True
        else:
            positional.append(arg)

    if len(positional) != 1:
        print(
            "usage: validate_feature_layout.py [--soft] <docs/feature-root>",
            file=sys.stderr,
        )
        return 2

    root = Path(positional[0])
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 2

    feature_paths = walk_feature_tree(root)
    result = validate_feature_layout(feature_paths)
    if result.is_valid:
        print(_format_success(result))
        return 0
    print(_format_failure(result))
    if soft:
        print(
            "\n[soft-warn] validate_feature_layout exiting 0 despite "
            "offenders. Strict mode pending: drop --soft after one "
            "stable release.",
            file=sys.stderr,
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
