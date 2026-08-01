"""Unit tests for `count_real_pytest` -- excludes earlyoom/bash/sh wrapper
processes that fooled a Sentinel pass three times on this box
(lane/sentinel-tool)."""

from __future__ import annotations

from des.application.capacity_snapshot import ProcInfo, count_real_pytest


def test_genuine_pytest_process_is_counted() -> None:
    procs = [ProcInfo(pid=1, comm="python3", cmdline="python3 -m pytest tests/")]

    assert count_real_pytest(procs) == 1


def test_earlyoom_is_excluded_even_if_its_argv_contains_pytest_substring() -> None:
    procs = [
        ProcInfo(
            pid=2,
            comm="earlyoom",
            cmdline="earlyoom -m 10 -s 5 --avoid '(pytest|mutmut)'",
        )
    ]

    assert count_real_pytest(procs) == 0


def test_bash_wrapper_running_pytest_is_excluded_by_comm() -> None:
    """The genuine pytest process is a CHILD of the bash wrapper -- the
    wrapper process itself (comm=bash) must not be double-counted or
    mistaken for the real suite."""
    procs = [
        ProcInfo(pid=3, comm="bash", cmdline='bash -c "cd wt && pytest tests/"'),
    ]

    assert count_real_pytest(procs) == 0


def test_sh_wrapper_running_pytest_is_excluded_by_comm() -> None:
    procs = [ProcInfo(pid=4, comm="sh", cmdline="sh -c pytest")]

    assert count_real_pytest(procs) == 0


def test_mixed_population_counts_only_the_genuine_suites() -> None:
    procs = [
        ProcInfo(pid=1, comm="python3", cmdline="python3 -m pytest tests/des/unit"),
        ProcInfo(pid=2, comm="earlyoom", cmdline="earlyoom --avoid pytest"),
        ProcInfo(pid=3, comm="bash", cmdline="bash -c pytest"),
        ProcInfo(pid=4, comm="pytest", cmdline="pytest tests/des/acceptance"),
        ProcInfo(pid=5, comm="node", cmdline="node server.js"),
    ]

    assert count_real_pytest(procs) == 2


def test_unrelated_process_is_not_counted() -> None:
    procs = [ProcInfo(pid=5, comm="node", cmdline="node server.js")]

    assert count_real_pytest(procs) == 0


def test_empty_population_counts_zero() -> None:
    assert count_real_pytest([]) == 0
