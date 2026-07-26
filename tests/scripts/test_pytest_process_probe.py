"""Pins for the shared pytest matcher, one per way a lane got it wrong today.

Every case below is a real shape observed on this box, not an invented one. The
console-script case is the load-bearing one: the matcher currently covers it by
accident (the substring appears), and this test is what makes the coverage
deliberate -- so narrowing the pattern to cut false positives fails here instead of
quietly losing a whole form.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from perf.pytest_process_probe import (
    ProcTableUnreadable,
    argv_runs_pytest,
    running_pytest_processes,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "argv",
    [
        # console-script: the executable is literally named pytest. The form the
        # `python -m pytest` pattern misses, and the reason this file exists.
        ["/repo/.venv/bin/pytest", "tests/", "-q"],
        ["pytest", "tests/des"],
        ["/usr/bin/py.test", "tests/"],
        # module form
        ["/repo/.venv/bin/python3", "-m", "pytest", "tests/", "-q"],
        ["python", "-m", "pytest"],
        # the worker this repo's gate spawns, module form with flags in between
        ["/repo/.venv/bin/python3", "-X", "faulthandler", "-m", "pytest", "tests/"],
    ],
)
def test_a_process_that_runs_pytest_matches(argv: list[str]) -> None:
    assert argv_runs_pytest(argv) is True


@pytest.mark.parametrize(
    "argv",
    [
        # earlyoom carries the word inside a regex argument. Naming is not being.
        ["/usr/bin/earlyoom", "--avoid", "^(pytest|python)$"],
        # a module whose name merely STARTS like pytest
        ["python", "-m", "pytest_asyncio"],
        ["python", "-m", "pytest-cov"],
        # capability probe: imports the module, runs no test
        ["/repo/.venv/bin/python3", "-c", "import pytest"],
        # unrelated
        ["git", "-C", "/repo", "rev-parse", "HEAD"],
        [],
    ],
)
def test_a_process_that_only_names_pytest_does_not_match(argv: list[str]) -> None:
    assert argv_runs_pytest(argv) is False


@pytest.mark.parametrize("shell", ["sh", "bash", "/bin/dash", "/usr/bin/zsh"])
def test_a_shell_carrying_the_command_is_excluded_by_executable_name(
    shell: str,
) -> None:
    """A shell's argv contains the command verbatim -- content cannot tell them apart.

    `sh -c "python -m pytest tests/"` is byte-for-byte the real command as far as any
    content-based matcher can see. Excluding by the EXECUTABLE's basename is the only
    discriminator that works, which is why the exclusion list holds names and not
    patterns.
    """
    assert argv_runs_pytest([shell, "-c", "python -m pytest tests/"]) is False


def test_a_trailing_dash_m_has_no_following_token() -> None:
    """`python -m` is malformed but spawnable; reading argv[i+1] would raise.

    The scan walks argv[:-1] precisely so a real, if broken, command line cannot
    turn the probe into an IndexError at the moment the box is busiest.
    """
    assert argv_runs_pytest(["python", "-m"]) is False


def _write_proc(root: Path, pid: str, argv: list[str]) -> None:
    pid_dir = root / pid
    pid_dir.mkdir()
    (pid_dir / "cmdline").write_bytes(("\0".join(argv) + "\0").encode())


def test_uv_run_makes_one_logical_run_show_up_as_two_processes(tmp_path: Path) -> None:
    """`uv run` does not exec -- it stays as the parent, carrying the same command.

    This is the reason the result is a PREDICATE and never a cardinality. The pin
    exists so nobody later "fixes" the double count into a run count: both processes
    genuinely match, and the honest answer is to stop quoting the figure as runs.
    """
    _write_proc(tmp_path, "100", ["uv", "run", "python", "-m", "pytest", "tests/"])
    _write_proc(tmp_path, "101", ["/repo/.venv/bin/python3", "-m", "pytest", "tests/"])

    presence = running_pytest_processes(proc_root=tmp_path)

    assert presence.any_running is True
    assert presence.matches == 2
    assert not hasattr(presence, "count")


def test_non_numeric_proc_entries_are_skipped(tmp_path: Path) -> None:
    (tmp_path / "self").mkdir()
    (tmp_path / "meminfo").write_text("MemAvailable: 1 kB\n", encoding="utf-8")
    _write_proc(tmp_path, "200", ["/repo/.venv/bin/pytest", "tests/"])

    assert running_pytest_processes(proc_root=tmp_path).matches == 1


def test_a_process_that_exits_mid_scan_is_not_a_read_failure(tmp_path: Path) -> None:
    """`/proc` is a live view; a vanished pid is normal, not an error.

    Treating the race as a failure would make the probe refuse at random, and a probe
    that cries wolf gets ignored -- the same end state as one that lies.
    """
    (tmp_path / "300").mkdir()  # a pid dir with no readable cmdline
    _write_proc(tmp_path, "301", ["/repo/.venv/bin/pytest", "tests/"])

    assert running_pytest_processes(proc_root=tmp_path).matches == 1


def test_an_unreadable_proc_refuses_instead_of_reporting_an_idle_box(
    tmp_path: Path,
) -> None:
    """The failure direction is the whole point.

    A probe that returns zero when it cannot see is permissive exactly when it
    matters: it says "go ahead and measure" to a box it never observed. This is the
    defect that produced a day of numbers taken under contention.
    """
    missing = tmp_path / "no-such-proc"

    with pytest.raises(ProcTableUnreadable) as excinfo:
        running_pytest_processes(proc_root=missing)

    message = str(excinfo.value)
    assert "UNKNOWN" in message
    assert "idle" in message
