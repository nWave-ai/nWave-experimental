"""mode-locus-gate — Layer-A guardrail (mode-registry-single-locus slice-05).

Analysis §3.1: a mode may be *referenced* (inside a ``GENERATED:`` region or on
an explicit ``<!-- mode-ref-ok -->`` allow-marker line), never *re-stated* by
hand. This gate scans ``nWave/{skills,agents,tasks}`` under ``--root`` for naked
mode literals OUTSIDE those two sanctuaries and refuses non-zero, NAMING every
offender file+line — the mechanical form of the root-cause rule.

The bare-`classic` disambiguation (the load-bearing DATA decision pinned in
``tests/des/acceptance/mode_registry_single_locus/steps/domain_types_slice_05.py``
``BARE_CLASSIC_RULE``):

* ``atdd_pure`` and ``workflow.mode`` are flagged UNCONDITIONALLY — neither has
  a benign English sense.
* ``classic`` is flagged ONLY in a config/declaration shape (``mode: classic``,
  ``flavor_id: classic``, ``--mode classic``, ``classic.yaml``,
  ``workflow.mode == classic``) — NEVER the bare English word
  (``classic Scenario`` / ``classic TDD`` / ``classic 3-phase``) nor the
  descriptive prose form (``classic mode`` / ``classic-mode``) that legitimately
  survives in documentation. This keeps the clean-corpus accept side green
  while still refusing a hand-restated ``classic`` declaration.

Pure read (Mandate 8): the gate rewrites nothing. Stdlib-only, git-free.
Modelled on ``scripts/cli/cohort_classifier.py`` (ADR-028 precedent): argparse +
a small dataclass + a pure scan function + a thin ``main``.

Exit codes: 0 = no naked literal | 1 = ``--root`` invalid | 2 = at least one
naked literal (each named file+line on stdout) | 3 = INDETERMINATE (an
``nWave/`` tree exists but none of the scanned families -- ``skills`` /
``agents`` / ``tasks`` -- exist under it, so zero files were scanned; this is
NOT the same fact as a clean tree and must never report the exit-0 verdict).
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.repo_path_resolver import resolve_repo_root


# The asset families the gate guards (analysis §3.1). The flavor registry
# (`nWave/flavors/`) is the SOLE legitimate home of the literals, so it is NOT
# scanned; templates are likewise out of scope for the locus rule.
_SCANNED_FAMILIES: tuple[str, ...] = ("skills", "agents", "tasks")
_SCANNED_SUFFIXES: frozenset[str] = frozenset({".md", ".yaml", ".yml"})

ALLOW_MARKER = "<!-- mode-ref-ok -->"

# A GENERATED region is the registry's own projection — its mode literals are
# authored by docgen, not by hand, so they are masked before the scan.
_GENERATED_REGION_RE = re.compile(
    r"<!--\s*GENERATED:[a-z0-9-]+\s+START[^>]*-->.*?"
    r"<!--\s*GENERATED:[a-z0-9-]+\s+END\s*-->",
    re.DOTALL,
)

# Unconditional naked literals — no benign English sense.
_UNCONDITIONAL_RE = re.compile(r"\batdd_pure\b|\bworkflow\.mode\b")

# `classic` ONLY in a config/declaration shape (BARE_CLASSIC_RULE). Prose forms
# (`classic mode`, `classic-mode`, `classic Scenario`, `classic TDD`) are NOT
# matched — they are benign documentation, not a re-stated mode declaration.
_CLASSIC_DECLARATION_RE = re.compile(
    r"workflow\.mode\s*==\s*[\"']?classic\b"
    r"|\bmode:\s*[\"']?classic\b"
    r"|--mode[= ]+[\"']?classic\b"
    r"|\bflavor_id:\s*[\"']?classic\b"
    r"|\bclassic\.yaml\b"
)


@dataclass(frozen=True)
class Offender:
    """One naked mode literal the gate refuses, located file+line."""

    relative_path: str
    line_number: int
    literal: str
    line_text: str


def _repo_root(root_arg: str | None) -> Path:
    return resolve_repo_root(root_arg)


def _naked_literal_on_line(line: str) -> str | None:
    """The naked mode literal on *line*, or None when the line is clean.

    Allow-marked lines are sanctuaries (explicit reference). `atdd_pure` /
    `workflow.mode` are unconditional; `classic` flags only in a declaration
    shape per BARE_CLASSIC_RULE.
    """
    if ALLOW_MARKER in line:
        return None
    unconditional = _UNCONDITIONAL_RE.search(line)
    if unconditional is not None:
        return unconditional.group(0)
    classic = _CLASSIC_DECLARATION_RE.search(line)
    if classic is not None:
        return "classic"
    return None


def _scan_text(relative_path: str, text: str) -> list[Offender]:
    """Every naked literal outside GENERATED regions / allow-markers in *text*."""
    masked = _GENERATED_REGION_RE.sub(_mask_preserving_lines, text)
    offenders: list[Offender] = []
    for line_number, line in enumerate(masked.splitlines(), start=1):
        literal = _naked_literal_on_line(line)
        if literal is not None:
            offenders.append(
                Offender(relative_path, line_number, literal, line.strip()[:120])
            )
    return offenders


def _mask_preserving_lines(match: re.Match[str]) -> str:
    """Blank the GENERATED region body while keeping line numbers stable."""
    return "\n" * match.group(0).count("\n")


def _missing_families(root: Path) -> list[str]:
    """The scanned families that do NOT exist under ``root / 'nWave'``."""
    return [
        family for family in _SCANNED_FAMILIES if not (root / "nWave" / family).is_dir()
    ]


def _scanned_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for family in _SCANNED_FAMILIES:
        family_dir = root / "nWave" / family
        if not family_dir.is_dir():
            continue
        for path in sorted(family_dir.rglob("*")):
            if path.is_file() and path.suffix in _SCANNED_SUFFIXES:
                files.append(path)
    return files


def scan_for_naked_literals(root: Path) -> list[Offender]:
    """Pure scan: every naked mode literal across the guarded asset families."""
    offenders: list[Offender] = []
    for path in _scanned_files(root):
        relative = str(path.relative_to(root))
        text = path.read_text(encoding="utf-8", errors="replace")
        offenders.extend(_scan_text(relative, text))
    return offenders


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mode-locus-gate",
        description=(
            "Refuse any naked mode literal in nWave/{skills,agents,tasks} "
            "outside a GENERATED region or a <!-- mode-ref-ok --> allow-marker."
        ),
    )
    add_repo_root_argument(
        parser,
        "--root",
        default=None,
        help="Root of the asset tree to scan (default: this repository).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    root = _repo_root(args.root)
    if not (root / "nWave").is_dir():
        sys.stderr.write(f"mode-locus-gate: no nWave/ tree under root {root}\n")
        sys.stderr.write(
            "Fix: pass --root pointing at the tree containing nWave/, or run "
            "this gate from the repo root.\n"
        )
        return 1
    missing_families = _missing_families(root)
    if len(missing_families) == len(_SCANNED_FAMILIES):
        sys.stderr.write(
            f"mode-locus-gate: INDETERMINATE -- nWave/ exists under root {root} "
            f"but none of the scanned families ({', '.join(_SCANNED_FAMILIES)}) "
            "exist under it, so zero files were scanned.\n"
        )
        sys.stderr.write(
            "Fix: pass --root pointing at a tree that actually contains "
            "nWave/skills, nWave/agents, or nWave/tasks -- a zero-file scan "
            "is not the same fact as a clean scan and must not be reported "
            "as a pass.\n"
        )
        return 3
    offenders = scan_for_naked_literals(root)
    if not offenders:
        sys.stdout.write("mode-locus-gate: no naked mode literal found.\n")
        return 0
    sys.stdout.write(
        f"mode-locus-gate: {len(offenders)} naked mode literal(s) re-state the "
        "mode by hand — reference the registry instead "
        "(GENERATED region / <!-- mode-ref-ok -->):\n"
    )
    for offender in offenders:
        sys.stdout.write(
            f"  {offender.relative_path}:{offender.line_number}: "
            f"{offender.literal}  |  {offender.line_text}\n"
        )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
