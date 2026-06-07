"""migrate_to_l7 — opt-in legacy-to-lean feature directory migration (DDD-3).

Per DDD-3 (lean-wave-documentation feature-delta.md):

- Idempotent (re-running on a feature where the marker is present is a no-op).
- Atomic write (`feature-delta.md.tmp` + `os.replace`).
- Recovery on partial migration (orphan `.tmp` is detected and removed).
- Heuristic classification table per the DDD-3 decision body.
- NOT shipped to end users via wheel (dev-only).
- Legacy directories are preserved for git diff inspection — the script
  never deletes them. Rollback is `git checkout -- docs/feature/<id>/`.

Architecture:
- Pure-functional core (`compute_migration_plan`) — given an in-memory map
  of legacy file paths -> contents, returns a `MigrationPlan` describing
  what would land in `feature-delta.md`. No I/O.
- Thin IO shell (`migrate_feature`, `main`) — reads files from disk, calls
  the planner, writes via tmp + rename. The split keeps the heuristic
  classification deterministic and trivially testable in isolation.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


# Marker the test suite uses to assert this module is still a RED scaffold.
# Real implementation: marker disabled (set to False) so GREEN guards do
# not trip downstream of this point in the lifecycle.
__SCAFFOLD__ = False


# Top-of-file marker that means "this feature has already been migrated"
# (per DDD-3). Idempotency relies on detecting this exact line in line 0
# of the produced `feature-delta.md`.
LEAN_FORMAT_MARKER = "<!-- L7_FORMAT: lean -->"

# HTML comment appended to a section the heuristic could not unambiguously
# classify (per DDD-3 conflict resolution).
REVIEW_NEEDED_MARKER = "<!-- review-needed -->"


# Heuristic classification: legacy (subdir, basename-prefix) -> wave + tier.
# basename-prefix means "stem startswith". This table is the single source
# of truth for the migration heuristic; it must stay stable across releases
# so users re-running the script see consistent outputs.
WaveName = Literal["DISCOVER", "DISCUSS", "DESIGN", "DEVOPS", "DISTILL", "DELIVER"]
Tier = Literal["REF", "WHY", "HOW"]


@dataclass(frozen=True)
class ClassificationRule:
    """One row from the DDD-3 heuristic classification table."""

    subdir: str
    stem_prefix: str
    wave: WaveName
    tier: Tier
    section_name: str


# Order matters: the first matching rule wins. The most specific rule
# (longer stem_prefix) must come first to avoid misrouting (e.g.
# `jtbd-analysis.md` should land under [WHY] JTBD narrative, NOT under
# [REF] User stories).
CLASSIFICATION_RULES: tuple[ClassificationRule, ...] = (
    # DISCUSS — Tier-2 expansions first (more specific stems)
    ClassificationRule("discuss", "jtbd-analysis", "DISCUSS", "WHY", "JTBD narrative"),
    ClassificationRule("discuss", "jtbd", "DISCUSS", "WHY", "JTBD narrative"),
    ClassificationRule("discuss", "persona", "DISCUSS", "WHY", "Persona narrative"),
    ClassificationRule(
        "discuss",
        "alternatives",
        "DISCUSS",
        "WHY",
        "Alternatives considered",
    ),
    ClassificationRule(
        "discuss", "tradeoffs", "DISCUSS", "WHY", "Alternatives considered"
    ),
    # DISCUSS — Tier-1 [REF]
    ClassificationRule(
        "discuss",
        "elevator-pitch",
        "DISCUSS",
        "REF",
        "Elevator pitch",
    ),
    ClassificationRule("discuss", "user-stories", "DISCUSS", "REF", "User stories"),
    ClassificationRule(
        "discuss",
        "acceptance-criteria",
        "DISCUSS",
        "REF",
        "Acceptance criteria",
    ),
    ClassificationRule("discuss", "dor", "DISCUSS", "REF", "DOR validation"),
    # DESIGN — ADRs land as [REF] decisions
    ClassificationRule("design", "adr", "DESIGN", "REF", "Decisions"),
    ClassificationRule("design", "architecture", "DESIGN", "REF", "Architecture"),
    # DISTILL — feature files / scenarios
    ClassificationRule(
        "distill", "scenarios", "DISTILL", "REF", "Acceptance scenarios"
    ),
    # DELIVER — retros land as Tier-2 [WHY]
    ClassificationRule("deliver", "retro", "DELIVER", "WHY", "Retrospective"),
    ClassificationRule(
        "deliver",
        "retrospective",
        "DELIVER",
        "WHY",
        "Retrospective",
    ),
)

# Subdirectories whose content is intentionally NOT migrated (per DDD-3
# "raw transcripts left as audit trail"). The planner emits an info note
# but never inlines this content into feature-delta.md.
SKIPPED_SUBDIRS: frozenset[str] = frozenset({"discover"})


@dataclass(frozen=True)
class MigratedSection:
    """One classified section that will be emitted into feature-delta.md."""

    wave: WaveName
    tier: Tier
    section_name: str
    body: str
    source_path: str  # legacy path relative to feature-dir, for traceability


@dataclass(frozen=True)
class MigrationPlan:
    """Pure-function output of `compute_migration_plan`.

    Attributes:
        sections: Sections to emit, ordered by wave then by source path
            for determinism.
        ambiguous: Source paths the heuristic could not classify; each
            lands under `## Wave: DISCUSS / [WHY] Migration residue` with
            a `<!-- review-needed -->` HTML comment marker.
        skipped: Source paths the heuristic intentionally skipped (e.g.
            DISCOVER raw transcripts).
        already_migrated: True when the input feature dir already shows
            the lean format marker; the planner returns an empty plan and
            the IO shell exits 0 with the idempotency message.
    """

    sections: list[MigratedSection]
    ambiguous: list[str]
    skipped: list[str]
    already_migrated: bool = False


@dataclass(frozen=True)
class ClassifiedFile:
    """One enumerated legacy file with its classification (or None)."""

    relative_path: str
    body: str
    rule: ClassificationRule | None


# ---------------------------------------------------------------------------
# Pure-function core — no I/O.
# ---------------------------------------------------------------------------


def _wave_order(wave: WaveName) -> int:
    """Return canonical wave ordering index per the canonical 6-wave sequence."""
    canonical: list[WaveName] = [
        "DISCOVER",
        "DISCUSS",
        "DESIGN",
        "DEVOPS",
        "DISTILL",
        "DELIVER",
    ]
    return canonical.index(wave)


def classify(relative_path: str) -> ClassificationRule | None:
    """Classify one legacy path against the heuristic rules.

    Args:
        relative_path: Path relative to the feature directory, with forward
            slashes (e.g. ``"discuss/jtbd-analysis.md"``).

    Returns:
        Matching ``ClassificationRule`` or None when no rule applies (the
        caller routes None to the ambiguous bucket).
    """
    parts = relative_path.split("/")
    if len(parts) < 2:
        return None
    subdir = parts[0]
    if subdir in SKIPPED_SUBDIRS:
        return None
    stem = Path(parts[-1]).stem.lower()
    for rule in CLASSIFICATION_RULES:
        if rule.subdir != subdir:
            continue
        if stem.startswith(rule.stem_prefix):
            return rule
    return None


def compute_migration_plan(
    legacy_files: dict[str, str],
    *,
    already_migrated: bool = False,
) -> MigrationPlan:
    """Compute the migration plan from in-memory legacy file content.

    Pure function. No I/O.

    Args:
        legacy_files: Map of relative_path -> file content. Paths use
            forward slashes regardless of host OS.
        already_migrated: True when the caller has detected the lean
            format marker on disk; the planner returns an empty plan to
            preserve idempotency.

    Returns:
        ``MigrationPlan`` with sections, ambiguous bucket, skipped bucket.
    """
    if already_migrated:
        return MigrationPlan(
            sections=[],
            ambiguous=[],
            skipped=[],
            already_migrated=True,
        )

    sections: list[MigratedSection] = []
    ambiguous: list[str] = []
    skipped: list[str] = []

    for relative_path, body in sorted(legacy_files.items()):
        first_segment = relative_path.split("/", 1)[0]
        if first_segment in SKIPPED_SUBDIRS:
            skipped.append(relative_path)
            continue

        rule = classify(relative_path)
        if rule is None:
            ambiguous.append(relative_path)
            continue

        sections.append(
            MigratedSection(
                wave=rule.wave,
                tier=rule.tier,
                section_name=rule.section_name,
                body=body.strip("\n"),
                source_path=relative_path,
            )
        )

    # Stable ordering: wave canonical order, then by source path.
    sections.sort(key=lambda s: (_wave_order(s.wave), s.source_path))
    return MigrationPlan(
        sections=sections,
        ambiguous=ambiguous,
        skipped=skipped,
        already_migrated=False,
    )


def render_feature_delta(plan: MigrationPlan, feature_id: str) -> str:
    """Render a `MigrationPlan` to the final ``feature-delta.md`` text.

    Pure function — no I/O. The output starts with ``LEAN_FORMAT_MARKER``
    so re-running the migration on this file is detected as already
    migrated.

    Args:
        plan: The plan produced by `compute_migration_plan`.
        feature_id: The feature id (used as the H1 heading).

    Returns:
        Full text content for ``feature-delta.md``.
    """
    parts: list[str] = [
        LEAN_FORMAT_MARKER,
        "",
        f"# {feature_id} — feature-delta",
        "",
        "> Auto-generated by `scripts/migrate_to_l7.py`. Legacy directories",
        "> are preserved for audit; this file is the new single-file scope.",
        "",
    ]

    for section in plan.sections:
        parts.append(
            f"## Wave: {section.wave} / [{section.tier}] {section.section_name}"
        )
        parts.append("")
        parts.append(f"<!-- migrated from: {section.source_path} -->")
        parts.append(section.body)
        parts.append("")

    if plan.ambiguous:
        parts.append("## Wave: DISCUSS / [WHY] Migration residue")
        parts.append("")
        parts.append(REVIEW_NEEDED_MARKER)
        parts.append(
            "The migration heuristic could not classify the following files. "
            "Review them and move the relevant content into the appropriate "
            "wave section, then delete this section."
        )
        parts.append("")
        for ambiguous_path in plan.ambiguous:
            parts.append(f"- `{ambiguous_path}`")
        parts.append("")

    if plan.skipped:
        parts.append("## Wave: DISCOVER / [WHY] Migration notes")
        parts.append("")
        parts.append(
            "The following legacy paths were intentionally NOT inlined into "
            "this feature-delta (raw transcripts / interview notes preserved "
            "in their legacy location for audit):"
        )
        parts.append("")
        for skipped_path in plan.skipped:
            parts.append(f"- `{skipped_path}`")
        parts.append("")

    # Trailing newline for POSIX-friendly file
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# IO shell — reads legacy files, writes the new feature-delta atomically.
# ---------------------------------------------------------------------------


@dataclass
class MigrationOutcome:
    """High-level outcome surfaced to the CLI shell."""

    feature_id: str
    target: Path
    already_migrated: bool = False
    sections_written: int = 0
    ambiguous: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


def _is_already_migrated(target: Path) -> bool:
    """Return True when ``target`` exists and starts with the lean marker."""
    if not target.is_file():
        return False
    try:
        with target.open("r", encoding="utf-8") as fh:
            first_line = fh.readline().rstrip("\n")
    except OSError:
        return False
    return first_line == LEAN_FORMAT_MARKER


def _enumerate_legacy_files(feature_dir: Path) -> dict[str, str]:
    """Return a path -> content map of every legacy `.md` file under feature_dir.

    Skips ``feature-delta.md`` itself (we don't recurse into our own output)
    and skips dotfiles. Only `.md` files are migrated; binary or non-md
    artifacts are out of scope per DDD-3.
    """
    out: dict[str, str] = {}
    for path in sorted(feature_dir.rglob("*.md")):
        if path.name == "feature-delta.md":
            continue
        if any(part.startswith(".") for part in path.parts):
            continue
        rel = path.relative_to(feature_dir).as_posix()
        try:
            out[rel] = path.read_text(encoding="utf-8")
        except OSError as exc:
            # Surface unreadable files as ambiguous (the planner routes them
            # to the residue bucket via classify() returning None — but we
            # never reach the planner for these). Skip with a stderr note.
            print(
                f"migrate_to_l7: could not read {path} ({exc})",
                file=sys.stderr,
            )
    return out


def _atomic_write(target: Path, content: str) -> None:
    """Write ``content`` to ``target`` atomically via tmp + Path.replace.

    Uses ``Path.with_suffix(".md.tmp")`` to keep the staging file beside
    the target on the same filesystem (POSIX rename atomicity precondition).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(target.name + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    tmp.replace(target)


def _cleanup_orphan_tmp(target: Path) -> bool:
    """Remove a stale ``feature-delta.md.tmp`` left from a crashed prior run.

    Returns True when a cleanup was performed, False otherwise.
    """
    tmp = target.with_name(target.name + ".tmp")
    if tmp.exists():
        try:
            tmp.unlink()
        except OSError:
            return False
        return True
    return False


def migrate_feature(feature_dir: Path) -> int:
    """Migrate one legacy feature directory to lean L7 layout.

    Args:
        feature_dir: Path to ``docs/feature/<id>/`` containing legacy
            subdirs (`discuss/`, `design/`, `distill/`, `deliver/`).

    Returns:
        Exit code: ``0`` on success or already-migrated; ``2`` when the
        feature directory does not exist or is not a directory.
    """
    if not feature_dir.is_dir():
        print(
            f"migrate_to_l7: not a directory: {feature_dir}",
            file=sys.stderr,
        )
        return 2

    feature_id = feature_dir.name
    target = feature_dir / "feature-delta.md"

    # Recover from any orphan .tmp from a prior crashed run.
    if _cleanup_orphan_tmp(target):
        print(f"migrate_to_l7: cleaned up orphan .tmp from prior run for {feature_id}")

    # Idempotency check: target already shows the lean format marker.
    if _is_already_migrated(target):
        print(f"already migrated: {feature_id}")
        return 0

    legacy_files = _enumerate_legacy_files(feature_dir)
    plan = compute_migration_plan(legacy_files)
    content = render_feature_delta(plan, feature_id)
    _atomic_write(target, content)

    print(
        f"migrate_to_l7: {feature_id} -> {target} "
        f"(sections={len(plan.sections)}, "
        f"ambiguous={len(plan.ambiguous)}, "
        f"skipped={len(plan.skipped)})"
    )
    return 0


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry. argparse-driven; takes one or more feature directory paths."""
    parser = argparse.ArgumentParser(
        prog="migrate_to_l7",
        description=(
            "Migrate a legacy `docs/feature/<id>/` tree (multi-subdir layout) "
            "into a single lean `feature-delta.md` (per DDD-3 of the "
            "lean-wave-documentation feature). Idempotent: re-running on a "
            "feature that already carries the lean format marker is a no-op."
        ),
        epilog=(
            "Recovery: if the script crashes mid-run, an orphan "
            "`feature-delta.md.tmp` may remain. The next invocation cleans "
            "it up automatically. Equivalently, "
            "`git checkout -- docs/feature/<id>/` restores the working "
            "tree to last-committed state."
        ),
    )
    parser.add_argument(
        "feature_dirs",
        nargs="+",
        type=Path,
        help="One or more docs/feature/<id>/ paths to migrate.",
    )

    args = parser.parse_args(argv)

    final_exit = 0
    for feature_dir in args.feature_dirs:
        rc = migrate_feature(feature_dir)
        if rc != 0:
            final_exit = rc
    return final_exit


if __name__ == "__main__":
    raise SystemExit(main())
