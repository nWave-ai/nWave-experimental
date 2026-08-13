#!/usr/bin/env python3
"""Does pairing cancel the provider noise, or only estimate it?

The benchmark's 10x-20x spread correlates with time of day, i.e. contention.
Contention shared by both arms of a pair CANCELS inside the pair; run the arms
hours apart and it is a confound you can only average away with large N.

So this asks ONE question, on an A-vs-A' campaign where the arms are identical
by construction: is the WITHIN-PAIR ratio materially smaller than the
ACROSS-PAIR ratio? If yes, pairing is the cheap lever and a real A/B can use it.
If no, pairing does not cancel and the design has to change.

A-vs-A' is deliberate. Calibrate the METHOD before trusting it to compare two
things that actually differ.
"""

from __future__ import annotations

import argparse
import statistics as st
import sys
from pathlib import Path

from scripts.analysis.paired_spread import (
    MIN_USABLE,
    TRANSCRIPT_ROOT_PLUS_SUBAGENTS,
    TranscriptWall,
    Usable,
    classify,
    resolve_transcript_wall,
)


#: Metrics whose ratio is meaningless ACROSS harnesses. Cache reads bill at 0.1x
#: base input and writes at 1.25-2x, so a raw token total compares two different
#: things the moment the arms have different cache mixes. Kept because within one
#: arm across pairs it still shows variance -- but flagged in the output, which
#: is what the lane-D audit found missing here while its sibling module had it.
_NOT_COMPARABLE_ACROSS_HARNESSES = {"output tok"}

#: `wall clock s` is deliberately absent here: `Usable.wall_s` is
#: root-payload-only and ends when the ROOT process returns even while its
#: dispatched agents keep running (the exact K4 gap). `main` resolves that
#: metric separately, per run, through `resolve_transcript_wall` -- the same
#: path-aware boundary `paired_spread.py` uses -- and never reads `r.wall_s`.
METRICS = (
    ("cost USD", lambda r: r.cost),
    ("turns", lambda r: float(r.turns)),
    ("output tok", lambda r: float(r.tokens["out"])),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--campaign",
        type=Path,
        default=Path.cwd(),
        help="campaign directory holding pair-*/ (default: cwd)",
    )
    base = parser.parse_args(argv).campaign
    pairs: dict[str, dict[str, Usable]] = {}
    paths: dict[str, dict[str, Path]] = {}
    for path in sorted(base.glob("pair-*/*.json")):
        outcome = classify(
            f"{path.parent.name}/{path.stem}", path.read_text(errors="replace")
        )
        if isinstance(outcome, Usable):
            pairs.setdefault(path.parent.name, {})[path.stem] = outcome
            paths.setdefault(path.parent.name, {})[path.stem] = path

    complete = {k: v for k, v in pairs.items() if len(v) == 2}
    print(f"pairs found: {len(pairs)}   complete (both arms usable): {len(complete)}")
    for k, v in sorted(pairs.items()):
        if len(v) != 2:
            print(
                f"   INCOMPLETE {k}: arms {sorted(v)} — excluded, a half pair cancels nothing"
            )
    if len(complete) < MIN_USABLE:
        print(
            f"\nREFUSING: fewer than {MIN_USABLE} complete pairs. Within-pair and"
            "\nacross-pair cannot be compared below the floor `paired_spread` already"
            "\ndeclares -- two modules disagreeing on what counts as a spread is how a"
            "\nnumber gets published from a sample its own sibling calls meaningless.",
            file=sys.stderr,
        )
        return 1

    # Wall clock is resolved from transcript evidence, path-aware, never from
    # the payload's own `wall_s` -- root-payload-only, it ends when the ROOT
    # process returns even while its dispatched agents keep running, the exact
    # K4 gap `resolve_transcript_wall` exists to close. A pair missing wall
    # evidence on either arm is excluded from the WALL METRIC ONLY: cost,
    # turns and tokens already have everything the payload gives them and stay
    # intact for that pair.
    wall_by_pair: dict[str, dict[str, float]] = {}
    wall_missing_pairs: list[str] = []
    for pair_name, arms in complete.items():
        resolved: dict[str, float] = {}
        for arm_name, run in arms.items():
            outcome = resolve_transcript_wall(
                run.name, run.session_id, paths[pair_name][arm_name]
            )
            if isinstance(outcome, TranscriptWall):
                resolved[arm_name] = outcome.wall_s
        if len(resolved) == 2:
            wall_by_pair[pair_name] = resolved
        else:
            wall_missing_pairs.append(pair_name)
    if wall_missing_pairs:
        print(
            f"\nwall clock evidence missing for {len(wall_missing_pairs)} pair(s), "
            "excluded from the wall metric only (cost/turns/tokens unaffected):"
        )
        for name in wall_missing_pairs:
            print(f"     {name}")

    print(
        f"\n{'metric':16s}{'within-pair max/min':>22s}{'across-pair max/min':>22s}{'cancelled':>12s}"
    )
    print("-" * 72)

    series: list[tuple[str, dict[str, dict[str, float]]]] = [
        ("wall clock s", wall_by_pair),
        *(
            (
                label,
                {
                    p: {a: get(r) for a, r in arms.items()}
                    for p, arms in complete.items()
                },
            )
            for label, get in METRICS
        ),
    ]

    for label, values in series:
        within = []
        for arms in values.values():
            a, b = arms.values()
            lo, hi = min(a, b), max(a, b)
            if lo > 0:
                within.append(hi / lo)
        # Across-pair is computed WITHIN each arm, across pairs, then taken at
        # its widest -- never over the two arms pooled. Pooling was valid only
        # in the degenerate A-vs-A' case where arm identity carries no meaning;
        # the moment the arms genuinely differ, which is the K4 comparison this
        # module exists to serve, it folds the arm effect into the number that
        # is supposed to isolate provider noise. Exhibited by the lane-D audit.
        per_arm: dict[str, list[float]] = {}
        for arms in values.values():
            for arm_name, v in arms.items():
                per_arm.setdefault(arm_name, []).append(v)
        arm_ranges = [
            max(vals) / min(vals)
            for vals in per_arm.values()
            if len(vals) > 1 and min(vals) > 0
        ]
        if not within or not arm_ranges:
            print(f"{label:16s}{'INDETERMINATE (a zero value, or one pair)':>56s}")
            continue
        w_med, across = st.median(within), max(arm_ranges)
        # How much of the observed spread the pairing removes.
        cancelled = (
            f"{(1 - (w_med - 1) / (across - 1)) * 100:5.1f}%" if across > 1 else "n/a"
        )
        flag = " *" if label in _NOT_COMPARABLE_ACROSS_HARNESSES else ""
        print(f"{label:16s}{w_med:22.2f}{across:22.2f}{cancelled:>12s}{flag}")

    print(
        "\n  * raw token totals are NOT comparable between two DIFFERENT harnesses:"
        "\n    cache reads bill at 0.1x base input, writes at 1.25-2x. Use USD, or a"
        "\n    per-category table. Within one arm across pairs the ratio is fine."
        "\n"
        f"\nwall clock reflects scope: {TRANSCRIPT_ROOT_PLUS_SUBAGENTS}"
        "\n"
        "\nREAD THIS AS: within-pair is the residue AFTER shared conditions cancel;"
        "\nacross-pair is the raw spread. A within-pair near 1.00 with a large"
        f"\nacross-pair means pairing is the lever. At {len(complete)} pairs this is an"
        "\nobserved range, not an estimate — it shows what varied, it bounds nothing."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
