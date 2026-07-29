"""Cohort classification CLI for the ATDD-pure pilot scope gate.

Plan v3 §4.1.bis: mechanical S/M/L/XL pre-assignment invoked by
`/nw-distill` Phase 0. Exit codes: 0 ok | 1 feature dir not found
| 2 malformed artifacts | 43 COHORT_OUT_OF_PILOT_SCOPE. Output:
single-line JSON. Repo root via NWAVE_REPO_ROOT env or parents[2].
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


# Expose ``src/`` so ``des`` resolves under a bare ``python3`` (this script
# runs outside the uv venv as a ``language: system`` hook / ad-hoc tool).
# Guarded: ``src/`` exists only in the dev repo -- in an installed layout
# ``des`` is already importable and this is a no-op.
_SRC = Path(__file__).resolve().parents[2] / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from des.domain.repo_path_resolver import (  # noqa: E402
    feature_delta_in_dir,
    feature_dir_path,
)


WorkflowMode = Literal["atdd_pure"]
Cohort = Literal["S", "M", "L", "XL"]

SCENARIO_RE = re.compile(r"^\s*Scenario(?: Outline)?:", re.MULTILINE)
EXAMPLES_ROW_RE = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)
TEST_DEF_RE = re.compile(r"^\s*def\s+test_\w+\s*\(", re.MULTILINE)
# The DISTILL Test Placement heading the cohort gate keys on; its numbered list
# enumerates a fresh feature's candidate ATs before any Gherkin is authored.
PLACEMENT_HEADING_RE = re.compile(r"^\s*#{2,}\s.*Test Placement")
SECTION_HEADING_RE = re.compile(r"^\s*#{2,3}\s")
NUMBERED_ITEM_RE = re.compile(r"^\s*\d+\.\s")


@dataclass(frozen=True)
class Classification:
    feature_id: str
    workflow_mode: WorkflowMode
    at_count: int
    cohort: Cohort
    scope_extension: bool
    event: str


def _repo_root() -> Path:
    override = os.environ.get("NWAVE_REPO_ROOT")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2]


def _locate_feature(repo: Path, feature_id: str) -> tuple[Path, str] | None:
    """Return (path, kind) where kind in {'distill', 'feature_delta'}."""
    base = feature_dir_path(repo, feature_id)
    distill = base / "distill"
    if distill.is_dir():
        return distill, "distill"
    delta = feature_delta_in_dir(base)
    if delta.is_file():
        return delta, "feature_delta"
    return None


def _count_scenarios_in_text(text: str) -> int:
    """Count Scenario/Scenario Outline. Outlines multiply by Examples rows.

    A pipe-row inside an Examples block past the header counts as one AT.
    Heuristic: scenarios + (data-rows - header-rows-per-outline).
    """
    scenarios = len(SCENARIO_RE.findall(text))
    outline_count = len(re.findall(r"^\s*Scenario Outline:", text, re.MULTILINE))
    pipe_rows = len(EXAMPLES_ROW_RE.findall(text))
    # Each Examples block contributes a header row + N data rows; net data = rows - outlines.
    examples_data_rows = max(0, pipe_rows - outline_count) if outline_count else 0
    return scenarios + examples_data_rows


def _count_test_placement_candidates(text: str) -> int:
    """Count the numbered candidate ATs in the DISTILL Test Placement section.

    A fresh feature has no authored Gherkin; its candidate ATs live as a numbered
    prose list under ``## Wave: DISTILL / [REF] Test Placement``. The section runs
    from that heading up to the NEXT ``##``/``###`` heading (or end of text). Each
    list item (``^\\s*\\d+\\.\\s``) is one candidate AT.
    """
    lines = text.splitlines()
    in_section = False
    candidates = 0
    for line in lines:
        if PLACEMENT_HEADING_RE.match(line):
            in_section = True
            continue
        if in_section and SECTION_HEADING_RE.match(line):
            break
        if in_section and NUMBERED_ITEM_RE.match(line):
            candidates += 1
    return candidates


def _count_ats(target: Path, kind: str) -> int:
    total = 0
    if kind == "distill":
        # gherkin-scope: already agnostic -- this same walk counts pytest
        # `steps_*.py` / `test_*.py` AT-defs in the elif branch below, so it
        # is not a Gherkin-only discovery gap.
        for path in target.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix == ".feature":
                total += _count_scenarios_in_text(path.read_text(errors="replace"))
            elif (path.suffix == ".py" and path.name.startswith("steps_")) or (
                path.suffix == ".py" and path.name.startswith("test_")
            ):
                total += len(TEST_DEF_RE.findall(path.read_text(errors="replace")))
    else:  # feature_delta
        text = target.read_text(errors="replace")
        total += max(
            _count_scenarios_in_text(text),
            _count_test_placement_candidates(text),
        )
    return total


def _classify_cohort(at_count: int) -> Cohort:
    if at_count <= 10:
        return "S"
    if at_count <= 30:
        return "M"
    if at_count <= 80:
        return "L"
    return "XL"


def _build_classification(
    feature_id: str,
    workflow_mode: WorkflowMode,
    at_count: int,
    accept_override: bool,
) -> tuple[int, Classification]:
    cohort = _classify_cohort(at_count)
    # atdd_pure is the sole active workflow. Historical classic features are
    # classified by the explicit migration/replay tooling, never by an active
    # workflow selector.
    if cohort == "M":
        return 0, Classification(
            feature_id, "atdd_pure", at_count, cohort, False, "CohortAssigned"
        )
    if accept_override:
        return 0, Classification(
            feature_id, "atdd_pure", at_count, cohort, True, "CohortAssigned"
        )
    return 43, Classification(
        feature_id,
        "atdd_pure",
        at_count,
        cohort,
        False,
        "CohortAssignmentRejected",
    )


def _emit(payload: dict[str, object]) -> None:
    sys.stdout.write(json.dumps(payload, sort_keys=True) + "\n")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="cohort_classifier",
        description="Mechanical cohort classification for ATDD-pure pilot gate.",
    )
    p.add_argument("--feature-id", required=True)
    p.add_argument(
        "--workflow-mode",
        required=True,
        choices=("atdd_pure",),
        help="The sole active workflow mode; historical classic is migration-only.",
    )
    p.add_argument(
        "--accept-pilot-scope-extension",
        action="store_true",
        help="Operator override allowing S/L/XL cohort in atdd_pure pilot.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    repo = _repo_root()
    located = _locate_feature(repo, args.feature_id)
    if located is None:
        _emit(
            {
                "feature_id": args.feature_id,
                "workflow_mode": args.workflow_mode,
                "error": (
                    f"feature directory not found: docs/feature/{args.feature_id}/"
                ),
            }
        )
        return 1
    target, kind = located
    at_count = _count_ats(target, kind)
    if at_count == 0:
        _emit(
            {
                "feature_id": args.feature_id,
                "workflow_mode": args.workflow_mode,
                "error": (
                    "no countable scenarios or test definitions in feature artifacts"
                ),
            }
        )
        return 2
    code, cls = _build_classification(
        args.feature_id,
        args.workflow_mode,
        at_count,
        args.accept_pilot_scope_extension,
    )
    _emit(
        {
            "feature_id": cls.feature_id,
            "workflow_mode": cls.workflow_mode,
            "at_count": cls.at_count,
            "cohort": cls.cohort,
            "scope_extension": cls.scope_extension,
            "event": cls.event,
        }
    )
    return code


if __name__ == "__main__":
    raise SystemExit(main())
