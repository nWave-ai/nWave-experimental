"""``des verify-execution-reach`` -- the P0.4 evidence-by-execution gate.

Expectation (evolution-plan P0.4): a shipped production module with ZERO
executions across the feature's verification cannot reach done. The eval'd
seat-booking repo shipped a crash-recovery reconciler that was a throwing
scaffold and a 100%-scaffold test tier -- accepted as done because nothing
ever RAN them, and every inspector read representations instead of observing
execution. This gate closes that class with a BINARY predicate over the
feature's coverage run: never executed = never observed = cannot ship.

This is deliberately NOT a coverage-percentage threshold. A tree at 60%
coverage where every file was touched is observable; a tree at 95% with one
never-imported module hides the lethal class. The unit is the FILE:

    for every production source file under ``--src-dir`` (recursively,
    ``--ext``-filtered, default ``.py``), the file must appear in the
    Cobertura report with at least one line hit.

Files present in the report with ZERO recorded executable lines (e.g. an
empty ``__init__.py``) are vacuously reached -- they contain nothing whose
execution could be observed.

Input is Cobertura XML because it is the runner-agnostic lingua franca:
coverage.py/pytest-cov, cargo-tarpaulin, istanbul/vitest all emit it, so the
gate stays language-agnostic per the target-machine constraint (Python +
stdlib only; no runner is invoked here -- the report from the verification
run that already happened is the evidence).

Verdicts (degrade-LOUD, never silent-pass; every failure states WHAT failed,
WHY, and HOW to fix -- the standing what/why/how rule):

    0  ExecutionReachVerified      -- every production file under src-dir has
                                      >0 observed line hits (or zero
                                      executable lines)
    1  ExecutionReachRefused       -- >=1 production file with zero hits or
                                      entirely absent from the report; the
                                      payload lists each unreached file
    2  ExecutionReachIndeterminate -- the gate could not judge (missing or
                                      malformed coverage XML, missing/empty
                                      src-dir, report with no file entries);
                                      NEVER a pass
"""

from __future__ import annotations

import argparse
import json
import sys

# The XML parsed here is the coverage report produced locally by the test
# runner we just invoked, in a file we own -- not untrusted input.
from pathlib import Path
from xml.etree import ElementTree


_EXIT_VERIFIED = 0
_EXIT_REFUSED = 1
_EXIT_INDETERMINATE = 2

_REASON_ZERO_HITS = "zero-hits"
_REASON_ABSENT = "absent-from-report"


def _emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload))


def _indeterminate(what: str, why: str, how: str) -> int:
    _emit(
        {
            "event": "ExecutionReachIndeterminate",
            "what": what,
            "why": why,
            "how": how,
        }
    )
    print(f"⚠ INDETERMINATE — {what}. {why} Fix: {how}")
    return _EXIT_INDETERMINATE


def _candidate_paths(
    filename: str, sources: list[str], repo: Path, src_root: Path
) -> set[Path]:
    """Resolve a Cobertura ``filename`` to the absolute paths it could mean.

    Cobertura filenames are relative to the report's ``<source>`` roots;
    different emitters also write repo-relative, src-relative, or absolute
    paths. Phantom candidates that match no production file are harmless.
    """
    rel = Path(filename)
    if rel.is_absolute():
        return {rel.resolve()}
    candidates = {(repo / rel).resolve(), (src_root / rel).resolve()}
    for source in sources:
        candidates.add((Path(source) / rel).resolve())
    return candidates


def _parse_report(
    coverage_xml: Path, repo: Path, src_root: Path
) -> dict[Path, tuple[int, int]] | int:
    """Cobertura XML -> ``{resolved path: (executable_lines, lines_hit)}``.

    Returns the LOUD indeterminate exit code on any degrade -- a report the
    gate cannot read must never become a pass.
    """
    try:
        root = ElementTree.parse(coverage_xml).getroot()
    except OSError as exc:
        return _indeterminate(
            what=f"coverage report {coverage_xml} is missing/unreadable",
            why=str(exc),
            how=(
                "run the feature's verification with Cobertura XML output "
                "(e.g. `pytest --cov=<src> --cov-report=xml`) and point "
                "--coverage-xml at the produced file."
            ),
        )
    except ElementTree.ParseError as exc:
        return _indeterminate(
            what=f"coverage report {coverage_xml} is not well-formed XML",
            why=str(exc),
            how="regenerate the Cobertura report; do not hand-edit it.",
        )
    sources = [s.text for s in root.iter("source") if s.text]
    reach: dict[Path, tuple[int, int]] = {}
    try:
        for cls in root.iter("class"):
            filename = cls.get("filename")
            if not filename:
                continue
            lines = cls.findall("./lines/line")
            n_lines = len(lines)
            n_hit = sum(1 for ln in lines if int(ln.get("hits", "0")) > 0)
            for candidate in _candidate_paths(filename, sources, repo, src_root):
                prev = reach.get(candidate, (0, 0))
                reach[candidate] = (prev[0] + n_lines, prev[1] + n_hit)
    except ValueError as exc:
        return _indeterminate(
            what=f"coverage report {coverage_xml} has a non-integer hits value",
            why=str(exc),
            how="regenerate the Cobertura report with a standard emitter.",
        )
    if not reach:
        return _indeterminate(
            what=f"coverage report {coverage_xml} contains no file entries",
            why=(
                "an empty report means the verification run observed nothing; "
                "treating it as a pass would be the silent-pass disease."
            ),
            how=(
                "check the coverage run actually executed tests and that the "
                "--cov source spec covers the production tree."
            ),
        )
    return reach


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="des verify-execution-reach",
        description=(
            "Binary execution-reach verdict over a Cobertura coverage report: "
            "every production file under --src-dir must show >0 line hits "
            "(evidence-by-execution gate, evolution P0.4)."
        ),
    )
    parser.add_argument(
        "--coverage-xml",
        required=True,
        help="Cobertura XML report from the feature's verification run.",
    )
    parser.add_argument(
        "--src-dir",
        required=True,
        help="Production source root, repo-relative.",
    )
    parser.add_argument("--repo", default=".", help="Path to the repository.")
    parser.add_argument(
        "--ext",
        default=".py",
        help="Source file extension to enumerate (default: .py).",
    )
    args = parser.parse_args(argv)
    repo = Path(args.repo).resolve()
    src_root = (repo / args.src_dir).resolve()
    ext = args.ext if args.ext.startswith(".") else f".{args.ext}"

    if not src_root.is_dir():
        return _indeterminate(
            what=f"src-dir {args.src_dir} is not a directory under {repo}",
            why="without a production root there is nothing to verify reach on.",
            how="pass --src-dir as the repo-relative production source root.",
        )
    prod_files = sorted(p.resolve() for p in src_root.rglob(f"*{ext}") if p.is_file())
    if not prod_files:
        return _indeterminate(
            what=f"src-dir {args.src_dir} contains no {ext} files",
            why=(
                "an empty production set would make the gate a vacuous pass "
                "over nothing."
            ),
            how=f"check --src-dir and --ext ({ext}) point at the production tree.",
        )

    coverage_xml = Path(args.coverage_xml)
    if not coverage_xml.is_absolute() and not coverage_xml.exists():
        candidate = repo / coverage_xml
        if candidate.exists():
            coverage_xml = candidate

    reach_or_exit = _parse_report(coverage_xml, repo, src_root)
    if isinstance(reach_or_exit, int):
        return reach_or_exit

    unreached: list[dict[str, str]] = []
    for prod_file in prod_files:
        try:
            rel = str(prod_file.relative_to(repo))
        except ValueError:
            rel = str(prod_file)
        entry = reach_or_exit.get(prod_file)
        if entry is None:
            unreached.append({"file": rel, "reason": _REASON_ABSENT})
            continue
        n_lines, n_hit = entry
        if n_lines > 0 and n_hit == 0:
            unreached.append({"file": rel, "reason": _REASON_ZERO_HITS})

    if unreached:
        names = ", ".join(u["file"] for u in unreached)
        _emit(
            {
                "event": "ExecutionReachRefused",
                "what": (
                    f"{len(unreached)} production file(s) under "
                    f"{args.src_dir} were NEVER executed by the feature's "
                    "verification"
                ),
                "why": (
                    "zero executions = zero observations: a throwing scaffold "
                    "or never-wired module in these files would ship as done "
                    "(the seat-booking reconciler class). This is a binary "
                    "reach predicate, not a coverage-% threshold."
                ),
                "how": (
                    "wire each listed module into an executed verification "
                    "path (a test, the golden run) or delete it; then "
                    "regenerate the coverage report and re-run this gate."
                ),
                "unreached": unreached,
            }
        )
        print(f"✗ REFUSED — never-executed production files: {names}")
        return _EXIT_REFUSED

    _emit(
        {
            "event": "ExecutionReachVerified",
            "src_dir": args.src_dir,
            "files": len(prod_files),
        }
    )
    print(
        f"✓ PASS — execution reach verified "
        f"({len(prod_files)} production files, all executed)"
    )
    return _EXIT_VERIFIED


if __name__ == "__main__":
    sys.exit(main())
