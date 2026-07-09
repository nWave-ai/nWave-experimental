"""des charter-scaffold -- the producing tool for expectation-charter scaffolds
(charter-scaffold feature, slice-01).

Makes charter authoring system-paid (GDP-5) and early (GDP-1): reads a
feature's `## Wave: DISCUSS / [REF] Slice Plan` table and, for each
OBSERVABLE-value slice (Annotation NOT `@infrastructure` / `@prefactoring`),
generates a charter SCAFFOLD at
`docs/product/expectations/<feature-id>/<intent-name>.md` using
`nWave/templates/expectation-charter.md` as the skeleton, Intent pre-filled
from the slice's Value statement VERBATIM. Every other section (Preconditions,
Charter, Expected observations, Session log) is left as the template's
fresh-PO-fill placeholder -- this tool does not invent judgment, only lifts
the user-side Value statement (uncontaminated by construction: it never sees
design/impl vocabulary).

Idempotent (never overwrites an existing charter); degrades LOUD (GDP-6) on a
missing/malformed feature-delta or absent Slice Plan -- never a silent no-op
nor a partial scaffold that looks complete.

Reuses the existing feature-delta Slice-Plan parser verbatim
(`_plan_table_rows` / `_parse_table_cells` / `_is_separator_row` /
`validate_slice_plan_content` from `des.cli.validate_feature_delta` -- the
same machinery `feature_delta_schema._slice_plan_row` composes) -- no
parallel table parser.

Architecture: pure functions for slug/skeleton/row classification; a thin
`main` shell does the filesystem I/O and JSON rendering (mirrors
`feature_delta_doctor`'s pure-core / thin-shell split).

CLI contract:
    des charter-scaffold --feature-id <id> [--repo-root .] [--format json]

stdout token (JSON):
    {feature_id, created:[...], skipped:[...], observable_slices:N, verdict,
     detail}
Exit 0 on `accepted` (scaffolding attempted, even when zero slices are
observable); non-zero on any degrade-LOUD verdict.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from des.cli.validate_feature_delta import (
    _SLICE_PLAN_HEADING_RE,
    VERDICT_ACCEPTED,
    _is_separator_row,
    _parse_table_cells,
    _plan_table_rows,
    validate_slice_plan_content,
)


#: The one NEW verdict token this tool adds -- file-absence, upstream of
#: anything `validate_slice_plan_content` can classify (it needs file content
#: to run). Every other degrade-LOUD verdict (missing-slice-plan,
#: malformed-slice-plan, rejected-infra-only, malformed-wave-heading) is
#: REUSED verbatim from `validate_feature_delta` -- this tool never invents a
#: parallel token for a case the shared parser already names.
VERDICT_MISSING_FEATURE_DELTA = "missing-feature-delta"

#: Degrade-LOUD token for an unreadable/absent charter template -- the one
#: local asset this tool reads besides the feature-delta.
VERDICT_MISSING_CHARTER_TEMPLATE = "missing-charter-template"

#: Degrade-LOUD token (slice-03) for `--seed-mode bug-observable` invoked
#: with a missing or blank `--observable` -- mirrors the naming convention of
#: the two verdicts above.
VERDICT_MISSING_OBSERVABLE = "missing-observable"

_TEMPLATE_RELATIVE_PATH = Path("nWave/templates/expectation-charter.md")
_TEMPLATE_HEADING = "## Template"

#: Annotation tokens (normalised: stripped, lower-cased, leading `@` dropped)
#: that mark a Slice Plan row as NOT observable -- infra/prefactoring rows
#: carry no user-visible value and never get a charter scaffold (mirrors the
#: normalisation `validate_feature_delta._classify_slice_cohesion` applies).
_NON_OBSERVABLE_ANNOTATIONS = frozenset({"infrastructure", "prefactoring"})

#: Filesystem-safe cap on the generated `<intent-name>.md` basename,
#: INCLUDING the `.md` suffix -- dogfood finding: a real Value statement is a
#: full user sentence (262 chars observed), and a slug derived from the
#: ENTIRE sentence crashes the scaffold write with `OSError: File name too
#: long`. Comfortably under the 255-byte NAME_MAX most filesystems enforce.
_MAX_SCAFFOLD_FILENAME_LENGTH = 100
_SCAFFOLD_SUFFIX = ".md"
_MAX_SLUG_LENGTH = _MAX_SCAFFOLD_FILENAME_LENGTH - len(_SCAFFOLD_SUFFIX)


def _kebab_slug(value_statement: str) -> str:
    """Kebab-slug a Value statement: lowercase words joined by single
    hyphens, TRUNCATED FROM THE END to `_MAX_SLUG_LENGTH` chars. Pure.

    Truncation lands on a hyphen boundary (never leaves a half-cut word)
    unless the Value statement's own first word already exceeds the bound --
    the slug is never silently emptied. Deterministic: no run-varying
    disambiguator (hash/counter) is appended, so the SAME long Value
    statement resolves to the SAME filename on every run -- idempotency
    (never-overwrite) depends on that stability.
    """
    normalised = re.sub(r"[^A-Za-z0-9\s-]", "", value_statement).strip().lower()
    slug = re.sub(r"\s+", "-", normalised)
    if len(slug) <= _MAX_SLUG_LENGTH:
        return slug
    truncated = slug[:_MAX_SLUG_LENGTH]
    boundary = truncated.rfind("-")
    if boundary > 0:
        truncated = truncated[:boundary]
    return truncated


def _is_observable(annotation: str) -> bool:
    """True when a Slice Plan row's Annotation cell marks user-visible value
    (i.e. it is neither `@infrastructure` nor `@prefactoring`). Pure."""
    normalised = annotation.strip().lower().lstrip("@")
    return normalised not in _NON_OBSERVABLE_ANNOTATIONS


def _observable_slice_rows(content: str) -> list[dict[str, str]]:
    """The Slice Plan rows (column -> cell dicts) for OBSERVABLE slices only.
    Pure.

    Reuses `_plan_table_rows` + `_parse_table_cells` + `_is_separator_row`
    (`des.cli.validate_feature_delta`) -- no parallel table parser (same
    machinery `feature_delta_schema._slice_plan_row` composes).
    """
    rows = _plan_table_rows(content, _SLICE_PLAN_HEADING_RE)
    if not rows:
        return []
    header = _parse_table_cells(rows[0])
    observable: list[dict[str, str]] = []
    for row in rows[1:]:
        if _is_separator_row(row):
            continue
        record = dict(zip(header, _parse_table_cells(row), strict=False))
        if _is_observable(record.get("Annotation", "")):
            observable.append(record)
    return observable


def _extract_template_skeleton(template_content: str) -> str:
    """The expectation-charter "Template" skeleton block. Pure.

    Extracts the fenced code block under the canonical `## Template` heading
    (the real shipped template's shape). Falls back to the entire file
    content when the heading/fence markers are absent, so this also works
    against a bare-skeleton fixture (no surrounding prose).
    """
    lines = template_content.splitlines()
    try:
        heading_idx = lines.index(_TEMPLATE_HEADING)
    except ValueError:
        return template_content

    fence_start = next(
        (
            idx
            for idx in range(heading_idx + 1, len(lines))
            if lines[idx].strip().startswith("```")
        ),
        None,
    )
    if fence_start is None:
        return template_content
    fence_end = next(
        (
            idx
            for idx in range(fence_start + 1, len(lines))
            if lines[idx].strip().startswith("```")
        ),
        None,
    )
    if fence_end is None:
        return template_content
    return "\n".join(lines[fence_start + 1 : fence_end]) + "\n"


def _fill_intent_section(skeleton: str, value_statement: str) -> str:
    """Replace the `## Intent` placeholder body with the Value statement
    VERBATIM. Pure.

    Every other section is left untouched -- the fresh-PO-fill placeholders
    (Preconditions, Charter, Expected observations, Session log) survive, per
    the feature-delta contract: this tool lifts the Value statement only, it
    does not invent judgment.
    """
    lines = skeleton.splitlines()
    output: list[str] = []
    idx, total = 0, len(lines)
    while idx < total:
        line = lines[idx]
        output.append(line)
        idx += 1
        if line.strip() == "## Intent":
            while (
                idx < total and lines[idx].strip() and not lines[idx].startswith("##")
            ):
                idx += 1
            output.append(value_statement)
    return "\n".join(output) + "\n"


def _scaffold_slice(
    repo_root: Path,
    feature_id: str,
    slice_row: dict[str, str],
    template_skeleton: str,
) -> tuple[str, bool]:
    """Write one charter scaffold if it does not already exist. Not pure
    (filesystem write).

    Returns:
        (filename, created) -- `created` is False when the charter already
        existed (idempotent skip, never overwritten).
    """
    value_statement = slice_row.get("Value statement", "").strip()
    filename = f"{_kebab_slug(value_statement)}.md"
    expectations_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    path = expectations_dir / filename
    if path.exists():
        return filename, False
    expectations_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(
        _fill_intent_section(template_skeleton, value_statement), encoding="utf-8"
    )
    return filename, True


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="charter-scaffold",
        description=(
            "Generate expectation-charter scaffolds for a feature's "
            "OBSERVABLE Slice Plan rows -- Intent pre-filled from the Value "
            "statement verbatim, idempotent, degrade-LOUD on a missing or "
            "malformed feature-delta."
        ),
    )
    parser.add_argument("--feature-id", required=True, help="The feature id.")
    parser.add_argument(
        "--repo-root", default=".", help="Repository root (default: cwd)."
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only 'json' is supported).",
    )
    parser.add_argument(
        "--seed-mode",
        choices=("slice-plan", "bug-observable"),
        default="slice-plan",
        help=(
            "'slice-plan' (default) scaffolds every observable Slice Plan row "
            "from the feature-delta -- byte-identical to the pre-slice-03 "
            "behaviour. 'bug-observable' scaffolds ONE charter straight from "
            "--observable text, no Slice Plan read."
        ),
    )
    parser.add_argument(
        "--observable",
        default=None,
        help=(
            "Required (and must be non-blank) for --seed-mode bug-observable: "
            "the bug's observable behaviour, user-side, pre-filled into the "
            "scaffold's Intent section verbatim."
        ),
    )
    return parser


def _degrade(feature_id: str, verdict: str, detail: str) -> int:
    """Emit a degrade-LOUD JSON payload (zero scaffolds attempted) and return
    the non-zero exit code."""
    print(
        json.dumps(
            {
                "feature_id": feature_id,
                "created": [],
                "skipped": [],
                "observable_slices": 0,
                "verdict": verdict,
                "detail": detail,
            }
        )
    )
    return 1


def _run_bug_observable(
    repo_root: Path, feature_id: str, observable: str | None
) -> int:
    """`--seed-mode bug-observable`: no Slice Plan read -- ONE charter
    scaffold straight from `--observable` text (Intent pre-filled verbatim,
    same skeleton/idempotency contract as the slice-plan path). Degrades LOUD
    on a missing/blank `--observable` (the slice-01 blank-Value lesson
    applies here too: never a `.md` garbage file)."""
    if observable is None or not observable.strip():
        return _degrade(
            feature_id,
            VERDICT_MISSING_OBSERVABLE,
            "--observable is required (and must be non-blank) for "
            "--seed-mode bug-observable",
        )

    template_path = repo_root / _TEMPLATE_RELATIVE_PATH
    try:
        template_content = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _degrade(
            feature_id,
            VERDICT_MISSING_CHARTER_TEMPLATE,
            f"cannot read charter template at {template_path}: {exc}",
        )
    template_skeleton = _extract_template_skeleton(template_content)

    row = {"Slice": "bug-observable", "Value statement": observable}
    filename, was_created = _scaffold_slice(
        repo_root, feature_id, row, template_skeleton
    )
    created = [filename] if was_created else []
    skipped = [] if was_created else [filename]

    print(
        json.dumps(
            {
                "feature_id": feature_id,
                "created": created,
                "skipped": skipped,
                "observable_slices": 1,
                "verdict": VERDICT_ACCEPTED,
                "detail": f"{len(created)} scaffold(s) created, {len(skipped)} skipped",
            }
        )
    )
    return 0


def _run_slice_plan(repo_root: Path, feature_id: str) -> int:
    """`--seed-mode slice-plan` (default): the slice-01 behaviour, unchanged
    byte-for-byte -- scaffold every observable Slice Plan row from the
    feature's feature-delta."""
    delta_path = repo_root / "docs" / "feature" / feature_id / "feature-delta.md"
    if not delta_path.is_file():
        return _degrade(
            feature_id,
            VERDICT_MISSING_FEATURE_DELTA,
            f"feature-delta not found for '{feature_id}': {delta_path}",
        )

    content = delta_path.read_text(encoding="utf-8")
    plan_result = validate_slice_plan_content(content)
    if plan_result.verdict != VERDICT_ACCEPTED:
        return _degrade(feature_id, plan_result.verdict, plan_result.detail)

    template_path = repo_root / _TEMPLATE_RELATIVE_PATH
    try:
        template_content = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        return _degrade(
            feature_id,
            VERDICT_MISSING_CHARTER_TEMPLATE,
            f"cannot read charter template at {template_path}: {exc}",
        )
    template_skeleton = _extract_template_skeleton(template_content)

    observable_rows = _observable_slice_rows(content)
    created: list[str] = []
    skipped: list[str] = []
    for row in observable_rows:
        if not row.get("Value statement", "").strip():
            slice_name = row.get("Slice", "<unknown slice>")
            skipped.append(f"{slice_name}: blank Value statement, skipped")
            continue
        filename, was_created = _scaffold_slice(
            repo_root, feature_id, row, template_skeleton
        )
        (created if was_created else skipped).append(filename)

    print(
        json.dumps(
            {
                "feature_id": feature_id,
                "created": created,
                "skipped": skipped,
                "observable_slices": len(observable_rows),
                "verdict": VERDICT_ACCEPTED,
                "detail": f"{len(created)} scaffold(s) created, {len(skipped)} skipped",
            }
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Generate charter scaffolds; return 0 on `accepted`, non-zero on any
    degrade-LOUD verdict. Dispatches on `--seed-mode` (default 'slice-plan',
    byte-identical to the pre-slice-03 behaviour)."""
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    feature_id = args.feature_id

    if args.seed_mode == "bug-observable":
        return _run_bug_observable(repo_root, feature_id, args.observable)

    return _run_slice_plan(repo_root, feature_id)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
