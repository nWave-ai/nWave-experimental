"""des charter-scaffold -- the producing tool for expectation-charter scaffolds.

Makes charter authoring system-paid (GDP-5) and early (GDP-1): generates a
charter SCAFFOLD at `docs/product/expectations/<feature-id>/<intent-name>.md`
using `nWave/templates/expectation-charter.md` as the skeleton, Intent
pre-filled VERBATIM from a user-side value/observable statement (uncontaminated
by construction: it never sees design/impl vocabulary). Every other section
(Preconditions, Charter, Expected observations, Session log) is left as the
template's fresh-PO-fill placeholder -- this tool does not invent judgment,
only lifts the value statement.

Three `--seed-mode` values, REQUIRED (no default), each producing exactly one
accepted scaffold run (see `--seed-mode` help / `_EXAMPLES_EPILOG` for the
per-mode cardinality and required flags): `bug-observable`,
`brownfield-discovery`, and `direct-value` (one charter each, straight from
`--observable` / `--area` / `--value`, no feature-delta read; `direct-value`
alone accepts an omitted `--feature-id`, mechanically deriving one from
`--value`).

Idempotent (never overwrites an existing charter); degrades LOUD (GDP-6) on
any missing/malformed required input for the active mode -- never a silent
no-op nor a partial scaffold that looks complete.

Architecture: pure functions for slug/skeleton/row classification; a thin
`main` shell dispatches on `--seed-mode` and does the filesystem I/O and JSON
rendering (mirrors `feature_delta_doctor`'s pure-core / thin-shell split).

CLI contract:
    des charter-scaffold --seed-mode <mode> [--feature-id <id>]
        [--observable <text> | --area <text> | --value <text>]
        [--repo-root .] [--format json]

stdout token (JSON):
    {feature_id, created:[...], skipped:[...], observable_slices:N, verdict,
     detail}
Exit 0 on `accepted` (scaffolding attempted, even when zero slices are
observable); non-zero on any degrade-LOUD verdict.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument
from des.cli._scaffold_core import decide_on_exists, emit_scaffold_verdict
from des.cli.validate_feature_delta import VERDICT_ACCEPTED
from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset


#: Degrade-LOUD token for an unreadable/absent charter template -- the one
#: local asset this tool reads besides the feature-delta.
VERDICT_MISSING_CHARTER_TEMPLATE = "missing-charter-template"

#: Degrade-LOUD token for a charter template that DOES exist on both sides
#: (the shipped/installed copy AND the operator's own checkout copy) but
#: DISAGREES between them -- `resolve_packaged_asset` classifies this as
#: AMBIGUOUS. Never silently prefer the installed copy (that is the exact
#: defect this migration closes, Mikado D82): refuse LOUD naming both.
VERDICT_AMBIGUOUS_CHARTER_TEMPLATE = "ambiguous-charter-template"

#: Degrade-LOUD token (slice-03) for `--seed-mode bug-observable` invoked
#: with a missing or blank `--observable` -- mirrors the naming convention of
#: the two verdicts above.
VERDICT_MISSING_OBSERVABLE = "missing-observable"

#: Degrade-LOUD token (slice-04) for `--seed-mode brownfield-discovery`
#: invoked with a missing or blank `--area` -- mirrors the naming convention
#: of the verdicts above.
VERDICT_MISSING_AREA = "missing-area"

#: Degrade-LOUD token for `--seed-mode direct-value` invoked with a missing
#: or blank `--value` -- mirrors the naming convention of the verdicts
#: above (K4 route fix: the honest direct-value mode for ordinary Auto M/L
#: work, no feature-delta/Slice Plan involved).
VERDICT_MISSING_VALUE = "missing-value"

#: Degrade-LOUD token for `--seed-mode direct-value` invoked with NO
#: `--feature-id` when the same `--value` seed also normalises to an empty
#: kebab-slug (symbol-only/non-Latin) -- there is then nothing mechanical to
#: derive a feature id FROM, and this mode has no Slice Plan/feature-delta
#: to fall back on. Never silently proceeds with a degenerate feature id.
VERDICT_UNDETERMINABLE_FEATURE_ID = "undeterminable-feature-id"

_TEMPLATE_RELATIVE_PATH = Path("nWave/templates/expectation-charter.md")
_TEMPLATE_HEADING = "## Template"

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


#: Grammar `resolve_slice_charter` (`des.domain.expectation_charter_mapping`)
#: accepts for `Spec rows:` -- mirrors that module's private `_SLICE_ID_PATTERN`
#: (not imported: a domain-internal symbol, and this module only needs the
#: shape, not the mapping logic itself).
_SLICE_ID_RE = re.compile(r"\Aslice-\d+\Z")

#: The three producer-owned `--seed-mode` identifiers that stamp as the
#: `Slice` field: `bug-observable`, `brownfield-discovery`, and `direct-value`.
#: Each is used when no Slice Plan is read, so the mode's own identifier is the
#: ONLY scope they can honestly claim -- a `slice-01` fabricated from the
#: template's untouched fence default is a silent-wrong claim. Deliberately a
#: closed, producer-owned set -- NOT "anything not slice-NN" -- so a future
#: third-party token (`n/a`, `human directive`, ...) keeps leaving the field
#: untouched.
_FEATURE_LEVEL_SEED_MODE_IDENTIFIERS: frozenset[str] = frozenset(
    {"bug-observable", "brownfield-discovery", "direct-value"}
)

#: The `ID:` line's `Spec rows:` field, up to the next `·` separator or end of
#: line -- same shape as `resolve_slice_charter`'s `_SPEC_ROWS_PATTERN`, scoped
#: to a replace instead of a read.
_SPEC_ROWS_FIELD_RE = re.compile(r"(Spec rows:\s*)([^·\n]+)")


def _fill_spec_rows_field(content: str, slice_id: str) -> str:
    """Replace the `ID:` line's `Spec rows:` placeholder with the slice this
    charter was actually generated for. Pure.

    Rewrites when `slice_id` matches the `slice-NN` grammar OR is one of the
    three producer-owned seed-mode identifiers (`_FEATURE_LEVEL_SEED_MODE_IDENTIFIERS`:
    `bug-observable`, `brownfield-discovery`, `direct-value`). The caller
    stamping one of these means the scaffolder already knows which seed-mode
    was used, so write it down in the comma-separated grammar
    `resolve_slice_charter` accepts, instead of copying the template's own
    literal placeholder (`<R…>`) verbatim. Any OTHER identifier is left
    UNTOUCHED -- deciding a third party's `Spec rows:` grammar stays out of scope.
    """
    if not (
        _SLICE_ID_RE.fullmatch(slice_id)
        or slice_id in _FEATURE_LEVEL_SEED_MODE_IDENTIFIERS
    ):
        return content
    lines = content.splitlines()
    for idx, line in enumerate(lines):
        if line.startswith("ID:") and _SPEC_ROWS_FIELD_RE.search(line):
            # Trailing space restored: the `[^·\n]+` capture in group 2
            # swallows the template's own space before the `·` delimiter
            # (it matches everything up to, but not including, `·`), and the
            # replacement drops group 2 entirely -- so the space must be
            # re-added here, not recovered from the match.
            lines[idx] = _SPEC_ROWS_FIELD_RE.sub(rf"\g<1>{slice_id} ", line, count=1)
            break
    return "\n".join(lines) + "\n"


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

    Names WHICH input was skipped -- a short snippet of the raw
    `--observable` / `--area` / `--value` text -- and WHY, so an
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
    slice_id = slice_row.get("Slice", "").strip()
    slug = _kebab_slug(value_statement)
    filename = f"{slug}.md"
    if not slug:
        return filename, False
    expectations_dir = repo_root / "docs" / "product" / "expectations" / feature_id
    path = expectations_dir / filename
    if decide_on_exists(target_exists=path.exists(), policy="skip") == "skip":
        return filename, False
    expectations_dir.mkdir(parents=True, exist_ok=True)
    content = _fill_intent_section(template_skeleton, value_statement)
    content = _fill_spec_rows_field(content, slice_id)
    path.write_text(content, encoding="utf-8")
    return filename, True


#: Example-invocations epilog (slice-01 of charter-scaffold-help-example,
#: #54) -- spells out the required flags per `--seed-mode` that the
#: prose-only help text left implicit. `RawDescriptionHelpFormatter` keeps
#: this block unwrapped.
_EXAMPLES_EPILOG = """\
Examples:
  # --seed-mode bug-observable: scaffolds exactly one charter, straight
  # from --observable text.
  des charter-scaffold --feature-id my-feature --seed-mode bug-observable \\
      --observable "the button does not respond to clicks"

  # --seed-mode brownfield-discovery: scaffolds exactly one discovery-framed
  # charter for an existing, undocumented --area.
  des charter-scaffold --feature-id my-feature --seed-mode brownfield-discovery \\
      --area "the legacy export pipeline"

  # --seed-mode direct-value: scaffolds exactly one charter straight from an
  # immutable user value/observable, no feature-delta/Slice Plan read.
  # --feature-id is OPTIONAL here -- omit it and one is derived mechanically
  # from --value.
  des charter-scaffold --seed-mode direct-value \\
      --value "Operator sees last night's backup succeeded before relying on it"
"""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="charter-scaffold",
        description=(
            "Generate expectation-charter scaffolds -- Intent pre-filled "
            "from the Value statement verbatim, idempotent, degrade-LOUD on "
            "any missing or malformed required input for the active mode."
        ),
        epilog=_EXAMPLES_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--feature-id",
        default=None,
        help=(
            "The feature id. Required for --seed-mode bug-observable / "
            "brownfield-discovery. Optional for --seed-mode direct-value: "
            "when omitted, a filesystem-safe feature id is derived "
            "mechanically from --value."
        ),
    )
    add_repo_root_argument(
        parser, "--repo-root", default=".", help="Repository root (default: cwd)."
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only 'json' is supported).",
    )
    parser.add_argument(
        "--seed-mode",
        choices=(
            "bug-observable",
            "brownfield-discovery",
            "direct-value",
        ),
        required=True,
        help=(
            "'bug-observable' scaffolds ONE charter straight from "
            "--observable text. 'brownfield-discovery' scaffolds ONE "
            "discovery-framed charter for an existing, undocumented --area. "
            "'direct-value' scaffolds ONE charter straight from --value text "
            "(an immutable user value/observable) -- the honest mode for "
            "ordinary Auto M/L work with a user directive; --feature-id is "
            "optional and derived mechanically from --value when omitted."
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
    parser.add_argument(
        "--value",
        default=None,
        help=(
            "Required (and must be non-blank) for --seed-mode direct-value: "
            "the immutable user value/observable (e.g. the human's directive "
            "verbatim), copied into the scaffold's Intent section verbatim. "
            "No feature-delta or Slice Plan is read."
        ),
    )
    return parser


def _degrade(feature_id: str, verdict: str, detail: str) -> int:
    """Emit a degrade-LOUD JSON payload (zero scaffolds attempted) and return
    the non-zero exit code. `verdict` here is always a non-accepted token, so
    `emit_scaffold_verdict` always returns 1 -- same as the hardcoded `return
    1` this replaces."""
    return emit_scaffold_verdict(
        {
            "feature_id": feature_id,
            "created": [],
            "skipped": [],
            "observable_slices": 0,
            "verdict": verdict,
            "detail": detail,
        }
    )


def _load_template_skeleton_or_degrade(
    repo_root: Path, feature_id: str
) -> tuple[str | None, int | None]:
    """Read + extract the charter template skeleton, or emit the shared
    degrade-LOUD payload when it is unreadable in NEITHER location tried.
    Not pure (filesystem read + the degrade path prints to stdout).

    D4 refactor (feature-end deep review): the ONE template-read locus every
    seed-mode shares -- `_run_bug_observable`, `_run_brownfield_discovery`,
    and `_run_direct_value` all previously duplicated this exact
    read-try/except/extract block byte-for-byte. Extracted verbatim
    (behavior byte-identical); no parallel template-read path remains.

    Bugfix (fix-scaffold-template-from-install-lib, RCA-confirmed): the
    template genuinely SHIPS alongside this module itself -- both the dev
    checkout (`src/des/cli/charter_scaffold.py` -> `parents[3]` = repo root)
    and the installed lib (`lib/python/des/cli/charter_scaffold.py` ->
    `parents[3]` = the lib root) keep the same `.../nWave/templates/...`
    sibling-of-source-root shape relative to `__file__`. A CONSUMER repo (no
    `nWave/templates/` of its own) was missing this MODULE-RELATIVE lookup
    entirely, so it always degraded even though the shipped template was
    findable.

    Migration (Mikado D82): resolving module-relative FIRST and falling back
    to `repo_root`-relative only on read failure meant a `repo_root` that
    carries its OWN, DIFFERENT copy of the template was never even compared
    -- the module-relative (shipped/installed) copy silently won every time,
    with no signal that the operator's own copy disagreed. Now routed
    through the shared `resolve_packaged_asset` producer (same primitive
    `wave_gate_stack_dispatch.resolve_stack` and `skill_normative_gate`
    already use): the module-relative path is named `installed` explicitly
    (not re-derived via `installed_package_root()`) so this stays anchored to
    `__file__`, matching the pre-migration resolution shape byte-for-byte in
    every non-divergent case. `repo_root` seeds the developer-checkout search
    (`.git` adjacency). AMBIGUOUS -- both copies exist and their content
    digests differ -- refuses LOUD naming both paths, never silently prefers
    the installed one. An absent template on both sides keeps the original
    degrade message, naming both locations tried (unchanged shape, so the
    existing NEITHER-found regression pin keeps its exact wording).

    Returns:
        `(template_skeleton, None)` on success -- the caller proceeds.
        `(None, exit_code)` when the template is unreadable, or AMBIGUOUS,
        at both/either location -- the caller MUST `return exit_code`
        immediately (the degrade-LOUD payload has already been printed).
    """
    module_relative_path = Path(__file__).resolve().parents[3] / _TEMPLATE_RELATIVE_PATH
    repo_root_relative_path = repo_root / _TEMPLATE_RELATIVE_PATH

    resolution = resolve_packaged_asset(
        str(_TEMPLATE_RELATIVE_PATH), start=repo_root, installed=module_relative_path
    )

    if resolution.origin is AssetOrigin.AMBIGUOUS:
        exit_code = _degrade(
            feature_id,
            VERDICT_AMBIGUOUS_CHARTER_TEMPLATE,
            f"WHAT  {resolution.detail}, and this invocation named neither.\n"
            f"WHY   scaffolding from the installed copy here would silently "
            f"ignore a local template edit at {resolution.repo} the operator "
            f"is actually working against -- the failure this refusal exists "
            f"to prevent is a scaffold built from a template the operator did "
            f"not intend.\n"
            f"HOW   reconcile the two copies (sync one to match the other), "
            f"then re-run des charter-scaffold. installed: "
            f"{resolution.installed}, checkout: {resolution.repo}",
        )
        return None, exit_code

    if resolution.is_usable:
        assert resolution.path is not None
        template_content = resolution.path.read_text(encoding="utf-8")
        return _extract_template_skeleton(template_content), None

    exit_code = _degrade(
        feature_id,
        VERDICT_MISSING_CHARTER_TEMPLATE,
        "cannot read charter template at either "
        f"{module_relative_path} (module-relative, shipped) or "
        f"{repo_root_relative_path} (repo-root-relative)",
    )
    return None, exit_code


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
    `_run_bug_observable`, `_run_brownfield_discovery`, and `_run_direct_value`
    -- all three scaffold exactly one row (`observable_slices: 1`, fixed) and
    emit the same `created`/`skipped` bucketing + payload shape.

    `raw_input` is the caller's USER-SUPPLIED text (`--observable` / `--area` /
    `--value`); `value_statement` is what actually fills Intent (verbatim for
    bug-observable and direct-value; the discovery-framed sentence for
    brownfield). The
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

    return emit_scaffold_verdict(
        {
            "feature_id": feature_id,
            "created": created,
            "skipped": skipped,
            "observable_slices": 1,
            "verdict": VERDICT_ACCEPTED,
            "detail": f"{len(created)} scaffold(s) created, {len(skipped)} skipped",
        }
    )


def _run_bug_observable(
    repo_root: Path, feature_id: str, observable: str | None
) -> int:
    """`--seed-mode bug-observable`: no Slice Plan read -- ONE charter
    scaffold straight from `--observable` text (Intent pre-filled verbatim).
    Degrades LOUD on a missing/blank `--observable` (the slice-01
    blank-Value lesson applies here too: never a `.md` garbage file)."""
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


def _derive_feature_id(value: str) -> str:
    """Deterministic, filesystem-safe feature id mechanically derived from
    the immutable `--value` seed when `--feature-id` is omitted for
    `--seed-mode direct-value`. Pure.

    Reuses `_kebab_slug` verbatim -- the SAME normalisation/truncation
    contract the scaffold filename itself already uses -- so this is never
    an LLM convention, always a mechanical function of the same seed text.
    Returns an empty string when the value has no derivable slug (caller
    degrades LOUD on that).
    """
    return _kebab_slug(value)


def _run_direct_value(
    repo_root: Path, feature_id: str | None, value: str | None
) -> int:
    """`--seed-mode direct-value`: no feature-delta/Slice Plan is read -- ONE
    charter scaffold straight from an immutable user value/observable,
    copied into Intent VERBATIM. The honest mode for ordinary Auto M/L work
    driven by a user directive (K4 route fix): PO no longer needs to invent
    a nested Agent/CLI lookup to seed a charter with no feature-delta.

    `--feature-id` is OPTIONAL: when omitted, it is derived mechanically
    (never by LLM convention) from the same `--value` seed via
    `_derive_feature_id`. Degrades LOUD when `--value` is missing/blank
    (mirrors bug-observable/brownfield-discovery), and degrades LOUD when no
    `--feature-id` was supplied AND derivation is impossible (the value
    normalises to an empty kebab-slug -- symbol-only/non-Latin input).
    """
    if value is None or not value.strip():
        return _degrade(
            feature_id or "",
            VERDICT_MISSING_VALUE,
            "--value is required (and must be non-blank) for --seed-mode direct-value",
        )

    resolved_feature_id = feature_id
    if not resolved_feature_id:
        resolved_feature_id = _derive_feature_id(value)
        if not resolved_feature_id:
            return _degrade(
                "",
                VERDICT_UNDETERMINABLE_FEATURE_ID,
                "no --feature-id was supplied and a filesystem-safe feature "
                f"id could not be mechanically derived from --value {value!r} "
                "(symbol-only/non-Latin input normalizes to an empty slug) "
                "-- supply --feature-id explicitly",
            )

    template_skeleton, degraded_exit = _load_template_skeleton_or_degrade(
        repo_root, resolved_feature_id
    )
    if degraded_exit is not None:
        return degraded_exit
    assert template_skeleton is not None  # narrows for mypy: degraded_exit is None

    return _emit_single_scaffold_result(
        repo_root,
        resolved_feature_id,
        identifier="direct-value",
        raw_input=value,
        value_statement=value,
        template_skeleton=template_skeleton,
    )


def main(argv: list[str] | None = None) -> int:
    """Generate charter scaffolds; return 0 on `accepted`, non-zero on any
    degrade-LOUD verdict. Dispatches on `--seed-mode` (required, no default).

    `--feature-id` stays byte-identically REQUIRED for the two slice-scoped
    seed-modes (argparse itself no longer enforces this -- only
    `direct-value` may omit it -- so this replicates argparse's own
    required-argument error, same message and exit code, for the other
    two)."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root)
    feature_id = args.feature_id

    if args.seed_mode != "direct-value" and not feature_id:
        parser.error("the following arguments are required: --feature-id")

    if args.seed_mode == "bug-observable":
        return _run_bug_observable(repo_root, feature_id, args.observable)
    if args.seed_mode == "brownfield-discovery":
        return _run_brownfield_discovery(repo_root, feature_id, args.area)
    return _run_direct_value(repo_root, feature_id, args.value)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
