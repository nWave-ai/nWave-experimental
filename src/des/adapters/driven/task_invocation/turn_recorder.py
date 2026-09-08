"""Write one diagnostic record per model turn.  NOTHING in DES reads them back.

WHY THIS EXISTS.  `DeliveryContinuationRunner._model_runs` lives in memory and
dies with the process, so a real end-to-end run leaves no trace of what each role
was asked and what it answered.  That costs twice: a human cannot read the run,
and the run cannot be replayed against the runner through a fake port, because
the material to build that fake from was never written down.

WHY IT IS DIAGNOSTIC AND NOTHING ELSE.  The runner deriving control flow from
these files would make a recording into an authority, and a recording of
model-authored prose is exactly the substrate the envelope law keeps out of the
control plane.  So there is no reader: `des` writes this directory and never
opens it.  A test asserts that property over `src/des` rather than trusting this
sentence.

WHY THE ADAPTER AND NOT THE RUNNER.  Only here are argv, the exact bytes written
to the child's stdin, and the provider's raw stdout all in scope at once; the
runner sees a `ModelRun` that has already been interpreted, so recording there
would lose the very envelope that makes a turn replayable.

WRITING NEVER DECIDES ANYTHING.  A failed write is one line on stderr, never an
outcome: a diagnostic that can fail a delivery is worse than no diagnostic.
Nothing is truncated either -- an aggregate review prompt is ~100 KB and that is
the size it is recorded at, because a silently shortened record would be a
replay that diverges from the run it claims to reproduce.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any


TURN_LOG_RELATIVE_DIR = ".nwave/des/logs/turns"
"""Under `.nwave/des/`, the runner's own state directory.

The exclusion that keeps these records out of a role's drift comparison is
`_RUNNER_OWNED_PREFIX` in the delivery runner, NOT a host repository's
`.gitignore`: `--untracked-files=all` reports an untracked record like any other
byte, and a repository that does not ignore `.nwave/` is an ordinary case, not a
misconfiguration.  Measured 2026-09-05: relying on the ignore file failed six
public acceptance tests whose fixtures write no `.gitignore` at all."""


def _new_run_id() -> str:
    """One id per runner invocation: UTC instant plus pid, no ledger, no index."""
    return f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}-{os.getpid()}"


class TurnRecorder:
    """One recorder per run; it numbers the turns it is handed, in order.

    ``root`` anchors every record of one run to ONE directory.  It is not the
    turn's own ``cwd``, and that distinction is measured, not stylistic: the
    implementation reviewer runs with the CANDIDATE WORKTREE as its cwd, so
    recording per-cwd split one run across two roots and the cleanup then
    destroyed the half in the candidate -- a full Success left records numbered
    01..05 and 07, with the reviewer's turn simply gone. A replay built from
    that is a different run. ``None`` keeps the per-cwd behaviour for the
    runtime smoke and any ad-hoc caller, which have no run to anchor to.
    """

    def __init__(self, run_id: str | None = None, root: Path | None = None) -> None:
        self._run_id = run_id or _new_run_id()
        self._root = root
        self._sequence = 0

    @property
    def run_id(self) -> str:
        return self._run_id

    def record(
        self,
        *,
        root: Path,
        role_id: str,
        prompt: str,
        argv: list[str] | None,
        outcome: str,
        diagnostic: str,
        exit_status: int,
        retry_safe: bool,
        provider_stdout: str | None,
        provider_stderr: str | None,
        started_at: float,
        ended_at: float,
        raised: str | None = None,
    ) -> Path | None:
        """Write one turn's record; return its path, or None when writing failed.

        The return value exists for the test that reads a record back, not for
        the runner: no caller branches on it.
        """
        self._sequence += 1
        name = f"{self._sequence:02d}-{role_id}.json"
        anchor = self._root if self._root is not None else Path(root)
        directory = anchor / TURN_LOG_RELATIVE_DIR / self._run_id
        document: dict[str, Any] = {
            "run_id": self._run_id,
            "sequence": self._sequence,
            "role_id": role_id,
            # The prompt exactly as it was written to the child's stdin.  It is
            # no longer in argv, which is why `argv` below is safe to keep whole.
            "prompt": prompt,
            "argv": argv,
            "outcome": outcome,
            "diagnostic": diagnostic,
            "exit_status": exit_status,
            "retry_safe": retry_safe,
            # Raw, never re-parsed: this is a recording, not a second parser of
            # the envelope.  `extract_model_run` remains the only reader of the
            # provider's document, and it reads the process, not this file.
            "provider_stdout": provider_stdout,
            "provider_stderr": provider_stderr,
            # The exception type when the turn left by RAISING, else None.  A
            # raised turn has no ModelRun, so without this a reader could not
            # tell it apart from one that honestly answered `indeterminate`.
            "raised": raised,
            "started_at": _utc(started_at),
            "ended_at": _utc(ended_at),
            "duration_seconds": round(ended_at - started_at, 6),
        }
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / name
            path.write_text(
                json.dumps(document, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except OSError as error:
            # Loud, and only that: the turn already happened and its outcome is
            # the model's, not this file's.
            print(
                f"des: could not record turn {self._sequence} for {role_id}: {error}",
                file=sys.stderr,
            )
            return None
        return path


def _utc(instant: float) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(instant))


__all__ = ["TURN_LOG_RELATIVE_DIR", "TurnRecorder"]
