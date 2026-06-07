"""Drift gate for the Definition-of-Ready homes against the canonical item-set.

A maintainer who edits any Definition-of-Ready *home* (a skill / agent file that
transcribes or counts the canonical readiness items) is mechanically stopped when
that home's stated item count diverges from the one authoritative place --
``nWave/data/dor-items.yaml`` -- so a future drift between the homes and the
canonical set cannot reach a reviewer (DISCUSS K2/K3 / DESIGN DDD-5).

Hosted in ``scripts/cli/`` alongside its sibling gates / readers
(``read_dor_items.py`` / ``check_reuse_first_design.py``): a stdlib-only,
hook-invocable standalone with NO ``des`` gate-catalog coupling (DESIGN D-2:
nwave-dev hooks-only; the ``des`` ``_REGISTRY`` is reserved for catalogued gates,
and a drift checker is wired here, not catalogued).

Python-only mandate: no ``import yaml``. The SSOT is read with the SAME narrow
stdlib block-sequence scanner the reader uses (``items:`` sequence), and each
home's stated count is extracted with anchored DoR-item phrasing (never a bare
number, so unrelated counts -- e.g. "8 antipattern types", "5 GWT scenarios",
a "8/8" pass-example -- are not mistaken for a DoR-item count).

Stdout contract (``--format json``) -- a single JSON object::

    {"verdict": "PASS"|"FAIL"|"MALFORMED",
     "diverged_homes": [...home paths whose count diverged...],
     "checked_homes": [...home paths actually traversed...],
     "ssot_item_count": <int>}

Exit codes: 0 = PASS (every checked home consistent) | 1 = FAIL (>=1 diverged)
| 2 = MALFORMED (the SSOT is missing or carries no items -- degrade LOUDLY,
never silent-pass).

The gate is read-only: it inspects the SSOT + home bytes and never mutates them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


# This file lives at ``scripts/cli/check_dor_items_drift.py`` -> two parents up is
# the repo root. The SSOT + the default homes are repo-tracked, resolved relative
# to that root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SSOT_RELPATH = Path("nWave") / "data" / "dor-items.yaml"

# Closed verdict-token set (mirrors the read_dor_items / validate_feature_delta
# closed-token contract). The composition root reads these tokens, never a
# free-text stdout substring.
VERDICT_PASS = "PASS"
VERDICT_FAIL = "FAIL"
VERDICT_MALFORMED = "MALFORMED"

# The default count-stating DoR homes the gate guards when no --home is given --
# the homes that STATE a DoR-item count post-reconciliation (DESIGN component
# table). nw-leanux-methodology is a POINTER (states no count) and is therefore
# drift-proof, so it is NOT a default count-check target.
_DEFAULT_HOME_RELPATHS: tuple[str, ...] = (
    "nWave/skills/nw-dor-validation/SKILL.md",
    "nWave/agents/nw-product-owner.md",
    "nWave/agents/nw-product-owner-reviewer.md",
)

# Anchored DoR-item-count patterns. Each captures a single integer that is a
# *DoR-item* count by phrasing -- never a bare number. Anchoring on "DoR items",
# "Item(s) ... Hard Gate", and the "### Item N" enumeration excludes unrelated
# counts ("8 antipattern types", "5 GWT scenarios", "8/8").
_COUNT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\((\d+)\s*Items?\s*-\s*Hard\s*Gate\)", re.IGNORECASE),
    re.compile(r"\((\d+)-Item\s+Hard\s+Gate\)", re.IGNORECASE),
    re.compile(r"\ball\s+(\d+)\s+DoR\s+items?\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s+DoR\s+items?\b", re.IGNORECASE),
    re.compile(r"\b(\d+)\s+readiness\s+items?\b", re.IGNORECASE),
    re.compile(r"^###\s+Item\s+(\d+)\b", re.IGNORECASE | re.MULTILINE),
)


def _scan_block_sequence(text: str, key: str) -> list[str]:
    """Stdlib scan for a top-level ``<key>:`` block-sequence of scalars.

    Mirrors ``read_dor_items._scan_block_sequence``: the ENTIRE text after the
    ``- `` marker is the value, a sequence ends at the next zero-indent line, and
    comment-only / blank lines are skipped.
    """
    values: list[str] = []
    in_sequence = False
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if indent == 0:
            in_sequence = stripped.rstrip(":") == key and stripped.endswith(":")
            continue
        if not in_sequence or not stripped.startswith("- "):
            continue
        values.append(stripped[2:].strip())
    return values


def _read_ssot_item_count(ssot_path: Path) -> int | None:
    """Return the SSOT's ``len(items)``, or None when it cannot be measured.

    None signals MALFORMED: the SSOT file is absent, unreadable, or carries no
    ``items:`` sequence. The gate degrades LOUDLY rather than silent-passing.
    """
    try:
        text = ssot_path.read_text(encoding="utf-8")
    except OSError:
        return None
    items = _scan_block_sequence(text, "items")
    if not items:
        return None
    return len(items)


def _stated_home_count(home_text: str) -> int | None:
    """Extract a home's stated DoR-item count, or None when it states none.

    Takes the MAXIMUM integer across the anchored DoR-item phrasings (the
    enumeration max and any "N DoR items" / "N Items - Hard Gate" heading agree
    on a consistent home; the max is the home's declared item count). A home that
    states no DoR-item count (a pure pointer) returns None and is not a count
    target.
    """
    counts: list[int] = []
    for pattern in _COUNT_PATTERNS:
        counts.extend(int(match) for match in pattern.findall(home_text))
    if not counts:
        return None
    return max(counts)


def _check_home(home_path: Path, ssot_count: int) -> bool | None:
    """Return True when the home agrees with the SSOT count, False when it
    diverges, None when the home states no count (skipped, not diverged)."""
    try:
        text = home_path.read_text(encoding="utf-8")
    except OSError:
        return None
    stated = _stated_home_count(text)
    if stated is None:
        return None
    return stated == ssot_count


def _resolve_home_paths(home_args: list[str]) -> list[Path]:
    """Resolve the home-set to check: the explicit --home args, or the default
    count-stating home-set (resolved under the repo root) when none are given."""
    if home_args:
        return [Path(arg) for arg in home_args]
    return [_REPO_ROOT / relpath for relpath in _DEFAULT_HOME_RELPATHS]


def check_drift(ssot_path: Path, home_paths: list[Path]) -> dict[str, object]:
    """Pure core: drift-check every home against the SSOT count.

    Returns the structured report payload (verdict token, diverged homes,
    checked homes, ssot item count). MALFORMED short-circuits when the SSOT
    cannot be measured -- the gate names no homes consistent on an unmeasurable
    authority.
    """
    ssot_count = _read_ssot_item_count(ssot_path)
    if ssot_count is None:
        return {
            "verdict": VERDICT_MALFORMED,
            "diverged_homes": [],
            "checked_homes": [],
            "ssot_item_count": 0,
        }

    diverged: list[str] = []
    checked: list[str] = []
    for home_path in home_paths:
        agrees = _check_home(home_path, ssot_count)
        if agrees is None:
            continue
        checked.append(str(home_path))
        if not agrees:
            diverged.append(str(home_path))

    verdict = VERDICT_FAIL if diverged else VERDICT_PASS
    return {
        "verdict": verdict,
        "diverged_homes": diverged,
        "checked_homes": checked,
        "ssot_item_count": ssot_count,
    }


def _exit_code_for(verdict: str) -> int:
    if verdict == VERDICT_PASS:
        return 0
    if verdict == VERDICT_FAIL:
        return 1
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Drift-check Definition-of-Ready homes against the canonical item-set."
        )
    )
    parser.add_argument(
        "--ssot",
        default=str(_REPO_ROOT / _SSOT_RELPATH),
        help="Path to the authoritative SSOT YAML (default: the real dor-items).",
    )
    parser.add_argument(
        "--home",
        action="append",
        default=[],
        dest="homes",
        help="A DoR home markdown to drift-check (repeatable).",
    )
    parser.add_argument(
        "--format",
        choices=("json", "human"),
        default="human",
        help="Output format: machine-readable JSON or a human summary.",
    )
    args = parser.parse_args(argv)

    report = check_drift(Path(args.ssot), _resolve_home_paths(args.homes))
    verdict = str(report["verdict"])

    if args.format == "json":
        sys.stdout.write(json.dumps(report))
    elif verdict == VERDICT_PASS:
        checked = report["checked_homes"]
        count = len(checked) if isinstance(checked, list) else 0
        print(f"PASS: {count} Definition-of-Ready homes agree with the SSOT.")
    elif verdict == VERDICT_FAIL:
        diverged = report["diverged_homes"]
        names = ", ".join(diverged) if isinstance(diverged, list) else ""
        print(f"FAIL: Definition-of-Ready homes diverged from the SSOT: {names}")
    else:
        print("MALFORMED: the canonical Definition-of-Ready set could not be read.")

    return _exit_code_for(verdict)


if __name__ == "__main__":
    raise SystemExit(main())
