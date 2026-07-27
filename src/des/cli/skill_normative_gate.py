"""CLI driving port #1 for the skill-normative-content gate.

Feature: skill-normative-content-gate (DESIGN §5/§6, component
`skill_normative_gate` CLI; driving port #1).
Layer: Driving port (CLI / pytest, maintainer-facing primary surface).

Contract (DESIGN §6):
  des skill-normative-gate [--manifest PATH] [--root PATH]
  (dispatcher form only — module-form invocations are forbidden in runtime
  emit per tests/regression/test_no_module_form_in_runtime_emit.py)
  Defaults: --manifest nWave/data/skill-normative-clauses.json, --root = repo root.
  stdout: the closed verdict, naming every failing/indeterminate skill — clause-id.
  Exit: reuse GateOutcome.exit_code — PASS 0 / FAIL 1 / INDETERMINATE 4.

M-1 (DESIGN §9): this module is reached by the slice-01 walking-skeleton AT
THROUGH the real `des` dispatcher (`des skill-normative-gate`); the registration
`_SubcommandRow("skill-normative-gate", "des.cli.skill_normative_gate", "main")`
is live in `des.cli.__main__:_REGISTRY`.

Status: IMPLEMENTED (DELIVER complete). `main(argv)` builds the real
`SkillNormativeGateService(SkillCorpusReader(), root)`, calls `evaluate()`, renders
the closed verdict, and returns the GateOutcome exit code (PASS 0 / FAIL 1 /
INDETERMINATE 4).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.skill_corpus_reader import SkillCorpusReader
from des.application.skill_normative_gate_service import SkillNormativeGateService
from des.domain.gate_outcome import _EXIT_BY_VERDICT, GateVerdict


if TYPE_CHECKING:
    from des.domain.skill_normative_clause import NormativeVerdict


_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parents[3]
    / "nWave"
    / "data"
    / "skill-normative-clauses.json"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des skill-normative-gate",
        description="Assert each registered clause marker is present in its skill.",
    )
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser


def _render(verdict: NormativeVerdict) -> str:
    if verdict.verdict is GateVerdict.PASS:
        return "PASS: 0 failing clauses"
    if verdict.verdict is GateVerdict.INDETERMINATE:
        offending = "\n".join(clause.render() for clause in verdict.indeterminate)
        return (
            f"INDETERMINATE: {len(verdict.indeterminate)} clause(s) the gate "
            f"refuses to certify\n{offending}"
        )
    failing = "\n".join(clause.render() for clause in verdict.failing)
    return f"FAIL: {len(verdict.failing)} failing clause(s)\n{failing}"


def main(argv: list[str] | None = None) -> int:
    """Run the gate over the manifest; print the verdict; return its exit code."""
    args = _build_parser().parse_args(argv)
    service = SkillNormativeGateService(SkillCorpusReader(), args.root)
    verdict = service.evaluate(args.manifest)
    print(_render(verdict))

    return _EXIT_BY_VERDICT[verdict.verdict]


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
