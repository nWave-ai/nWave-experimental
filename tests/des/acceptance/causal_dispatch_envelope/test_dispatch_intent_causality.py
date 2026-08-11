# @feature-causal-dispatch-envelope
"""Acceptance contract for truthful causal dispatch envelopes.

The public dispatch command only renders an operator's intended work.  It is
not a lifecycle producer, so a correlated hook return must make that boundary
explicit instead of inferring completion from the dispatch prose.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from tests.common.delivery_contract_fixture import contract_args
from tests.common.in_process_cli import run_cli_in_process, run_module_in_process


_FEATURE_ID = "causal-dispatch-envelope"
_CAUSAL_MARKER = "DES-CAUSAL-ID"
_TERMINAL_WORDS = ("completed", "committed", "executed", "shipped")


def _render_intent(project: Path) -> str:
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "dispatch",
            "--mode",
            "atdd_pure",
            "--project-id",
            _FEATURE_ID,
            "--slice",
            "slice-01",
            "--phase",
            "A_GREEN",
            "--wave",
            "deliver",
            "--intent",
            "Make the next dispatched work traceable without claiming it finished.",
            *contract_args(project),
        ],
        cwd=project,
    )
    assert exit_code == 0, (
        "WHAT: the public dispatch surface could not render the operator's work intent. "
        "WHY: causal evidence cannot be correlated if the public instruction was never emitted. "
        f"HOW: keep `des dispatch` available for valid work intent; stderr was {stderr!r}."
    )
    return stdout


def _causal_ids(dispatch_text: str) -> list[str]:
    return re.findall(rf"{_CAUSAL_MARKER}\s*:\s*([^\s<]+)", dispatch_text)


def _project_files(project: Path) -> set[str]:
    return {
        path.relative_to(project).as_posix()
        for path in project.rglob("*")
        if path.is_file()
    }


def _run_stop_hook(project: Path, transcript_text: str) -> dict[str, object]:
    transcript = project / "agent-return.jsonl"
    transcript.write_text(
        json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": transcript_text},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    exit_code, stdout, stderr = run_module_in_process(
        "des.adapters.drivers.hooks.hook_router",
        "subagent-stop",
        cwd=project,
        stdin_text=json.dumps(
            {
                "agent_id": "causal-envelope-agent",
                "agent_type": "nw-software-crafter",
                "agent_transcript_path": str(transcript),
                "cwd": str(project),
            }
        ),
    )
    assert exit_code == 0, (
        "WHAT: the public stop-hook surface could not examine a dispatched return. "
        "WHY: a missing causal correlation must be reported honestly, not crash the operator path. "
        f"HOW: make the hook emit a causal envelope for a valid transcript; stderr was {stderr!r}."
    )
    for line in reversed(stdout.splitlines()):
        try:
            candidate = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "causal_envelope" in candidate:
            return candidate
    return {}


@pytest.mark.negative_at
def test_dispatch_intent_is_correlated_without_a_terminal_claim(tmp_path: Path) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — An operator can trace a dispatched
    work instruction without being told that a renderer completed it.

    # covers: R1 R2
    """
    dispatch_text = _render_intent(tmp_path)
    causal_ids = _causal_ids(dispatch_text)
    assert len(causal_ids) == 1, (
        f"WHAT: `des dispatch` emitted {len(causal_ids)} DES-CAUSAL-ID markers, not exactly one. "
        "WHY: zero IDs prevent correlation and duplicate IDs make one rendered intent ambiguous. "
        "HOW: mint and render one opaque DES-CAUSAL-ID exactly once per work intent."
    )
    causal_id = causal_ids[0]
    assert not any(word in dispatch_text.lower() for word in _TERMINAL_WORDS), (
        "WHAT: the dispatch renderer claimed a terminal lifecycle result. "
        "WHY: rendering work intent is not evidence that a lifecycle producer ran it. "
        "HOW: keep dispatch language limited to intent and leave terminal evidence to lifecycle producers."
    )

    observed = _run_stop_hook(tmp_path, dispatch_text)
    envelope = observed.get("causal_envelope") if isinstance(observed, dict) else None
    assert isinstance(envelope, dict), (
        "WHAT: a correlated stop-hook return did not expose a causal envelope. "
        "WHY: operators need an observable distinction between dispatch intent and lifecycle evidence. "
        "HOW: project the parsed dispatch intent and its evidence status on hook output."
    )
    assert envelope.get("correlation_id") == causal_id, (
        "WHAT: the hook did not preserve the exact dispatch causal marker. "
        "WHY: feature and slice labels can repeat, so only the exact marker can bind this return to this instruction. "
        "HOW: carry DES-CAUSAL-ID unchanged from the rendered dispatch through hook correlation."
    )
    assert envelope.get("lifecycle_status") == "unavailable", (
        "WHAT: an intent-only correlation was not labelled lifecycle-unavailable. "
        "WHY: the dispatch renderer is not a lifecycle producer and cannot certify completion. "
        "HOW: report lifecycle_status=unavailable until a real producer supplies evidence."
    )
    assert envelope.get("terminal_claim") is None, (
        "WHAT: an intent-only correlation made a terminal claim. "
        "WHY: terminal truth belongs to a real tick, drain, or commit producer, never the dispatch renderer. "
        "HOW: leave terminal_claim null when no lifecycle evidence is present."
    )


@pytest.mark.negative_at
@pytest.mark.parametrize(
    "phase", ("A_GREEN", "D_REFACTOR_COMMIT", "F_FINAL_REVIEW", "D_DISTILL")
)
def test_stop_hook_marks_markerless_return_as_causally_unavailable(
    tmp_path: Path, phase: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Outcome anchor: DISCUSS Elevator Pitch — An operator can tell a markerless
    return from a correlated instruction instead of mistaking missing evidence
    for a lifecycle result.

    # covers: R3
    """
    before_files = _project_files(tmp_path)
    markerless_return = (
        "<!-- DES-VALIDATION : required -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        f"<!-- DES-PHASE : {phase} -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        "I described the work, but this return carries no causal marker.\n"
    )
    observed = _run_stop_hook(tmp_path, markerless_return)
    after_files = _project_files(tmp_path)
    assert after_files - before_files == {"agent-return.jsonl"}, (
        "WHAT: examining a markerless return changed project files beyond the supplied transcript. "
        "WHY: correlation-unavailable is an output-only hook result, not permission to mutate a ledger or scorecard. "
        "HOW: keep this boundary's only project write limited to the caller-supplied transcript fixture."
    )
    assert before_files - after_files == set(), (
        "WHAT: examining a markerless return removed an existing project file. "
        "WHY: an unavailable correlation result must preserve pre-existing project evidence. "
        "HOW: leave all existing project files unchanged while emitting the unavailable envelope."
    )
    envelope = observed.get("causal_envelope") if isinstance(observed, dict) else None
    assert isinstance(envelope, dict), (
        "WHAT: a markerless return produced no causal-unavailable envelope. "
        "WHY: silence cannot distinguish missing correlation from a genuine lifecycle outcome. "
        "HOW: emit an explicit causal envelope whenever a DES return cannot be correlated."
    )
    assert envelope.get("correlation_status") == "unavailable", (
        "WHAT: the markerless return was not marked correlation-unavailable. "
        "WHY: absent causal evidence must never be treated as a matched instruction. "
        "HOW: require DES-CAUSAL-ID for correlation and report unavailable when it is absent."
    )
    assert envelope.get("lifecycle_status") == "unavailable", (
        "WHAT: the markerless return was presented as lifecycle evidence. "
        "WHY: no exact marker means no causal binding to any lifecycle producer. "
        "HOW: preserve lifecycle_status=unavailable until a producer provides matching evidence."
    )
    assert envelope.get("terminal_claim") is None, (
        "WHAT: the markerless return made a terminal lifecycle claim. "
        "WHY: absence of correlation is not proof of completion, refusal, or a clean no-op. "
        "HOW: leave terminal_claim null for causally unavailable returns."
    )
