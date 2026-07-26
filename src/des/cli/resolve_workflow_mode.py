"""Resolve the one active workflow mode without mutating the project.

Classic is removed: historic requests are reported as migration-required and
never reach a workload or a fallback dispatcher.
"""

from __future__ import annotations

import argparse
import json
import re
import zipfile
from pathlib import Path

from des.application.workflow_mode import (
    ACTIVE_MODES,
    WorkflowModeSelection,
    resolve_workflow_selection,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des resolve-workflow-mode",
        description="Resolve atdd_pure only; classic is removed and migration-required.",
    )
    parser.add_argument("--project-dir", required=True)
    parser.add_argument(
        "--operation", required=True, help="Operation to protect before execution."
    )
    parser.add_argument("--mode")
    parser.add_argument("--dispatch-marker")
    parser.add_argument("--stop-context-mode")
    parser.add_argument("--classic-attestation", help=argparse.SUPPRESS)
    parser.add_argument("--dispatch-source", help=argparse.SUPPRESS)
    parser.add_argument("--require-dispatch-marker", action="store_true")
    parser.add_argument("--falsifier-state")
    parser.add_argument("--show-agent-guidance", action="store_true")
    parser.add_argument("--candidate-wheel", type=Path)
    parser.add_argument("--json", action="store_true")
    return parser


def _candidate_is_compatible(candidate: Path) -> bool:
    """Reject every selectable retired-workflow carrier in a candidate.

    This is deliberately a semantic scanner: aliases and instructions that can
    select, dispatch, restore, or mutate a retired workflow are equivalent to
    a literal ``classic.yaml`` asset.  A candidate must not pass merely because
    its stale spine was renamed.
    """
    retired = r"(?:classic|retired[ _-]?workflow)"
    executable_carrier = re.compile(
        rf"(?:"
        rf"workflow\.mode[^\n]{{0,48}}\b{retired}\b|"
        rf"\b{retired}\b[^\n]{{0,120}}\b(?:default|fallback|fall[ -]?back|"
        rf"select|dispatch(?:es)?|template|spine|roadmap|execution[ -]?log|"
        rf"patch|write|mutat(?:e|ion)|restore)\b|"
        rf"\b(?:default|fallback|fall[ -]?back|select|dispatch(?:es)?|use|run|"
        rf"route|patch|write|mutat(?:e|ion)|restore)\b[^\n]{{0,120}}\b{retired}\b|"
        rf"DES-MODE\s*:\s*{retired}"
        rf")",
        re.IGNORECASE,
    )
    try:
        with zipfile.ZipFile(candidate) as archive:
            for member in archive.infolist():
                name = member.filename.lower()
                if re.search(retired, name, re.IGNORECASE) and (
                    "/flavors/" in name or "orchestration" in name
                ):
                    return False
                if not name.endswith((".md", ".yaml", ".yml", ".json", ".py")):
                    continue
                if executable_carrier.search(
                    archive.read(member).decode("utf-8", "ignore")
                ):
                    return False
    except (OSError, zipfile.BadZipFile):
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.show_agent_guidance:
        print("Classic is removed; migrate or repair the project to atdd_pure.")
        return 0
    if args.candidate_wheel is not None and not _candidate_is_compatible(
        args.candidate_wheel
    ):
        print(
            json.dumps(
                {
                    "outcome": "CANDIDATE_INCOMPATIBLE",
                    "effective_mode": None,
                    "active_modes": sorted(ACTIVE_MODES),
                    "surface_coherence": "FAIL",
                    "diagnostic": (
                        "WHAT: the candidate carries retired classic assets. "
                        "WHY: an archive may not reintroduce a selectable spine. "
                        "HOW: rebuild the candidate from the atdd_pure-only package."
                    ),
                },
                sort_keys=True,
            )
        )
        return 1
    result: WorkflowModeSelection = resolve_workflow_selection(
        Path(args.project_dir),
        requested_mode=args.mode,
        dispatch_marker=args.dispatch_marker,
        stop_context_mode=args.stop_context_mode,
        classic_attestation=args.classic_attestation,
        dispatch_source=args.dispatch_source,
        require_dispatch_marker=args.require_dispatch_marker,
        falsifier_state=args.falsifier_state,
    )
    payload: dict[str, object] = {
        "outcome": result.outcome,
        "effective_mode": result.effective_mode,
        "active_modes": sorted(ACTIVE_MODES),
        "surface_coherence": "PASS",
    }
    if result.selected:
        payload["dispatch_mode"] = "atdd_pure"
    if result.reason_code is not None:
        payload["reason_code"] = result.reason_code
    if not result.selected:
        payload["diagnostic"] = result.diagnostic
    print(json.dumps(payload, sort_keys=True))
    return 0 if result.selected else 1
