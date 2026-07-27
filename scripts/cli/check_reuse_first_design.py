"""Reuse-first design gate CLI.

F-DESIGN-REUSE-FIRST-GATE-CLI (DDD-1..DDD-11). Sibling spine-gate of
``check_robustness_density.py``. Hosted in ``scripts/cli/`` because the gate
has no DES-runtime coupling (DDD-3 nwave-dev hooks-only).

The gate asserts that every NEW component introduced by the feature's real
commit range is justified in the feature-delta's ``## Reuse Analysis`` (or
``## Wave: DESIGN / [REF] Reuse Analysis``) section. Two detection units
(DDD-8 path-kind dispatch) contribute to the NEW-component UNION (DDD-11):

* **class-components** — added files under ``--scoped-path`` (default ``src``)
  are grepped for ``^class <Name>(`` declarations; each declared name is a NEW
  component justified iff its name appears in a Reuse Analysis column-1 cell.
* **file-components** — added files under any ``--methodology-path`` prefix are
  themselves NEW components keyed by repo-relative PATH (not grepped for
  ``^class``); each is justified iff its path OR its stem appears in a column-1
  cell (DDD-9, DDD-10).

The detector derives the added-file set from a real ``git diff --name-status
<base>...HEAD`` invocation; ``--git-diff-source=path:<file>`` remains as a
fixture-injection escape hatch listing one NEW class name per line. The gate is
read-only: it inspects diff PATHS and (class-mode only) added-source bytes, and
NEVER reads a methodology file's bytes (DDD-11).

Stdout token contract (DDD-4) -- single line, machine-parseable::

    reuse_first feature=<id> new_components=<n> justified=<m> verdict=<PASS|FAIL>

Exit code contract (DDD-5):
    0 = PASS      -- every NEW component is justified by a Reuse Analysis row
    1 = FAIL      -- at least one NEW component is unjustified
    2 = MALFORMED -- feature-delta missing / unparseable

LENIENT justified-match (DDD-6): justification inspects the **Existing
Component** column (column 1) of any GFM table row of any matching Reuse
Analysis section. Column-1-only inspection means a row whose Justification cell
mentions a NEW component in a negation (e.g. "this row does not mention
OrphanService") cannot vacuously justify it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from des.adapters.driven.git.git_subprocess import (
    resolve_default_base_ref,
    resolve_feature_genesis_base_ref,
)
from des.cli.human_surface import Verdict, print_human_summary
from des.cli.validate_feature_delta import REUSE_ANALYSIS_HEADING


_EXIT_PASS = 0
_EXIT_FAIL = 1
_EXIT_MALFORMED = 2

# slice-02 conventional defaults (DDD-7): the trunk the feature diverged from
# and the source-tree prefix that counts as feature code. The override flags
# (--base-branch / --scoped-path) accept these as their default values; the
# real-diff path consumes whichever values the invocation supplies.
_DEFAULT_BASE_BRANCH = "master"
_DEFAULT_SCOPED_PATH = "src"

# slice-06 (DDD-9): the published-language methodology-path set the nw-design
# skill promises the architect. When --methodology-path is omitted (the no-flag
# real-diff caller: CI, the post-DESIGN gate wiring) the gate defaults to these
# prefixes so a NEW methodology SSOT artifact cannot ship via a vacuous PASS.
_DEFAULT_METHODOLOGY_PATHS = ("nWave/data", "nWave/skills", "scripts/cli")

# A NEW component class declaration: ``^class <Name>(`` at column 0 (DDD-7).
_CLASS_DECLARATION_RE = re.compile(r"^class\s+(?P<name>\w+)\s*\(", re.MULTILINE)


# The lenient superset matcher (DDD-6) DERIVES its core text from the
# canonical `des.cli.validate_feature_delta.REUSE_ANALYSIS_HEADING` constant
# -- never an independent hardcoded literal (FR-11 root fix: the SSOT drift
# a duplicated grammar concept caused). Matches a Markdown level-2 heading
# whose text CONTAINS the canonical core -- either the bare canonical
# ``## Reuse Analysis`` or the carpaccio variant
# ``## Wave: DESIGN / [REF] Reuse Analysis``.
_REUSE_ANALYSIS_HEADING_CORE = REUSE_ANALYSIS_HEADING.removeprefix("##").strip()
_REUSE_ANALYSIS_HEADING_RE = re.compile(
    rf"^##\s+(?:.*\b{re.escape(_REUSE_ANALYSIS_HEADING_CORE)}\b.*)$",
    re.MULTILINE,
)


def _extract_reuse_analysis_sections(feature_delta_text: str) -> list[str]:
    """Return every Reuse Analysis section body found in the feature-delta.

    Each section runs from its ``##`` heading line up to (exclusive) the next
    ``##`` heading or end-of-document. The LENIENT match (DDD-6) only needs
    the section *bytes* to grep for NEW class names.
    """
    headings = list(_REUSE_ANALYSIS_HEADING_RE.finditer(feature_delta_text))
    next_section_re = re.compile(r"^##\s", re.MULTILINE)
    sections: list[str] = []
    for heading_match in headings:
        section_start = heading_match.start()
        next_section = next_section_re.search(feature_delta_text, heading_match.end())
        section_end = next_section.start() if next_section else len(feature_delta_text)
        sections.append(feature_delta_text[section_start:section_end])
    return sections


def _detect_new_components_via_diff_source(diff_source_path: Path) -> list[str]:
    """Read NEW class names from the slice-01 fixture-injection diff source.

    DDD-7 walking-skeleton: ``--git-diff-source=path:<file>`` lists one NEW
    class name per line. slice-02 promotes to real ``git diff master...HEAD``
    invocation.
    """
    text = diff_source_path.read_text(encoding="utf-8")
    return [line.strip() for line in text.splitlines() if line.strip()]


def _added_entries_in_range(repo_root: Path, base_branch: str) -> list[str]:
    """Return every added (status ``A``) repo-relative path in the range.

    Runs the real ``git diff --name-status <base>...HEAD`` over ``repo_root``
    (DDD-7) and collects the repo-relative path of each added file, unscoped.
    Both detection units (class-component scope-filter, file-component
    methodology-path filter) lift their own filtering off this shared list.
    Read-only — ``git diff`` mutates nothing.
    """
    completed = subprocess.run(
        ["git", "diff", "--name-status", f"{base_branch}...HEAD"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    added: list[str] = []
    for line in completed.stdout.splitlines():
        fields = line.split("\t")
        if len(fields) < 2 or fields[0] != "A":
            continue
        added.append(fields[1])
    return added


def _detect_new_components_via_git_diff(
    repo_root: Path, base_branch: str, scoped_path: str
) -> list[str]:
    """Detect NEW component classes from the feature's real commit range (DDD-7).

    Each added ``<scoped_path>/**`` file is grepped for ``^class <Name>(``
    declarations; the union of class names is the NEW component set. slice-02
    promotes the slice-01 ``--git-diff-source`` name-list fixture-injection to
    this real-diff path.
    """
    scope_prefix = f"{scoped_path}/"
    new_components: list[str] = []
    for rel_path in _added_entries_in_range(repo_root, base_branch):
        if not rel_path.startswith(scope_prefix):
            continue
        source = (repo_root / rel_path).read_text(encoding="utf-8")
        for match in _CLASS_DECLARATION_RE.finditer(source):
            new_components.append(match.group("name"))
    return new_components


def _detect_methodology_file_components(
    repo_root: Path, base_branch: str, methodology_paths: list[str]
) -> list[str]:
    """Detect NEW methodology file-components from the commit range (DDD-8..11).

    A path-kind dispatch (DDD-8): each added file whose repo-relative path lies
    under a declared methodology-path prefix is ITSELF a NEW component (DDD-9),
    keyed by its repo-relative path — NOT grepped for ``^class`` (DDD-11:
    file-components are components by virtue of being added, not by content).
    Reads diff PATHS only; never the methodology file's bytes (DDD-11 read-only).
    """
    components: list[str] = []
    for rel_path in _added_entries_in_range(repo_root, base_branch):
        if any(_path_under_prefix(rel_path, prefix) for prefix in methodology_paths):
            components.append(rel_path)
    return components


def _path_under_prefix(rel_path: str, prefix: str) -> bool:
    """True iff ``rel_path`` lies under the ``prefix`` directory."""
    return rel_path == prefix or rel_path.startswith(f"{prefix}/")


def _existing_component_cells(reuse_analysis_sections: list[str]) -> list[str]:
    """Collect the Existing Component (column 1) cell text of every table row.

    Walks every GFM table data row in every Reuse Analysis section and returns
    the trimmed text of column 1. Skips the heading row and the separator row
    (``|---|---|...``). The walking-skeleton uses column-1 inspection so a
    Justification-cell mention of the NEW class name (e.g. a negation) cannot
    vacuously justify it.
    """
    cells: list[str] = []
    for section in reuse_analysis_sections:
        for raw_line in section.splitlines():
            line = raw_line.strip()
            if not line.startswith("|"):
                continue
            row_cells = [cell.strip() for cell in line.strip("|").split("|")]
            first_cell = row_cells[0]
            if not first_cell or set(first_cell) <= set("-: "):
                # Separator row (``|---|---|``) or blank first cell.
                continue
            cells.append(first_cell)
    return cells


def _lenient_justified_in_section(
    new_class_name: str, reuse_analysis_sections: list[str]
) -> bool:
    """LENIENT match (DDD-6): NEW class name appears in any column-1 cell.

    The cell may wrap the name in Markdown code-spans (``` `WidgetService` ```)
    or surrounding prose; substring-in-cell is the walking-skeleton predicate.
    """
    cells = _existing_component_cells(reuse_analysis_sections)
    return any(new_class_name in cell for cell in cells)


def _lenient_file_component_justified(
    rel_path: str, reuse_analysis_sections: list[str]
) -> bool:
    """LENIENT file-component match (DDD-10): path OR stem in any column-1 cell.

    A methodology file-component keyed by its repo-relative path (e.g.
    ``nWave/data/dor-items.yaml``) is justified iff that path OR its stem
    (``dor-items``) appears in the Existing Component (column 1) cell of any
    Reuse Analysis row — mirroring the class-component column-1 inspection.
    """
    stem = Path(rel_path).stem
    cells = _existing_component_cells(reuse_analysis_sections)
    return any(rel_path in cell or stem in cell for cell in cells)


def _parse_diff_source_flag(raw: str) -> Path:
    """Parse ``--git-diff-source=path:<file>`` (DDD-7 fixture-injection)."""
    prefix = "path:"
    assert raw.startswith(prefix), (
        f"--git-diff-source must use the path:<file> form in slice-01; got {raw!r}"
    )
    return Path(raw[len(prefix) :])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_reuse_first_design",
        description=(
            "Reuse-first design gate (slice-01 walking skeleton). "
            "Asserts every NEW component class introduced by the feature's "
            "commit range is named in the feature-delta's Reuse Analysis "
            "section."
        ),
    )
    parser.add_argument(
        "--feature-id",
        required=True,
        help="Kebab-case feature identifier (e.g. reuse-first-cli-demo).",
    )
    parser.add_argument(
        "--repo-root",
        required=True,
        help="Repository root containing docs/feature/<feature-id>/.",
    )
    parser.add_argument(
        "--git-diff-source",
        required=False,
        default=None,
        help=(
            "slice-01 fixture-injection: path:<file> listing one NEW class "
            "name per line. When omitted, the detector runs the real "
            "git diff over --repo-root (slice-02)."
        ),
    )
    parser.add_argument(
        "--base-branch",
        default=None,
        help=(
            "The trunk the feature diverged from (slice-02 real-diff path). "
            "Default: None -- resolved via _resolve_base_branch "
            "(reuse-first-gate-branch-topology-false-positive): the feature-"
            "delta's OWN git-genesis parent commit (the commit before "
            "docs/feature/<id>/feature-delta.md first entered history), so "
            "an unscoped diff on a long-lived branch never counts files "
            "added by OTHER, already-merged features against THIS one's "
            "Reuse table. Falls back to resolve_default_base_ref (the "
            f"repo's own trunk) then the literal {_DEFAULT_BASE_BRANCH!r} "
            "when the genesis commit cannot be resolved (e.g. a brand-new, "
            "not-yet-committed feature-delta). An EXPLICIT --base-branch "
            "always overrides this resolution."
        ),
    )
    parser.add_argument(
        "--scoped-path",
        default=_DEFAULT_SCOPED_PATH,
        help=(
            "The repo-relative source-tree prefix that counts as feature "
            f"code (slice-02 real-diff path). Default: {_DEFAULT_SCOPED_PATH}."
        ),
    )
    parser.add_argument(
        "--methodology-path",
        dest="methodology_paths",
        action="append",
        default=None,
        metavar="PREFIX",
        help=(
            "A repo-relative methodology-path prefix (e.g. nWave/data, "
            "nWave/skills, scripts/cli) whose added files are themselves NEW "
            "file-components keyed by path/stem (slice-03 DDD-8..DDD-11). "
            "Repeatable; additive to the --scoped-path class-component "
            "detection. When omitted on the real-diff path, defaults to the "
            f"published-language set {list(_DEFAULT_METHODOLOGY_PATHS)} "
            "(slice-06 DDD-9)."
        ),
    )
    return parser


def _resolve_base_branch(repo_root: Path, feature_id: str, explicit: str | None) -> str:
    """Resolve the effective ``base_branch`` for the real-diff detection path.

    reuse-first-gate-branch-topology-false-positive: an EXPLICIT
    ``--base-branch`` always wins (byte-identical to every existing caller
    that passes one). Otherwise, tiered resolution -- reusing the SAME
    ``des.adapters.driven.git.git_subprocess`` SSOT ``resolve_default_base_ref``
    already consults elsewhere (``walking_skeleton_gate.py``,
    ``dormant_seam_gate.py``), never a second algorithm:

      1. The feature-delta's OWN git-genesis parent (the commit BEFORE
         ``docs/feature/<feature_id>/feature-delta.md`` first entered
         history) -- scopes the diff to exactly THIS feature's own commits,
         immune to how many OTHER features have merged onto a long-lived
         branch since it diverged.
      2. ``resolve_default_base_ref`` (the repo's own resolved trunk) when
         the feature-delta has no git history yet (e.g. a brand-new,
         not-yet-committed feature-delta -- the walking-skeleton case).
      3. The literal ``_DEFAULT_BASE_BRANCH`` ("master") when neither
         resolves -- never a crash; the gate degrades to the pre-fix
         behavior rather than refusing to run.
    """
    if explicit is not None:
        return explicit
    genesis = resolve_feature_genesis_base_ref(
        repo_root, f"docs/feature/{feature_id}/feature-delta.md"
    )
    if genesis is not None:
        return genesis
    default_trunk = resolve_default_base_ref(repo_root)
    if default_trunk is not None:
        return default_trunk
    return _DEFAULT_BASE_BRANCH


def main(argv: list[str] | None = None) -> int:
    """Run the reuse-first design gate; return the verdict exit code."""
    args = _build_parser().parse_args(argv)
    feature_id = args.feature_id
    repo_root = Path(args.repo_root)
    base_branch = _resolve_base_branch(repo_root, feature_id, args.base_branch)

    feature_delta_path = (
        repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    feature_delta_text = feature_delta_path.read_text(encoding="utf-8")
    reuse_analysis_sections = _extract_reuse_analysis_sections(feature_delta_text)

    if args.git_diff_source is not None:
        # slice-01 fixture-injection: NEW class names from a path:<file> list.
        class_components = _detect_new_components_via_diff_source(
            _parse_diff_source_flag(args.git_diff_source)
        )
    else:
        # slice-02 real-diff path: NEW classes from git diff --name-status.
        class_components = _detect_new_components_via_git_diff(
            repo_root, base_branch, args.scoped_path
        )
    justified_classes = [
        name
        for name in class_components
        if _lenient_justified_in_section(name, reuse_analysis_sections)
    ]

    # slice-03 (DDD-8..DDD-11): the second detection unit. Each added file under
    # a declared --methodology-path prefix is itself a NEW file-component
    # (path/stem-keyed, no ^class grep). new_components is the UNION across both
    # units; the verdict is PASS iff every component of either kind is justified.
    methodology_paths = (
        args.methodology_paths
        if args.methodology_paths is not None
        else list(_DEFAULT_METHODOLOGY_PATHS)
    )
    file_components = (
        _detect_methodology_file_components(repo_root, base_branch, methodology_paths)
        if methodology_paths and args.git_diff_source is None
        else []
    )
    justified_files = [
        rel_path
        for rel_path in file_components
        if _lenient_file_component_justified(rel_path, reuse_analysis_sections)
    ]

    new_components = class_components + file_components
    justified = justified_classes + justified_files
    verdict = "PASS" if len(justified) == len(new_components) else "FAIL"
    exit_code = _EXIT_PASS if verdict == "PASS" else _EXIT_FAIL

    print(
        f"reuse_first feature={feature_id} "
        f"new_components={len(new_components)} "
        f"justified={len(justified)} verdict={verdict}"
    )
    if verdict == "PASS":
        print_human_summary(
            Verdict.PASS,
            f"reuse-first design verified: every NEW component "
            f"({len(new_components)}) is justified in the Reuse Analysis section",
        )
    else:
        unjustified_count = len(new_components) - len(justified)
        print_human_summary(
            Verdict.FAIL,
            f"reuse-first design refused: {unjustified_count} of "
            f"{len(new_components)} NEW component(s) lack a Reuse Analysis row",
        )
    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
