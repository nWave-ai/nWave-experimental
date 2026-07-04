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
              ``_fails_``.
  Gherkin  -- a Scenario is a NEGATIVE AT when it is tagged ``@negative``
              OR its name contains "not " / "never " / "reject"
              (case-insensitive).

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
import sys
from dataclasses import dataclass
from pathlib import Path


_PYTEST_NEGATIVE_MARK = "negative_at"
_PYTEST_CRITICAL_MARK = "critical"
_PYTEST_NEGATIVE_NAME_TOKENS = ("_not_", "_never_", "_rejects_", "_refuses_", "_fails_")
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


def _is_negative_pytest_name(name: str) -> bool:
    return any(token in name for token in _PYTEST_NEGATIVE_NAME_TOKENS)


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


def _scan_file(path: Path) -> _FileScan | int:
    if path.suffix == ".feature":
        return _scan_feature_file(path)
    return _scan_pytest_file(path)


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
            "name contains _not_/_never_/_rejects_/_refuses_/_fails_; "
            "Gherkin -- @negative tag OR scenario name contains "
            "'not '/'never '/'reject'. Critical: @pytest.mark.critical / "
            "@critical tag, or --all-critical (whole file). A critical file "
            "needs >=1 negative AT anywhere within it."
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
