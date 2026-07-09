"""``des verify-negative-at`` -- the P0.3 negative-AT mandate gate.

Expectation (evolution-plan P0.3): a presence-only AT set on a CRITICAL
scenario cannot pass DISTILL. The RED->GREEN seal (P0.2) kills always-pass
tests but NOT weak ones: the eval's GS-8 legitimately went red once, then
green forever while asserting almost nothing about the atomicity guarantee it
claimed to cover. Weak assertions die only to negative ATs -- tests that
assert the WRONG output is NOT produced. Empirical anchors: GS-8 (vacuous
test on the atomicity guarantee) and lyra-tsunami's 4-of-4 features where
presence-only ATs passed every code-reading review and the negative case
caught real defects.

This gate is STATIC analysis (``ast`` for ``.py``, tag/name parsing for
``.feature``) -- it verifies the negative assertion EXISTS; executing it is
P0.2's job.

Negative-AT convention (the mechanical discriminator):

  pytest   -- a test is a NEGATIVE AT when it is marked
              ``@pytest.mark.negative_at`` OR its function name contains
              ``_not_`` / ``_never_`` / ``_rejects_`` / ``_refuses_`` /
              ``_fails_`` / ``_still_errors`` / ``_still_requires`` /
              ``_still_flags`` / ``still_flags_`` / ``_negative_control``.
  Gherkin  -- a Scenario is a NEGATIVE AT when it is tagged ``@negative``
              OR its name contains "not " / "never " / "reject"
              (case-insensitive).
  Other languages (.rs/.go/.ts/...) -- no AST, no language-specific parser;
              a language-neutral regex finds test-declaration names
              (``fn``/``func``/``function``/``def`` <name>) and applies the
              SAME pytest name-token discriminator above -- the negative verb
              lives in the identifier regardless of host language. Go-style
              camelCase/PascalCase identifiers (``TestRejectsBadInput``) are
              split into words on case transitions by the same word-based
              vocabulary the underscore-joined path uses, so ``rejects`` is
              seen as its own word regardless of the joining convention.
              JS/TS also get a second scan for the ``test``/``it``/
              ``describe`` string-call idiom (the name is a string literal,
              not an identifier); negativity there is decided by the same
              word-based vocabulary since the name is space-separated, not
              underscore-joined.

Criticality (what arms the mandate):

  pytest   -- ``@pytest.mark.critical`` on a test function or its class.
  Gherkin  -- ``@critical`` on a Scenario (or inherited from the Feature).
  --all-critical -- the caller declares every scanned file critical as a
              whole; the gate does not fabricate criticality on its own.

Scope semantics: the unit of obligation is the FILE. A file enters a
critical scope when it contains >=1 critical-marked test/scenario (or the
gate runs with ``--all-critical``). The scope is satisfied by >=1 negative
AT anywhere in that same file -- the negative case for a critical scenario
lives beside it; requiring the negative test to also carry the critical mark
would add ceremony without discriminating power.

Verdicts (degrade-LOUD, never silent-pass; every failure states WHAT failed,
WHY, and HOW to fix -- the standing what/why/how rule):

    0  NegativeAtVerified      -- every critical scope contains >=1 negative AT
    0  NegativeAtNotApplicable -- no critical scopes found and no
                                  --all-critical; N/A is honest, criticality
                                  is never fabricated
    1  NegativeAtRefused       -- >=1 critical scope has ZERO negative ATs;
                                  the payload names each offending scope
    2  NegativeAtIndeterminate -- the gate could not analyze (missing file,
                                  unparseable source, no input); NEVER a pass

Python + stdlib only; no test execution, no external tools.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


_PYTEST_NEGATIVE_MARK = "negative_at"
_PYTEST_CRITICAL_MARK = "critical"
_PYTEST_NEGATIVE_NAME_TOKENS = (
    "_not_",
    "_never_",
    "_rejects_",
    "_refuses_",
    "_fails_",
    "_still_errors",
    "_still_requires",
    "_still_flags",
    "still_flags_",
    "_negative_control",
)
_GENERIC_TEST_DECL_PATTERN = re.compile(r"\b(?:fn|func|function|def)\s+([A-Za-z_]\w*)")
_JS_TEST_CALL_PATTERN = re.compile(r"\b(?:test|it|describe)\s*\(\s*(['\"`])(.*?)\1")
_WORD_SPLIT_PATTERN = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_NEGATIVE_INTENT_WORDS = frozenset(
    {"rejects", "reject", "refuses", "refuse", "never", "fails", "fail", "errors"}
)
_NEGATIVE_INTENT_PHRASES = ("does not", "doesn't", "cannot", "can't", "not allow")
_GHERKIN_NEGATIVE_TAG = "negative"
_GHERKIN_CRITICAL_TAG = "critical"
_GHERKIN_NEGATIVE_NAME_TOKENS = ("not ", "never ", "reject")

_EXIT_VERIFIED = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2

_HOW_TO_FIX = (
    "add an AT asserting the wrong outcome is NOT produced -- e.g. an "
    "unrelated input must NOT trigger the behavior; see the negative-AT "
    "convention in this gate's --help"
)


@dataclass(frozen=True)
class _Case:
    """One test function (pytest) or Scenario (Gherkin) found by the scan."""

    name: str
    line: int
    critical: bool
    negative: bool


@dataclass(frozen=True)
class _FileScan:
    """The per-file scan result: every case, plus the file's scope facts."""

    path: Path
    cases: tuple[_Case, ...]

    def critical_cases(self) -> tuple[_Case, ...]:
        return tuple(c for c in self.cases if c.critical)

    def negative_cases(self) -> tuple[_Case, ...]:
        return tuple(c for c in self.cases if c.negative)


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload))


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "NegativeAtIndeterminate",
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _mark_names(decorators: list[ast.expr]) -> set[str]:
    """Extract pytest mark names from ``@pytest.mark.X`` / ``@mark.X`` forms."""
    names: set[str] = set()
    for dec in decorators:
        node: ast.expr = dec.func if isinstance(dec, ast.Call) else dec
        parts: list[str] = []
        while isinstance(node, ast.Attribute):
            parts.append(node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            parts.append(node.id)
        parts.reverse()
        if len(parts) >= 2 and parts[-2] == "mark":
            names.add(parts[-1])
    return names


def _split_words(name: str) -> list[str]:
    """Split an identifier/phrase into lowercase words -- snake_case,
    camelCase, PascalCase, space-separated, and acronym-aware, uniformly.
    A lower->upper case transition (``rejectsInvalid`` -> ``rejects`` /
    ``Invalid``) and an acronym-then-word transition (``HTTPServer`` ->
    ``HTTP`` / ``Server``) are both split, exactly like an existing
    underscore/space/hyphen separator already is -- so
    ``TestRejectsBadInput`` and ``test_rejects_bad_input`` yield the same
    word set. Never raises: a name with no letter/digit runs yields ``[]``.
    """
    return [w.lower() for w in _WORD_SPLIT_PATTERN.findall(name)]


def _name_signals_negative(name: str) -> bool:
    """Word-based negative-intent SSOT, shared by the underscore-joined
    identifier path, the camelCase/PascalCase identifier path (Go's
    ``TestRejectsBadInput`` / ``TestDoesNotAcceptNil`` idiom), and the JS/TS
    ``test``/``it``/``describe`` string-call path -- one vocabulary, one
    split, all name-casing conventions. Lowercase, split into words via
    ``_split_words`` (snake_case, camelCase, PascalCase, and space-separated
    all yield the same words), flag a negative verb (``rejects``/``never``/
    ``fails``/``errors``/...) or a negative bigram (``does not``/
    ``cannot``/...). The bigram check runs against BOTH the raw lowered name
    (catches phrases already joined by a real separator, e.g. the
    space-separated JS/TS string-call idiom) and the space-joined split
    words (catches the same bigram spanning a camelCase word boundary with
    no separator at all, e.g. ``DoesNotAcceptNil``). Conservative by
    construction -- a bare ``still``/``ok``/``not`` alone never matches, so
    ``still_works``/``still works``/``TestStillWorks``/``returns ok`` stay
    unclassified.
    """
    words = _split_words(name)
    candidates = (name.lower(), " ".join(words))
    if any(phrase in c for c in candidates for phrase in _NEGATIVE_INTENT_PHRASES):
        return True
    return any(word in _NEGATIVE_INTENT_WORDS for word in words)


def _is_negative_pytest_name(name: str) -> bool:
    return any(
        token in name for token in _PYTEST_NEGATIVE_NAME_TOKENS
    ) or _name_signals_negative(name)


def _scan_pytest_file(path: Path) -> _FileScan | int:
    """AST scan: every test_* function (module-level or in classes)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot parse {path}",
            why=str(exc),
            how="fix the file (it must be valid Python) and re-run.",
        )
    cases: list[_Case] = []

    def _collect(body: list[ast.stmt], inherited_marks: frozenset[str]) -> None:
        for node in body:
            if isinstance(node, ast.ClassDef):
                class_marks = inherited_marks | _mark_names(node.decorator_list)
                _collect(node.body, frozenset(class_marks))
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("test"):
                    continue
                marks = inherited_marks | _mark_names(node.decorator_list)
                cases.append(
                    _Case(
                        name=node.name,
                        line=node.lineno,
                        critical=_PYTEST_CRITICAL_MARK in marks,
                        negative=(
                            _PYTEST_NEGATIVE_MARK in marks
                            or _is_negative_pytest_name(node.name)
                        ),
                    )
                )

    _collect(tree.body, frozenset())
    return _FileScan(path=path, cases=tuple(cases))


def _is_negative_scenario(name: str, tags: set[str]) -> bool:
    lowered = name.lower()
    return _GHERKIN_NEGATIVE_TAG in tags or any(
        token in lowered for token in _GHERKIN_NEGATIVE_NAME_TOKENS
    )


def _scan_feature_file(path: Path) -> _FileScan | int:
    """Tag/name scan of a Gherkin .feature file (no external parser)."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot read {path}",
            why=str(exc),
            how="fix the file encoding/permissions and re-run.",
        )
    cases: list[_Case] = []
    pending_tags: set[str] = set()
    feature_tags: set[str] = set()
    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if line.startswith("@"):
            pending_tags |= {t.lstrip("@").lower() for t in line.split() if t != "@"}
        elif line.startswith("Feature:"):
            feature_tags = set(pending_tags)
            pending_tags = set()
        elif line.startswith(("Scenario:", "Scenario Outline:")):
            name = line.split(":", 1)[1].strip()
            tags = feature_tags | pending_tags
            cases.append(
                _Case(
                    name=name,
                    line=lineno,
                    critical=_GHERKIN_CRITICAL_TAG in tags,
                    negative=_is_negative_scenario(name, tags),
                )
            )
            pending_tags = set()
        elif line and not line.startswith("#"):
            pending_tags = set()
    return _FileScan(path=path, cases=tuple(cases))


def _scan_generic_name_file(path: Path) -> _FileScan | int:
    """Language-neutral scan for non-.py/.feature test files (e.g. .rs, .go,
    .ts): no AST, no language-specific parser. Two independent scans, run
    together so a file's negative AT is found via EITHER idiom:

    1. Identifier scan -- test-declaration names via a keyword-prefixed
       regex (``fn``/``func``/``function``/``def`` <name>), classified with
       the SAME name-token discriminator the pytest scanner uses; a Rust
       ``fn ..._still_errors()`` is detected exactly like a Python
       ``def ..._still_errors()`` would be.
    2. JS/TS string-call scan -- idiomatic ``test('name', ...)`` /
       ``it('name', ...)`` / ``describe('name', ...)`` calls, where the test
       name is a string literal rather than an identifier. The name is
       classified by the shared word-based vocabulary (``_name_signals_negative``)
       since it is space-separated, not underscore-joined.

    Neither scan raises on malformed/binary/empty content -- a non-matching
    regex simply yields zero cases from that arm, never a traceback.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return _indeterminate(
            what=f"cannot read {path}",
            why=str(exc),
            how="fix the file encoding/permissions and re-run.",
        )
    cases: list[_Case] = []
    for match in _GENERIC_TEST_DECL_PATTERN.finditer(text):
        name = match.group(1)
        line = text.count("\n", 0, match.start()) + 1
        cases.append(
            _Case(
                name=name,
                line=line,
                critical=False,
                negative=_is_negative_pytest_name(name),
            )
        )
    for js_match in _JS_TEST_CALL_PATTERN.finditer(text):
        name = js_match.group(2)
        line = text.count("\n", 0, js_match.start()) + 1
        cases.append(
            _Case(
                name=name,
                line=line,
                critical=False,
                negative=_name_signals_negative(name),
            )
        )
    return _FileScan(path=path, cases=tuple(cases))


def _scan_file(path: Path) -> _FileScan | int:
    if path.suffix == ".feature":
        return _scan_feature_file(path)
    if path.suffix == ".py":
        return _scan_pytest_file(path)
    return _scan_generic_name_file(path)


def _discover(test_dir: Path) -> list[Path]:
    """Test files under a directory: pytest-convention .py + all .feature."""
    found = [
        p
        for pattern in ("test_*.py", "*_test.py", "*.feature")
        for p in test_dir.rglob(pattern)
        if p.is_file()
    ]
    return sorted(set(found))


def _resolve_inputs(args: argparse.Namespace, repo: Path) -> list[Path] | int:
    """Turn --test-file/--test-dir into an analyzable file list, or degrade."""
    if args.test_dir is not None:
        test_dir = (repo / args.test_dir).resolve()
        if not test_dir.is_dir():
            return _indeterminate(
                what=f"--test-dir {test_dir} is not a directory",
                why="the gate cannot analyze what it cannot find.",
                how="pass an existing directory of test files.",
            )
        files = _discover(test_dir)
        if not files:
            return _indeterminate(
                what=f"no test files under {test_dir}",
                why=(
                    "the directory contains no test_*.py / *_test.py / "
                    "*.feature files; an empty scan would be a silent pass."
                ),
                how="point --test-dir at the directory holding the ATs.",
            )
        return files
    files = [(repo / f).resolve() for f in args.test_file]
    missing = [f for f in files if not f.is_file()]
    if missing:
        return _indeterminate(
            what="missing test file(s): " + ", ".join(str(m) for m in missing),
            why="the gate cannot analyze what it cannot find.",
            how="pass existing test files via --test-file.",
        )
    return files


def _refuse(offending: list[dict[str, object]]) -> int:
    _emit(
        {
            "event": "NegativeAtRefused",
            "what": (
                f"{len(offending)} critical scope(s) carry NO negative AT "
                "(presence-only coverage)"
            ),
            "why": (
                "a presence-only AT set proves the right output CAN appear, "
                "never that the wrong one CANNOT (the GS-8 class: red once, "
                "then green forever while asserting almost nothing); weak "
                "assertions die only to negative ATs."
            ),
            "how": _HOW_TO_FIX,
            "scopes": offending,
        }
    )
    for scope in offending:
        print(f"✗ REFUSED — critical scope without a negative AT: {scope['file']}")
    return _EXIT_REFUSED


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-negative-at",
        description=(
            "Verify every CRITICAL test scope carries >=1 negative AT -- an "
            "assertion that the WRONG output is NOT produced (evidence "
            "gate, evolution P0.3). Static analysis only; no test execution."
        ),
        epilog=(
            "Negative-AT convention: pytest -- @pytest.mark.negative_at OR "
            "name contains _not_/_never_/_rejects_/_refuses_/_fails_/"
            "_still_errors/_still_requires/_still_flags/still_flags_/"
            "_negative_control; Gherkin -- @negative tag OR scenario name "
            "contains 'not '/'never '/'reject'. Other languages (.rs/.go/"
            ".ts/...) -- name-scanned with the same pytest tokens, no "
            "AST. Critical: @pytest.mark.critical / @critical tag, or "
            "--all-critical (whole file). A critical file needs >=1 "
            "negative AT anywhere within it."
        ),
    )
    parser.add_argument(
        "--test-file",
        action="append",
        default=[],
        help="Test file to analyze (.py or .feature); repeatable.",
    )
    parser.add_argument(
        "--test-dir",
        default=None,
        help="Directory to scan for test_*.py / *_test.py / *.feature files.",
    )
    parser.add_argument("--repo", default=".", help="Path to the repository root.")
    parser.add_argument(
        "--all-critical",
        action="store_true",
        help=(
            "Treat every scanned file as a critical scope (the caller "
            "decides criticality; the gate never fabricates it)."
        ),
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()

    if not args.test_file and args.test_dir is None:
        return _indeterminate(
            what="no input given",
            why="neither --test-file nor --test-dir was provided.",
            how="pass at least one --test-file <path> or a --test-dir <dir>.",
        )

    files_or_exit = _resolve_inputs(args, repo)
    if isinstance(files_or_exit, int):
        return files_or_exit

    offending: list[dict[str, object]] = []
    critical_scopes = 0
    negative_ats_found = 0
    for path in files_or_exit:
        scan_or_exit = _scan_file(path)
        if isinstance(scan_or_exit, int):
            return scan_or_exit
        scan = scan_or_exit
        criticals = scan.critical_cases()
        if not args.all_critical and not criticals:
            continue
        critical_scopes += 1
        negatives = scan.negative_cases()
        negative_ats_found += len(negatives)
        if negatives:
            continue
        offending.append(
            {
                "file": str(scan.path),
                "scope": (
                    "whole file (--all-critical)"
                    if args.all_critical
                    else "critical-marked tests"
                ),
                "critical_cases": [{"name": c.name, "line": c.line} for c in criticals],
                "what": f"critical scope {scan.path} has no negative AT",
                "why": (
                    "every AT in this scope asserts only that the expected "
                    "output appears (presence-only); none asserts the wrong "
                    "output is NOT produced."
                ),
                "how": _HOW_TO_FIX,
            }
        )

    if offending:
        return _refuse(offending)
    if critical_scopes == 0:
        _emit(
            {
                "event": "NegativeAtNotApplicable",
                "what": "no critical scopes found",
                "files_scanned": len(files_or_exit),
            }
        )
        print(
            "○ N/A — no @critical-marked tests/scenarios and no "
            "--all-critical; criticality is never fabricated"
        )
        return _EXIT_VERIFIED
    _emit(
        {
            "event": "NegativeAtVerified",
            "critical_scopes": critical_scopes,
            "negative_ats_found": negative_ats_found,
        }
    )
    print(
        f"✓ PASS — {critical_scopes} critical scope(s), "
        f"{negative_ats_found} negative AT(s) found"
    )
    return _EXIT_VERIFIED


if __name__ == "__main__":
    sys.exit(main())
