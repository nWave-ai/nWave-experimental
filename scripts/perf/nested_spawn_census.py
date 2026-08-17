"""Count and time every nested pytest invocation a suite run makes.

Read-only census: it observes spawns, it never changes what the suite does. Enable
it explicitly, so a normal run is untouched::

    PYTHONPATH=scripts NWAVE_SPAWN_CENSUS=.nwave/perf/census.jsonl \\
        NWAVE_GATE_JOBS=serial uv run poe test -p perf.nested_spawn_census

Why a count rather than a breakdown: a duration measured on a contended box is a
measure of the load, but a COUNT is not -- it is the same number whoever else is
running. The per-invocation floor times it produces are the part that still needs a
quiet box; the count and the per-file attribution do not.

The arithmetic this exists to settle: at a ~0.91s floor it takes 3008 nested
invocations to account for a 2737s run, at ~1.44s it takes 1901 -- so 12-19 per
file across the 158 files that reach the gate. A result inside that band means the
floor explains the run almost entirely; a result near 200 total means it explains
~10% and the cost is elsewhere. Either way it is one run, not two.

## The witness (why this reports its own blind spots instead of degrading)

An enumeration with no second way of counting the same thing is a possibly-partial
list wearing the costume of a complete one. So this plugin reports, beside the
census, what it could NOT see:

* `spawns_seen` split by the API each was caught through, against
  `spawns_unattributed` -- spawns that happened outside a running test;
* `nested_wall_sum` and `nested_cpu_sum` against the session's own wall clock, so a
  sum that cannot fit inside the run is visible as an inconsistency rather than
  being quietly reported;
* `cpu_attribution_trustworthy: false` whenever xdist is active, because
  `RUSAGE_CHILDREN` deltas are only attributable to one child when children do not
  overlap. It says so; it does not silently emit a wrong number.

Every spawn is recorded with its classification, including the ones classified as
NOT nested-pytest, so nothing is dropped on the floor by a matcher that turns out
to be too narrow.
"""

from __future__ import annotations

import json
import os
import resource
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest


_CENSUS_ENV = "NWAVE_SPAWN_CENSUS"
_DEFAULT_OUT = ".nwave/perf/nested-spawn-census.jsonl"

# Argv markers that identify a child which will itself run pytest. Deliberately
# broad: a false positive is visible in the record (its argv is written out and can
# be re-judged), a false negative is invisible -- and invisible is the failure mode
# this plugin exists to avoid.
_NESTED_MARKERS = (
    "pytest",
    "run-contract-gate",
    "run_contract_gate",
)

# A spawn that MENTIONS pytest is not a spawn that RUNS a suite. The gate probes
# interpreter capability with `python -c "import pytest"` (~0.25s: imports a module
# and exits) and resolves the interpreter with `python -c "import sys; print(...)"`.
# Both carry "pytest" in argv; neither runs a single test.
#
# Counting them would inflate the nested count AND deflate the measured floor --
# biasing, in both directions at once, exactly the two numbers the arithmetic rests
# on. An inline `-c` program is the discriminator: a probe by construction, since
# running a suite needs a module or a script path.
#
# They are still recorded, classified `interpreter_probe`, so the exclusion is
# inspectable rather than a silent subtraction -- the rule the untimed Popen rows
# already follow.
_INLINE_PROGRAM_FLAG = " -c "

_records: list[dict[str, Any]] = []
_counters = {
    "spawns_seen_run": 0,
    "spawns_seen_popen": 0,
    "spawns_seen_check_output": 0,
    "spawns_unattributed": 0,
}
_current_nodeid: str | None = None
_session_start = 0.0
_xdist_active = False


def _argv_text(cmd: Any) -> str:
    if isinstance(cmd, (list, tuple)):
        return " ".join(str(part) for part in cmd)
    return str(cmd)


def _classify(argv: str) -> str:
    """``nested_pytest`` (runs a suite) · ``interpreter_probe`` (only names one)
    · ``other``.

    The middle class is the whole point: `python -c "import pytest"` matches every
    name-based marker while running zero tests. Classified, never dropped.
    """
    if not any(marker in argv for marker in _NESTED_MARKERS):
        return "other"
    if _INLINE_PROGRAM_FLAG in argv:
        return "interpreter_probe"
    return "nested_pytest"


def _child_cpu() -> tuple[float, float]:
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    return usage.ru_utime, usage.ru_stime


def _record(
    argv: str,
    wall: float,
    cpu_user: float,
    cpu_sys: float,
    api: str,
    *,
    timed: bool,
) -> None:
    """Append one spawn. ``timed`` false means the duration fields are NOT the
    child's cost -- see ``_wrap``'s note on ``Popen``."""
    if _current_nodeid is None:
        _counters["spawns_unattributed"] += 1
    _records.append(
        {
            "nodeid": _current_nodeid,
            "test_file": (_current_nodeid or "").split("::")[0] or None,
            "api": api,
            "kind": _classify(argv),
            "nested_pytest": _classify(argv) == "nested_pytest",
            "timed": timed,
            "wall_s": round(wall, 4) if timed else None,
            "cpu_user_s": round(cpu_user, 4) if timed else None,
            "cpu_sys_s": round(cpu_sys, 4) if timed else None,
            "argv": argv[:400],
        }
    )


def _wrap(original: Any, api: str, counter_key: str, *, timed: bool) -> Any:
    """Wrap a spawn API.

    ``timed`` distinguishes the two shapes. ``subprocess.run`` and
    ``check_output`` return only once the child has exited, so the interval
    around them IS the child's cost. ``Popen.__init__`` returns as soon as the
    child is forked, so the interval around it measures the fork and nothing
    else -- those rows are counted, and explicitly NOT timed, rather than
    contributing a near-zero duration that would silently deflate the floor.

    ``Popen.__init__`` also takes ``self`` first, so the command is the SECOND
    positional argument there; reading ``args[0]`` for every API would have
    recorded the Popen object's repr as the argv for exactly the rows the
    nested-pytest matcher then has to classify.
    """
    argv_index = 1 if api == "subprocess.Popen" else 0

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        _counters[counter_key] += 1
        user0, sys0 = _child_cpu()
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            wall = time.perf_counter() - started
            user1, sys1 = _child_cpu()
            if len(args) > argv_index:
                argv = _argv_text(args[argv_index])
            else:
                argv = _argv_text(kwargs.get("args", ""))
            _record(argv, wall, user1 - user0, sys1 - sys0, api, timed=timed)

    return wrapper


class CensusOutputUnusable(RuntimeError):
    """The census cannot write where it was told to -- refuse NOW, not in 45 min."""


def _out_path() -> Path:
    return Path(os.environ.get(_CENSUS_ENV) or _DEFAULT_OUT)


def _verify_output_is_writable(path: Path) -> None:
    """Write and read back a probe record BEFORE the session starts.

    A 45-minute run that ends green having produced no artifact is
    indistinguishable from a successful one: pass/fail is the only vocabulary the
    exit status has, and "ran but produced nothing" has no home in it, so it
    collapses into pass. That collapse is worth one round-trip at second zero.

    Asking the FORMAT whether the artifact is valid -- parsing the probe back with
    the real parser rather than trusting that the write worked -- is the same check,
    applied to the shape rather than to the path.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        probe = {"kind": "preflight", "written_at": time.time()}
        path.write_text(json.dumps(probe) + "\n", encoding="utf-8")
        parsed = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    except (OSError, ValueError, IndexError) as exc:
        raise CensusOutputUnusable(
            f"the census cannot produce its artifact at {path} ({exc}). "
            f"REFUSING before the run rather than finishing green with no "
            f"breakdown -- set {_CENSUS_ENV} to a writable path and re-run."
        ) from exc
    if parsed.get("kind") != "preflight":
        raise CensusOutputUnusable(
            f"the census wrote {path} but read back something else ({parsed!r}); "
            f"refusing rather than trusting the write silently."
        )


def pytest_configure(config: Any) -> None:
    global _session_start, _xdist_active
    try:
        _verify_output_is_writable(_out_path())
    except CensusOutputUnusable as exc:
        # A UsageError prints the message as a clean one-liner. The refusal has to
        # be READ to be acted on, and an INTERNALERROR traceback buries the WHAT/WHY
        # /HOW under a stack that is about pytest's plumbing, not the operator's fix.
        raise pytest.UsageError(f"[spawn-census] {exc}") from exc
    _session_start = time.perf_counter()
    _xdist_active = bool(getattr(config.option, "numprocesses", None))

    subprocess.run = _wrap(
        subprocess.run, "subprocess.run", "spawns_seen_run", timed=True
    )
    subprocess.check_output = _wrap(
        subprocess.check_output,
        "subprocess.check_output",
        "spawns_seen_check_output",
        timed=True,
    )
    subprocess.Popen.__init__ = _wrap(  # type: ignore[method-assign]
        subprocess.Popen.__init__, "subprocess.Popen", "spawns_seen_popen", timed=False
    )


def pytest_runtest_logstart(nodeid: str, location: Any) -> None:
    global _current_nodeid
    _current_nodeid = nodeid


def pytest_runtest_logfinish(nodeid: str, location: Any) -> None:
    global _current_nodeid
    _current_nodeid = None


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:
    session_wall = time.perf_counter() - _session_start
    nested_all = [record for record in _records if record["nested_pytest"]]
    # Only the timed rows may be summed. `subprocess.run` is itself implemented on
    # `Popen`, so every run ALSO produces a Popen row -- summing both would double
    # count. The Popen rows are kept (a direct Popen use would otherwise vanish)
    # but reported as their own witness, never folded into the totals.
    nested = [record for record in nested_all if record["timed"]]
    nested_untimed = len(nested_all) - len(nested)
    nested_walls = [record["wall_s"] for record in nested]
    nested_wall = sum(nested_walls)
    nested_cpu = sum(record["cpu_user_s"] + record["cpu_sys_s"] for record in nested)

    per_file: dict[str, dict[str, float]] = {}
    for record in nested:
        key = record["test_file"] or "<no running test>"
        bucket = per_file.setdefault(key, {"count": 0, "wall_s": 0.0})
        bucket["count"] += 1
        bucket["wall_s"] = round(bucket["wall_s"] + record["wall_s"], 3)

    summary = {
        "kind": "summary",
        "session_wall_s": round(session_wall, 2),
        "spawns_total": len(_records),
        "nested_pytest_spawns": len(nested),
        "nested_pytest_spawns_untimed_popen": nested_untimed,
        # Excluded from the count above because they only NAME pytest. Shown so the
        # exclusion can be audited: if this number is large, re-read the argv rows
        # before trusting either the count or the floor.
        "interpreter_probes_excluded": sum(
            1 for record in _records if record["kind"] == "interpreter_probe"
        ),
        "interpreter_probe_wall_sum_s": round(
            sum(
                record["wall_s"] or 0.0
                for record in _records
                if record["kind"] == "interpreter_probe" and record["timed"]
            ),
            2,
        ),
        "nested_wall_sum_s": round(nested_wall, 2),
        "nested_cpu_sum_s": round(nested_cpu, 2),
        "nested_share_of_session_wall": (
            round(nested_wall / session_wall, 4) if session_wall > 0 else None
        ),
        # The DISTRIBUTION, not a single "floor". Measured on one file while
        # wiring this up: 18 nested spawns, 91.24s total -- but one of them was a
        # whole nested acceptance suite at ~89s, so the mean was 5.07s while the
        # typical spawn cost a fraction of a second.
        #
        # A mean over a distribution with one dominant outlier is not a floor, and
        # calling it one feeds the "invocations x floor accounts for the run"
        # arithmetic a number that already contains the thing the arithmetic is
        # trying to find. The MEDIAN is the per-invocation floor; the MEAN times
        # the count is just the sum, which is reported separately and honestly.
        "nested_wall_median_s": (
            round(statistics.median(nested_walls), 4) if nested_walls else None
        ),
        "nested_wall_mean_s": (
            round(statistics.fmean(nested_walls), 4) if nested_walls else None
        ),
        "nested_wall_min_s": round(min(nested_walls), 4) if nested_walls else None,
        "nested_wall_max_s": round(max(nested_walls), 4) if nested_walls else None,
        "counters": dict(_counters),
        # The witness fields: what this census could not see, stated rather than
        # rounded away. `sum_fits_in_session` false means the accounting is
        # inconsistent and the numbers above must NOT be quoted.
        "cpu_attribution_trustworthy": not _xdist_active,
        "cpu_attribution_note": (
            "xdist active: RUSAGE_CHILDREN deltas overlap across concurrent "
            "children and are NOT attributable per spawn"
            if _xdist_active
            else "serial run: each delta belongs to exactly one child"
        ),
        "sum_fits_in_session": nested_wall <= session_wall * 1.02,
        "per_file": per_file,
    }

    out_path = _out_path()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as handle:
        for record in _records:
            handle.write(json.dumps(record) + "\n")
        handle.write(json.dumps(summary) + "\n")

    # Read the artifact back with the real parser and confirm the summary is there.
    # The write above can succeed and still leave nothing usable -- a full disk
    # truncating the last line, a record that serialised to something unparseable.
    # Without this the session ends green and the breakdown is simply missing, which
    # on a run nobody can repeat is the failure that matters.
    artifact_ok = False
    try:
        last = out_path.read_text(encoding="utf-8").splitlines()[-1]
        artifact_ok = json.loads(last).get("kind") == "summary"
    except (OSError, ValueError, IndexError):
        artifact_ok = False
    if not artifact_ok:
        session.exitstatus = 1

    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_line("")
        reporter.write_line(
            f"[spawn-census] {summary['nested_pytest_spawns']} nested-pytest spawns "
            f"of {summary['spawns_total']} total; "
            f"{summary['nested_wall_sum_s']}s wall "
            f"({summary['nested_share_of_session_wall']} of the session); "
            f"per-spawn median {summary['nested_wall_median_s']}s "
            f"mean {summary['nested_wall_mean_s']}s "
            f"max {summary['nested_wall_max_s']}s"
        )
        if not summary["sum_fits_in_session"]:
            reporter.write_line(
                "[spawn-census] INCONSISTENT: nested wall exceeds session wall -- "
                "do not quote these numbers"
            )
        if not summary["cpu_attribution_trustworthy"]:
            reporter.write_line(
                f"[spawn-census] CPU NOT attributable: "
                f"{summary['cpu_attribution_note']}"
            )
        if not artifact_ok:
            reporter.write_line(
                f"[spawn-census] FAILED the run: the artifact at {out_path} has no "
                f"readable summary record. The suite result is NOT the question -- "
                f"a run that produces no breakdown has not done its job."
            )
        reporter.write_line(f"[spawn-census] written to {out_path}")
