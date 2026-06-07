"""des.domain.feature_classifier -- pure feature-classification logic.

Feature `classic-spine-decommission`, slice-01/slice-03. `classify(feature_dir)`
re-reads a feature directory FRESH at scan time (M7) and returns its DELIVER
spine class -- a pure function, return-only, never mutating (DESIGN: Reuse
Analysis, contract shape pure-function).

slice-01 (the walking skeleton) drove the `classic-mid-implementation`
predicate plus the never-crash probe contract: any malformed artifact yields
`classic-needs-manual-review` rather than raising. slice-03 drives the four
remaining predicate branches (`classic-distill-done`, `atdd_pure`,
`pre-distill`) and the corrupt-roadmap manual-review row.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


CLASSIC_MID_IMPLEMENTATION = "classic-mid-implementation"
CLASSIC_DISTILL_DONE = "classic-distill-done"
ATDD_PURE = "atdd_pure"
PRE_DISTILL = "pre-distill"
CLASSIC_NEEDS_MANUAL_REVIEW = "classic-needs-manual-review"

# The canonical DISCUSS Slice Plan heading -- the single domain-vocabulary
# constant naming the heading the carpaccio entry gate parses. Owned here (the
# feature-state classifier) and imported by `conversion_planner` so the
# classic->atdd_pure converter promotes to exactly the string the classifier
# detects -- one definition, no cross-module drift.
SLICE_PLAN_HEADING = "## Wave: DISCUSS / [REF] Slice Plan"


def classify(feature_dir: Path) -> str:
    """Classify a feature directory into a DELIVER spine state.

    Pure function: re-reads the directory fresh and returns a class string,
    never mutating the tree. Never raises -- a malformed artifact yields
    `classic-needs-manual-review` (the Earned-Trust probe contract).
    """
    try:
        return _classify(feature_dir)
    except (OSError, ValueError):
        return CLASSIC_NEEDS_MANUAL_REVIEW


def has_slice_plan(feature_dir: Path) -> bool:
    """Whether a feature dir carries a promoted DISCUSS Slice Plan heading.

    Pure, crash-free probe: an unreadable markdown file yields `False` rather
    than raising. Drives the manifest's `has_slice_plan` column -- a feature
    with BOTH a roadmap and a slice plan (S21) is classified
    `classic-mid-implementation` AND stamped `has_slice_plan: true`.
    """
    try:
        return _has_slice_plan_heading(feature_dir)
    except OSError:
        return False


def _classify(feature_dir: Path) -> str:
    """The predicate ladder. May raise on a malformed artifact -- `classify` guards."""
    roadmap = feature_dir / "deliver" / "roadmap.json"
    if roadmap.is_file():
        return _classify_with_roadmap(feature_dir, roadmap)
    return _classify_without_roadmap(feature_dir)


def _classify_with_roadmap(feature_dir: Path, roadmap: Path) -> str:
    """Classify a feature that carries a `deliver/roadmap.json`.

    A roadmap binds the feature to the classic spine. A corrupt roadmap is a
    malformed artifact -- it yields `classic-needs-manual-review`. The S21
    false-negative guard lives here: a feature with a roadmap is never
    `atdd_pure` even if it also carries a Slice Plan heading.

    A roadmap whose phases are inconsistent with the execution log's step ids
    (a hand-edited roadmap) is a malformed artifact -- the inconsistency is
    surfaced as a `ValueError` and `classify` maps it to manual review.
    """
    roadmap_phases = _require_parsable_roadmap(roadmap)
    execution_log = feature_dir / "deliver" / "execution-log.json"
    if execution_log.is_file() and _is_classic_mid_implementation(
        execution_log, roadmap_phases
    ):
        return CLASSIC_MID_IMPLEMENTATION
    return CLASSIC_NEEDS_MANUAL_REVIEW


def _classify_without_roadmap(feature_dir: Path) -> str:
    """Classify a feature with no `roadmap.json` -- atdd_pure / distill / pre."""
    if _is_atdd_pure(feature_dir):
        return ATDD_PURE
    if _has_acceptance_tests(feature_dir):
        return CLASSIC_DISTILL_DONE
    return PRE_DISTILL


def _require_parsable_roadmap(roadmap: Path) -> set[str]:
    """Return the roadmap's phase ids, raising `ValueError` when malformed.

    A roadmap that is not valid JSON (truncated -- F-17 -- or not JSON at all)
    raises `json.JSONDecodeError` (a `ValueError`); `classify` maps it to
    `classic-needs-manual-review`.
    """
    parsed = json.loads(roadmap.read_text(encoding="utf-8"))
    phases = parsed.get("phases", []) if isinstance(parsed, dict) else []
    return {
        str(phase["id"])
        for phase in phases
        if isinstance(phase, dict) and "id" in phase
    }


def _is_classic_mid_implementation(
    execution_log: Path, roadmap_phases: set[str]
) -> bool:
    """Whether an execution log shows >=1 EXECUTED and >=1 step un-committed.

    A malformed execution log -- a mixed-version log (v2.0-pipe strings beside
    v3.0 structured events) or one whose step ids are inconsistent with the
    roadmap phases (a hand-edited roadmap) -- is NOT a mid-implementation
    feature; it falls through to `classic-needs-manual-review`.
    """
    raw_events = _load_raw_events(execution_log)
    if _log_is_mixed_version(raw_events):
        return False
    events = [event for event in raw_events if isinstance(event, dict)]
    if not _has_executed_event(events):
        return False
    if not _log_consistent_with_roadmap(events, roadmap_phases):
        return False
    return _has_step_without_commit_pass(events)


def _load_raw_events(execution_log: Path) -> list[object]:
    """Parse the raw `events` array -- entries left untyped for schema checks."""
    parsed = json.loads(execution_log.read_text(encoding="utf-8"))
    events = parsed.get("events", []) if isinstance(parsed, dict) else []
    return list(events) if isinstance(events, list) else []


def _log_is_mixed_version(raw_events: list[object]) -> bool:
    """Whether a log mixes v2.0-pipe string events with v3.0 structured dicts."""
    has_pipe_event = any(isinstance(event, str) for event in raw_events)
    has_structured_event = any(isinstance(event, dict) for event in raw_events)
    return has_pipe_event and has_structured_event


def _log_consistent_with_roadmap(
    events: list[dict[str, object]], roadmap_phases: set[str]
) -> bool:
    """Whether every logged step id belongs to a declared roadmap phase.

    A hand-edited roadmap leaves a log step id (`PP-NN`) whose `PP` phase is
    absent from the roadmap -- an inconsistency that yields manual review.
    """
    if not roadmap_phases:
        return True
    logged_phases = {
        str(event["step_id"]).split("-")[0] for event in events if event.get("step_id")
    }
    return logged_phases <= roadmap_phases


def _has_executed_event(events: list[dict[str, object]]) -> bool:
    """Whether at least one event records an EXECUTED status."""
    return any(event.get("status") == "EXECUTED" for event in events)


def _has_step_without_commit_pass(events: list[dict[str, object]]) -> bool:
    """Whether at least one step never reached a COMMIT phase with PASS."""
    committed_steps = {
        event.get("step_id")
        for event in events
        if event.get("phase") == "COMMIT" and event.get("data") == "PASS"
    }
    all_steps = {event.get("step_id") for event in events if event.get("step_id")}
    return bool(all_steps - committed_steps)


def _is_atdd_pure(feature_dir: Path) -> bool:
    """Whether a roadmap-free feature is already on the atdd_pure spine.

    True when an atdd_pure telemetry file exists OR a DISCUSS Slice Plan
    heading is present. The roadmap-free precondition is established by the
    caller (`_classify_without_roadmap`) -- the S21 guard.
    """
    return _has_atdd_pure_telemetry(feature_dir) or _has_slice_plan_heading(feature_dir)


def _has_atdd_pure_telemetry(feature_dir: Path) -> bool:
    """Whether a `.nwave/telemetry/atdd-pure/{id}.jsonl` file exists."""
    telemetry_dir = feature_dir / ".nwave" / "telemetry" / "atdd-pure"
    if not telemetry_dir.is_dir():
        return False
    return any(telemetry_dir.glob("*.jsonl"))


def _has_slice_plan_heading(feature_dir: Path) -> bool:
    """Whether any markdown file under the feature dir carries the heading."""
    return any(
        SLICE_PLAN_HEADING in markdown.read_text(encoding="utf-8")
        for markdown in feature_dir.rglob("*.md")
    )


def _has_acceptance_tests(feature_dir: Path) -> bool:
    """Whether the feature dir carries at least one `.feature` acceptance test."""
    return any(feature_dir.rglob("*.feature"))
