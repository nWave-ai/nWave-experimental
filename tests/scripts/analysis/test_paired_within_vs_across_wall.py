"""Laws for the wall-clock metric in `paired_within_vs_across.py`.

The defect this guards: the module used to read `Usable.wall_s` directly --
root-payload-only, ends when the ROOT process returns even while dispatched
agents keep running, the exact K4 gap. It must instead resolve wall clock
per run through the same path-aware `resolve_transcript_wall` boundary
`paired_spread.py` uses, and a pair missing wall evidence on either arm must
be excluded from the WALL metric only -- cost/turns/tokens stay intact for
that pair, computed straight from the payload as before.

Run: uv run pytest -q test_paired_within_vs_across_wall.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.analysis.paired_within_vs_across import main


def _iso(seconds_from_epoch: float) -> str:
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return (
        (base + timedelta(seconds=seconds_from_epoch))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _payload(session_id: str, *, duration_ms: int = 5_000) -> str:
    return json.dumps(
        {
            "session_id": session_id,
            "is_error": False,
            "total_cost_usd": 1.5,
            "num_turns": 7,
            "duration_ms": duration_ms,
            "usage": {
                "input_tokens": 10,
                "output_tokens": 20,
                "cache_creation_input_tokens": 30,
                "cache_read_input_tokens": 40,
            },
        }
    )


def _write_transcript(workspace: Path, session_id: str, offsets: list[float]) -> None:
    root = workspace / ".claude-k4" / "projects" / "-proj" / f"{session_id}.jsonl"
    root.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps({"type": "user", "timestamp": _iso(o)}) for o in offsets]
    root.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_pair(
    base: Path,
    pair_name: str,
    *,
    control_offsets: list[float] | None,
    nwave_offsets: list[float] | None,
) -> None:
    """Write one pair with both arms usable; each arm's transcript is present
    only when its offsets are given, so a `None` reproduces a run with no
    readable wall evidence at all."""
    pair_dir = base / pair_name
    pair_dir.mkdir(parents=True, exist_ok=True)
    for arm, offsets in (("control", control_offsets), ("nwave", nwave_offsets)):
        session_id = f"sess-{pair_name}-{arm}"
        (pair_dir / f"{arm}.json").write_text(_payload(session_id), encoding="utf-8")
        workspace = pair_dir / arm
        workspace.mkdir(exist_ok=True)
        if offsets is not None:
            _write_transcript(workspace, session_id, offsets)


def test_wall_metric_uses_transcript_span_not_payload_duration(
    tmp_path: Path, capsys
) -> None:
    """Every payload here claims a 5s duration; every transcript spans
    100/101/102s (control and nwave identical per pair, so within-pair
    cancels to 1.00; across pair-0..2 the span ranges 100->102, a 1.02
    spread). Computed from the transcript span, the row reads exactly
    `within=1.00, across=1.02, cancelled=100.0%`.

    Computed from the 5s payload duration instead (the old, defective
    reading of `r.wall_s`) every arm and every pair would read the SAME
    5.0s, collapsing across-pair to 1.00 and cancelled to `n/a` -- so this
    exact row is a real falsifier against that implementation, not just a
    presence check that any non-INDETERMINATE row would satisfy.

    The row is parsed by the fixed column widths `main` itself prints with
    (`label:16s`, `within:22.2f`, `across:22.2f`, `cancelled:>12s`), not by
    a substring search that could match a coincidentally similar metric row
    (cost/turns/output-tok are all constant across these fixtures too, and
    print `1.00`/`1.00`/`n/a` -- distinct from the wall row's values)."""
    for i in range(3):
        _write_pair(
            tmp_path,
            f"pair-{i}",
            control_offsets=[0, 100 + i],
            nwave_offsets=[0, 100 + i],
        )

    rc = main(["--campaign", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    wall_line = next(
        line for line in out.splitlines() if line.startswith("wall clock s")
    )
    label, within_field, across_field, cancelled_field = (
        wall_line[:16],
        wall_line[16:38],
        wall_line[38:60],
        wall_line[60:72],
    )
    assert label.strip() == "wall clock s"
    assert within_field.strip() == "1.00"
    assert across_field.strip() == "1.02"
    assert cancelled_field.strip() == "100.0%"


def test_pair_missing_wall_evidence_is_excluded_from_wall_metric_only(
    tmp_path: Path, capsys
) -> None:
    """One pair has no transcript at all on one arm (no wall evidence); two
    other pairs have full evidence. That one pair must still count fully
    toward cost/turns/tokens -- only the wall metric drops it -- and the run
    must not fail closed for the whole campaign."""
    _write_pair(tmp_path, "pair-0", control_offsets=[0, 50], nwave_offsets=[0, 50])
    _write_pair(tmp_path, "pair-1", control_offsets=[0, 60], nwave_offsets=[0, 60])
    _write_pair(tmp_path, "pair-2", control_offsets=None, nwave_offsets=[0, 70])

    rc = main(["--campaign", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "complete (both arms usable): 3" in out
    assert "wall clock evidence missing for 1 pair(s)" in out
    assert "pair-2" in out
    cost_line = next(line for line in out.splitlines() if line.startswith("cost USD"))
    assert "INDETERMINATE" not in cost_line


def test_all_pairs_missing_wall_evidence_makes_wall_metric_indeterminate_while_cost_remains_determinate(
    tmp_path: Path, capsys
) -> None:
    """When every complete pair lacks transcript-wall evidence on at least one
    arm, wall_by_pair is empty and the `wall clock s` row becomes fully
    INDETERMINATE. An unaffected metric such as `cost USD` that reads straight
    from payloads remains determinate for all pairs.

    This guards against independent-review blocker: verifies wall metric
    correctly degrades to INDETERMINATE while other metrics survive intact."""
    _write_pair(tmp_path, "pair-0", control_offsets=[0, 50], nwave_offsets=None)
    _write_pair(tmp_path, "pair-1", control_offsets=None, nwave_offsets=[0, 60])
    _write_pair(tmp_path, "pair-2", control_offsets=[0, 70], nwave_offsets=None)

    rc = main(["--campaign", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "complete (both arms usable): 3" in out
    assert "wall clock evidence missing for 3 pair(s)" in out

    wall_line = next(
        line for line in out.splitlines() if line.startswith("wall clock s")
    )
    label = wall_line[:16].strip()
    content = wall_line[16:].strip()
    assert label == "wall clock s"
    assert "INDETERMINATE" in content

    cost_line = next(line for line in out.splitlines() if line.startswith("cost USD"))
    assert "INDETERMINATE" not in cost_line
