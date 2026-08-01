"""Host capacity snapshot -- nproc, load, MemAvailable, real pytest suites.

lane/sentinel-tool. Ported from the scratchpad prototype's `real_pytest()` +
memory-reading logic, split into a pure classifier (`count_real_pytest`,
testable without touching `/proc`) and a thin `/proc`-reading collector
(`read_capacity_snapshot`).

WHY `MemAvailable`, NEVER THE `free` COMMAND'S "available" COLUMN: `free`
under-reports by roughly 5x on this class of box (measured, per
`nw-throughput` SKILL.md and the standing project memory) -- `/proc/meminfo`
is the kernel's own figure and is read directly here, no shell-out.

WHY THE PYTEST COUNT EXCLUDES `earlyoom` / `bash` / `sh`: a naive `pytest\\b`
regex match over every process's cmdline has fooled a Sentinel pass three
times on this box -- `earlyoom`'s own argv can contain the substring, and a
`bash -c "... pytest ..."` wrapper process matches the regex on `comm=bash`
while the GENUINE pytest process is a separate child. Filtering by `comm`
(the kernel-reported process name, immune to argv spoofing) before the
regex is what makes the count trustworthy.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from des.ports.driven_ports.committed_scope_port import Indeterminate


__all__ = [
    "CapacitySnapshot",
    "ProcInfo",
    "count_real_pytest",
    "read_capacity_snapshot",
]


#: A wrapper `comm` known to produce a false positive on a naive pytest-cmdline
#: match (measured 2026-07-30: fooled a Sentinel pass three times on this box).
_EXCLUDED_COMM = frozenset({"earlyoom", "bash", "sh"})

_PYTEST_CMDLINE_RE = re.compile(r"(^|/)pytest\b|-m pytest\b")


class ProcInfo(NamedTuple):
    """One process's identity, as read from `/proc/<pid>/{comm,cmdline}`."""

    pid: int
    comm: str
    cmdline: str


def count_real_pytest(procs: list[ProcInfo]) -> int:
    """Count GENUINE pytest suites among `procs` -- excludes `earlyoom` and
    shell wrappers by `comm` (kernel-reported, not argv-spoofable) before
    matching the cmdline regex. Pure: no `/proc` access here."""
    return sum(
        1
        for p in procs
        if p.comm not in _EXCLUDED_COMM and _PYTEST_CMDLINE_RE.search(p.cmdline)
    )


@dataclass(frozen=True)
class CapacitySnapshot:
    """The host-capacity facts a scheduling decision needs. Any field the
    collector could not read is `Indeterminate`, never a fabricated zero
    (GDP-6) -- a caller must not read a failed read as "no load"."""

    nproc: int | Indeterminate
    load_avg: tuple[float, float, float] | Indeterminate
    mem_available_kb: int | Indeterminate
    real_pytest_count: int | Indeterminate


def _read_procs() -> list[ProcInfo]:
    procs: list[ProcInfo] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            cmdline = (
                (entry / "cmdline")
                .read_bytes()
                .replace(b"\0", b" ")
                .decode(errors="replace")
                .strip()
            )
            comm = (entry / "comm").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        procs.append(ProcInfo(pid=int(entry.name), comm=comm, cmdline=cmdline))
    return procs


def _read_nproc() -> int | Indeterminate:
    count = os.cpu_count()
    return count if count is not None else Indeterminate("os.cpu_count() returned None")


def _read_load_avg() -> tuple[float, float, float] | Indeterminate:
    try:
        parts = Path("/proc/loadavg").read_text(encoding="utf-8").split()
        return float(parts[0]), float(parts[1]), float(parts[2])
    except (OSError, IndexError, ValueError) as exc:
        return Indeterminate(f"could not read /proc/loadavg: {exc}")


def _read_mem_available_kb() -> int | Indeterminate:
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemAvailable:"):
                # "MemAvailable:   12345678 kB"
                return int(line.split(":", 1)[1].strip().split()[0])
        return Indeterminate("/proc/meminfo has no MemAvailable line")
    except (OSError, ValueError) as exc:
        return Indeterminate(f"could not read /proc/meminfo: {exc}")


def read_capacity_snapshot() -> CapacitySnapshot:
    """Collect the live host capacity snapshot. Each field degrades to its
    own `Indeterminate` independently -- one unreadable file never hides
    the others."""
    try:
        procs = _read_procs()
        pytest_count: int | Indeterminate = count_real_pytest(procs)
    except OSError as exc:
        pytest_count = Indeterminate(f"could not enumerate /proc: {exc}")

    return CapacitySnapshot(
        nproc=_read_nproc(),
        load_avg=_read_load_avg(),
        mem_available_kb=_read_mem_available_kb(),
        real_pytest_count=pytest_count,
    )
