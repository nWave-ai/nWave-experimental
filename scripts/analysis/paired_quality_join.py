#!/usr/bin/env python3
"""Join each run of a paired campaign to an INDEPENDENTLY OWNED quality verdict.

K3's fifth property. The capture specification is explicit that acceptance stays
authoritative where it already lives and that capture stores "a structural
reference to its record and commit, not a competing YES". So this module never
decides quality. It only answers one question, and refuses when it cannot:

    is every run bound to exactly one verdict, by a key present on BOTH sides?

The key is `session_id`, taken from the run's own payload. Not a timestamp, not
a directory name, not the arm label -- the capture spec lists exactly those as
rejected constructions ("run_id reconstructed from timestamp proximity"), because
each of them can bind the wrong pair of things and look right.

Why this must refuse rather than report a partial join: a cost-per-accepted-outcome
figure computed over the runs that HAPPENED to have a verdict silently changes its
own denominator. The arm whose runs failed to be scored looks cheaper, and the
direction of that bias is exactly the direction a motivated reader wants.

    paired_quality_join.py --campaign ./campaign --verdicts verdicts.json

`verdicts.json` is written by whoever owns acceptance, never by this tool:

    {"<session_id>": {"accepted": true,  "evidence": "hidden-suite 81/81",
                      "scorer": "nw-user-examiner", "commit": "<sha>"},
     "<session_id>": {"accepted": false, "evidence": "2 features failed", ...}}
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from scripts.analysis.paired_spread import Usable, classify


@dataclass(frozen=True)
class Joined:
    """A run bound to its verdict. `accepted` came from the scorer, not here."""

    run: str
    session_id: str
    arm: str
    accepted: bool
    evidence: str


@dataclass(frozen=True)
class Duplicate:
    """A second artifact carrying a `session_id` already seen.

    Exhibited by the lane-D audit 2026-08-06: `runs[session_id] = ...` overwrote
    without a check, so two well-formed runs sharing one session produced
    `usable: 1, JOINED: 1, exit 0` and the second vanished with no mention. That
    is this tool's OWN stated failure mode - a denominator shrinking in silence,
    so the arm whose runs went unscored looks cheaper - reproduced inside the
    tool built to prevent it. `paired_spread.py` already carried this guard: it
    was written in one file and not the other."""

    name: str
    session_id: str
    first_seen: str


@dataclass(frozen=True)
class Unjoined:
    """A run with no verdict, or a verdict with no run. Named, never dropped."""

    what: str
    key: str
    reason: str


def join(
    runs: dict[str, tuple[str, str]], verdicts: dict[str, dict]
) -> tuple[list[Joined], list[Unjoined]]:
    """Total: every run and every verdict lands in exactly one of the two lists.

    `runs` maps session_id -> (run name, arm). Both directions are checked --
    an unmatched VERDICT matters as much as an unmatched run, because it means
    the scorer judged something this campaign did not produce.
    """
    joined: list[Joined] = []
    unjoined: list[Unjoined] = []

    for session_id, (name, arm) in sorted(runs.items()):
        verdict = verdicts.get(session_id)
        if verdict is None:
            unjoined.append(
                Unjoined("run", name, f"no verdict carries session {session_id[:12]}")
            )
            continue
        if "accepted" not in verdict:
            unjoined.append(Unjoined("run", name, "verdict has no `accepted` field"))
            continue
        joined.append(
            Joined(
                name,
                session_id,
                arm,
                bool(verdict["accepted"]),
                str(verdict.get("evidence", "<none stated>")),
            )
        )

    for session_id in sorted(set(verdicts) - set(runs)):
        unjoined.append(
            Unjoined(
                "verdict",
                session_id[:12],
                "scored a session this campaign did not produce",
            )
        )
    return joined, unjoined


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--campaign", required=True, type=Path)
    parser.add_argument("--verdicts", required=True, type=Path)
    args = parser.parse_args(argv)

    runs: dict[str, tuple[str, str]] = {}
    duplicates: list[Duplicate] = []
    unusable = 0
    for path in sorted(args.campaign.glob("pair-*/*.json")):
        outcome = classify(
            f"{path.parent.name}/{path.stem}", path.read_text(errors="replace")
        )
        if not isinstance(outcome, Usable):
            unusable += 1
            continue
        if outcome.session_id in runs:
            # NEVER an overwrite. A repeated session is a counting error, and
            # dropping it is exactly the silent denominator change this tool
            # refuses to make anywhere else.
            duplicates.append(
                Duplicate(outcome.name, outcome.session_id, runs[outcome.session_id][0])
            )
            continue
        runs[outcome.session_id] = (outcome.name, path.stem)

    verdicts = json.loads(args.verdicts.read_text(encoding="utf-8"))
    joined, unjoined = join(runs, verdicts)

    print(f"usable runs      : {len(runs)}   (unusable, excluded: {unusable})")
    print(f"DUPLICATE runs   : {len(duplicates)}   (same session_id seen twice)")
    for item in duplicates:
        print(
            f"     {item.name}: session {item.session_id[:12]} "
            f"already counted as {item.first_seen}"
        )
    print(f"verdicts supplied: {len(verdicts)}")
    print(f"JOINED           : {len(joined)}")
    print(f"UNJOINED         : {len(unjoined)}")
    for item in unjoined:
        print(f"     {item.what:7s} {item.key}: {item.reason}")

    if duplicates:
        print(
            "\nWHAT: two artifacts carry the same session_id.\n"
            "WHY:  a run counted twice, or a run silently dropped, changes the\n"
            "      denominator of every per-outcome ratio computed from this join.\n"
            "HOW:  remove the copy, or re-run the campaign so each run carries its\n"
            "      own session. Do not reconcile them here.",
            file=sys.stderr,
        )
        return 1

    if unjoined:
        print(
            "\nWHAT: the join is incomplete.\n"
            "WHY:  any per-outcome figure computed now would silently change its own\n"
            "      denominator - the arm whose runs went unscored would look cheaper,\n"
            "      and that is the direction a motivated reader wants.\n"
            "HOW:  have the acceptance owner emit a verdict per session_id, or state\n"
            "      why a run is out of scope. Do not score it here; this tool holds a\n"
            "      reference to someone else's verdict, never a verdict of its own.",
            file=sys.stderr,
        )
        return 1

    by_arm: dict[str, list[Joined]] = {}
    for item in joined:
        by_arm.setdefault(item.arm, []).append(item)
    print(f"\n{'arm':16s}{'runs':>6s}{'accepted':>10s}")
    print("-" * 32)
    for arm, items in sorted(by_arm.items()):
        print(f"{arm:16s}{len(items):6d}{sum(1 for i in items if i.accepted):10d}")
    print(
        "\nAcceptance above is the SCORER'S, carried by reference. This tool did"
        "\nnot judge any of it, and a joined run is not a good run - it is a run"
        "\nwhose quality someone else stated and this campaign can point at."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
