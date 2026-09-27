"""The decomposition must reproduce a split a reader can check by hand.

Each fixture states the timestamps and the answer arithmetic gives, so a change
that silently redefines delegated or root-only time fails here rather than in a
number nobody can re-derive.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))

import phase_timing as pt


_START = datetime(2026, 8, 23, 18, 53, 29, tzinfo=timezone.utc)


def _stamp(offset: float) -> str:
    return (_START + timedelta(seconds=offset)).isoformat().replace("+00:00", "Z")


def _write(path: Path, offsets: list[float]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for offset in offsets:
            handle.write(json.dumps({"timestamp": _stamp(offset)}) + "\n")


def _arm(tmp_path: Path, root: list[float], *subagents: list[float]) -> Path:
    session = tmp_path / ".claude-k4" / "projects" / "p" / "s.jsonl"
    _write(session, root)
    for index, offsets in enumerate(subagents):
        _write(session.parent / "s" / "subagents" / f"agent-{index}.jsonl", offsets)
    return tmp_path


def test_the_span_comes_from_the_transcript_not_a_payload(tmp_path: Path) -> None:
    result = pt.decompose(_arm(tmp_path, [0, 100, 300]), "nwave")
    assert result.span_seconds == 300


def test_root_only_is_the_time_no_delegated_turn_was_open(tmp_path: Path) -> None:
    """Root 0-300, one delegated turn 100-200: root-only is the other 200s."""
    result = pt.decompose(_arm(tmp_path, [0, 300], [100, 200]), "nwave")
    assert result.delegated_seconds == 100
    assert result.root_only_seconds == 200
    assert result.root_only_share == 200 / 300
    assert result.gaps == (100.0, 100.0)


def test_concurrent_turns_count_once(tmp_path: Path) -> None:
    """Two turns overlapping 100-250 are 150s of delegated time, not 200."""
    result = pt.decompose(_arm(tmp_path, [0, 300], [100, 200], [150, 250]), "nwave")
    assert result.delegated_seconds == 150
    assert result.root_only_seconds == 150


def test_a_run_with_no_delegation_is_all_root_only(tmp_path: Path) -> None:
    result = pt.decompose(_arm(tmp_path, [0, 120]), "nwave")
    assert result.delegated_seconds == 0
    assert result.root_only_share == 1.0


def test_merge_is_the_union_never_the_sum() -> None:
    merged = pt.merge([pt.Interval(0, 10), pt.Interval(5, 20), pt.Interval(30, 40)])
    assert [(span.start, span.end) for span in merged] == [(0, 20), (30, 40)]


def test_a_campaign_with_no_arm_workspace_refuses_loudly(
    tmp_path: Path, capsys
) -> None:
    (tmp_path / "pair-1").mkdir(parents=True)
    assert pt.main(["--campaign", str(tmp_path)]) == 2
    printed = capsys.readouterr().out
    assert "WHAT:" in printed and "WHY:" in printed and "HOW:" in printed
