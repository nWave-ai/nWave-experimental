"""Verify that one expectation charter contains an executable human oracle.

A charter is FILLED iff every judgment section the scaffold left as a TODO
placeholder has been replaced by real content:
  (a) the oracle section ("## Expected observations (oracle)") is non-empty
      AND carries >=1 negative observation line (a "the wrong output is NOT
      produced" line -- the same negative-oracle obligation the
      expectation-charter skill prescribes);
  (b) the start-recipe section ("## Preconditions") is non-empty;
  (c) no residual scaffold TODO/placeholder (`<...>`) markers remain in
      either judgment section.

Verdicts: PASS (filled), FAIL (present-but-hollow -- names EACH
still-incomplete section + HOW to fix it), INDETERMINATE (unreadable/
malformed charter path -- missing file, empty file, directory -- LOUD
what/why/how, never a bare traceback, never a false PASS). No sixth
verdict.

Structural, not semantic. This gate only detects scaffold residue and
section presence -- it never judges whether a Preconditions body actually
names a modality-appropriate PublicStartRecipe (exact CLI argv, public
library import+setup+call, endpoint+request, or URL+ordered UI actions;
ADR-SSOT-002 §4b "PublicStartRecipe precondition"). That semantic judgment
belongs to value authority and the PO's construction contract and, at
runtime, to the source-blind Examiner's start precondition (ADR-SSOT-002 §9b,
"C -> D precondition") -- never a brittle regex/keyword sniff added here to
approximate that judgment.

CLI contract:
    des verify-charter-filled --charter <path> [--format json]

stdout token (JSON):
    {charter, filled:bool, missing_sections:[...],
     has_negative_observation:bool, verdict, detail}

Architecture: pure functions for section extraction / placeholder detection
/ negative-observation detection / analysis; a thin `main` shell does the
filesystem I/O and JSON rendering (mirrors `charter_scaffold`'s pure-core /
thin-shell split). Pure Python + filesystem only -- no git.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.cli._emit_json import emit_json_line as _emit
from des.cli.charter_scaffold import (
    _TEMPLATE_RELATIVE_PATH,
    _extract_template_skeleton,
)
from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INDETERMINATE = "INDETERMINATE"

_PRECONDITIONS_HEADING = "## Preconditions"
_ORACLE_HEADING_PREFIX = "## Expected observations"

#: One `<...>` placeholder span inside the template skeleton. `[^<>]` spans
#: newlines, so a multi-line token (the Preconditions PublicStartRecipe
#: placeholder wraps across three physical lines) is captured whole.
_PLACEHOLDER_TOKEN_RE = re.compile(r"<[^<>]+>")


class CharterTemplateUnavailable(Exception):
    """The scaffold-template SSOT cannot yield placeholder tokens, so the
    FILLED property is UNDECIDABLE -- callers must degrade LOUD
    (INDETERMINATE / Block), never silently PASS."""


def _resolve_placeholder_tokens(anchor: Path) -> tuple[str, ...]:
    """The scaffold placeholder tokens, DERIVED from the template SSOT.

    Reads `nWave/templates/expectation-charter.md` through the SAME
    resolution `charter_scaffold` uses to emit scaffolds (installed tree vs
    developer checkout, AMBIGUOUS refused), extracts the fenced skeleton with
    the SAME parser (`charter_scaffold._extract_template_skeleton` -- one
    parser, no second copy to drift), and returns every literal `<...>` token
    the skeleton carries. Matching ONLY these template-derived literal tokens
    -- never a blanket `<...>` sweep over the charter -- keeps legitimate
    angle-bracket prose (e.g. "log in as the `<developer>`") from being
    mistaken for surviving scaffold residue (GDP-6 false positive, sister
    friction #90). Deriving instead of hardcoding makes producer/checker
    drift unrepresentable (GDP-0): the checker reads the same bytes the
    producer emits.

    Raises `CharterTemplateUnavailable` (LOUD what/why/how) when the template
    is absent, ambiguous, unreadable, or token-free -- never guesses.
    """
    resolution = resolve_packaged_asset(
        _TEMPLATE_RELATIVE_PATH.as_posix(), start=anchor
    )
    if resolution.origin is AssetOrigin.AMBIGUOUS or not resolution.is_usable:
        raise CharterTemplateUnavailable(
            "WHAT: the expectation-charter template SSOT cannot be resolved "
            f"({resolution.detail}). WHY: this gate derives its scaffold "
            "placeholder tokens from that template; without it FILLED is "
            "undecidable and a PASS would check nothing. HOW: reinstall nWave "
            "or reconcile/restore nWave/templates/expectation-charter.md, "
            "then rerun."
        )
    assert resolution.path is not None
    try:
        template_content = resolution.path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CharterTemplateUnavailable(
            f"WHAT: the expectation-charter template at {resolution.path} "
            f"cannot be read ({exc}). WHY: without it the scaffold "
            "placeholder tokens are unknown and FILLED is undecidable. "
            "HOW: restore read access to the template and rerun."
        ) from exc
    skeleton = _extract_template_skeleton(template_content)
    tokens = tuple(dict.fromkeys(_PLACEHOLDER_TOKEN_RE.findall(skeleton)))
    if not tokens:
        raise CharterTemplateUnavailable(
            f"WHAT: the expectation-charter template at {resolution.path} "
            "yields ZERO placeholder tokens. WHY: a token-free skeleton means "
            "the template and this gate's parser have drifted apart, and a "
            "residue check against an empty set would pass every raw "
            "scaffold. HOW: restore the canonical template (fenced skeleton "
            "under '## Template' carrying literal <...> placeholders) and "
            "rerun."
        )
    return tokens


def _section_body(content: str, is_heading: Callable[[str], bool]) -> str | None:
    """The body text following the first heading line matching `is_heading`
    (exclusive), up to the next `## ` heading or EOF. None when no matching
    heading is found. Pure."""
    lines = content.splitlines()
    start = next(
        (idx for idx, line in enumerate(lines) if is_heading(line.strip())),
        None,
    )
    if start is None:
        return None
    body_lines: list[str] = []
    for line in lines[start + 1 :]:
        if line.strip().startswith("## "):
            break
        body_lines.append(line)
    return "\n".join(body_lines)


def _has_placeholder(section_body: str, tokens: Sequence[str]) -> bool:
    """True when `section_body` still carries a scaffold token verbatim."""
    return any(token in section_body for token in tokens)


def _has_negative_observation(oracle_body: str, tokens: Sequence[str]) -> bool:
    """True when the oracle body carries >=1 bullet line starting with
    `Negative:` (case-insensitive) whose text is NOT still a scaffold
    placeholder -- a real negative observation, never the template's own
    `Negative: <...>` residue counted as one. Pure."""
    for line in oracle_body.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped.lower().startswith("negative:") and not _has_placeholder(
            stripped, tokens
        ):
            return True
    return False


def _section_is_filled(body: str | None, tokens: Sequence[str]) -> bool:
    """True when a section body exists, is non-blank, and carries no
    residual scaffold placeholder marker. Pure."""
    if body is None or not body.strip():
        return False
    return not _has_placeholder(body, tokens)


def _start_recipe_missing_reason(body: str | None) -> str:
    if not body or not body.strip():
        return (
            "start-recipe: section is empty or missing -- fill the "
            "Preconditions section with the real start recipe"
        )
    return (
        "start-recipe: still contains scaffold placeholder markers -- fill "
        "the Preconditions section with the real start recipe"
    )


def _oracle_missing_reason(
    body: str | None, has_negative: bool, tokens: Sequence[str]
) -> str:
    if not body or not body.strip():
        return "oracle: section is empty or missing -- fill in real observations"
    if _has_placeholder(body, tokens):
        return (
            "oracle: still contains scaffold placeholder markers -- fill "
            "in real observations"
        )
    if not has_negative:
        return (
            "oracle: needs >=1 negative observation line "
            "(e.g. 'Negative: ...' -- what must NOT happen)"
        )
    return "oracle: incomplete"


@dataclass(frozen=True)
class _CharterAnalysis:
    """The FILLED verdict for one charter's content. Pure result type."""

    filled: bool
    missing_sections: list[str]
    has_negative_observation: bool
    verdict: str
    detail: str


def _analyze_charter(content: str, tokens: Sequence[str]) -> _CharterAnalysis:
    """Judge a charter's content against the FILLED contract, using the
    template-derived scaffold placeholder `tokens`. Pure."""
    oracle_body = _section_body(
        content, lambda line: line.startswith(_ORACLE_HEADING_PREFIX)
    )
    start_recipe_body = _section_body(
        content, lambda line: line == _PRECONDITIONS_HEADING
    )

    has_negative = oracle_body is not None and _has_negative_observation(
        oracle_body, tokens
    )
    oracle_ok = _section_is_filled(oracle_body, tokens) and has_negative
    start_recipe_ok = _section_is_filled(start_recipe_body, tokens)

    missing_sections: list[str] = []
    if not oracle_ok:
        missing_sections.append(
            _oracle_missing_reason(oracle_body, has_negative, tokens)
        )
    if not start_recipe_ok:
        missing_sections.append(_start_recipe_missing_reason(start_recipe_body))

    filled = oracle_ok and start_recipe_ok
    detail = (
        "charter is structurally filled; PublicStartRecipe semantics are not evaluated."
        if filled
        else "still incomplete: " + "; ".join(missing_sections)
    )
    verdict = VERDICT_PASS if filled else VERDICT_FAIL
    return _CharterAnalysis(filled, missing_sections, has_negative, verdict, detail)


def charter_missing_sections(content: str, *, template_anchor: Path) -> list[str]:
    """PUBLIC: the still-incomplete judgment sections of a charter's content --
    an EMPTY list means FILLED.

    The same judgment ``main`` renders into its JSON verdict, exposed so that
    callers which must decide on the FILLED *property* (rather than on the
    mere presence of a charter file) reuse this ONE implementation instead of
    re-deriving it. ``template_anchor`` names the tree the charter belongs to
    (its own path works) so the placeholder tokens are derived from the same
    template resolution the scaffolder used there.

    Raises `CharterTemplateUnavailable` when the template SSOT cannot yield
    tokens -- callers degrade LOUD, never treat that as FILLED.
    """
    tokens = _resolve_placeholder_tokens(template_anchor)
    return _analyze_charter(content, tokens).missing_sections


def _read_charter(charter_path: Path) -> tuple[str | None, str | None]:
    """Read a charter file. Returns (content, None) on success, or
    (None, detail) on any unreadable condition -- never raises. Not pure
    (filesystem read)."""
    if not charter_path.exists():
        return None, f"charter file not found: {charter_path}"
    if charter_path.is_dir():
        return None, f"charter path is a directory, not a file: {charter_path}"
    try:
        content = charter_path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"cannot read charter at {charter_path}: {exc}"
    if not content.strip():
        return None, f"charter file is empty: {charter_path}"
    return content, None


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify-charter-filled",
        description=(
            "Verify an expectation-charter is genuinely FILLED (not just "
            "scaffolded) -- oracle with >=1 negative observation, a real "
            "start recipe, and no residual scaffold placeholder markers."
        ),
    )
    parser.add_argument("--charter", required=True, help="Path to the charter file.")
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only 'json' is supported).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Verify a charter is FILLED; return 0 on PASS, non-zero on FAIL or
    INDETERMINATE."""
    args = _build_parser().parse_args(argv)
    charter_path = Path(args.charter)

    content, read_error = _read_charter(charter_path)
    if read_error is not None:
        _emit(
            {
                "charter": str(charter_path),
                "filled": False,
                "missing_sections": [],
                "has_negative_observation": False,
                "verdict": VERDICT_INDETERMINATE,
                "detail": read_error,
            }
        )
        return 1

    assert content is not None  # invariant: read_error is None iff content is set
    try:
        tokens = _resolve_placeholder_tokens(charter_path.resolve().parent)
    except CharterTemplateUnavailable as unavailable:
        _emit(
            {
                "charter": str(charter_path),
                "filled": False,
                "missing_sections": [],
                "has_negative_observation": False,
                "verdict": VERDICT_INDETERMINATE,
                "detail": str(unavailable),
            }
        )
        return 1
    analysis = _analyze_charter(content, tokens)

    _emit(
        {
            "charter": str(charter_path),
            "filled": analysis.filled,
            "missing_sections": analysis.missing_sections,
            "has_negative_observation": analysis.has_negative_observation,
            "verdict": analysis.verdict,
            "detail": analysis.detail,
        }
    )
    return 0 if analysis.verdict == VERDICT_PASS else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
