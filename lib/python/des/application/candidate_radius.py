"""How wide the oracle and the blind examination must be, measured not declared.

ADR-DES-003 §6: two things are never skipped -- an oracle exists before the
code, and a blind examiner judges the result without seeing it.  How WIDE they
must be «is not declared up front and not promised by the Request: it is
measured from what the candidate actually touched».

REUSED, NOT WRITTEN.  `measure_blast_radius` already measures files, changed
lines, boundary files and the callers of every touched symbol, and classifies a
tier with every reason named.  It had ONE caller, its own CLI.  This module is
the second: it hands the same measurement to `des verify`.

THE SOFTWARE REFUSES NOTHING ON IT.  Width is the reviewer's and the examiner's
judgement over a measured fact -- `boundary:software-measures-model-decides`.
What the software owes is that the fact is honest, so every way of not knowing
degrades LOUD to the widest tier with the reason stated, never to a fabricated
`S`.

BOUNDED IN TIME, because the cost was measured: the caller-count walk exceeded
200 s on a high fan-in file (2026-07-18).  Inside a delivery step that is not a
slow answer, it is no answer, so the measurement runs on a worker and a
measurement that does not return in time is reported as indeterminate -- which
the existing rule already classifies `L`.
"""

from __future__ import annotations

import json
import os
import sys
from typing import TYPE_CHECKING

from des.runtime.spawn import spawn


if TYPE_CHECKING:
    from pathlib import Path


#: How long the whole measurement may take inside a step.  A number, because a
#: bound that is not a number is not a bound; this one is an order of magnitude
#: under the 200 s the caller walk was measured at, so a slow scope degrades
#: rather than holding the step.
RADIUS_TIMEOUT_SECONDS = 20.0

#: What the terminal says when the measurement did not resolve.  The widest
#: tier, with the reason, is the existing rule's own answer for an unresolved
#: consumer count; saying it here keeps the two consistent.
INDETERMINATE = (
    "tier=L files=? boundary=? consumers=indeterminate "
    "(the radius did not resolve in time, so the widest tier is assumed)"
)


def candidate_radius(root: Path, paths: tuple[str, ...]) -> str:
    """One line describing the candidate's radius, or why it is not known.

    A string, because that is what both consumers need: a row on the terminal
    and a fact in two prompts.  Nothing branches on it.
    """
    if not paths:
        return (
            "tier=S files=0 boundary=0 consumers=none (the candidate changed no path)"
        )
    try:
        completed = spawn(
            _blast_radius_argv(root, paths),
            timeout=RADIUS_TIMEOUT_SECONDS,
            capture_output=True,
            text=True,
            check=False,
            reap_process_group=(os.name == "posix"),
        )
        if completed.returncode != 0:
            return INDETERMINATE
        return _radius_row(_final_json_line(completed.stdout))
    except Exception:
        # Every way of not knowing is one way: an unreadable scope, a path the
        # measurement refuses, a walk that did not return. None of them may
        # become a confident `S` (GDP-6).
        return INDETERMINATE


def _blast_radius_argv(root: Path, paths: tuple[str, ...]) -> list[str]:
    """Build the existing CLI producer invocation for this measurement."""
    return [
        sys.executable,
        "-m",
        "des.cli",
        "blast-radius",
        "--repo",
        str(root),
        "--paths",
        *paths,
    ]


def _final_json_line(stdout: str) -> dict[str, object]:
    """Decode the CLI's final nonempty stdout line as its verdict."""
    lines = [line for line in stdout.splitlines() if line.strip()]
    if not lines:
        raise ValueError("blast-radius emitted no JSON verdict")
    payload = json.loads(lines[-1])
    return payload


def _radius_row(payload: dict[str, object]) -> str:
    """Project the existing ``BlastRadiusMeasured`` payload into its row."""
    if payload.get("event") != "BlastRadiusMeasured":
        raise ValueError("blast-radius did not emit a measurement")
    tier = payload["tier"]
    measures = payload["measures"]
    files = measures["files"]
    boundary_files = measures["boundary_files"]
    consumer_counts = measures["consumer_counts"]
    counts = list(consumer_counts.values())
    if not counts or any(count is None for count in counts):
        consumers = "indeterminate"
    else:
        top = max(consumer_counts.items(), key=lambda item: item[1] or 0)
        consumers = f"max {top[1]} ({top[0]})"
    return (
        f"tier={tier} files={files} boundary={len(boundary_files)} "
        f"consumers={consumers}"
    )
