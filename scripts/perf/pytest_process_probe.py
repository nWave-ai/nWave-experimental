"""One matcher for "is this a pytest run", shared by the box probe and the census.

Three lanes independently built a pytest matcher today and all three got it wrong
in a different place. This reconciles them into a single predicate, so the next
person tightening it cannot fix one caller and silently break the other.

## What each lane missed

* `pgrep -c pytest` counted zero on a box at load 9, because the processes are named
  `python`. It answered a question nobody asked and answered it permissively.
* `pgrep -f pytest` counts `earlyoom`, whose *arguments* contain the word inside a
  regex. Naming a thing is not being it.
* The `python -m pytest` argv pattern — adopted by three lanes, this module's own
  census included — misses the **console-script** form, where the executable is
  literally named `pytest`. The two patterns are blind in complementary ways, which
  is why each lane's testing confirmed its own.

The census's current substring match happens to cover both forms, but by accident:
it matches because the string appears, not because the console-script shape was
considered. Accidental coverage is the dangerous kind — it disappears the moment
someone narrows the pattern to cut false positives, and their tests still pass.

## What this counts, and what the number does NOT mean

`uv run <cmd>` does not `exec`: it stays alive as the parent with the full command
in its own argv. So one logical pytest run shows up as TWO matching processes.

**The result is a PREDICATE, never a cardinality.** "Is anything running" is sound;
"how many runs are there" is not, and no amount of care in this module makes it so.
`PytestPresence.count` therefore does not exist -- the field is `matches`, and its
docstring says what it is -- for the same reason the census marks its `Popen` rows
`untimed` instead of letting a plausible-looking number be quoted.

## Adoption by the census (the integration step, stated rather than half-done)

`nested_spawn_census._classify` still matches substrings against a JOINED argv
string, so it cannot use `argv_runs_pytest`, which needs the tokens. Adopting it is
two changes, and they belong to whoever does the branch integration -- doing half of
it here would leave the census with a predicate that silently disagrees with the
probe's:

1. record the spawn argv as a LIST beside the display string (`_record` already
   receives the raw command; only the joining is lossy);
2. replace the marker-substring test with `argv_runs_pytest(argv_list)`, keeping the
   `interpreter_probe` class -- that one is orthogonal and stays, since a probe is
   excluded for what it DOES, not for how it is named.

Until then the census keeps its own matcher. That is a known, bounded divergence,
written down here so it is a decision rather than a discovery.

## Refusal over a comfortable zero

If `/proc` cannot be read, this raises. It does not return zero. A probe whose
failure mode is "the box looks idle" fails in the permissive direction, which is
exactly how a contended box gets measured as a quiet one -- the defect that cost
this team a full day of numbers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


# Excluded by the basename of the EXECUTABLE, never by scanning the command line.
# A shell invoked as `sh -c "python -m pytest ..."` carries the command verbatim in
# its own argv, so it is byte-for-byte indistinguishable from the real thing by
# content. The executable name is the only honest discriminator.
_SHELL_NAMES = frozenset({"sh", "bash", "dash", "zsh", "fish", "ksh", "csh", "tcsh"})

_PYTEST_NAMES = frozenset({"pytest", "py.test"})


class ProcTableUnreadable(RuntimeError):
    """`/proc` could not be read, so presence is UNKNOWN -- never 'idle'."""


@dataclass(frozen=True)
class PytestPresence:
    """The probe's verdict.

    `matches` is the number of PROCESSES that match, which is not the number of
    pytest RUNS: `uv run` contributes a second match for the same run. Treat it as
    a predicate via `any_running`; quote the raw figure only as "matching
    processes", never as "runs in flight".
    """

    matches: int
    argvs: tuple[tuple[str, ...], ...]

    @property
    def any_running(self) -> bool:
        return self.matches > 0


def argv_runs_pytest(argv: list[str] | tuple[str, ...]) -> bool:
    """True when this argv is a process that RUNS pytest.

    Accepts BOTH forms, which is the whole point:

    * console-script -- ``/path/to/pytest tests/`` (basename of argv[0])
    * module -- ``python -m pytest tests/`` (a ``-m`` whose NEXT token is pytest)

    The `-m` scan walks ``argv[:-1]``: a trailing ``-m`` has no following token, and
    reading ``argv[i + 1]`` there is an IndexError on a real command line
    (``python -m``, malformed but spawnable).

    Matching ``-m`` against the next token EXACTLY, rather than as a prefix, keeps
    ``-m pytest_asyncio`` or ``-m pytest-cov`` from counting: those are other
    modules whose names merely start the same way.
    """
    if not argv:
        return False

    executable = os.path.basename(argv[0])
    if executable in _SHELL_NAMES:
        return False
    if executable in _PYTEST_NAMES:
        return True

    for index, token in enumerate(argv[:-1]):
        if token == "-m" and argv[index + 1] in _PYTEST_NAMES:
            return True
    return False


def _read_argv(pid_dir: Path) -> tuple[str, ...] | None:
    """One process's argv, or None when it exited between listdir and read.

    A vanished process is normal and is NOT a read failure: `/proc` is a live view,
    and treating a race as an error would make the probe refuse at random. An
    unreadable `/proc` itself is a different matter and is raised by the caller.
    """
    try:
        raw = (pid_dir / "cmdline").read_bytes()
    except (FileNotFoundError, ProcessLookupError, PermissionError):
        return None
    except OSError:
        return None
    return tuple(part for part in raw.decode("utf-8", "replace").split("\0") if part)


def running_pytest_processes(proc_root: Path | None = None) -> PytestPresence:
    """Scan the process table for pytest runs.

    Raises `ProcTableUnreadable` when `/proc` itself cannot be listed, rather than
    reporting an idle box it never observed.
    """
    root = proc_root or Path("/proc")
    try:
        entries = sorted(root.iterdir())
    except OSError as exc:
        raise ProcTableUnreadable(
            f"cannot list {root} ({exc}); pytest presence is UNKNOWN, not zero -- "
            f"do not treat this as an idle box"
        ) from exc

    matched: list[tuple[str, ...]] = []
    for entry in entries:
        if not entry.name.isdigit():
            continue
        argv = _read_argv(entry)
        if argv and argv_runs_pytest(list(argv)):
            matched.append(argv)

    return PytestPresence(matches=len(matched), argvs=tuple(matched))
