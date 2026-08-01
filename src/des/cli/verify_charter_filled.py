"""des verify-charter-filled -- the backstop gate for expectation-charter
scaffolds (charter-scaffold feature, slice-02).

The enforcement half of the producing-tool vertical: slice-01
(`des charter-scaffold`) PRODUCES a charter scaffold; this gate VERIFIES a
charter is genuinely FILLED (not just scaffolded-and-forgotten) before an
operator trusts it or lets it arm a downstream EXAMINE.

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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.cli._emit_json import emit_json_line as _emit
from des.domain.expectation_charter_mapping import (
    _SLICE_ID_PATTERN,
    _SPEC_ROWS_PATTERN,
)


if TYPE_CHECKING:
    from collections.abc import Callable


VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_INDETERMINATE = "INDETERMINATE"

_PRECONDITIONS_HEADING = "## Preconditions"
_ORACLE_HEADING_PREFIX = "## Expected observations"

#: The exact scaffold placeholder tokens the `charter-scaffold` template
#: leaves behind inside the two sections this gate inspects (SSOT:
#: `nWave/templates/expectation-charter.md`, the fenced block under
#: `## Template`, as read by `charter_scaffold._extract_template_skeleton`
#: and left untouched by `_fill_intent_section`). Matching ONLY these
#: literal tokens -- never a blanket `<...>` sweep -- keeps legitimate
#: angle-bracket prose (e.g. "log in as the `<developer>`") from being
#: mistaken for surviving scaffold residue (GDP-6 false positive, sister
#: friction #90).
_SCAFFOLD_PLACEHOLDER_TOKENS = (
    "<start recipe: how to run the system from a clean state, seed state>",
    "<observable outcome, user language>",
    "<negative: what must NOT happen>",
)


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


def _has_placeholder(section_body: str) -> bool:
    """True when `section_body` still carries a scaffold token verbatim."""
    return any(token in section_body for token in _SCAFFOLD_PLACEHOLDER_TOKENS)


def _has_negative_observation(oracle_body: str) -> bool:
    """True when the oracle body carries >=1 bullet line starting with
    `Negative:` (case-insensitive) -- a real negative observation, not a
    placeholder token. Pure."""
    for line in oracle_body.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped.lower().startswith("negative:"):
            return True
    return False


def _section_is_filled(body: str | None) -> bool:
    """True when a section body exists, is non-blank, and carries no
    residual scaffold placeholder marker. Pure."""
    if body is None or not body.strip():
        return False
    return not _has_placeholder(body)


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


def _oracle_missing_reason(body: str | None, has_negative: bool) -> str:
    if not body or not body.strip():
        return "oracle: section is empty or missing -- fill in real observations"
    if _has_placeholder(body):
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


def _analyze_charter(content: str) -> _CharterAnalysis:
    """Judge a charter's content against the FILLED contract. Pure."""
    oracle_body = _section_body(
        content, lambda line: line.startswith(_ORACLE_HEADING_PREFIX)
    )
    start_recipe_body = _section_body(
        content, lambda line: line == _PRECONDITIONS_HEADING
    )

    has_negative = oracle_body is not None and _has_negative_observation(oracle_body)
    oracle_ok = _section_is_filled(oracle_body) and has_negative
    start_recipe_ok = _section_is_filled(start_recipe_body)

    missing_sections: list[str] = []
    if not oracle_ok:
        missing_sections.append(_oracle_missing_reason(oracle_body, has_negative))
    if not start_recipe_ok:
        missing_sections.append(_start_recipe_missing_reason(start_recipe_body))

    filled = oracle_ok and start_recipe_ok
    detail = (
        "charter is fully filled and ready."
        if filled
        else "still incomplete: " + "; ".join(missing_sections)
    )
    verdict = VERDICT_PASS if filled else VERDICT_FAIL
    return _CharterAnalysis(filled, missing_sections, has_negative, verdict, detail)


def charter_missing_sections(content: str) -> list[str]:
    """PUBLIC: the still-incomplete judgment sections of a charter's content --
    an EMPTY list means FILLED.

    The same judgment ``main`` renders into its JSON verdict, exposed so that
    callers which must decide on the FILLED *property* (rather than on the
    mere presence of a charter file) reuse this ONE implementation instead of
    re-deriving it. Pure.
    """
    return _analyze_charter(content).missing_sections


def _spec_rows_violation(content: str) -> str | None:
    """WHAT/WHY/HOW: is the ID line's ``Spec rows:`` field in the SAME
    vocabulary ``resolve_slice_charter``
    (``des.domain.expectation_charter_mapping``) actually accepts --
    comma-separated ``slice-NN`` tokens, matched by the SAME
    ``_SPEC_ROWS_PATTERN`` / ``_SLICE_ID_PATTERN`` that resolver uses?

    None when the field is present and every token is in-vocabulary (this
    gate's PASS path is unaffected). A WHAT/WHY/HOW reason string naming the
    offending raw value otherwise -- this is a CLI-verdict-only check, never
    folded into ``_analyze_charter``/``charter_missing_sections`` (those stay
    byte-identical; `commit_slice.py` reuses them for a different gate). Pure.
    """
    match = _SPEC_ROWS_PATTERN.search(content)
    if match is None:
        return (
            "spec-rows: the ID line has no `Spec rows:` field -- "
            "resolve_slice_charter cannot map this charter to a slice "
            "(WHY); add `Spec rows: slice-NN` to the ID line, "
            "comma-separated for multiple slices (HOW)"
        )
    raw_value = match.group(1).strip()
    tokens = [token.strip() for token in raw_value.split(",")]
    invalid = [token for token in tokens if not _SLICE_ID_PATTERN.fullmatch(token)]
    if not tokens or invalid:
        offending = ", ".join(invalid) if invalid else raw_value
        return (
            f"spec-rows: `Spec rows: {raw_value}` is not in the vocabulary "
            "resolve_slice_charter accepts -- offending value(s): "
            f"{offending!r} (WHY: only comma-separated `slice-NN` tokens "
            "resolve downstream); rewrite the ID line's Spec rows field to "
            "slice-NN form, e.g. `Spec rows: slice-01` (HOW)"
        )
    return None


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
    analysis = _analyze_charter(content)
    spec_rows_violation = _spec_rows_violation(content)

    missing_sections = list(analysis.missing_sections)
    if spec_rows_violation is not None:
        missing_sections.append(spec_rows_violation)

    # Never let a spec-rows vocabulary violation alone report PASS -- it
    # names a DIFFERENT obligation (does this charter ARM downstream) than
    # `analysis.filled` (are the prose sections compiled); both must hold.
    filled = analysis.filled and spec_rows_violation is None
    verdict = VERDICT_PASS if filled else VERDICT_FAIL
    detail = (
        "charter is fully filled and ready."
        if filled
        else "still incomplete: " + "; ".join(missing_sections)
    )

    _emit(
        {
            "charter": str(charter_path),
            "filled": filled,
            "missing_sections": missing_sections,
            "has_negative_observation": analysis.has_negative_observation,
            "verdict": verdict,
            "detail": detail,
        }
    )
    return 0 if verdict == VERDICT_PASS else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv[1:]))
