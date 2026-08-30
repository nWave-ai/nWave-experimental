"""F-ROOT-MODE-GATE-SCOPE-CAPTURE-AND-LATCH defect 3 -- the AUTO_ENGAGED latch
has no unlatch.

CONFIRMED IN SOURCE 2026-08-24: `resolve_root_mode_state` checked
`if observed_auto: return AUTO_ENGAGED` FIRST, before any `NW-MODE-SELECTED`
marker was considered -- a corrected `human <size>` after `Skill(nw-auto)`
was unreachable code, and the docstring declared this intentional
"including older transcripts", so the latch survived `--resume`/`--continue`
too. A beta user's prose-drafting session was forced into `auto M`, obeyed
the gate's own instruction to invoke `Skill(nw-auto)`, and then had no way
back for the rest of the session -- a lost task plus the investigation time
to prove why.

The fix: a LATER, unambiguous, non-auto `NW-MODE-SELECTED` marker (following
the last `Skill(nw-auto)` call in transcript order) supersedes the
engagement -- but ONLY before any delivery artifact exists. Once delivery has
genuinely started, the engagement is irreversible again (switching mode
mid-delivery is unsafe, not a correction) -- `delivery_artifact_exists`
defaults to `False`, so the default value alone changes nothing for a caller
that never passes it; existing behaviour for every transcript shape without a
superseding marker is unchanged (see `test_skill_tracking_transcript.py::
TestRootModeState`, still green after this fix).

Every scenario drives the REAL `resolve_root_mode_state` (never a stub)
against a real JSONL transcript file -- the established pattern
`test_skill_tracking_transcript.py::TestRootModeState` already uses for this
exact seam.
"""

from __future__ import annotations

import json
from pathlib import Path

from des.application.skill_tracking_service import (
    RootModeState,
    resolve_root_mode_state,
)


def _skill_call(skill: str) -> dict:
    return {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "tool_use", "name": "Skill", "input": {"skill": skill}}
            ]
        },
    }


def _marker_text(text: str) -> dict:
    return {
        "type": "assistant",
        "message": {"content": [{"type": "text", "text": text}]},
    }


def _write_transcript(tmp_path: Path, entries: list[dict]) -> str:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8"
    )
    return str(transcript)


def _engaged_then_corrected_transcript(tmp_path: Path, correction: str) -> str:
    """The exact reported shape: select auto M, engage nw-auto, THEN a real
    `Skill(nw-mode-select)` call again followed by one `correction` marker."""
    return _write_transcript(
        tmp_path,
        [
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: auto M"),
            _skill_call("nw-auto"),
            _skill_call("nw-mode-select"),
            _marker_text(f"NW-MODE-SELECTED: {correction}"),
        ],
    )


def test_later_human_marker_supersedes_auto_engagement_before_delivery(
    tmp_path: Path,
) -> None:
    """FALSIFIER: the exact reported trap -- auto M selected, nw-auto
    engaged, then the human corrects course with `human S` before any
    delivery artifact exists. Must resolve SELECTED, not AUTO_ENGAGED."""
    transcript_path = _engaged_then_corrected_transcript(tmp_path, "human S")

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.SELECTED, (
        f"a later, unambiguous human correction must supersede an nw-auto "
        f"engagement before delivery starts -- got {state!r}"
    )


def test_later_direct_marker_also_supersedes_auto_engagement(tmp_path: Path) -> None:
    """The same property holds for `direct S`, not just `human <size>`."""
    transcript_path = _engaged_then_corrected_transcript(tmp_path, "direct S")

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.SELECTED


def test_auto_engagement_stays_latched_once_delivery_artifact_exists(
    tmp_path: Path,
) -> None:
    """NEGATIVE CONTROL, the vincolo di merito: the SAME correcting
    transcript must NOT unlatch once a delivery artifact exists -- switching
    mode mid-delivery is unsafe, not a correction. Today's behaviour is
    preserved exactly."""
    transcript_path = _engaged_then_corrected_transcript(tmp_path, "human S")

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=True)

    assert state is RootModeState.AUTO_ENGAGED, (
        "once a delivery artifact exists the engagement must stay latched "
        f"-- got {state!r}"
    )


def test_default_delivery_artifact_exists_permits_the_same_unlatch(
    tmp_path: Path,
) -> None:
    """The parameter's own default is `False` ("no delivery yet") -- a
    caller that never passes it explicitly gets the SAME unlatch behaviour
    as `delivery_artifact_exists=False`, not the old unconditional latch.
    Every REAL production call site (`pre_tool_use_handler.py`,
    `pre_write_handler.py`) passes the flag explicitly; this documents what
    the bare default itself resolves to, so it is never mistaken for
    "unchanged legacy behaviour"."""
    transcript_path = _engaged_then_corrected_transcript(tmp_path, "human S")

    state = resolve_root_mode_state(transcript_path)

    assert state is RootModeState.SELECTED


def test_ambiguous_conflicting_markers_after_engagement_are_invalid(
    tmp_path: Path,
) -> None:
    """Two DIFFERENT correcting markers after the engagement (a second
    `Skill(nw-mode-select)` call emitting `human S` then another emitting
    `human M`) is ambiguous -- must fail loud (INVALID), never silently
    pick one."""
    transcript_path = _write_transcript(
        tmp_path,
        [
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: auto M"),
            _skill_call("nw-auto"),
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: human S"),
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: human M"),
        ],
    )

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.INVALID


def test_same_class_auto_reselection_after_engagement_stays_engaged(
    tmp_path: Path,
) -> None:
    """Re-selecting auto (M or L) again after nw-auto is already engaged is
    not a correction -- the engagement stays AUTO_ENGAGED, no behaviour
    change, no spurious AUTO_PENDING re-trap."""
    transcript_path = _engaged_then_corrected_transcript(tmp_path, "auto L")

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.AUTO_ENGAGED


def test_no_correcting_marker_after_engagement_stays_engaged(tmp_path: Path) -> None:
    """No later marker at all after nw-auto (the common case): unchanged
    AUTO_ENGAGED, matching every pre-existing transcript shape."""
    transcript_path = _write_transcript(
        tmp_path,
        [
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: auto M"),
            _skill_call("nw-auto"),
        ],
    )

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.AUTO_ENGAGED


def test_correction_before_the_first_auto_engagement_is_not_a_supersede(
    tmp_path: Path,
) -> None:
    """A `human S` marker BEFORE nw-auto is ever engaged is the ORIGINAL
    selection changing its mind pre-engagement, not a post-engagement
    correction -- covered by the existing INVALID-on-conflicting-selections
    path (`test_skill_tracking_transcript.py`), not this one. Sanity check
    that this fix's new branch never fires when nw-auto was never observed
    at all."""
    transcript_path = _write_transcript(
        tmp_path,
        [
            _skill_call("nw-mode-select"),
            _marker_text("NW-MODE-SELECTED: human S"),
        ],
    )

    state = resolve_root_mode_state(transcript_path, delivery_artifact_exists=False)

    assert state is RootModeState.SELECTED
