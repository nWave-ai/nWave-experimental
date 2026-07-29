"""``des verify-spec-coverage`` -- the P3.2 spec-coverage gate.

Expectation (evolution-plan P3.2): a requirement without an AT is a VISIBLE
red row, never a silent absence. The external eval's largest weighted gap
(~75 of 148 lost points) was requirements -- UI screens, e2e journey, NFRs,
identity/security, input validation, build/packaging -- that no AT ever
covered and nothing ever flagged. This gate takes the requirement checklist
extracted at DISTILL-open (P3.1) and the AT corpus, and refuses DISTILL-exit
while ANY checklist row lacks a covering AT.

Checklist grammar (the mechanical contract, deliberately simple):

  A checklist row declares ONE requirement and carries (a) an ID matching
  ``R<n>`` or ``R-S<two digits>-<two digits>`` and (b) a category from the CLOSED set
  {ui, e2e, nfr, security, validation, build, functional}. Two row forms:

    table row:  | R12 | <requirement text> | ui |
        cells split on ``|``; the ID is the first cell matching the closed
        requirement-ID grammar;
        the category is the first OTHER cell equal (case-insensitive) to a
        closed-set name; the remaining cells join into the text.
        Header/separator rows (no ``R\\d+`` cell) are ignored.

    list row:   - R12 [ui] <requirement text>
        ``-`` or ``*`` bullet, the ID, the category in square brackets
        (case-insensitive), then the text.

  A row that carries an R-id but NO valid category is MALFORMED: the gate
  degrades LOUD (exit 2) naming the line -- a half-parsed checklist must
  never silently shrink the coverage denominator. Duplicate R-ids are
  likewise malformed (an ambiguous denominator is no denominator).

Coverage discriminator -- an AT covers requirement Rn iff it carries the
marker (document once, enforce mechanically):

  pytest   -- ``@pytest.mark.covers("R12")`` (>=1 string args; function- or
              class-level) OR a ``# covers: R12`` comment inside the test
              function body (multiple IDs allowed on the line) OR the token
              ``R12`` in the test function docstring.
  Gherkin  -- a ``@covers-R12`` tag (Feature- or Scenario-level).

Verdicts (degrade-LOUD, never silent-pass; every failure states WHAT failed,
WHY, and HOW to fix -- the standing what/why/how rule):

    0  SpecCoverageVerified      -- every checklist row is covered by >=1 AT;
                                    payload carries N/M counts per category
    1  SpecCoverageRefused       -- >=1 uncovered row; each is a visible red
                                    line {id, category, text, how}; the SIX
                                    MANDATORY categories (ui, e2e, nfr,
                                    security, validation, build -- the eval's
                                    silent-absence classes) are called out
                                    explicitly when uncovered
    2  SpecCoverageIndeterminate -- missing/malformed checklist or empty AT
                                    corpus; a feature without a checklist
                                    cannot claim coverage -- NEVER a pass

Python + stdlib only; static analysis, no test execution.
"""

from __future__ import annotations

import argparse
import ast
import io
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path

from des.cli._emit_json import emit_json_line as _emit
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.requirement_id import (
    COVERS_TAG_RE,
    REQUIREMENT_ID_PATTERN,
    is_requirement_id,
    requirement_ids_in,
)


def _comment_lines(source: str) -> dict[int, str]:
    """Map 1-based line number -> real COMMENT token text via ``tokenize``.

    Comment-aware: only ``tokenize.COMMENT`` tokens are collected, so a
    string literal that happens to contain marker-shaped text (e.g.
    ``"# covers: R1"`` as fixture data passed to ``.write_text(...)``) is
    never mistaken for a genuine comment. On a tokenize failure (should not
    happen for a file that already parsed via ``ast.parse``) degrades to no
    comments rather than raising -- callers already surface parse failures.
    """
    comments: dict[int, str] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comments[tok.start[0]] = tok.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return comments
    return comments


CATEGORIES = frozenset(
    {"ui", "e2e", "nfr", "security", "validation", "build", "functional"}
)
MANDATORY_CATEGORIES = ("ui", "e2e", "nfr", "security", "validation", "build")

_LIST_ROW_RE = re.compile(rf"^[-*]\s+({REQUIREMENT_ID_PATTERN})\s+\[([^\]]+)\]\s*(.*)$")
# Language-general comment marker: accept the common single-line comment
# prefixes so `// covers: R12` (TS/JS/Rust/Java/C), `-- covers: R12` (SQL/Lua)
# and `# covers: R12` (Python/shell/Ruby) all count. Full per-language adapter
# is backlog (F-SPEC-COVERAGE-LANG-ADAPTER); this broadens the hardcoded set.
_COVERS_COMMENT_RE = re.compile(r"(?:#|//|--)\s*covers:\s*(.+)", re.IGNORECASE)

_EXIT_VERIFIED = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2

_HOW_TO_FIX = (
    "author an AT for the requirement and mark it -- pytest: "
    '@pytest.mark.covers("R<n>" or "R-S01-03") on the test, or a '
    '"# covers: R<n>" or "# covers: R-S01-03" comment in its body, or '
    'that exact ID in its docstring; Gherkin: tag the scenario "@covers-R<n>" '
    'or "@covers-R-S01-03"'
)


@dataclass(frozen=True)
class _Requirement:
    """One checklist row: a numbered requirement with its category."""

    req_id: str
    category: str
    text: str
    line: int


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "SpecCoverageIndeterminate",
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _parse_table_row(cells: list[str], lineno: int) -> _Requirement | int | None:
    """Parse one ``|``-delimited row; None when it is not a requirement row."""
    id_index = next((i for i, c in enumerate(cells) if is_requirement_id(c)), None)
    if id_index is None:
        return None
    category_index = next(
        (i for i, c in enumerate(cells) if i != id_index and c.lower() in CATEGORIES),
        None,
    )
    if category_index is None:
        return _indeterminate(
            what=f"malformed checklist row at line {lineno} ({cells[id_index]})",
            why=(
                "the row carries a requirement ID but no category cell from "
                "the closed set {ui, e2e, nfr, security, validation, build, "
                "functional}; a half-parsed row would silently shrink the "
                "coverage denominator."
            ),
            how="add a category cell to the row and re-run.",
        )
    text = " ".join(
        c for i, c in enumerate(cells) if i not in (id_index, category_index) and c
    )
    return _Requirement(
        req_id=cells[id_index],
        category=cells[category_index].lower(),
        text=text,
        line=lineno,
    )


def _parse_list_row(line: str, lineno: int) -> _Requirement | int | None:
    """Parse one ``- R12 [ui] ...`` row; None when it is not a list row."""
    match = _LIST_ROW_RE.match(line)
    if match is None:
        return None
    category = match.group(2).strip().lower()
    if category not in CATEGORIES:
        return _indeterminate(
            what=(
                f"malformed checklist row at line {lineno} "
                f"({match.group(1)}: unknown category '{match.group(2)}')"
            ),
            why=(
                "the category must come from the closed set {ui, e2e, nfr, "
                "security, validation, build, functional}."
            ),
            how="fix the [category] tag on the row and re-run.",
        )
    return _Requirement(
        req_id=match.group(1),
        category=category,
        text=match.group(3).strip(),
        line=lineno,
    )


def _parse_checklist(path: Path) -> list[_Requirement] | int:
    """Parse the checklist or return the LOUD indeterminate exit code."""
    if not path.is_file():
        return _indeterminate(
            what=f"no requirement checklist at {path}",
            why=(
                "the gate verifies N of M requirements AT-covered; without "
                "the checklist there is no M -- a feature without a "
                "checklist cannot claim coverage (a silent pass here is the "
                "eval's silent-absence disease)."
            ),
            how=(
                "extract the checklist at DISTILL-open (P3.1) -- one row per "
                "requirement, '| R<n> | <text> | <category> |' or "
                "'- R<n> [<category>] <text>' (where <n> may be "
                "legacy R<n> or canonical R-Sdd-dd) -- and pass it via "
                "--checklist."
            ),
        )
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"unreadable checklist {path}",
            why=str(exc),
            how="fix the file encoding/permissions and re-run.",
        )
    requirements: list[_Requirement] = []
    for lineno, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            row = _parse_table_row(cells, lineno)
        else:
            row = _parse_list_row(stripped, lineno)
        if isinstance(row, int):
            return row
        if row is not None:
            requirements.append(row)
    if not requirements:
        return _indeterminate(
            what=f"checklist {path} declares no requirement rows",
            why=(
                "no row matched the closed requirement-ID grammar in "
                "'| R<n> | ... | <category> |' or '- R<n> [<category>] ...'; "
                "an empty denominator "
                "would make the gate a silent pass."
            ),
            how="add one row per requirement (see this gate's --help).",
        )
    seen: dict[str, int] = {}
    for req in requirements:
        if req.req_id in seen:
            return _indeterminate(
                what=(
                    f"duplicate requirement id {req.req_id} "
                    f"(lines {seen[req.req_id]} and {req.line})"
                ),
                why="an ambiguous denominator is no denominator.",
                how="renumber the rows so every R-id is unique.",
            )
        seen[req.req_id] = req.line
    return requirements


def _covers_ids_from_marks(decorators: list[ast.expr]) -> set[str]:
    """R-ids from ``@pytest.mark.covers("R12", ...)`` / ``@mark.covers(...)``."""
    ids: set[str] = set()
    for dec in decorators:
        if not isinstance(dec, ast.Call):
            continue
        node: ast.expr = dec.func
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        if len(parts) < 2 or parts[-2] != "mark" or parts[-1] != "covers":
            continue
        for arg in dec.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                ids.update(requirement_ids_in(arg.value))
    return ids


def _covers_ids_from_body_comments(
    comments_by_line: dict[int, str], node: ast.FunctionDef | ast.AsyncFunctionDef
) -> set[str]:
    """R-ids from genuine ``# covers: R12`` COMMENT tokens inside the body.

    ``comments_by_line`` holds ONLY real ``tokenize.COMMENT`` tokens (see
    ``_comment_lines``) -- a string literal on the same line range (e.g.
    fixture data written by ``.write_text("# covers: R1")``) is never a
    COMMENT token, so it cannot leak in here.
    """
    ids: set[str] = set()
    end = node.end_lineno or node.lineno
    for lineno in range(node.lineno, end + 1):
        comment = comments_by_line.get(lineno)
        if comment is None:
            continue
        match = _COVERS_COMMENT_RE.search(comment)
        if match:
            ids.update(requirement_ids_in(match.group(1)))
    return ids


def _covered_ids_in_pytest_file(path: Path) -> set[str] | int:
    """AST scan of one pytest file -> the set of R-ids its tests cover."""
    try:
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot parse {path}",
            why=str(exc),
            how="fix the file (it must be valid Python) and re-run.",
        )
    comments_by_line = _comment_lines(source)
    covered: set[str] = set()

    def _collect(body: list[ast.stmt], inherited: frozenset[str]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                class_ids = inherited | _covers_ids_from_marks(node.decorator_list)
                _collect(node.body, frozenset(class_ids))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test"):
                    continue
                covered.update(inherited)
                covered.update(_covers_ids_from_marks(node.decorator_list))
                covered.update(_covers_ids_from_body_comments(comments_by_line, node))
                docstring = ast.get_docstring(node)
                if docstring:
                    covered.update(requirement_ids_in(docstring))

    _collect(tree.body, frozenset())
    return covered


def _covered_ids_in_feature_file(path: Path) -> set[str] | int:
    """Tag scan of one Gherkin file -> R-ids from ``@covers-R<n>`` tags."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot read {path}",
            why=str(exc),
            how="fix the file encoding/permissions and re-run.",
        )
    return set(COVERS_TAG_RE.findall(text))


_PY_SUFFIXES = frozenset({".py"})

# Single-line quoted string literals ("...", '...', `...`) with escape
# awareness. Used to blank out string CONTENT before the comment-marker scan
# so a decoy like `const marker = "// covers: R1";` cannot be mistaken for a
# real comment. Deliberately single-line only (a backtick template literal
# spanning multiple lines is a known edge case left for the per-language
# adapter backlog, F-SPEC-COVERAGE-LANG-ADAPTER).
_STRING_LITERAL_RE = re.compile(
    r'"(?:\\.|[^"\\])*"' r"|'(?:\\.|[^'\\])*'" r"|`(?:\\.|[^`\\])*`"
)


def _strip_string_literals(line: str) -> str:
    """Blank single-line quoted strings so their content cannot be mistaken
    for a genuine comment marker."""
    return _STRING_LITERAL_RE.sub("", line)


def _covered_ids_in_source_text(path: Path) -> set[str] | int:
    """Language-general text scan for `// covers: Rn` / `# covers: Rn` markers.

    For non-Python source (TS/JS/…), a Python `ast.parse` chokes on the syntax;
    the coverage marker lives in a single-line comment, so a pure line scan +
    the language-general comment regex is enough (no AST). Full per-language
    adapter is backlog (F-SPEC-COVERAGE-LANG-ADAPTER). String-literal content
    is stripped before the marker regex runs, so a decoy string containing
    marker-shaped text (e.g. `const marker = "// covers: R1";`) does not
    count -- only a marker in an actual comment does.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot read AT file {path}",
            why=str(exc),
            how="ensure the AT file is readable UTF-8 text.",
        )
    covered: set[str] = set()
    for line in text.splitlines():
        match = _COVERS_COMMENT_RE.search(_strip_string_literals(line))
        if match:
            covered.update(requirement_ids_in(match.group(1)))
    return covered


def _covered_ids_in_file(path: Path) -> set[str] | int:
    # gherkin-scope: PARSER dispatch, not AT-discovery -- `path` is already
    # discovered by this module's own multi-language file walk; this only
    # picks which content-parser reads it (pytest/TS/JS branches beside it).
    if path.suffix == ".feature":
        return _covered_ids_in_feature_file(path)
    if path.suffix in _PY_SUFFIXES:
        return _covered_ids_in_pytest_file(path)
    # TS/JS/other source: text scan (no Python AST — it would reject the syntax).
    return _covered_ids_in_source_text(path)


_AT_FILE_GLOBS = (
    # pytest convention
    "test_*.py",
    "*_test.py",
    # TS/JS convention (Vitest/Jest): *.test.ts / *.spec.ts (+ x/js variants)
    "*.test.ts",
    "*.spec.ts",
    "*.test.tsx",
    "*.spec.tsx",
    "*.test.js",
    "*.spec.js",
    "*.test.jsx",
    "*.spec.jsx",
    # Gherkin
    "*.feature",
)


def _discover(at_dir: Path) -> list[Path]:
    """AT files under a directory: pytest + TS/JS test conventions + Gherkin.

    The coverage-marker scan itself is text-based (the language-general comment
    regex), so a `.test.ts` carrying `// covers: R12` is counted like a pytest
    `# covers: R12`. Full per-language adapter is backlog.
    """
    found = [
        p for pattern in _AT_FILE_GLOBS for p in at_dir.rglob(pattern) if p.is_file()
    ]
    return sorted(set(found))


def _resolve_at_files(at_dirs: list[str], repo: Path) -> list[Path] | int:
    """Turn the --at-dir arguments into an AT file list, or degrade LOUD."""
    files: list[Path] = []
    for raw in at_dirs:
        at_dir = (repo / raw).resolve()
        if not at_dir.is_dir():
            return _indeterminate(
                what=f"--at-dir {at_dir} is not a directory",
                why="the gate cannot scan a corpus it cannot find.",
                how="pass an existing directory of AT files.",
            )
        files.extend(_discover(at_dir))
    if not files:
        return _indeterminate(
            what="empty AT corpus",
            why=(
                "no pytest (test_*.py/*_test.py), TS/JS (*.test.ts/*.spec.ts "
                "+ variants) or Gherkin (*.feature) AT files under the given "
                "--at-dir(s); zero ATs can cover zero requirements, and a "
                "silent pass on an empty corpus is the disease."
            ),
            how="point --at-dir at the directory holding the ATs.",
        )
    return sorted(set(files))


def _category_counts(
    requirements: list[_Requirement], covered: set[str]
) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for req in requirements:
        bucket = counts.setdefault(req.category, {"covered": 0, "total": 0})
        bucket["total"] += 1
        if req.req_id in covered:
            bucket["covered"] += 1
    return counts


def _refuse(
    uncovered: list[_Requirement],
    requirements: list[_Requirement],
    counts: dict[str, dict[str, int]],
) -> int:
    mandatory_uncovered = [
        category
        for category in MANDATORY_CATEGORIES
        if any(req.category == category for req in uncovered)
    ]
    _emit(
        {
            "event": "SpecCoverageRefused",
            "what": (
                f"{len(uncovered)} of {len(requirements)} requirement(s) "
                "have NO covering AT"
            ),
            "why": (
                "a requirement without an AT is a silent absence -- the "
                "eval's largest weighted gap (UI/security/validation "
                "requirements shipped uncovered with nothing flagging them); "
                "this gate makes each one a visible red row."
            ),
            "how": _HOW_TO_FIX,
            "uncovered": [
                {
                    "id": req.req_id,
                    "category": req.category,
                    "text": req.text,
                    "line": req.line,
                    "how": _HOW_TO_FIX.replace("R<n>", req.req_id),
                }
                for req in uncovered
            ],
            "mandatory_categories_uncovered": mandatory_uncovered,
            "counts": counts,
        }
    )
    for req in uncovered:
        print(f"✗ REFUSED — {req.req_id} [{req.category}] uncovered: {req.text}")
    for category in mandatory_uncovered:
        print(
            f"✗ MANDATORY category uncovered: {category} "
            "(one of the eval's silent-absence classes)"
        )
    return _EXIT_REFUSED


def _verify(requirements: list[_Requirement], counts: dict[str, dict[str, int]]) -> int:
    _emit(
        {
            "event": "SpecCoverageVerified",
            "requirements_total": len(requirements),
            "requirements_covered": len(requirements),
            "counts": counts,
        }
    )
    per_category = ", ".join(
        f"{category} {bucket['covered']}/{bucket['total']}"
        for category, bucket in sorted(counts.items())
    )
    print(
        f"✓ PASS — {len(requirements)}/{len(requirements)} requirements "
        f"AT-covered ({per_category})"
    )
    return _EXIT_VERIFIED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-spec-coverage",
        description=(
            "Verify every requirement in the DISTILL-open checklist is "
            "covered by >=1 AT (spec-coverage gate, evolution P3.2). Static "
            "analysis only; no test execution."
        ),
        epilog=(
            "Checklist rows: '| R<n> | <text> | <category> |' or "
            "'- R<n> [<category>] <text>', where IDs are legacy R<n> or "
            "canonical R-Sdd-dd, with category in {ui, e2e, nfr, "
            "security, validation, build, functional}. Coverage marker: "
            'pytest @pytest.mark.covers("R<n>" or "R-S01-03") / '
            '"# covers: R<n>" or "# covers: R-S01-03" body comment / that '
            "exact ID in the test docstring; Gherkin @covers-R<n> or "
            "@covers-R-S01-03 "
            "tag. The six mandatory categories (ui, e2e, nfr, security, "
            "validation, build) are called out explicitly when uncovered."
        ),
    )
    parser.add_argument(
        "--checklist",
        required=True,
        help="Requirement checklist file extracted at DISTILL-open (P3.1).",
    )
    parser.add_argument(
        "--at-dir",
        action="append",
        default=[],
        help="Directory of AT files (.py / .feature); repeatable.",
    )
    add_repo_root_argument(
        parser, "--repo", default=".", help="Path to the repository root."
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    if not args.at_dir:
        return _indeterminate(
            what="no AT corpus given",
            why="--at-dir was not provided; there is nothing to scan.",
            how="pass at least one --at-dir <dir> holding the ATs.",
        )

    requirements_or_exit = _parse_checklist((repo / args.checklist).resolve())
    if isinstance(requirements_or_exit, int):
        return requirements_or_exit
    requirements = requirements_or_exit

    files_or_exit = _resolve_at_files(args.at_dir, repo)
    if isinstance(files_or_exit, int):
        return files_or_exit

    covered: set[str] = set()
    for path in files_or_exit:
        ids_or_exit = _covered_ids_in_file(path)
        if isinstance(ids_or_exit, int):
            return ids_or_exit
        covered |= ids_or_exit

    counts = _category_counts(requirements, covered)
    uncovered = [req for req in requirements if req.req_id not in covered]
    if uncovered:
        return _refuse(uncovered, requirements, counts)
    return _verify(requirements, counts)


if __name__ == "__main__":
    sys.exit(main())
