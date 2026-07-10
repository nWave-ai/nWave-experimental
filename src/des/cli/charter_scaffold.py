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
    _NON_OBSERVABLE_ANNOTATIONS,
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

#: Degrade-LOUD token (slice-04) for `--seed-mode brownfield-discovery`
#: invoked with a missing or blank `--area` -- mirrors the naming convention
#: of the verdicts above.
VERDICT_MISSING_AREA = "missing-area"

_TEMPLATE_RELATIVE_PATH = Path("nWave/templates/expectation-charter.md")
_TEMPLATE_HEADING = "## Template"

#: Annotation tokens (normalised: stripped, lower-cased, leading `@` dropped)
#: that mark a Slice Plan row as NOT observable -- infra/prefactoring rows
#: carry no user-visible value and never get a charter scaffold. Imported
#: (not redefined) from `validate_feature_delta` -- SAME set
#: `_classify_slice_cohesion`'s cohesion-MECC floor vetoes on, so the two
#: modules can never drift apart on what counts as "observable".

#: Filesystem-safe cap on the generated `<intent-name>.md` basename,
#: INCLUDING the `.md` suffix -- dogfood finding: a real Value statement is a
#: full user sentence (262 chars observed), and a slug derived from the
#: ENTIRE sentence crashes the scaffold write with `OSError: File name too
#: long`. Comfortably under the 255-byte NAME_MAX most filesystems enforce.
_MAX_SCAFFOLD_FILENAME_LENGTH = 100
_SCAFFOLD_SUFFIX = ".md"
_MAX_SLUG_LENGTH = _MAX_SCAFFOLD_FILENAME_LENGTH - len(_SCAFFOLD_SUFFIX)

#: How much of a hostile (empty-slug) input to echo into its self-explaining
#: `skipped` label -- enough for an operator to recognise WHICH input was
#: skipped, capped so a long sentence does not bloat the JSON payload.
_SKIP_LABEL_SNIPPET_LENGTH = 40


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
    if not any(char.isalnum() for char in slug):
        return ""
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


def _empty_slug_skip_label(identifier: str, raw_input: str) -> str:
    """Self-explaining (GDP-3) `skipped`-list entry for an input that
    normalised to an EMPTY kebab-slug (symbol-only / purely non-Latin). Pure.

    Names WHICH input was skipped -- the slice-id (slice-plan mode) or a short
    snippet of the raw `--observable` / `--area` text -- and WHY, so an
    operator reading the `skipped` list never sees a bare, meaningless `.md`
    (the un-self-explaining label the feature-end review flagged, GDP-3). The
    raw input is whitespace-collapsed and truncated to
    `_SKIP_LABEL_SNIPPET_LENGTH` chars.
    """
    snippet = " ".join(raw_input.split())[:_SKIP_LABEL_SNIPPET_LENGTH]
    return (
        f"{identifier}: input {snippet!r} normalized to an empty slug "
        "(symbol-only/non-Latin); skipped, no charter written"
    )


def _scaffold_slice(
    repo_root: Path,
    feature_id: str,
    slice_row: dict[str, str],
    template_skeleton: str,
) -> tuple[str, bool]:
    """Write one charter scaffold if it does not already exist. Not pure
    (filesystem write).

    D1 guard (feature-end deep review, GDP-6 silent-wrong): a symbol-only or
    purely non-Latin Value statement/`--observable`/`--area` is NON-blank
    BEFORE `_kebab_slug` normalisation (so it sails past every
    `not text.strip()` guard upstream) but normalises to an EMPTY slug. This
    is the SINGLE LOCUS all three `--seed-mode` values funnel through, so the
    guard lives here, once: an empty post-normalisation slug is NEVER
    scaffolded -- no `.md` file is written for it, and `created` is never
    True for it -- mirroring the existing idempotent-skip contract (the
    caller's `created`-vs-`skipped` bucketing already handles `created=False`
    correctly without change).

    Returns:
        (filename, created) -- `created` is False when the charter already
        existed (idempotent skip, never overwritten) OR the Value
        statement/observable/area normalised to an empty kebab-slug (never
        written in the first place).
    """
    value_statement = slice_row.get("Value statement", "").strip()
    slug = _kebab_slug(value_statement)
    filename = f"{slug}.md"
    if not slug:
        return filename, False
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
        choices=("slice-plan", "bug-observable", "brownfield-discovery"),
        default="slice-plan",
        help=(
            "'slice-plan' (default) scaffolds every observable Slice Plan row "
            "from the feature-delta -- byte-identical to the pre-slice-03 "
            "behaviour. 'bug-observable' scaffolds ONE charter straight from "
            "--observable text, no Slice Plan read. 'brownfield-discovery' "
            "scaffolds ONE discovery-framed charter for an existing, "
            "undocumented --area, no Slice Plan read."
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
    parser.add_argument(
        "--area",
        default=None,
        help=(
            "Required (and must be non-blank) for --seed-mode "
            "brownfield-discovery: the existing, undocumented system area to "
            "retrofit a charter onto -- named in a discovery-framed Intent "
            "that invites exploring the running system, not a finished "
            "description of the area's behaviour."
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


def _load_template_skeleton_or_degrade(
    repo_root: Path, feature_id: str
) -> tuple[str | None, int | None]:
    """Read + extract the charter template skeleton, or emit the shared
    degrade-LOUD payload when it is unreadable. Not pure (filesystem read +
    the degrade path prints to stdout).

    D4 refactor (feature-end deep review): the ONE template-read locus every
    seed-mode shares -- `_run_bug_observable`, `_run_brownfield_discovery`,
    and `_run_slice_plan` all previously duplicated this exact
    read-try/except/extract block byte-for-byte. Extracted verbatim
    (behavior byte-identical); no parallel template-read path remains.

    Returns:
        `(template_skeleton, None)` on success -- the caller proceeds.
        `(None, exit_code)` when the template is unreadable -- the caller
        MUST `return exit_code` immediately (the degrade-LOUD payload has
        already been printed).
    """
    template_path = repo_root / _TEMPLATE_RELATIVE_PATH
    try:
        template_content = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        exit_code = _degrade(
            feature_id,
            VERDICT_MISSING_CHARTER_TEMPLATE,
            f"cannot read charter template at {template_path}: {exc}",
        )
        return None, exit_code
    return _extract_template_skeleton(template_content), None


def _emit_single_scaffold_result(
    repo_root: Path,
    feature_id: str,
    *,
    identifier: str,
    raw_input: str,
    value_statement: str,
    template_skeleton: str,
) -> int:
    """Scaffold ONE row and emit the shared single-scaffold JSON payload.
    Not pure (filesystem write + stdout print).

    D4 refactor: the ONE single-scaffold JSON-emission locus shared by
    `_run_bug_observable` and `_run_brownfield_discovery` -- both scaffold
    exactly one row (`observable_slices: 1`, fixed) and emitted the same
    `created`/`skipped` bucketing + payload shape, previously duplicated
    byte-for-byte. `_run_slice_plan` is NOT routed through this helper: it
    loops over N rows with its own blank-Value-statement skip and an
    `observable_slices` count that varies with the plan, so its emission
    shape genuinely differs (not a false-DRY collapse).

    `raw_input` is the caller's USER-SUPPLIED text (`--observable` / `--area`);
    `value_statement` is what actually fills Intent (the observable verbatim
    for bug-observable; the discovery-framed sentence for brownfield). The
    hostility decision reads `raw_input`, NOT `value_statement` (GDP-3):
    brownfield WRAPS the area in fixed English prose, so the composed
    `value_statement` never slugs empty -- only the raw `--area` reveals a
    symbol-only/non-Latin input. When `raw_input` normalises to an empty slug
    the row is skipped with a SELF-EXPLAINING label naming the input, never a
    bare `.md`.
    """
    if not _kebab_slug(raw_input):
        created: list[str] = []
        skipped = [_empty_slug_skip_label(identifier, raw_input)]
    else:
        row = {"Slice": identifier, "Value statement": value_statement}
        filename, was_created = _scaffold_slice(
            repo_root, feature_id, row, template_skeleton
        )
        created = [filename] if was_created else []
        # An idempotent-existing skip reports the real filename (already
        # self-explaining); the empty-slug case is handled above.
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

    template_skeleton, degraded_exit = _load_template_skeleton_or_degrade(
        repo_root, feature_id
    )
    if degraded_exit is not None:
        return degraded_exit
    assert template_skeleton is not None  # narrows for mypy: degraded_exit is None

    return _emit_single_scaffold_result(
        repo_root,
        feature_id,
        identifier="bug-observable",
        raw_input=observable,
        value_statement=observable,
        template_skeleton=template_skeleton,
    )


def _discovery_intent(area: str) -> str:
    """The discovery-framed Intent text for `--seed-mode
    brownfield-discovery`. Pure.

    INVERTS the normal derivation: instead of lifting a Value statement
    verbatim, it invites the examiner to DISCOVER and document what `area`
    is supposed to do for the user by exploring the running system -- an
    invitation, never a finished description of the area's behaviour.
    """
    return (
        f"Discover and document what {area} is supposed to do for the "
        "user, by exploring the running system."
    )


def _run_brownfield_discovery(
    repo_root: Path, feature_id: str, area: str | None
) -> int:
    """`--seed-mode brownfield-discovery`: no Slice Plan read -- ONE charter
    scaffold with a discovery-framed Intent naming `--area` (Intent inverts
    the normal derivation: it invites exploring the running system rather
    than lifting a Value statement verbatim). Degrades LOUD on a
    missing/blank `--area` (the slice-01/03 blank-input lesson applies here
    too: never a `.md` garbage file)."""
    if area is None or not area.strip():
        return _degrade(
            feature_id,
            VERDICT_MISSING_AREA,
            "--area is required (and must be non-blank) for "
            "--seed-mode brownfield-discovery",
        )

    template_skeleton, degraded_exit = _load_template_skeleton_or_degrade(
        repo_root, feature_id
    )
    if degraded_exit is not None:
        return degraded_exit
    assert template_skeleton is not None  # narrows for mypy: degraded_exit is None

    # D1 (feature-end deep review): `_discovery_intent` WRAPS `area` inside a
    # fixed-prose sentence, so a hostile (symbol-only/non-Latin) `area` never
    # makes the composed Value statement slug empty. `_emit_single_scaffold_result`
    # therefore decides hostility on the RAW `raw_input=area` (not the composed
    # value_statement), and reports a self-explaining skip naming the area.
    return _emit_single_scaffold_result(
        repo_root,
        feature_id,
        identifier="brownfield-discovery",
        raw_input=area,
        value_statement=_discovery_intent(area),
        template_skeleton=template_skeleton,
    )


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

    template_skeleton, degraded_exit = _load_template_skeleton_or_degrade(
        repo_root, feature_id
    )
    if degraded_exit is not None:
        return degraded_exit
    assert template_skeleton is not None  # narrows for mypy: degraded_exit is None

    observable_rows = _observable_slice_rows(content)
    created: list[str] = []
    skipped: list[str] = []
    for row in observable_rows:
        slice_name = row.get("Slice", "<unknown slice>")
        value_statement = row.get("Value statement", "").strip()
        if not value_statement:
            skipped.append(f"{slice_name}: blank Value statement, skipped")
            continue
        if not _kebab_slug(value_statement):
            # Hostile (symbol-only/non-Latin) Value statement: non-blank
            # pre-slug but normalises to an empty slug -- skip with a
            # self-explaining label (GDP-3), never a bare `.md`.
            skipped.append(_empty_slug_skip_label(slice_name, value_statement))
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
    if args.seed_mode == "brownfield-discovery":
        return _run_brownfield_discovery(repo_root, feature_id, args.area)

    return _run_slice_plan(repo_root, feature_id)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
