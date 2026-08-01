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

gate-ratchet-skill-normative (Mikado D86): an INDETERMINATE verdict no longer
exits 4 unconditionally. The exit code is decided on the DELTA of the
INDETERMINATE population against HEAD (`skill_normative_gate_ratchet.py`,
reusing the gate-agnostic `des.domain.gate_ratchet` -- the same decision
`validate_mikado_tree_coherence.py` already applies, commit 4a84eba0e): no
growth allows (exit 0, loudly NOT a clean pass), growth or an unreadable
baseline still refuses (exit 4). PASS and FAIL pay nothing extra -- the
ratchet's second pass over git history runs ONLY when the verdict IS
INDETERMINATE, and a FAIL is never ratcheted.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.git_commit_contents import build_contents
from des.adapters.driven.git.git_commit_reachability import build_reachability
from des.adapters.driven.skill_corpus_reader import SkillCorpusReader
from des.application.skill_normative_gate_ratchet import ratchet_decision
from des.application.skill_normative_gate_service import SkillNormativeGateService
from des.cli._repo_root_arg import add_repo_root_argument
from des.domain.gate_outcome import _EXIT_BY_VERDICT, GateVerdict
from des.runtime.packaged_asset import (
    AssetOrigin,
    ambiguity_message,
    resolve_packaged_asset,
)


if TYPE_CHECKING:
    from des.domain.skill_normative_clause import NormativeVerdict


_MANIFEST_RELATIVE = "nWave/data/skill-normative-clauses.json"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des skill-normative-gate",
        description="Assert each registered clause marker is present in its skill.",
    )
    # No default: which tree's manifest to read is DECIDED at run time, because
    # resolving it from this module's own location made the installed shim
    # validate the repo's skills against the installed manifest -- and say PASS
    # for a clause that only exists in the repo.
    parser.add_argument("--manifest", type=Path, default=None)
    add_repo_root_argument(parser, "--root", type=Path, default=Path.cwd())
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
    rendered = f"FAIL: {len(verdict.failing)} failing clause(s)\n{failing}"
    if verdict.indeterminate:
        # A reject wins over the third state (gate-ratchet-skill-normative),
        # but the third state must still reach the aggregate (GDP-8) -- printed
        # here, never discarded, and never confused for what refused this run.
        offending = "\n".join(clause.render() for clause in verdict.indeterminate)
        rendered += (
            f"\n\nALSO {len(verdict.indeterminate)} clause(s) the gate could "
            f"not verify (not what refused this run -- the FAIL above did):\n"
            f"{offending}"
        )
    return rendered


def main(argv: list[str] | None = None) -> int:
    """Run the gate over the manifest; print the verdict; return its exit code."""
    args = _build_parser().parse_args(argv)

    manifest = args.manifest
    if manifest is None:
        resolution = resolve_packaged_asset(_MANIFEST_RELATIVE, start=args.root)
        if resolution.origin is AssetOrigin.AMBIGUOUS:
            print(
                "INDETERMINATE: the gate will not choose which tree to validate\n"
                + ambiguity_message(resolution, "--manifest")
            )
            return _EXIT_BY_VERDICT[GateVerdict.INDETERMINATE]
        if not resolution.is_usable:
            print(f"INDETERMINATE: {resolution.detail}")
            return _EXIT_BY_VERDICT[GateVerdict.INDETERMINATE]
        manifest = resolution.path
        # Which tree answered is part of the verdict, never left implicit.
        print(f"manifest: {manifest}")

    service = SkillNormativeGateService(SkillCorpusReader(), args.root)
    verdict = service.evaluate(manifest)
    print(_render(verdict))

    exit_code = _EXIT_BY_VERDICT[verdict.verdict]

    # The ratchet is reached ONLY on the third state (INDETERMINATE) -- a
    # PASS/FAIL run pays nothing extra (no second pass over git history), and
    # a FAIL never sees an allowance printed beside it: FAIL is never
    # ratcheted, at any count.
    if verdict.verdict is GateVerdict.INDETERMINATE:
        decision = ratchet_decision(
            verdict,
            root=args.root,
            manifest_path=manifest,
            repo=args.root,
            contents=build_contents(args.root),
            reachability=build_reachability(args.root),
        )
        print()
        print(decision.render())
        if not decision.blocks:
            exit_code = 0

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
