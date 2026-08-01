"""Lane path-audit scanner: extract path-like references from shipped .md assets."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path("/home/alexd/Projects/nWave-dev-wt-pathaudit")
ASSET_DIRS = [
    "nWave/skills",
    "nWave/agents",
    "nWave/tasks",
    "nWave/templates",
    "nWave/data",
]

# Path-like token: a segment chain containing at least one '/', or a bare known file.
TOKEN = re.compile(
    r"(?<![\w/.-])"
    r"(?:\.?[A-Za-z_][\w.-]*/)+"  # >=1 dir segment
    r"(?:[\w.{}%*-]+(?:\.[A-Za-z][\w]*)?)?"  # optional final segment (bare dir ok)
    r"|(?<![\w/.-])pyproject\.toml"
)

# Families we care about (prefix -> family label)
FAMILIES = {
    "docs/": "docs",
    "tests/": "tests",
    "src/": "src",
    "scripts/": "scripts",
    "nWave/": "nWave",
    "lib/python/des": "lib-des",
    ".nwave/": "dot-nwave",
    ".venv/": "venv",
    ".claude/": "dot-claude",
    "pyproject.toml": "pyproject",
    ".github/": "github",
}


def family(tok: str) -> str | None:
    for pref, lab in FAMILIES.items():
        if tok.startswith(pref) or tok == pref.rstrip("/"):
            return lab
    return None


def main() -> None:
    rows = []
    files = []
    for d in ASSET_DIRS:
        files.extend(sorted((ROOT / d).rglob("*.md")))
    for f in files:
        rel = str(f.relative_to(ROOT))
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            for m in TOKEN.finditer(line):
                tok = m.group(0)
                fam = family(tok)
                if fam is None:
                    continue
                rows.append(
                    {
                        "file": rel,
                        "line": i,
                        "token": tok,
                        "family": fam,
                        "text": line.strip()[:300],
                    }
                )
    out = ROOT / "scratch_pathaudit_occurrences.json"
    out.write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"assets scanned: {len(files)}")
    print(f"occurrences: {len(rows)}")
    print(f"files with >=1 occurrence: {len({r['file'] for r in rows})}")
    from collections import Counter

    print("\nby family (occurrences / distinct files):")
    occ = Counter(r["family"] for r in rows)
    fil = {k: len({r["file"] for r in rows if r["family"] == k}) for k in occ}
    for k, v in occ.most_common():
        print(f"  {k:12s} {v:5d}  {fil[k]:4d}")


if __name__ == "__main__":
    sys.exit(main())
