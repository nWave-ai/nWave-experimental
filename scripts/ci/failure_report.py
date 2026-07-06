#!/usr/bin/env python3
"""Turn a JUnit-XML test report into a self-explaining WHAT / WHY / HOW summary.

ADR-PLAT-010 Decision 4. When the experimental (or trunk) CI fails, a developer must
understand WHAT failed, WHY, and HOW to fix it WITHOUT digging through raw logs (the
standing "every failure explains what/why/how" mandate applied to CI). This script
consumes the JUnit XML that pytest already produces (`pytest --junitxml=<file>`), extracts
every failure/error, and emits a Markdown table suitable for `$GITHUB_STEP_SUMMARY`.

Stdlib only (xml.etree) per the Python-only dependency mandate — no external deps, so it
runs on any CI runner with a Python interpreter. Language-agnostic by construction: it reads
the JUnit XML contract, not pytest internals, so a `vitest`/`cargo-test`/`go-test` runner
that emits JUnit XML is reported identically (target-machine agnosticism, ADR-PLAT-010 §3).

Usage:
    python scripts/ci/failure_report.py <junit.xml> [<junit2.xml> ...] [--title "..."]
Exit code: 0 when no failures/errors, 1 when at least one — so a CI step can gate on it.
"""

from __future__ import annotations

import argparse
import html
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Failure:
    suite: str
    classname: str
    name: str
    kind: str  # "failure" | "error"
    message: str
    file: str
    line: str

    @property
    def what(self) -> str:
        cls = self.classname.rsplit(".", 1)[-1] if self.classname else ""
        node = f"{cls}::{self.name}" if cls else self.name
        return node.strip() or "(unnamed test)"

    @property
    def why(self) -> str:
        # First non-empty line of the failure message is the assertion/error headline.
        for ln in (self.message or "").splitlines():
            ln = ln.strip()
            if ln:
                return ln[:240]
        return f"({self.kind} with no message)"

    @property
    def how(self) -> str:
        # A concrete reproduce command scoped to the failing node.
        loc = self.file or self.classname.replace(".", "/") + ".py"
        node = f"{loc}::{self.name}" if loc and not loc.endswith("/") else loc
        return f"reproduce: `uv run pytest {node} -x -vv`"


def _text(el: ET.Element | None) -> str:
    if el is None:
        return ""
    parts = [el.get("message", "")]
    if el.text:
        parts.append(el.text)
    return "\n".join(p for p in parts if p).strip()


def parse(junit_paths: list[Path]) -> tuple[list[Failure], int, int]:
    """Return (failures, total_tests, total_suites_parsed)."""
    failures: list[Failure] = []
    total = 0
    suites = 0
    for path in junit_paths:
        if not path.is_file():
            print(f"::warning::JUnit XML not found: {path}", file=sys.stderr)
            continue
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError as exc:
            print(f"::warning::unparseable JUnit XML {path}: {exc}", file=sys.stderr)
            continue
        # Root may be <testsuites> or a single <testsuite>.
        testsuites = root.iter("testsuite")
        for suite in testsuites:
            suites += 1
            suite_name = suite.get("name", path.stem)
            for case in suite.iter("testcase"):
                total += 1
                for kind in ("failure", "error"):
                    node = case.find(kind)
                    if node is not None:
                        failures.append(
                            Failure(
                                suite=suite_name,
                                classname=case.get("classname", ""),
                                name=case.get("name", ""),
                                kind=kind,
                                message=_text(node),
                                file=case.get("file", ""),
                                line=case.get("line", ""),
                            )
                        )
    return failures, total, suites


def render(failures: list[Failure], total: int, title: str) -> str:
    if not failures:
        return f"## ✅ {title}\n\nAll **{total}** tests passed — nothing to explain.\n"
    lines = [
        f"## ❌ {title} — {len(failures)} failing of {total}",
        "",
        "Every failure below states **what** broke, **why**, and **how** to fix it —",
        "no need to open the raw logs.",
        "",
        "| # | WHAT (test) | WHY (cause) | HOW (fix / reproduce) |",
        "|---|---|---|---|",
    ]
    for i, f in enumerate(failures, 1):
        what = html.escape(f.what).replace("|", "\\|")
        why = html.escape(f.why).replace("|", "\\|")
        how = f.how.replace("|", "\\|")
        badge = "🔴 error" if f.kind == "error" else "❌ fail"
        lines.append(f"| {i} | {badge} `{what}` | {why} | {how} |")
    lines += [
        "",
        '**Suite:** run `uv run pytest -m "unit or integration or acceptance"` '
        "locally to reproduce the full set.",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("junit", nargs="+", type=Path, help="JUnit XML report file(s)")
    ap.add_argument("--title", default="CI test results", help="Summary heading")
    args = ap.parse_args(argv)

    failures, total, suites = parse(args.junit)
    if suites == 0:
        # No parseable report at all — degrade LOUD, do not silently pass.
        print(
            f"## ⚠️ {args.title} — NO test report parsed\n\n"
            f"None of the given JUnit XML files were parseable "
            f"({', '.join(str(p) for p in args.junit)}). "
            f"The test step may have crashed before emitting results — "
            f"check the raw job log.\n"
        )
        return 1
    sys.stdout.write(render(failures, total, args.title))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
