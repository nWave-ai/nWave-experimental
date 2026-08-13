"""Laws for the path-aware, transcript-scoped wall-clock boundary.

The mission defect: a K4 payload claimed 337s/78s wall clock while its own
root+subagent transcript spanned 1764s/1287s -- the payload's `duration_ms`
ends the instant the ROOT process returns, even while background agents it
dispatched keep running. `resolve_transcript_wall` is the measurement that
closes that gap: it locates the ONE root transcript the payload's `session_id`
names, adds only that transcript's own `subagents/*.jsonl`, and spans every
valid ISO timestamp parsed across them -- never the payload duration.

Each test below is named for the falsifier it would catch, not for coverage.

Run: uv run pytest -q test_paired_spread_transcript_wall.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.analysis.paired_spread import (
    TRANSCRIPT_ROOT_PLUS_SUBAGENTS,
    TranscriptWall,
    TranscriptWallUnreadable,
    resolve_transcript_wall,
)


_SETTINGS = settings(max_examples=100, deadline=None)


def _iso(seconds_from_epoch: float) -> str:
    """A deterministic, timezone-aware ISO timestamp -- no `datetime.now()`,
    every instant fixed relative to an arbitrary epoch the test controls."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (
        (base + timedelta(seconds=seconds_from_epoch))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _write_jsonl(
    path: Path, timestamps: list[str], *, extra_lines: list[str] = ()
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"type": "user", "timestamp": ts}) for ts in timestamps]
    lines.extend(extra_lines)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _workspace(tmp_path: Path, arm: str = "nwave") -> tuple[Path, Path]:
    """Return (payload_path, workspace) matching `paired_campaign.py`'s own
    layout: `{pair_dir}/{arm}.json` next to workspace `{pair_dir}/{arm}/`."""
    pair_dir = tmp_path / "pair-1"
    pair_dir.mkdir(parents=True, exist_ok=True)
    payload_path = pair_dir / f"{arm}.json"
    payload_path.write_text("{}", encoding="utf-8")
    workspace = pair_dir / arm
    workspace.mkdir(exist_ok=True)
    return payload_path, workspace


def _root_transcript(
    workspace: Path, session_id: str, project: str = "-fake-proj"
) -> Path:
    return workspace / ".claude-k4" / "projects" / project / f"{session_id}.jsonl"


def _subagents_dir(root: Path) -> Path:
    return root.parent / root.stem / "subagents"


# --- falsifier 1: transcript span, not payload duration -----------------------


def test_span_comes_from_transcript_not_payload_duration(tmp_path: Path) -> None:
    """Fixture payload duration is 5s; root+subagent timestamps span 80s. The
    result must be 80s and scoped `transcript-root-plus-subagents` -- payload
    duration never enters this function at all."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-1"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(root, [_iso(0), _iso(30)])
    _write_jsonl(_subagents_dir(root) / "agent-a.jsonl", [_iso(10), _iso(80)])

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWall)
    assert outcome.wall_s == 80.0
    assert outcome.scope == TRANSCRIPT_ROOT_PLUS_SUBAGENTS


# --- falsifier 2: unrelated sibling session must not leak in -------------------


def test_unrelated_sibling_session_does_not_extend_the_span(tmp_path: Path) -> None:
    """A second, unrelated session under the same `.claude-k4/projects/` tree
    spans 200s. The result for THIS session must remain 80s: matching is by
    exact `session_id` filename, never by directory-wide `rglob`."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-2"
    other_session_id = "sess-unrelated-sibling"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(root, [_iso(0), _iso(30)])
    _write_jsonl(_subagents_dir(root) / "agent-a.jsonl", [_iso(10), _iso(80)])

    other_root = _root_transcript(workspace, other_session_id)
    _write_jsonl(other_root, [_iso(0), _iso(200)])

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWall)
    assert outcome.wall_s == 80.0


# --- falsifier 3: fail closed, never report the payload duration --------------


def test_missing_root_transcript_fails_closed(tmp_path: Path) -> None:
    payload_path, workspace = _workspace(tmp_path)
    (workspace / ".claude-k4" / "projects" / "-fake-proj").mkdir(parents=True)

    outcome = resolve_transcript_wall("nwave", "sess-missing", payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_missing_claude_k4_workspace_fails_closed(tmp_path: Path) -> None:
    """No `.claude-k4` directory at all under the workspace -- the ordinary
    shape for a run that was never captured with a config dir override."""
    payload_path, _workspace_dir = _workspace(tmp_path)

    outcome = resolve_transcript_wall("nwave", "sess-none", payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_duplicate_root_transcript_fails_closed(tmp_path: Path) -> None:
    """Two files named `<session_id>.jsonl` under `projects/**` -- ambiguous,
    not "pick the first one". A wall claim resolved from the wrong transcript
    is worse than no claim."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-3-dup"
    root_a = _root_transcript(workspace, session_id, project="-proj-a")
    root_b = _root_transcript(workspace, session_id, project="-proj-b")
    _write_jsonl(root_a, [_iso(0), _iso(30)])
    _write_jsonl(root_b, [_iso(0), _iso(30)])

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_invalid_timestamps_fail_closed_never_report_five_seconds(
    tmp_path: Path,
) -> None:
    """Every line present but no `timestamp` field parses -- a malformed
    capture, not a legitimate zero-length run. Must never resolve to the
    payload's 5s duration, because this function never reads it at all."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-3-invalid"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(
        root,
        [],
        extra_lines=[
            json.dumps({"type": "user", "timestamp": "not-a-timestamp"}),
            json.dumps({"type": "user", "timestamp": "2026-01-01 00:00:00"}),  # naive
            "not even json",
        ],
    )

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_mixed_valid_and_present_invalid_timestamp_fails_closed(tmp_path: Path) -> None:
    """A transcript carrying real, valid timestamps ALONGSIDE one line whose
    `timestamp` key is present but invalid (naive, here) must fail the whole
    file closed -- not silently drop the bad line because other valid
    timestamps exist and compute a span from those alone. That silent drop is
    the exact defect: a partially-corrupt transcript would still report a
    plausible-looking span instead of refusing."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-mixed-invalid"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(
        root,
        [_iso(0), _iso(30)],
        extra_lines=[json.dumps({"type": "user", "timestamp": "2026-01-01 00:00:00"})],
    )

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_mixed_valid_and_malformed_json_line_fails_closed(tmp_path: Path) -> None:
    """Same discipline for a line that is not valid JSON at all: present
    alongside otherwise-valid timestamps, it must still fail the whole
    transcript closed rather than being skipped as noise."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-mixed-malformed-json"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(root, [_iso(0), _iso(30)], extra_lines=["not even json"])

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_single_valid_timestamp_fails_closed(tmp_path: Path) -> None:
    """Exactly one valid timestamp across root+subagents -- a span needs two
    points, so `MIN_USABLE`-style reasoning applies here too."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-3-single"
    root = _root_transcript(workspace, session_id)
    _write_jsonl(root, [_iso(0)])

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


def test_unreadable_root_file_fails_closed(tmp_path: Path) -> None:
    """The matched path exists as a directory, not a file -- reading it raises
    `OSError`, which must surface as a refusal, not an uncaught exception."""
    payload_path, workspace = _workspace(tmp_path)
    session_id = "sess-falsifier-3-dir"
    root = _root_transcript(workspace, session_id)
    root.mkdir(parents=True)

    outcome = resolve_transcript_wall("nwave", session_id, payload_path)

    assert isinstance(outcome, TranscriptWallUnreadable)


# --- falsifier 4: order and split invariance -----------------------------------


@_SETTINGS
@given(
    # Integer offsets, not arbitrary floats: `_iso` round-trips through
    # microsecond-precision ISO text, and an arbitrary float seconds value can
    # lose precision in that round-trip in a way an exact `==` against
    # `max(offsets) - min(offsets)` would then spuriously fail. An integer
    # number of seconds has no such rounding boundary to cross.
    offsets=st.lists(
        st.integers(min_value=0, max_value=10_000),
        min_size=2,
        max_size=12,
        unique=True,
    ),
    seed=st.randoms(use_true_random=False),
)
def test_span_is_invariant_under_record_order_and_root_subagent_split(
    offsets: list[int], seed
) -> None:
    """The span is a function of the MULTISET of timestamps. Permuting line
    order within a file, and permuting which timestamps land in the root file
    versus which land in a subagent file, must leave `max - min` unchanged.

    Uses a fresh `tempfile.TemporaryDirectory()` per generated example rather
    than pytest's function-scoped `tmp_path` fixture: `tmp_path` is created
    once for the whole test function, so sharing it across Hypothesis's many
    generated examples trips the `function_scoped_fixture` health check --
    the fixture's lifetime does not match the per-example lifetime Hypothesis
    assumes. A directory scoped to the example, not the function, has no such
    mismatch and needs no health-check suppression."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        payload_path, workspace = _workspace(Path(tmp_dir))
        session_id = "sess-falsifier-4"
        root_stamps = list(offsets)
        seed.shuffle(root_stamps)
        split = seed.randint(0, len(root_stamps))
        root_part, sub_part = root_stamps[:split], root_stamps[split:]

        root = _root_transcript(workspace, session_id)
        _write_jsonl(root, [_iso(s) for s in root_part] or [_iso(offsets[0])])
        if sub_part:
            _write_jsonl(
                _subagents_dir(root) / "agent-a.jsonl", [_iso(s) for s in sub_part]
            )
        # Ensure at least two timestamps total even if the split emptied one
        # side onto an already-populated root; the property only claims
        # invariance of the span, so top up root with the full set when the
        # split degenerates.
        if not sub_part and len(root_part) < 2:
            _write_jsonl(root, [_iso(s) for s in offsets])

        outcome = resolve_transcript_wall("nwave", session_id, payload_path)

        assert isinstance(outcome, TranscriptWall)
        assert outcome.wall_s == max(offsets) - min(offsets)
