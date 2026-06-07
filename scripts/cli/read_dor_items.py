"""Standalone reader for the canonical Definition-of-Ready item-set.

A reviewer (or a hook) reads the canonical Definition-of-Ready set from ONE
authoritative place -- ``nWave/data/dor-items.yaml`` -- so every readiness
decision checks the same complete nine and no hard-gate item is silently
dropped (AD-55: the live hole is a loaded 8-item skill copy that omits the
Outcome-KPIs item).

Hosted in ``scripts/cli/`` because the reader has NO DES-runtime coupling: it is
a stdlib-only, hook-invocable standalone -- the same shape as its siblings
``check_reuse_first_design.py`` / ``verify_coverage_map.py`` (DESIGN D-2:
nwave-dev hooks-only, NO ``des`` gate-catalog coupling; the ``des`` ``_REGISTRY``
is reserved for catalogued GATES, and a READER is not a gate).

Python-only mandate: no ``import yaml``. The SSOT is read with a narrow stdlib
block-sequence scanner (mirrors ``run_contract_gate._scan_gate_jobs`` /
``carpaccio_format._scan_atdd_pure_int``) that parses exactly the two
block-sequence shapes this reader needs (``items:`` and ``hard_gates:``), never
arbitrary YAML.

Stdout contract (``--format json``) -- a single JSON object::

    {"items": [...nine readiness item strings...], "hard_gates": ["job-traceability"]}

The reader is read-only: it inspects the SSOT bytes and never mutates them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from des.cli.human_surface import Verdict, print_human_summary


# This file lives at ``scripts/cli/read_dor_items.py`` -> two parents up is the
# repo root. The SSOT is repo-tracked data resolved relative to that root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SSOT_RELPATH = Path("nWave") / "data" / "dor-items.yaml"


def _scan_block_sequence(text: str, key: str) -> list[str]:
    """Stdlib scan for a top-level ``<key>:`` block-sequence of scalars.

    Reads the one shape this reader needs::

        items:
          - first value
          - second value
        hard_gates:
          - job-traceability

    Returns the ordered list of dash-item scalar values found under the named
    top-level key, or an empty list when the key is absent. Deliberately narrow
    (mirrors ``run_contract_gate._scan_gate_jobs``): the ENTIRE text after the
    ``- `` marker is the value (item strings legitimately contain ``:`` and
    ``()``), and a sequence ends at the next zero-indent line. Comment-only and
    blank lines are skipped.
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


def _read_canonical_set(ssot_path: Path) -> dict[str, list[str]]:
    """Read the canonical item-set + separate hard gates from the SSOT file."""
    text = ssot_path.read_text(encoding="utf-8")
    return {
        "items": _scan_block_sequence(text, "items"),
        "hard_gates": _scan_block_sequence(text, "hard_gates"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read the canonical Definition-of-Ready item-set from the SSOT."
    )
    parser.add_argument(
        "--format",
        choices=("json", "human"),
        default="human",
        help="Output format: machine-readable JSON or a human summary.",
    )
    args = parser.parse_args(argv)

    ssot_path = _REPO_ROOT / _SSOT_RELPATH
    payload = _read_canonical_set(ssot_path)

    if args.format == "json":
        sys.stdout.write(json.dumps(payload))
        return 0

    gates = ", ".join(payload["hard_gates"])
    print_human_summary(
        Verdict.PASS,
        f"{len(payload['items'])} canonical readiness items "
        f"(separate hard gates: {gates})",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
