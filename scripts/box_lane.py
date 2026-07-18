#!/usr/bin/env python3
"""The box lane: ONE heavy step at a time, across instances, without deadlock.

WHY THIS EXISTS
---------------
The swarm shape is N cloud lanes + ONE box lane. The cloud lanes are free --
dispatched agents cost no local CPU, so any number may run at once. The box lane
is the scarce one: a heavy gate (a full suite, a contract-gate digest, a cargo
enumerate) saturates the machine, and two of them at once produce mutual timeout
false-reds and orphaned children. Measured repeatedly on this box.

Until now that discipline was PROSE an operator had to remember at 3am. Prose
drifts. This makes it mechanical.

WHAT IT IS NOT
--------------
It is NOT a wrapper. You do NOT run `box-lane run <command>` -- and specifically
you must never wrap a COMMITTING command, because the commit hook runs inside the
wrapper and blocks on the lock the wrapper already holds: a self-deadlock we have
already paid for once. Acquire, run, release are three separate steps, so the
heavy command runs with no lock in its own process tree.

WHY IT CANNOT DEADLOCK YOU OVERNIGHT
------------------------------------
The holder is recorded as a PID. Every acquire checks whether that PID is still
alive; a dead holder's lock is STOLEN, loudly, naming the pid it reclaimed. So the
worst case of a crashed lane is one message, not a machine wedged until morning.
A `--max-age` bound steals from a live-but-hung holder too.

The design rule behind both: a mechanism meant to prevent a mess must not be able
to CAUSE a worse one. A lock that can wedge the box while you sleep is a worse
failure than the contention it prevents.

USAGE
-----
    scripts/box_lane.py acquire --lane heavy --owner "commit-slice slice-04"
    ... run the heavy command ...
    scripts/box_lane.py release --lane heavy

    scripts/box_lane.py status --lane heavy      # who holds it, since when
    scripts/box_lane.py acquire --lane heavy --wait 600   # block, then take it

Exit codes: 0 acquired/released/free · 1 busy (a live holder) · 2 malformed input.
Every outcome is one JSON line on stdout, so a caller can branch on it.

Python-only, stdlib-only, no external tool: it must run on any target machine.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path


# The lock lives under the repo's own .nwave/ runtime dir, so it is per-checkout
# (two clones do not contend) and disappears with the checkout.
_LANE_DIR = Path(".nwave") / "box-lane"

# A live holder older than this is treated as HUNG and stolen. Chosen from the
# measured ceiling of the heaviest real step (a cargo digest needs ~8 uninterrupted
# minutes); 30 minutes is comfortably past any honest heavy step, so a lock older
# than that is far more likely wedged than working.
_DEFAULT_MAX_AGE_S = 1800

_POLL_INTERVAL_S = 5


@dataclass(frozen=True)
class _Holder:
    """Who currently holds a lane, and since when."""

    pid: int
    owner: str
    acquired_at: float

    @property
    def age_s(self) -> float:
        return max(0.0, time.time() - self.acquired_at)


def _emit(payload: dict[str, object]) -> None:
    """One JSON line on stdout -- the caller branches on it, never on prose."""
    print(json.dumps(payload))


def _lane_path(repo: Path, lane: str) -> Path:
    return repo / _LANE_DIR / f"{lane}.json"


def _pid_alive(pid: int) -> bool:
    """True iff a process with this pid exists.

    `os.kill(pid, 0)` raises ProcessLookupError when it does not, and
    PermissionError when it does but belongs to another user -- which still
    means ALIVE, so that branch must not be read as dead.
    """
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _read_holder(path: Path) -> _Holder | None:
    """The recorded holder, or None when the lane is free or the record is junk.

    A corrupt record is treated as FREE rather than as a permanent blocker: a
    half-written file must never be able to wedge the lane.
    """
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    try:
        return _Holder(
            pid=int(record["pid"]),
            owner=str(record.get("owner", "<unnamed>")),
            acquired_at=float(record["acquired_at"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _write_holder(path: Path, owner: str, holder_pid: int) -> _Holder:
    holder = _Holder(pid=holder_pid, owner=owner, acquired_at=time.time())
    path.parent.mkdir(parents=True, exist_ok=True)
    # Write-then-rename so a reader never sees a half-written record.
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {
                "pid": holder.pid,
                "owner": holder.owner,
                "acquired_at": holder.acquired_at,
            }
        ),
        encoding="utf-8",
    )
    tmp.replace(path)
    return holder


def _stale_reason(holder: _Holder, max_age_s: float) -> str | None:
    """Why this holder may be displaced, or None when it must be respected."""
    if not _pid_alive(holder.pid):
        return f"holder pid {holder.pid} is not alive -- the lane was abandoned"
    if holder.age_s > max_age_s:
        return (
            f"holder pid {holder.pid} has held the lane for {holder.age_s:.0f}s, "
            f"past the {max_age_s:.0f}s bound -- treated as hung"
        )
    return None


def _acquire(
    repo: Path,
    lane: str,
    owner: str,
    wait_s: float,
    max_age_s: float,
    holder_pid: int,
) -> int:
    path = _lane_path(repo, lane)
    deadline = time.time() + wait_s
    announced_wait = False

    while True:
        holder = _read_holder(path)
        if holder is None:
            got = _write_holder(path, owner, holder_pid)
            _emit(
                {
                    "event": "BoxLaneAcquired",
                    "lane": lane,
                    "owner": got.owner,
                    "pid": got.pid,
                    "why": "the lane was free",
                }
            )
            return 0

        stale = _stale_reason(holder, max_age_s)
        if stale is not None:
            got = _write_holder(path, owner, holder_pid)
            _emit(
                {
                    "event": "BoxLaneStolen",
                    "lane": lane,
                    "owner": got.owner,
                    "pid": got.pid,
                    "displaced_pid": holder.pid,
                    "displaced_owner": holder.owner,
                    "why": stale,
                    "how": (
                        "nothing to do -- the lane is yours. This is the "
                        "anti-deadlock path: a crashed or hung lane holder can "
                        "never wedge the box."
                    ),
                }
            )
            return 0

        if time.time() >= deadline:
            _emit(
                {
                    "event": "BoxLaneBusy",
                    "lane": lane,
                    "holder_pid": holder.pid,
                    "holder_owner": holder.owner,
                    "held_for_s": round(holder.age_s, 1),
                    "why": (
                        f"'{holder.owner}' (pid {holder.pid}) is running a heavy "
                        "step on this box; a second one would make both slower "
                        "and can produce mutual timeout false-reds"
                    ),
                    "how": (
                        "run a CLOUD lane instead (dispatch an agent -- those "
                        "cost no local CPU and any number may run at once), or "
                        f"wait: `scripts/box_lane.py acquire --lane {lane} "
                        "--owner <you> --wait 600`. Do NOT run the heavy step "
                        "anyway: the contention is the defect, not the wait."
                    ),
                }
            )
            return 1

        if not announced_wait:
            _emit(
                {
                    "event": "BoxLaneWaiting",
                    "lane": lane,
                    "holder_pid": holder.pid,
                    "holder_owner": holder.owner,
                    "why": "waiting for the current heavy step to finish",
                }
            )
            announced_wait = True
        time.sleep(_POLL_INTERVAL_S)


def _release(repo: Path, lane: str) -> int:
    path = _lane_path(repo, lane)
    holder = _read_holder(path)
    if holder is None:
        _emit(
            {
                "event": "BoxLaneAlreadyFree",
                "lane": lane,
                "why": "no holder was recorded -- nothing to release",
            }
        )
        return 0
    # Release is deliberately NOT owner-checked: a lane whose holder died must be
    # releasable by whoever notices. Refusing here would recreate the deadlock
    # this design exists to prevent.
    try:
        path.unlink()
    except OSError as exc:
        _emit(
            {
                "event": "BoxLaneReleaseFailed",
                "lane": lane,
                "why": f"could not remove the lane record: {exc}",
                "how": f"remove {path} by hand; the lane is otherwise unusable",
            }
        )
        return 2
    _emit(
        {
            "event": "BoxLaneReleased",
            "lane": lane,
            "released_owner": holder.owner,
            "held_for_s": round(holder.age_s, 1),
        }
    )
    return 0


def _status(repo: Path, lane: str, max_age_s: float) -> int:
    holder = _read_holder(_lane_path(repo, lane))
    if holder is None:
        _emit({"event": "BoxLaneFree", "lane": lane})
        return 0
    stale = _stale_reason(holder, max_age_s)
    _emit(
        {
            "event": "BoxLaneHeld",
            "lane": lane,
            "holder_pid": holder.pid,
            "holder_owner": holder.owner,
            "held_for_s": round(holder.age_s, 1),
            "stealable": stale is not None,
            "why": stale or "the holder is alive and within its time bound",
        }
    )
    return 0 if stale is not None else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="box_lane.py",
        description=(
            "Serialize the ONE box lane of a swarm. Cloud lanes stay parallel; "
            "heavy local steps take turns."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "SHAPE: N cloud lanes (dispatched agents -- free, run them all at "
            "once) + ONE box lane (heavy local gates -- take turns here).\n"
            "\n"
            "NEVER wrap a committing command with this. Acquire, run, release "
            "are three\nseparate steps on purpose: a wrapper around a commit "
            "self-deadlocks, because\nthe commit hook runs inside the wrapper "
            "and waits on the lock the wrapper holds.\n"
            "\n"
            "It cannot wedge your box: a dead holder is stolen from, loudly, and "
            "so is a\nlive one that has held past --max-age."
        ),
    )
    parser.add_argument(
        "verb", choices=("acquire", "release", "status"), help="What to do."
    )
    parser.add_argument("--repo", default=".", help="Repository root (default: cwd).")
    parser.add_argument(
        "--lane",
        default="heavy",
        help="Lane name -- one queue per name (default: heavy).",
    )
    parser.add_argument(
        "--owner",
        default="",
        help="Who is taking the lane, in words. Shown to whoever is blocked.",
    )
    parser.add_argument(
        "--holder-pid",
        type=int,
        default=0,
        help=(
            "PID of the LONG-LIVED process that will do the heavy work -- the "
            "shell or session that runs the gate, NOT this short-lived CLI. "
            "Defaults to the parent process (the invoking shell), which is "
            "almost always what you want. Getting this wrong is not cosmetic: "
            "recording this CLI's own pid makes the lock useless, because the "
            "CLI exits immediately and the next acquire sees a dead holder and "
            "steals the lane (caught by dogfooding this script, 2026-07-18)."
        ),
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="Seconds to wait for a busy lane before giving up (default: 0).",
    )
    parser.add_argument(
        "--max-age",
        type=float,
        default=_DEFAULT_MAX_AGE_S,
        help=(
            "Seconds after which a still-live holder is treated as hung and "
            f"displaced (default: {_DEFAULT_MAX_AGE_S:.0f})."
        ),
    )
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    if not repo.is_dir():
        _emit(
            {
                "event": "MalformedInput",
                "why": f"--repo {args.repo!r} is not a directory",
                "how": "pass the repository root, or omit --repo to use the cwd",
            }
        )
        return 2

    if args.verb == "acquire":
        owner = args.owner or f"pid-{os.getpid()}"
        holder_pid = args.holder_pid if args.holder_pid > 0 else os.getppid()
        return _acquire(repo, args.lane, owner, args.wait, args.max_age, holder_pid)
    if args.verb == "release":
        return _release(repo, args.lane)
    return _status(repo, args.lane, args.max_age)


if __name__ == "__main__":
    sys.exit(main())
