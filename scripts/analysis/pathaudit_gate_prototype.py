"""PROTOTYPE of the widened predicate for validate_no_data_refs.py. Not wired anywhere.

Demonstration only: run against a deliberately-BAD and a deliberately-GOOD file and
show both outcomes, per the check:unfired-is-not-evidence clause.

THE PREDICATE
=============
Flag an occurrence iff its ROOT segment is a path root that EXISTS ONLY in the nWave
repo and can never denote anything in the reader's own project:

    nWave/...     -> installed at ~/.claude/{skills,agents,tasks,templates,data}/,
                     ~/.claude/lib/nWave/..., ~/.nwave/nWave/..., site-packages/nWave/...
    src/des/...   -> installed at ~/.claude/lib/python/des/...

...UNLESS the occurrence is exempt (an exemption is a PROPERTY of the line, checked
mechanically -- not a per-file allow-list, which would rot):

    E1 DUAL-FORM      the line also gives the installed form for the SAME reference,
                      i.e. it says "(installed)" / "(repo)" or "whichever resolves".
    E2 DOCGEN MARKER  the line is a `<!-- GENERATED:... -->` provenance marker. Its
                      audience is docgen and the repo author, never an installed reader.
    E3 NEGATIVE       the line is a deliberately-BAD example (a `| BAD |` table row,
                      ANTI-PATTERN, "do NOT write"). Fixing it would destroy the example.

Roots deliberately NOT covered, because the token does not carry the property:
docs/ tests/ scripts/ .nwave/ pyproject.toml .github/ -- see the audit report.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


FLAGGED_ROOT = re.compile(r"(?<![\w/.-])(nWave/|src/des\b)")

E1_DUAL_FORM = re.compile(
    r"\(installed\)|\(repo\)|whichever resolves|installed path|repo path", re.I
)
E2_DOCGEN_MARKER = re.compile(r"<!--\s*GENERATED:")
E3_NEGATIVE = re.compile(r"\|\s*BAD\s*\||ANTI-PATTERN|do NOT write|WRONG:", re.I)


def exempt(line: str) -> str | None:
    if E1_DUAL_FORM.search(line):
        return "E1 dual-form"
    if E2_DOCGEN_MARKER.search(line):
        return "E2 docgen marker"
    if E3_NEGATIVE.search(line):
        return "E3 negative example"
    return None


def scan(path: Path) -> list[tuple[int, str, str]]:
    """Return [(line_no, token, line)] for non-exempt flagged occurrences."""
    out = []
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        m = FLAGGED_ROOT.search(line)
        if not m or exempt(line):
            continue
        out.append((n, m.group(1), line.strip()[:120]))
    return out


def main(argv: list[str]) -> int:
    rc = 0
    for arg in argv:
        p = Path(arg)
        v = scan(p)
        if v:
            rc = 1
            print(f"FAIL {p.name}: {len(v)} nWave-install path reference(s)")
            for n, tok, line in v:
                print(f"  {p.name}:{n}  [{tok}]  {line}")
        else:
            print(f"PASS {p.name}: no non-exempt nWave-install path reference")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
