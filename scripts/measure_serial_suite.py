"""Serial whole-suite timing run, with its provenance recorded alongside the data.

The point of this script is NOT that it times the suite -- pytest already does.
It is that a duration is only interpretable together with the conditions that
produced it, and a bare number's natural reading is the wrong one. ``.test_durations``
is the standing proof: recorded under contention, inflated by a factor that VARIES
between roughly 2x and 48x, it ranks files in an order that does not survive
re-measurement, and three separate pieces of work were planned off that ranking
before anyone re-ran it.

So every run here writes, next to the per-file durations:

  * load average and MemAvailable at START and at END, plus the count of foreign
    pytest processes -- if the two ends disagree materially, the run was measuring
    the box, not the suite;
  * whether the run was serial (it is, by construction -- xdist is disabled
    explicitly rather than left to a config default);
  * the host, the interpreter, the repo, the commit, and whether the tree was dirty;
  * a NULL CONTROL: a file the change under study cannot touch, timed separately
    before and after the suite. If the null control moves, the box moved. It is the
    only thing in the output that can falsify the run itself.

Start conditions are enforced, not suggested: the run REFUSES to begin above the
load ceiling or with foreign pytest processes alive. A run that begins on a busy
box produces a number that looks exactly like a good one, which is precisely how
the bad data got made the first time.

Usage:
    uv run python scripts/measure_serial_suite.py --out <dir>            # gated
    uv run python scripts/measure_serial_suite.py --out <dir> --force    # skip gate
    uv run python scripts/measure_serial_suite.py --check                # gate only

The raw pytest output goes to a file, never to a pipe that is later ``cat``-ed
whole: it is megabytes, and the parts worth reading are the tail and the summary.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

# Start-condition ceiling. Both must hold: a quiet 1-minute load average AND no
# foreign pytest. Load alone is not enough -- a pytest that just started has not
# yet moved the average.
#
# An ABSOLUTE 1.0, not a per-core fraction, and the distinction matters: a load
# average is a count of runnable tasks, so it is only interpretable against the
# core count. This box has 4 cores, where load 9 is 2.25x oversubscription -- not
# "moderately busy", which is how it reads to anyone who assumes a big machine.
# The bar stays at 1.0 absolute because a SERIAL timing run wants the box to
# itself: one other runnable task is already 25% of this machine competing with
# the thing being measured. Every snapshot therefore records the oversubscription
# ratio alongside the raw load, so a reader on a different box cannot misread it.
MAX_LOAD_1MIN = 1.0
MIN_MEM_AVAILABLE_MIB = 2000

# The null control: a file whose duration nothing we are studying can change.
# It is timed before and after the suite; if it moves, the box moved.
NULL_CONTROL = "tests/release/test_read_toml_field.py"

_RESULT = re.compile(r"NWAVE_TEST_RESULT:(\{.*?\})")

# Wall-clock ceilings, sized to what each spawn actually does. Every spawn here
# also passes `stdin=subprocess.DEVNULL`: POSIX hands fd 0 down transitively, so
# a child that makes no stdin decision can sit forever on a descriptor that
# delivers data and never reaches EOF -- the confirmed root cause of the
# `des refactor --pile` deadlock. A measurement harness is the worst place for
# that failure: a hang produces no datum while looking like a slow run.
_GIT_TIMEOUT_SECONDS = 60
_PROBE_TIMEOUT_SECONDS = 120
_NULL_CONTROL_TIMEOUT_SECONDS = 900
_SUITE_TIMEOUT_SECONDS = 5400


# --------------------------------------------------------------------------
# provenance
# --------------------------------------------------------------------------


def _load_averages() -> tuple[float, float, float]:
    return os.getloadavg()


def _mem_available_mib() -> int:
    for line in Path("/proc/meminfo").read_text().splitlines():
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return -1


_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "fish", "ksh"})


def _cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except (OSError, ValueError):
        return []
    return [a for a in raw.decode("utf-8", "replace").split("\0") if a]


def _ppid(pid: int) -> int:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except (OSError, ValueError):
        return 0
    # The comm field may contain spaces/parens; everything after the LAST ')'
    # is positional, and PPid is the 2nd field there.
    tail = stat.rsplit(")", 1)[-1].split()
    return int(tail[1]) if len(tail) > 1 else 0


def _is_pytest_invocation(argv: list[str]) -> bool:
    """True only for a process that IS pytest, never one that merely names it.

    Three traps this rules out, each of which produced a wrong answer today:
      * ``pgrep -c pytest`` matches the process NAME, which for ``python -m pytest``
        is "python" -- it returns 0 with a real run alive (a FALSE NEGATIVE, the
        dangerous direction for a gate that is supposed to refuse);
      * ``pgrep -f pytest`` matches any command LINE containing the word, which
        includes earlyoom (its --avoid/--prefer regexes mention pytest) and every
        shell wrapper carrying the command string -- FALSE POSITIVES that would
        make the gate refuse forever on this box;
      * a shell whose argv contains the full command it is about to run looks
        identical to the command itself, so shells are excluded explicitly.
    """
    if not argv:
        return False
    exe = os.path.basename(argv[0])
    if exe in _SHELLS:
        return False  # a wrapper QUOTING the command, not the command
    if exe == "pytest":
        return True
    # `python -m pytest ...` -- the module must be the -m argument itself.
    for i, arg in enumerate(argv[:-1]):
        if arg == "-m" and argv[i + 1] == "pytest":
            return True
    return False


def _own_process_tree() -> set[int]:
    """This process and its DESCENDANTS -- deliberately NOT its ancestors.

    Walking up to pid 1 and taking that whole subtree looks like the careful
    choice and is the wrong one: every agent lane on this box hangs off the same
    session root, so "the tree containing my ancestors" is *everyone's* work, and
    a sibling lane's pytest gets classified as mine. Measured: with a real pytest
    alive the ancestor-walking version returned 0 foreign processes -- a false
    negative in the exact direction that lets a contended run start.

    Only this process' own children need excluding, because only they are spawned
    BY the measurement. Ancestors are shells, never pytest, so they are harmless.
    """
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if entry.name.isdigit():
            children.setdefault(_ppid(int(entry.name)), []).append(int(entry.name))
    mine = {os.getpid()}
    stack = [os.getpid()]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in mine:
                mine.add(child)
                stack.append(child)
    return mine


def _foreign_pytest_count() -> int:
    """Count real pytest PROCESSES that are not ours -- processes, NOT runs.

    The distinction is load-bearing and measured: ``uv`` does NOT ``exec``, it stays
    as the parent with the full command in its own argv while the venv python runs
    underneath. So one logical ``uv run python -m pytest ...`` presents as TWO
    matches -- the ``uv`` parent (argv[0] is "uv", but its argv contains ``-m
    pytest``) and the real child. On this repo ``uv run`` is the habitual form, so
    the count reads roughly double the number of concurrent suites.

    For a START GATE that is exactly right and deliberately kept: overstating
    occupancy is the safe direction, and ">= 1 means busy" stays correct. It is NOT
    a concurrency metric -- anyone reusing this number as "how many suites are
    running" is wrong by a factor of two here, which is why every message that
    prints it says "process(es)" and never "run(s)".

    Pure Python over ``/proc`` -- no ``pgrep``, no external CLI (the target-machine
    agnosticism rule). Where ``/proc`` is absent the count degrades LOUD to -1,
    which the gate treats as a refusal: an unknown answer must never read as zero.
    """
    if not Path("/proc").is_dir():
        return -1
    ours = _own_process_tree()
    count = 0
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid in ours:
            continue
        if _is_pytest_invocation(_cmdline(pid)):
            count += 1
    return count


def _git(*args: str) -> str:
    """Git stdout, trimmed -- for single-value queries (a SHA, a branch name)."""
    return _git_raw(*args).strip()


def _git_raw(*args: str) -> str:
    """Git stdout VERBATIM -- for output whose leading whitespace is significant.

    ``git status --porcelain`` encodes the staged/unstaged state in columns 0-1, so
    an unstaged modification begins with a SPACE (`` M path``). Trimming the whole
    output eats that space on the FIRST line only, shifting exactly one path by one
    character while every following line parses correctly -- which is how the bug
    presented: a single mangled entry in a list that otherwise looked right.
    """
    proc = subprocess.run(
        ["git", *args],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
        timeout=_GIT_TIMEOUT_SECONDS,
    )
    return proc.stdout


def snapshot(label: str) -> dict:
    """The machine's state at one instant, recorded WITH the data it explains."""
    l1, l5, l15 = _load_averages()
    return {
        "label": label,
        "utc": datetime.now(timezone.utc).isoformat(),
        "load_1min": round(l1, 2),
        "load_5min": round(l5, 2),
        "load_15min": round(l15, 2),
        # Load divided by cores: the only form of the number that means the same
        # thing on two different machines. 1.0 = fully committed, >1 = oversubscribed.
        "cpu_count": os.cpu_count(),
        "oversubscription": round(l1 / (os.cpu_count() or 1), 2),
        "mem_available_mib": _mem_available_mib(),
        # processes, NOT runs -- see _foreign_pytest_count (uv does not exec)
        "pytest_processes": _foreign_pytest_count(),
        # WHAT the load is made of, not just how big it is. A reader judging an
        # override needs this: "load 7.3" cannot be argued with, but "load 7.3,
        # composed of the agent sessions themselves plus two foreign C++ builds"
        # can. Reading `rustc` and concluding "external" without checking whose it
        # was already cost this team five hours today.
        "top_cpu": _top_cpu_processes(),
    }


def _top_cpu_processes(limit: int = 6) -> list[dict]:
    """The heaviest processes by CPU, by name, best-effort.

    Degrades to an empty list rather than failing the run: this is context for a
    human reading the record later, never an input to a decision the script makes.
    """
    try:
        proc = subprocess.run(
            ["ps", "-eo", "pcpu,comm", "--sort=-pcpu"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[dict] = []
    for line in proc.stdout.splitlines()[1 : limit + 1]:
        parts = line.split(None, 1)
        if len(parts) == 2:
            rows.append({"pcpu": parts[0], "comm": parts[1].strip()})
    return rows


def provenance() -> dict:
    """Everything needed to decide whether a later reader may trust these numbers."""
    return {
        "host": platform.node(),
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "interpreter": sys.executable,
        "repo": str(REPO),
        "branch": _git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": _git("rev-parse", "HEAD"),
        # WHICH paths are dirty, not merely THAT the tree is -- a bare boolean is
        # permanently true in a measurement worktree (the TypeScript pilot rewrites
        # its tracked package-lock.json on every run, 1557 lines), and a flag that
        # is always set carries no information while looking like it does. Listing
        # the paths keeps the signal: a reader can tell "only the tools plus the
        # known lockfile churn" from "somebody's uncommitted work is in this tree",
        # which are very different answers to "may I trust this run".
        "dirty_paths": sorted(
            line[3:] for line in _git_raw("status", "--porcelain").splitlines() if line
        ),
        "serial": True,
        "parallelism": "xdist disabled explicitly (-p no:xdist)",
        "random_order": "disabled if pytest-randomly present (-p no:randomly)",
    }


# --------------------------------------------------------------------------
# start gate
# --------------------------------------------------------------------------


def check_start_conditions(verbose: bool = True) -> tuple[bool, list[str]]:
    """Refuse to measure a busy box. Returns (ok, reasons_it_is_not_ok)."""
    snap = snapshot("gate")
    problems = []
    if snap["load_1min"] >= MAX_LOAD_1MIN:
        problems.append(
            f"load_1min={snap['load_1min']} >= {MAX_LOAD_1MIN} on "
            f"{snap['cpu_count']} cores = {snap['oversubscription']}x "
            "oversubscription (the box is busy; a run started now measures the "
            "other work, and the result will look exactly like a good one)"
        )
    if snap["pytest_processes"] < 0:
        problems.append(
            "the pytest-process count is UNKNOWN (/proc unavailable) -- an "
            "unanswerable question is refused, never read as zero"
        )
    elif snap["pytest_processes"] > 0:
        problems.append(
            f"{snap['pytest_processes']} foreign pytest PROCESS(es) alive "
            "(a concurrent suite contends for the same cores and disk). NOTE: "
            "processes, NOT runs -- `uv run` does not exec, so one suite shows "
            "as two matches; use this to decide busy/idle, never as concurrency"
        )
    if snap["mem_available_mib"] < MIN_MEM_AVAILABLE_MIB:
        problems.append(
            f"MemAvailable={snap['mem_available_mib']} MiB < {MIN_MEM_AVAILABLE_MIB} "
            "(a test killed by the OOM reaper looks like a failure, not a shortage)"
        )
    if verbose:
        print(json.dumps(snap, indent=2))
        if problems:
            print("\nNOT READY:")
            for p in problems:
                print(f"  - {p}")
        else:
            print("\nREADY: load quiet, no foreign pytest, memory sufficient.")
    return (not problems), problems


# --------------------------------------------------------------------------
# the run
# --------------------------------------------------------------------------


def _pytest_argv(target: str | None, durations_path: Path | None) -> list[str]:
    argv = [
        sys.executable,
        "-m",
        "pytest",
        # Serial BY CONSTRUCTION, never by config default -- but via xdist's own
        # "no workers" switch, NOT by unloading the plugin. `-p no:xdist` also
        # unregisters the `xdist_group` marker, and with strict markers on, every
        # file carrying one fails COLLECTION: measured here as 17 errors and an
        # INTERNALERROR 12.78s in, before a single test ran. `-n 0` keeps the
        # marker registered and still runs everything in this process.
        "-n",
        "0",
        "-p",
        "no:pspec",
        "--durations=0",  # every file's duration, not just the slowest
        "--durations-min=0",
        "-q",
        "--tb=no",
    ]
    # pytest-randomly reorders tests between runs; good for finding order
    # dependence, bad for comparing two timings. Disabled only if present --
    # passing -p no:<absent plugin> is an error, not a no-op.
    if _has_plugin("randomly"):
        argv += ["-p", "no:randomly"]
    # The spawn census rides along, so ONE window answers both questions: where
    # the time goes (durations) and how many nested pytest invocations there are,
    # at what per-invocation floor, from which file (census). The plugin refuses
    # at configure when it cannot write its artifact, so a census that could not
    # deliver stops the run at second zero instead of at minute 45.
    argv += ["-p", "perf.nested_spawn_census"]
    if durations_path is not None:
        argv += ["--store-durations", "--durations-path", str(durations_path)]
    if target:
        argv.append(target)
    return argv


def _has_plugin(name: str) -> bool:
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--version", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=_PROBE_TIMEOUT_SECONDS,
    )
    return name in (proc.stdout + proc.stderr)


def time_null_control(label: str) -> dict:
    """Time the file nothing under study can affect. The run's own falsifier."""
    t0 = time.monotonic()
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            NULL_CONTROL,
            "-q",
            "--tb=no",
            "-p",
            "no:pspec",
            "-p",
            "no:xdist",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=_NULL_CONTROL_TIMEOUT_SECONDS,
    )
    dt = time.monotonic() - t0
    m = _RESULT.search(proc.stdout)
    return {
        "label": label,
        "file": NULL_CONTROL,
        "seconds": round(dt, 2),
        "result": json.loads(m.group(1)) if m else {"parse_error": True},
    }


def run(out_dir: Path, force: bool, force_reason: str = "") -> int:
    ok, _problems = check_start_conditions(verbose=True)
    if not ok and not force:
        print(
            "\nREFUSING to start. Wait for the window, or pass --force and accept "
            "that the numbers carry the box's other work.",
            file=sys.stderr,
        )
        return 2

    out_dir.mkdir(parents=True, exist_ok=True)
    raw_log = out_dir / "pytest-raw.log"
    durations = out_dir / "durations.json"
    report = out_dir / "run.json"

    record: dict = {
        "provenance": provenance(),
        "forced": bool(force),
        "force_reason": force_reason,
        "snapshots": [],
    }
    record["snapshots"].append(snapshot("start"))
    record["null_control_before"] = time_null_control("before")

    argv = _pytest_argv(None, durations)
    record["pytest_argv"] = argv

    # The census plugin lives under scripts/ and writes beside the durations, so
    # the breakdown and the timings share a directory and cannot be paired with
    # the wrong run later. Recorded in the provenance for the same reason.
    census_out = out_dir / "nested-spawn-census.jsonl"
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(REPO / "scripts"), env.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    env["NWAVE_SPAWN_CENSUS"] = str(census_out)
    record["census_path"] = str(census_out)

    print(f"\nrunning serially; raw output -> {raw_log}")
    t0 = time.monotonic()
    with raw_log.open("w") as fh:
        proc = subprocess.run(
            argv,
            cwd=REPO,
            stdout=fh,
            stderr=subprocess.STDOUT,
            env=env,
            stdin=subprocess.DEVNULL,
            timeout=_SUITE_TIMEOUT_SECONDS,
        )
    record["wall_seconds"] = round(time.monotonic() - t0, 2)
    record["exit_code"] = proc.returncode

    record["null_control_after"] = time_null_control("after")
    record["snapshots"].append(snapshot("end"))

    tail = raw_log.read_text(errors="replace")[-20000:]
    m = _RESULT.search(tail)
    record["result"] = json.loads(m.group(1)) if m else {"parse_error": True}

    before = record["null_control_before"]["seconds"]
    after = record["null_control_after"]["seconds"]
    drift = abs(after - before) / before if before else 0.0
    record["null_control_drift"] = round(drift, 3)
    record["null_control_verdict"] = (
        "STABLE"
        if drift < 0.25
        else "MOVED -- the box changed during the run; "
        "treat the per-file ranking as unreliable"
    )

    start, end = record["snapshots"][0], record["snapshots"][1]
    record["load_verdict"] = (
        "QUIET"
        if max(start["load_1min"], end["load_1min"]) < MAX_LOAD_1MIN * 2
        and end["pytest_processes"] <= start["pytest_processes"]
        else "CONTENDED -- foreign work appeared during the run"
    )

    report.write_text(json.dumps(record, indent=2))

    print(f"\nwall            {record['wall_seconds']}s")
    print(f"result          {record['result']}")
    print(f"null control    {before}s -> {after}s  ({record['null_control_verdict']})")
    print(f"load            {record['load_verdict']}")
    print(f"\nper-file durations -> {durations}")
    print(f"provenance + verdicts -> {report}")
    print(
        f"raw log ({raw_log.stat().st_size // 1024} KiB) -> {raw_log}  (read the TAIL)"
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, help="directory for durations + provenance")
    ap.add_argument("--check", action="store_true", help="evaluate the start gate only")
    ap.add_argument("--force", action="store_true", help="run despite a busy box")
    ap.add_argument(
        "--force-reason",
        default="",
        help=(
            "why the gate was overridden, recorded beside forced:true. A reader a "
            "week from now must be able to JUDGE the override, not merely see it."
        ),
    )
    args = ap.parse_args()

    if args.check or not args.out:
        ok, _ = check_start_conditions(verbose=True)
        return 0 if ok else 1
    if shutil.which("git") is None:
        print("note: git absent; provenance will omit branch/commit", file=sys.stderr)
    return run(args.out, args.force, args.force_reason)


if __name__ == "__main__":
    raise SystemExit(main())
