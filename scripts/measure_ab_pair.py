"""A/B timing of one file across two worktrees, with the order ALTERNATED.

Interleaving the two arms so they share a load window is necessary and not
sufficient. If the order inside each repetition is FIXED -- always BASE then CONV
-- the second arm systematically inherits a warmer cache (page cache, import
caches, uv's resolution cache, the git object store both worktrees share), and
that advantage is indistinguishable from the effect under study. A sister lane
caught exactly this: its null control -- a file the patch could not touch --
reported a 2.31x "improvement" that was pure position.

So the order alternates: repetition 0 runs BASE then CONV, repetition 1 runs CONV
then BASE, and so on. With an even number of repetitions each arm occupies each
position the same number of times, and the position advantage cancels instead of
accruing to one side.

The null control is measured the same way, alternated, from the SAME pair of
worktrees. It is the falsifier: on a file neither tree changed, the two arms must
come out equal. If the null control shows a factor, the harness is measuring
position or load, and every other factor in the run is suspect by the same amount.

Usage:
    uv run python scripts/measure_ab_pair.py <base_wt> <conv_wt> <files.txt> <out.json>
                                             [--reps 4] [--null <path>]
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import subprocess
import time
from pathlib import Path


_RESULT = re.compile(r"NWAVE_TEST_RESULT:(\{.*?\})")

# A file that neither arm modifies. Its measured factor must be ~1.0; anything
# else is the harness reporting on itself.
DEFAULT_NULL_CONTROL = "tests/release/test_read_toml_field.py"

# Wall-clock ceiling for one arm. Generous, because a slow arm is exactly what
# this script exists to measure -- but bounded, because an unbounded measurement
# that hangs yields no datum while looking like work in progress.
_RUN_TIMEOUT_SECONDS = 1800


def _run_once(worktree: Path, target: str) -> tuple[float, dict, int]:
    t0 = time.monotonic()
    proc = subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-m",
            "pytest",
            target,
            "-q",
            "--tb=no",
            "-p",
            "no:pspec",
            "-p",
            "no:xdist",
        ],
        cwd=worktree,
        capture_output=True,
        text=True,
        # A measurement child must never inherit fd 0: POSIX passes it down
        # transitively, so a nested pytest could block forever on a descriptor
        # that never reaches EOF -- and a measurement that hangs produces no
        # number at all, which reads the same as a slow one.
        stdin=subprocess.DEVNULL,
        timeout=_RUN_TIMEOUT_SECONDS,
    )
    elapsed = time.monotonic() - t0
    match = _RESULT.search(proc.stdout) or _RESULT.search(proc.stderr)
    return (
        elapsed,
        (json.loads(match.group(1)) if match else {"parse_error": True}),
        proc.returncode,
    )


def _collected(result: dict) -> int:
    return sum(result.get(k, 0) for k in ("passed", "failed", "skipped", "xfailed"))


def measure_pair(base: Path, conv: Path, target: str, reps: int) -> dict:
    """Time `target` in both worktrees, alternating which arm goes first."""
    base_times: list[float] = []
    conv_times: list[float] = []
    base_res: dict = {}
    conv_res: dict = {}
    base_rc = conv_rc = 0
    order_log: list[str] = []

    for rep in range(reps):
        base_first = rep % 2 == 0
        order_log.append("base-first" if base_first else "conv-first")
        if base_first:
            bt, base_res, base_rc = _run_once(base, target)
            ct, conv_res, conv_rc = _run_once(conv, target)
        else:
            ct, conv_res, conv_rc = _run_once(conv, target)
            bt, base_res, base_rc = _run_once(base, target)
        base_times.append(bt)
        conv_times.append(ct)

    # The median resists a single contended repetition better than the min, which
    # is optimistic, or the mean, which one outlier dominates.
    b = statistics.median(base_times)
    c = statistics.median(conv_times)
    return {
        "file": target,
        "before_s": round(b, 2),
        "after_s": round(c, 2),
        "factor": round(b / c, 2) if c else None,
        "before_tests": _collected(base_res),
        "after_tests": _collected(conv_res),
        "before_rc": base_rc,
        "after_rc": conv_rc,
        "reps": reps,
        "order": order_log,
        "before_samples": [round(x, 2) for x in base_times],
        "after_samples": [round(x, 2) for x in conv_times],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base_worktree", type=Path)
    ap.add_argument("conv_worktree", type=Path)
    ap.add_argument("files", type=Path, help="newline-separated test paths")
    ap.add_argument("out", type=Path)
    ap.add_argument("--reps", type=int, default=4, help="EVEN, so order cancels")
    ap.add_argument("--null", default=DEFAULT_NULL_CONTROL)
    args = ap.parse_args()

    if args.reps % 2:
        print(
            f"--reps must be EVEN so each arm holds each position equally "
            f"(got {args.reps}); the order advantage would not cancel."
        )
        return 2

    targets = args.files.read_text().split()
    rows = []

    null_row = measure_pair(
        args.base_worktree, args.conv_worktree, args.null, args.reps
    )
    null_factor = null_row["factor"] or 1.0
    null_ok = 0.9 <= null_factor <= 1.1
    print(
        f"NULL CONTROL {args.null}: {null_row['before_s']}s vs {null_row['after_s']}s "
        f"= x{null_factor}  -> {'CLEAN' if null_ok else 'BIASED, every factor below is suspect'}"
    )

    for target in targets:
        row = measure_pair(args.base_worktree, args.conv_worktree, target, args.reps)
        rows.append(row)
        flag = (
            ""
            if row["before_tests"] == row["after_tests"] and row["after_rc"] == 0
            else "  <<<"
        )
        print(
            f"{row['before_s']:7.2f}s -> {row['after_s']:7.2f}s  x{row['factor']:5.2f}  "
            f"tests {row['before_tests']}->{row['after_tests']}  {target}{flag}",
            flush=True,
        )
        args.out.write_text(
            json.dumps(
                {"null_control": null_row, "null_control_clean": null_ok, "rows": rows},
                indent=2,
            )
        )

    before = sum(r["before_s"] for r in rows)
    after = sum(r["after_s"] for r in rows)
    print(
        f"\nBATCH {before:.2f}s -> {after:.2f}s  x{before / after:.2f}"
        f"   (null control x{null_factor} -- {'clean' if null_ok else 'BIASED'})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
