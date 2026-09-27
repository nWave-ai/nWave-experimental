"""One local mirror of the subject, shared by every K4 entry point.

Two network clones of the subject inside the campaign's concurrent setup barrier
killed six consecutive runs for memory. Cloning once into a local mirror and
serving both arms from it removes that class -- GDP-0, rather than a memory check
that fires after the damage is done.

## An existing cache is REFRESHED, never merely trusted and never fatal

A cache that does not carry the pin is fetched before it is refused. Without
that, a persistent default-path mirror would strand every later preflight the
first time `SUT_PINNED_REV` moves -- and that revision is documented as
something to bump deliberately -- leaving a human to delete the directory by
hand, which is exactly the manual step this module exists to remove. Found in
review 2026-09-14, before it could be built.

## Absence is a stated choice, never an inference

A caller that cannot or will not use a mirror says so, and the source actually
used is reported. A run must never fall back to the network silently, because
the network clone is where the memory failure came from.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


try:
    from scripts.analysis.k4 import subject as k4_subject
except ImportError:  # invoked as a script, with this directory on sys.path
    import subject as k4_subject  # type: ignore[no-redef]


class MirrorUnavailable(RuntimeError):
    """The mirror cannot serve the pinned revision, and says why."""


@dataclass(frozen=True)
class MirrorOutcome:
    """What a caller clones from, and what its run should record about it."""

    source: str
    """The `git clone` source: the mirror's path, or the subject's URL."""

    detail: str
    """One line naming the source and how it was reached."""

    is_mirror: bool


def _git(argv: list[str], cwd: Path | None = None, timeout: int = 1800):
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=timeout,
        check=False,
    )


def _carries_pin(cache: Path) -> bool:
    found = _git(
        ["git", "cat-file", "-t", k4_subject.SUT_PINNED_REV], cwd=cache, timeout=120
    )
    return found.stdout.strip() == "commit"


def ensure_mirror(cache: Path) -> MirrorOutcome:
    """A mirror at `cache` carrying the pinned revision, or a loud failure.

    Clones when absent, fetches when present but behind the pin, and refuses
    only when a fetch still does not bring the revision in.
    """
    if not (cache / "HEAD").is_file():
        cache.parent.mkdir(parents=True, exist_ok=True)
        cloned = _git(["git", "clone", "--mirror", k4_subject.SUT_URL, str(cache)])
        if cloned.returncode != 0:
            raise MirrorUnavailable(
                "WHAT: the subject mirror could not be created.\n"
                f"WHY:  `git clone --mirror` exited {cloned.returncode}: "
                f"{(cloned.stderr or cloned.stdout).strip()[-300:]}\n"
                "HOW:  make the subject reachable, or declare no mirror so each\n"
                "      arm clones the subject directly."
            )
        if _carries_pin(cache):
            return MirrorOutcome(
                str(cache), f"mirror {cache} (cloned, pin present)", True
            )
        raise MirrorUnavailable(
            f"WHAT: a freshly cloned mirror at {cache} does not carry the pinned\n"
            f"      revision {k4_subject.SUT_PINNED_REV}.\n"
            "WHY:  the clone succeeded, so this is the pin naming a revision the\n"
            "      subject does not have -- not a transport failure.\n"
            "HOW:  check SUT_PINNED_REV against the subject's own history.\n"
        )

    if _carries_pin(cache):
        return MirrorOutcome(str(cache), f"mirror {cache} (reused, pin present)", True)

    fetched = _git(["git", "fetch", "--prune", "origin", "+refs/*:refs/*"], cwd=cache)
    if _carries_pin(cache):
        return MirrorOutcome(str(cache), f"mirror {cache} (fetched, pin present)", True)

    raise MirrorUnavailable(
        f"WHAT: the mirror at {cache} does not carry the pinned revision\n"
        f"      {k4_subject.SUT_PINNED_REV}, and a fetch did not bring it in.\n"
        f"WHY:  `git fetch` exited {fetched.returncode}: "
        f"{(fetched.stderr or fetched.stdout).strip()[-200:]}\n"
        "HOW:  check the pin names a revision the subject actually carries, or\n"
        f"      remove {cache} so the mirror is rebuilt from scratch."
    )


def resolve_subject_source(cache: Path | None) -> MirrorOutcome:
    """The clone source for BOTH arms: the mirror, or a declared direct clone.

    Passing `None` is the explicit opt-out. It is reported like any other
    choice, so a reader of the run's record can tell which source it used
    rather than inferring it from a path that happens not to exist.
    """
    if cache is None:
        return MirrorOutcome(
            k4_subject.SUT_URL, "direct network clone (mirror declined)", False
        )
    return ensure_mirror(cache)
