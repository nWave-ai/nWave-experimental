"""The one TOTAL git seam: every observation answers, none raises.

WHY THIS MODULE EXISTS.  ``des.application.delivery_continuation`` reached git
through two private helpers that called ``spawn(["git", ...], text=True)``
directly.  Both were typed as total and were not
(``docs/analysis/2026-09-05-runner-totality-audit-os-git-fs-seams.md``, rows G1,
G2, G3, G5).  Two inputs from the WORLD, neither expressible in the helpers'
signatures, escaped as a bare traceback across 21 call sites:

1. **git is not on ``PATH``** -- ``FileNotFoundError`` out of ``execve``.
   Measured 2026-09-05: ``PATH=/nonexistent-bin`` with ``GIT_EXEC_PATH`` unset
   raised ``FileNotFoundError: [Errno 2] ... 'git'`` from ``_git`` AND from
   ``_git_bytes``.
2. **git's output is not UTF-8** -- ``text=True`` DECODES, and the decoder has
   no fallback.  Measured on the same run: one tracked path holding byte
   ``0xff`` made ``git status --porcelain -z -uall`` raise
   ``UnicodeDecodeError`` at position 21.  A path is bytes on POSIX; the
   runner's own ``_git_bytes`` docstring already says so.

WHERE THE TOTALITY SITS.  In this seam, once -- never as 21 scattered
``try/except`` blocks.  The two non-answers are CONSTRUCTED into the same shape
every caller already consumes: a non-zero ``returncode`` plus a ``stderr`` that
explains itself (GDP-3), and, for a caller that wants to tell "git refused" from
"git never answered" apart, a typed ``unanswered`` discriminant (GDP-8: decide on
the PROPERTY, not the designation).  ``__post_init__`` makes the wrong state --
a non-answer wearing a success returncode -- unrepresentable (GDP-0), so a future
constructor cannot reintroduce a silent pass.

THE BOUND (audit G2).  Every observation carries the GIT tier
(``git_timeout_seconds``, 30 s, ``NWAVE_GIT_TIMEOUT``) instead of inheriting
``spawn``'s RUN default of 45 minutes -- a factor of 90.  MEASURED on this repo
2026-09-05, so the tier is not a guess: ``status --porcelain -z -uall`` 0.452 s,
``rev-parse HEAD`` 0.003 s, ``ls-tree -r`` 0.009 s, ``write-tree`` 0.004 s,
``diff --name-only -z`` over 200 commits 0.036 s, and the widest command the
runner issues, ``diff --binary`` over those same 200 commits (5.1 MB of output),
**0.210 s** -- a 140x margin under the tier.  No command needs an exception, so
none is granted.

THE CHILD ENVIRONMENT (audit G5, silent-wrong).  A caller that passes ``env=``
has DECIDED, and is forwarded untouched (the thin-passthrough rule
``des.runtime.spawn`` states for itself).  A caller that passes nothing used to
inherit ``os.environ`` whole, so a ``GIT_INDEX_FILE`` or ``GIT_DIR`` belonging
to the PARENT silently redirected the child at every one of those sites.  Here
the repository-selecting variables are REMOVED instead: the ``-C <root>``
argument becomes the only thing that says which repository is observed.

Deliberately NOT removed: ``GIT_AUTHOR_*`` / ``GIT_COMMITTER_*`` and the config
variables.  Identity is the operator's to set, and the only site that writes a
commit object supplies its own ``env`` and so never reaches this branch at all
-- stripping identity here would change nothing that is measured and would
misstate which defect this closes.
"""

from __future__ import annotations

import errno
import os
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.runtime.spawn import (
    GIT_TIMEOUT_ENV,
    SpawnRefusal,
    classify_spawn_refusal,
    git_timeout_seconds,
    spawn,
)


if TYPE_CHECKING:
    from pathlib import Path


#: The exit status a POSIX shell reports for a command it could not execute.
#: Reused rather than invented so an operator reading the number recognises it.
GIT_UNANSWERED_RETURNCODE = 127

#: Variables that select WHICH repository, index or object store git acts on.
#: Inheriting any of them makes the observation depend on the parent's state
#: rather than on the ``-C <root>`` argument the runner passes.
_REPOSITORY_SELECTING_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_CEILING_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_SUPER_PREFIX",
)


@dataclass(frozen=True)
class GitUnanswered:
    """Why git itself never produced an observation, already WHAT/WHY/HOW.

    Composed HERE rather than at the call site: the reason is a property of the
    seam (the tool, the decoder), never of the phase that happened to ask, and
    one sentence per class beats 21 sentences that drift apart.
    """

    what: str
    why: str
    how: str


@dataclass(frozen=True)
class GitObservation:
    """One text observation of git.  Total: this value always exists.

    ``unanswered is None`` means git ran and both its streams decoded; then
    ``returncode`` is git's own and ``stdout``/``stderr`` are git's own.
    Otherwise ``returncode`` is non-zero BY CONSTRUCTION and ``stderr`` carries
    the self-explaining reason, so a caller that only tests ``returncode`` --
    which is what every existing call site does -- still degrades LOUD instead
    of reading an empty stdout as an answer.
    """

    returncode: int
    stdout: str
    stderr: str
    unanswered: GitUnanswered | None = None

    def __post_init__(self) -> None:
        if self.unanswered is not None and self.returncode == 0:
            raise ValueError("an unanswered git observation cannot report success")


@dataclass(frozen=True)
class GitByteObservation:
    """One byte-exact observation of git.  Total for the same reason.

    Bytes are never decoded, so ``UnicodeDecodeError`` is not reachable on this
    path -- the only non-answer it can carry is the absent tool.
    """

    returncode: int
    stdout: bytes
    stderr: bytes
    unanswered: GitUnanswered | None = None

    def __post_init__(self) -> None:
        if self.unanswered is not None and self.returncode == 0:
            raise ValueError("an unanswered git observation cannot report success")


_TOOL_ABSENT_HOW = (
    "install git and put it on PATH, then re-run the dispatch; the runner "
    "observed no process at all, so no repository state was read or written"
)

_ARGUMENT_LIST_HOW = (
    "reduce how many paths one value declares, or split the Request: the "
    "runner passes owned paths as git arguments, and the kernel caps a single "
    "argument at 131072 bytes and the whole vector near 2 MiB. The structural "
    "repair belongs to the runner, not the operator -- pass the pathspec on "
    "stdin -- and is recorded as an open defect"
)

_KERNEL_REFUSED_HOW = (
    "read the errno named above: it is the kernel's own answer about why git "
    "could not start, and the runner reports it verbatim rather than guessing "
    "which repair it implies"
)

_UNDECODABLE_HOW = (
    "re-run once the repository holds no path or content git reports outside "
    "UTF-8, or set core.quotePath so git escapes them; the runner refuses to "
    "guess bytes it cannot decode"
)

_UNBOUNDED_HOW = (
    "clear whatever git is blocked on (an index.lock, a credential prompt, a "
    "hung mount), or widen the bound with NWAVE_GIT_TIMEOUT; the observation "
    "was killed, so the repository may hold partial state"
)


def _bound_fired(argv: tuple[str, ...], detail: str) -> GitUnanswered:
    """A fired GIT-tier bound is a NON-ANSWER, never an exception the caller forgot.

    ``SpawnTimeout`` subclasses ``subprocess.TimeoutExpired``, which is NOT an
    ``OSError`` -- the audit's row K4 names exactly that gap on the sibling
    native seam.  Introducing a bound here without catching it would trade a
    45-minute stall for a new traceback class, so the bound and its capture
    land together.
    """
    return GitUnanswered(
        "GitUnanswered",
        f"git ran `{' '.join(argv[:4])}` and did not answer within the bound: {detail}",
        _UNBOUNDED_HOW,
    )


def _tool_absent(detail: str) -> GitUnanswered:
    return GitUnanswered(
        "GitUnanswered",
        f"git could not be executed at all: {detail}",
        _TOOL_ABSENT_HOW,
    )


def _spawn_refused(argv: tuple[str, ...], refused: OSError) -> GitUnanswered:
    """Why the kernel would not run git -- ONE reason per world, never one lump.

    The first version of this seam caught three named ``OSError`` subclasses and
    its docstring claimed totality anyway.  An independent review falsified that
    claim in one line: ``observe_text(root, "status", "--porcelain", "--",
    "x" * 200000)`` raised ``OSError [Errno 7] Argument list too long``, which is
    none of the three.  Reproduced 2026-09-05 on both ``observe_text`` and
    ``observe_bytes``, and reachable from production -- the runner passes its
    owned paths as git arguments in ``git add``, ``git reset`` and
    ``git status`` (the audit's row K3).

    So the catch is now the WHOLE class, and the discrimination moved into the
    reason.  Widening a catch without widening the WHY would trade a traceback
    for a rejection that cannot tell an absent tool from an over-long argument
    vector, and those ask for opposite repairs (GDP-3, GDP-6).

    The errno knowledge itself now lives ONCE, in ``classify_spawn_refusal``:
    the native verification seam needs the same three worlds for its own reader,
    and a second copy of this list would be a second place to be incomplete in.
    The WORDING stays here, because it addresses git's operator and not that
    seam's.
    """
    world = classify_spawn_refusal(refused)
    if world is SpawnRefusal.ArgumentListTooLong:
        return GitUnanswered(
            "GitUnanswered",
            f"the kernel refused `{' '.join(argv[:4])}`: the argument vector is "
            f"too long ({sum(len(part) for part in argv)} bytes over "
            f"{len(argv)} arguments)",
            _ARGUMENT_LIST_HOW,
        )
    if world is SpawnRefusal.ExecutableAbsent:
        return _tool_absent(str(refused))
    named = errno.errorcode.get(refused.errno or 0, "unknown errno")
    return GitUnanswered(
        "GitUnanswered",
        f"the kernel refused to start git for `{' '.join(argv[:4])}` with "
        f"{named}: {refused}",
        _KERNEL_REFUSED_HOW,
    )


def _undecodable(argv: tuple[str, ...], detail: str) -> GitUnanswered:
    return GitUnanswered(
        "GitUnanswered",
        f"git ran `{' '.join(argv[:4])}` but its output is not UTF-8: {detail}",
        _UNDECODABLE_HOW,
    )


def declared_child_environment() -> dict[str, str]:
    """The environment a git child runs in, with the repository-selecting names gone.

    Public because a caller that must add ONE variable of its own -- the
    candidate builder, which runs on a temporary ``GIT_INDEX_FILE`` -- has to be
    able to start from the declared environment instead of from ``os.environ``.
    Handing it only the private default would leave it choosing between its own
    variable and the guarantee, which is the choice that made the inheritance
    silent in the first place.
    """
    return {
        name: value
        for name, value in os.environ.items()
        if name not in _REPOSITORY_SELECTING_VARIABLES
    }


def _child_environment(env: dict[str, str] | None) -> dict[str, str]:
    """The environment one git child runs in -- declared, never inherited whole."""
    return declared_child_environment() if env is None else env


def observe_text(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> GitObservation:
    """Observe git in ``root`` as text.  Total: it answers or says why it cannot.

    Every ``OSError`` the kernel can raise at ``execve`` is caught, not a named
    subset, and ``_spawn_refused`` turns each into its own reason.  A subset was
    the first version's defect and its docstring asserted totality regardless;
    the catch is the whole class precisely so a world nobody enumerated cannot
    make the claim false again.
    """
    argv = ("git", "-C", str(root), *args)
    try:
        completed = spawn(
            list(argv),
            capture_output=True,
            text=True,
            env=_child_environment(env),
            timeout=git_timeout_seconds(),
            timeout_env=GIT_TIMEOUT_ENV,
        )
    except OSError as refused:
        return _unanswered_text(_spawn_refused(argv, refused))
    except UnicodeDecodeError as undecodable:
        return _unanswered_text(_undecodable(argv, str(undecodable)))
    except subprocess.TimeoutExpired as unbounded:
        return _unanswered_text(_bound_fired(argv, str(unbounded)))
    return GitObservation(completed.returncode, completed.stdout, completed.stderr)


def observe_bytes(
    root: Path,
    *args: str,
    env: dict[str, str] | None = None,
    stdin: bytes | None = None,
) -> GitByteObservation:
    """Observe git in ``root`` as bytes.  Total for the same reason as the text form.

    ``stdin`` feeds the child's standard input, for the one git interface that
    accepts its arguments only there (``check-ignore --stdin``, whose ``-z``
    form has no argv spelling).  Passing it through the seam rather than around
    it is what keeps that call on the same tier and the same declared
    environment as the other twenty-one.
    """
    argv = ("git", "-C", str(root), *args)
    try:
        completed = spawn(
            list(argv),
            capture_output=True,
            env=_child_environment(env),
            timeout=git_timeout_seconds(),
            timeout_env=GIT_TIMEOUT_ENV,
            **({} if stdin is None else {"input": stdin}),
        )
    except OSError as refused:
        return _unanswered_bytes(_spawn_refused(argv, refused))
    except subprocess.TimeoutExpired as unbounded:
        return _unanswered_bytes(_bound_fired(argv, str(unbounded)))
    return GitByteObservation(completed.returncode, completed.stdout, completed.stderr)


def _unanswered_text(reason: GitUnanswered) -> GitObservation:
    return GitObservation(GIT_UNANSWERED_RETURNCODE, "", reason.why, reason)


def _unanswered_bytes(reason: GitUnanswered) -> GitByteObservation:
    return GitByteObservation(
        GIT_UNANSWERED_RETURNCODE, b"", reason.why.encode(), reason
    )


__all__ = [
    "GIT_UNANSWERED_RETURNCODE",
    "GitByteObservation",
    "GitObservation",
    "GitUnanswered",
    "declared_child_environment",
    "observe_bytes",
    "observe_text",
]
