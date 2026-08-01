"""Lane path-audit classifier.

Classifies each path occurrence on the PROPERTY that matters:
does the reference RESOLVE for the reader in their own context?

  USER-PROJECT  -- names something in the reader's OWN project. Resolves. Correct as written.
  NWAVE-INSTALL -- names something in the nWave INSTALLATION, whose path moves per host
                   (dev tree / ~/.claude / ~/.nwave). Misdirects 2 readers out of 3.
  AMBIGUOUS     -- cannot be decided from the token alone.

Second axis (ranking): how much damage does a wrong reference do?
  IMPERATIVE -- the reader is TOLD to open/run/edit it. Worst: it sends them somewhere absent.
  PROVENANCE -- cited as the source of a stated fact. Mild: nobody navigates it.
  INCIDENTAL -- illustration/example in prose. Least.
"""

from __future__ import annotations

import collections
import json
import re
from pathlib import Path


ROOT = Path("/home/alexd/Projects/nWave-dev-wt-pathaudit")

# --- nWave's OWN installation artifacts: path differs per host ------------------
# nWave/*  -> dev: nWave/... | installed CC: ~/.claude/... | installed codex: ~/.nwave/nWave/...
# src/des  -> dev: src/des/... | installed: ~/.claude/lib/python/des/...
# scripts/<subdir> -> nWave repo dirs; distribution is whitelist-only (3 files, copied FLAT),
#                     so a subdir-qualified script path does not exist for an installed user.
NWAVE_SCRIPT_DIRS = {
    "analysis",
    "automation",
    "ci",
    "cli",
    "docs_site",
    "framework",
    "hooks",
    "install",
    "maintenance",
    "mutation",
    "observability",
    "perf",
    "polyglot",
    "release",
    "reports",
    "research",
    "shared",
    "sync",
    "update",
    "validation",
}
# Dev-repo-only doc trees (not produced by any wave in a user's project).
DEV_ONLY_DOCS = {"analysis", "internal", "mikado", "epic"}
# nWave's OWN test suites. A user project has no `tests/des/` -- `des` is our package --
# nor tests/installer, tests/state_delta, ... These names are as decisive as `nWave/`.
DEV_TEST_SUITES = {
    "des",
    "build",
    "installer",
    "state_delta",
    "canary",
    "meta",
    "plugins",
    "bugs",
}
# Doc trees the waves WRITE INTO in the reader's own project.
USER_DOCS = {
    "feature",
    "product",
    "research",
    "architecture",
    "evolution",
    "adrs",
    "guides",
    "scenarios",
    "ux",
    "design",
    "adoption",
    "reference",
    "diagrams",
    "api",
}

IMPERATIVE = re.compile(
    r"\b(read|open|edit|run|invoke|execute|see|consult|load|check|inspect|cat|"
    r"grep|write|create|append|update|copy|append to|refer to|look at|"
    r"python|uv run|des )\b",
    re.I,
)
PROVENANCE = re.compile(
    r"\b(source|defined in|per|see also|cf\.|from|implemented in|enforced by|"
    r"lives in|owned by|canonical|ssot|evidence|ref:)\b",
    re.I,
)


def classify(tok: str) -> tuple[str, str]:
    """Return (verdict, reason)."""
    seg = tok.strip("/").split("/")
    head = seg[0]
    second = seg[1] if len(seg) > 1 else ""

    if head == "nWave":
        return (
            "NWAVE-INSTALL",
            "nWave asset tree: dev nWave/ | ~/.claude/ | ~/.nwave/nWave/",
        )
    if head == "src":
        if second == "des":
            return (
                "NWAVE-INSTALL",
                "nWave runtime source: installed at ~/.claude/lib/python/des/",
            )
        return "USER-PROJECT", "reader's own source tree"
    if head == "scripts":
        if second in NWAVE_SCRIPT_DIRS:
            return (
                "NWAVE-INSTALL",
                f"nWave repo script dir (scripts/{second}); not distributed",
            )
        if second.endswith(".py"):
            return "AMBIGUOUS", "bare script name: nWave's or the reader's own scripts/"
        return "AMBIGUOUS", "unqualified scripts/ reference"
    if head == "docs":
        if second in DEV_ONLY_DOCS:
            return (
                "AMBIGUOUS",
                f"docs/{second} exists in the dev repo; a reader may also have one",
            )
        if second in USER_DOCS or second.endswith(".md"):
            return "USER-PROJECT", "wave-authored doc in the reader's own project"
        return "AMBIGUOUS", f"unrecognised docs subtree ({second or 'bare'})"
    if head == ".nwave":
        return (
            "USER-PROJECT",
            "per-project state dir (<project>/.nwave/), or ~/.nwave -- resolves",
        )
    if head == "tests":
        if second in DEV_TEST_SUITES:
            return (
                "NWAVE-INSTALL",
                f"nWave's own test suite (tests/{second}); ships to no host",
            )
        return "USER-PROJECT", "reader's own test tree"
    if head == ".venv":
        return "USER-PROJECT", "reader's own virtualenv"
    if head == ".claude":
        return "USER-PROJECT", "already the installed-host form -- resolves"
    if tok == "pyproject.toml":
        return (
            "AMBIGUOUS",
            "the reader's own manifest, or nWave's -- decide per occurrence",
        )
    if head == ".github":
        return "AMBIGUOUS", "reader's CI config, or nWave's own workflows"
    return "AMBIGUOUS", "unclassified root"


def rank(text: str) -> str:
    if IMPERATIVE.search(text):
        return "IMPERATIVE"
    if PROVENANCE.search(text):
        return "PROVENANCE"
    return "INCIDENTAL"


def main() -> None:
    rows = json.loads((ROOT / "scratch_pathaudit_occurrences.json").read_text())
    for r in rows:
        r["verdict"], r["reason"] = classify(r["token"])
        r["rank"] = rank(r["text"])
    (ROOT / "scratch_pathaudit_classified.json").write_text(json.dumps(rows, indent=1))

    v = collections.Counter(r["verdict"] for r in rows)
    print(f"occurrences: {len(rows)}\n")
    print("verdict            occ   files")
    for k, n in v.most_common():
        f = len({r["file"] for r in rows if r["verdict"] == k})
        print(f"  {k:16s} {n:5d}  {f:5d}")

    print("\nNWAVE-INSTALL by rank:")
    ni = [r for r in rows if r["verdict"] == "NWAVE-INSTALL"]
    for k, n in collections.Counter(r["rank"] for r in ni).most_common():
        print(f"  {k:12s} {n:5d}")

    print("\nNWAVE-INSTALL top files:")
    for f, n in collections.Counter(r["file"] for r in ni).most_common(15):
        print(f"  {n:4d}  {f}")

    # The actionable / non-actionable split reported in the audit (S2). Lives HERE so the
    # number in the report is reproducible from committed code, not from an ad-hoc one-liner.
    e1 = re.compile(
        r"\(installed\)|\(repo\)|whichever resolves|installed path|repo path", re.I
    )
    e2 = re.compile(r"<!--\s*GENERATED:")
    e3 = re.compile(r"\|\s*BAD\s*\||ANTI-PATTERN|do NOT write|WRONG:", re.I)
    imp = re.compile(
        r"\b(read|open|run|invoke|execute|load|write|create|update|call|glob|grep|"
        r"python|uv run)\b",
        re.I,
    )
    for r in ni:
        t = r["text"]
        if e2.search(t):
            r["cls"] = "NON-ACTIONABLE docgen marker"
        elif e1.search(t):
            r["cls"] = "NON-ACTIONABLE dual-form (already correct)"
        elif e3.search(t):
            r["cls"] = "NON-ACTIONABLE negative example"
        elif imp.search(t):
            r["cls"] = "ACTIONABLE imperative"
        else:
            r["cls"] = "ACTIONABLE provenance/incidental"
    print("\nNWAVE-INSTALL actionable split:")
    for k, n in collections.Counter(r["cls"] for r in ni).most_common():
        print(f"  {n:5d}  {k}")
    (ROOT / "scratch_pathaudit_final.json").write_text(json.dumps(ni, indent=1))


if __name__ == "__main__":
    main()
