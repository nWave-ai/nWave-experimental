"""The runner's git and filesystem seams answer; they never raise.

WHY THIS FILE EXISTS.  ``docs/analysis/2026-09-05-runner-totality-audit-os-git-
fs-seams.md`` found the delivery runner's algebra applied to its CODOMAINS --
``DeliveryOutcome``, ``Blocked``, ``Disposition`` are closed sums -- and not to
its DOMAINS: the seams reaching git and the filesystem were typed as total
functions and were partial.  Four inputs from the world, none of them
expressible in those signatures, escaped as a bare traceback across every phase
of a delivery:

* git absent from ``PATH`` (``FileNotFoundError``, 17 text sites + 4 byte sites);
* git output that is not UTF-8 (``UnicodeDecodeError``, because ``text=True``
  decodes and the decoder has no fallback);
* a workspace or product-tree path the filesystem refuses mid-turn
  (``OSError`` out of ``read_bytes`` / ``readlink`` / ``rglob``);
* approved authority bytes reached through a symlink leaving the repository.

Each test below was RUN against the pre-repair seam and observed to fail with
the named exception, then run again against the repair.  A check nobody has
seen fail is not evidence, so the exception each one replaces is named in its
own docstring rather than left to the reader's trust.

These are unit tests of the SEAM.  The whole-runner statement -- that every one
of these worlds still lands on one of the four dispositions, over generated
sizes, encodings and link shapes -- is the property in
``tests/des/acceptance/dispatch_owns_e2_e4/test_runner_totality_over_system_domains.py``.
"""

from __future__ import annotations

import errno
import os
import subprocess
from pathlib import Path

import pytest

from des.adapters.driven.git.git_observation import (
    GIT_UNANSWERED_RETURNCODE,
    GitByteObservation,
    GitObservation,
    GitUnanswered,
    observe_bytes,
    observe_text,
)
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    _authority_bytes,
    _workspace_bytes,
)
from des.runtime.spawn import git_timeout_seconds


UNDECODABLE_PATH = b"note-\xff.md"

#: One argument longer than the kernel's WHOLE argument budget.  Linux refuses
#: any single argument over ``MAX_ARG_STRLEN`` (131072 bytes); macOS has no
#: per-argument ceiling and refuses only past ``ARG_MAX`` in total, so a 200000
#: byte argument ran git there and exited 0.  A length past ``SC_ARG_MAX`` is
#: ``E2BIG`` under both rules.
OVER_LONG_ARGUMENT = "x" * (os.sysconf("SC_ARG_MAX") + 1)


def repo(root: Path) -> Path:
    """One real repository -- the seam under test observes git, not a double."""
    root.mkdir(parents=True, exist_ok=True)
    for argv in (
        ("init", "-q"),
        ("config", "user.email", "a@b"),
        ("config", "user.name", "a"),
    ):
        subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True)
    (root / "README.md").write_text("x\n")
    return root


def tracked_without_a_file(root: Path, path: bytes) -> None:
    """Put ``path`` in git's index WITHOUT asking the filesystem to hold the name.

    APFS refuses a non-UTF-8 name at ``open`` (``EILSEQ``), so writing the file
    failed on macOS before git ever ran.  Git's index holds bytes on every
    platform, so ``git status -z`` emits the same raw byte either way.
    """
    blob = subprocess.run(
        ["git", "-C", str(root), "hash-object", "-w", "--stdin"],
        input=b"x\n",
        check=True,
        capture_output=True,
    ).stdout.strip()
    cacheinfo = b"100644," + blob + b"," + path
    subprocess.run(
        [
            b"git",
            b"-C",
            os.fsencode(root),
            b"update-index",
            b"--add",
            b"--cacheinfo",
            cacheinfo,
        ],
        check=True,
        capture_output=True,
    )


def without_git(monkeypatch: pytest.MonkeyPatch, empty: Path) -> None:
    """A substrate with no git at all -- ``GIT_EXEC_PATH`` removed as well."""
    empty.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("GIT_EXEC_PATH", raising=False)


def test_absent_git_is_an_indeterminate_disposition_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED before the repair: ``FileNotFoundError: [Errno 2] ... 'git'``.

    Measured 2026-09-05 by calling this same entry point with ``PATH`` narrowed:
    the exception left the runner entirely, so the operator got a traceback
    instead of one of the four dispositions -- and no HOW at all.
    """
    root = repo(tmp_path / "repo")
    without_git(monkeypatch, tmp_path / "empty-bin")

    observed = DeliveryContinuationRunner()._observed_scope(root)

    assert isinstance(observed, DeliveryOutcome)
    assert observed.disposition is Disposition.Indeterminate
    assert observed.failure is not None
    assert "git could not be executed" in observed.failure.why
    assert "install git" in observed.failure.how


def test_undecodable_git_output_is_a_disposition_not_a_unicode_error(
    tmp_path: Path,
) -> None:
    """RED before the repair: ``UnicodeDecodeError: 'utf-8' codec can't decode
    byte 0xff in position 21``.

    A path is bytes on POSIX.  ``git status --porcelain -z -uall`` reports one
    holding ``0xff``, and ``text=True`` decoded it with no fallback.
    """
    root = repo(tmp_path / "repo")
    tracked_without_a_file(root, UNDECODABLE_PATH)

    observed = DeliveryContinuationRunner()._observed_scope(root)

    assert isinstance(observed, DeliveryOutcome)
    assert observed.disposition is Disposition.Indeterminate
    assert observed.failure is not None
    assert "not UTF-8" in observed.failure.why


def test_absent_git_answers_none_on_the_byte_seam(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED before the repair: the same ``FileNotFoundError`` out of `_git_bytes`."""
    root = repo(tmp_path / "repo")
    without_git(monkeypatch, tmp_path / "empty-bin")

    assert DeliveryContinuationRunner._git_bytes(root, "ls-tree", "-r", "HEAD") is None


def test_an_unanswered_observation_cannot_report_success() -> None:
    """GDP-0: the state a caller could misread is not constructible at all.

    Every call site discriminates on ``returncode``.  A non-answer carrying zero
    would read as an empty but VALID git answer -- a silent-wrong -- so the
    constructor refuses it rather than a later gate catching it.
    """
    reason = GitUnanswered("GitUnanswered", "git was never executed", "install git")

    with pytest.raises(ValueError):
        GitObservation(0, "", "", reason)
    with pytest.raises(ValueError):
        GitByteObservation(0, b"", b"", reason)


def test_the_seam_carries_the_git_tier_not_the_run_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit G2: 17 sites inherited the RUN default of 45 minutes, a factor of 90.

    The tier is not a guess.  Measured on this repository 2026-09-05, the widest
    command the runner issues, ``git diff --binary`` over 200 commits (5.1 MB of
    output), took 0.210s -- a 140x margin under the 30s tier, so no command
    needs an exception and none is granted.
    """
    root = repo(tmp_path / "repo")
    seen: dict[str, object] = {}

    def recording_spawn(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(
        "des.adapters.driven.git.git_observation.spawn", recording_spawn
    )
    observe_text(root, "rev-parse", "HEAD")

    assert seen["timeout"] == git_timeout_seconds()
    assert seen["timeout_env"] == "NWAVE_GIT_TIMEOUT"


def test_a_fired_bound_is_a_non_answer_not_a_timeout_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``SpawnTimeout`` subclasses ``TimeoutExpired``, which is NOT an ``OSError``.

    Introducing a 30s bound without capturing it would trade a 45-minute stall
    for a new traceback class -- the audit's row K4 on the sibling native seam.
    """

    def timing_out_spawn(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 30.0)

    monkeypatch.setattr(
        "des.adapters.driven.git.git_observation.spawn", timing_out_spawn
    )
    observed = observe_text(tmp_path, "rev-parse", "HEAD")

    assert observed.unanswered is not None
    assert observed.returncode == GIT_UNANSWERED_RETURNCODE
    assert "NWAVE_GIT_TIMEOUT" in observed.unanswered.how
    assert observe_bytes(tmp_path, "ls-tree", "HEAD").unanswered is not None


def test_an_inherited_git_index_file_never_reaches_the_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Audit G5, silent-wrong: 13 of 17 text sites inherited ``os.environ`` whole.

    A ``GIT_INDEX_FILE`` belonging to the PARENT redirected the child's index at
    every one of them, so the runner's observation described a repository state
    the ``-C <root>`` argument never named.
    """
    root = repo(tmp_path / "repo")
    (root / "dirty.txt").write_text("x\n")
    monkeypatch.setenv("GIT_INDEX_FILE", str(tmp_path / "foreign-index"))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "foreign-git-dir"))

    observed = observe_text(root, "status", "--porcelain=v1")

    assert observed.unanswered is None
    assert observed.returncode == 0
    assert "dirty.txt" in observed.stdout


def test_a_caller_supplied_environment_is_forwarded_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caller that passes ``env=`` has DECIDED; the seam is a thin passthrough.

    The one site that builds a candidate commit deliberately supplies its own
    ``GIT_INDEX_FILE``.  Rewriting a kwarg the caller chose would break it.
    """
    chosen = {**os.environ, "GIT_INDEX_FILE": str(tmp_path / "chosen-index")}
    seen: dict[str, object] = {}

    def recording_spawn(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "", "")

    monkeypatch.setattr(
        "des.adapters.driven.git.git_observation.spawn", recording_spawn
    )
    observe_text(tmp_path, "write-tree", env=chosen)

    assert seen["env"] == chosen


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits under test")
def test_an_unreadable_workspace_path_is_recorded_not_raised(tmp_path: Path) -> None:
    """RED before the repair: ``PermissionError`` out of ``Path.read_bytes``.

    The snapshot brackets a model turn, so the window in which a path can stop
    being readable is exactly as wide as that turn.
    """
    root = tmp_path / "repo"
    (root / "locked").mkdir(parents=True)
    secret = root / "locked" / "value.txt"
    secret.write_text("x\n")
    (root / "locked").chmod(0o000)
    try:
        snapshot = _workspace_bytes(root, ("locked/value.txt",))
    finally:
        (root / "locked").chmod(0o755)

    assert snapshot["locked/value.txt"] == ("unreadable", "PermissionError")


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits under test")
def test_an_unwalkable_product_tree_is_recorded_not_raised(tmp_path: Path) -> None:
    """RED before the repair: ``PermissionError`` out of ``Path.rglob``.

    A read-only role is judged by comparing this snapshot before and after its
    turn; the marker keeps that comparison total instead of crashing it.
    """
    root = tmp_path / "repo"
    product = root / "docs" / "product"
    product.mkdir(parents=True)
    (product / "vision.md").write_text("x\n")
    product.chmod(0o000)
    try:
        snapshot = DeliveryContinuationRunner._snapshot(root, Path("docs/product"))
    finally:
        product.chmod(0o755)

    assert snapshot == {"docs/product": b"PermissionError"}


def test_authority_bytes_refuses_a_symlink_leaving_the_repository(
    tmp_path: Path,
) -> None:
    """Admitted by PROPERTY, as the sibling authority reader already admits one.

    Approved bytes reached through a link decide what the oracle says without
    the repository ever owning them; ``_repo_local_markdown`` already refuses
    this shape and ``_authority_bytes`` did not.
    """
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    outside = tmp_path / "outside.py"
    outside.write_text("assert False\n")
    (root / "tests" / "support.py").symlink_to(outside)

    assert _authority_bytes(root, ("tests/support.py",)) is None


def test_authority_bytes_still_reads_a_plain_repository_file(tmp_path: Path) -> None:
    """The containment check admits what it must -- the honest-yes branch."""
    root = tmp_path / "repo"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "support.py").write_text("x = 1\n")

    assert _authority_bytes(root, ("tests/support.py",)) == (
        ("tests/support.py", b"x = 1\n"),
    )


def test_the_ignored_support_probe_answers_when_git_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The last git call in the runner that still held its own raw spawn.

    It was already total for the absent tool -- its own ``try`` caught
    ``OSError`` -- and that is exactly why it was easy to miss: being total on
    one axis, it kept inheriting the 45-minute RUN bound on the other, and it
    ran with the parent's repository-selecting environment.  A census by
    ``_git``/``_git_bytes`` call site does not find it; a census by "what
    spawns git" does.
    """
    root = repo(tmp_path / "repo")
    without_git(monkeypatch, tmp_path / "empty-bin")

    assert (
        DeliveryContinuationRunner._ignored_supports(root, ("tests/support.py",))
        is None
    )


def test_the_ignored_support_probe_carries_the_git_tier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Routing it through the seam is what puts it on the tier, once."""
    seen: dict[str, object] = {}

    def recording_spawn(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 1, b"", b"")

    monkeypatch.setattr(
        "des.adapters.driven.git.git_observation.spawn", recording_spawn
    )
    DeliveryContinuationRunner._ignored_supports(tmp_path, ("tests/support.py",))

    assert seen["timeout"] == git_timeout_seconds()
    assert seen["input"] == b"tests/support.py"


def test_a_verification_command_that_outruns_its_bound_is_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED before the repair: the fired bound crossed the runner untouched.

    ``SpawnTimeout`` subclasses ``subprocess.TimeoutExpired``, which is not an
    ``OSError``, so the ``except OSError`` guarding this site never saw it --
    the audit's row K4.  The operator's repair is the opposite of the absent-
    executable one, so it gets its own WHAT and its own HOW rather than being
    folded into ``VerificationUnavailable``.
    """

    def timing_out_spawn(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, 2700.0)

    monkeypatch.setattr("des.application.delivery_continuation.spawn", timing_out_spawn)
    outcome = DeliveryContinuationRunner()._native(
        tmp_path, (("bin/verify",),), tmp_path
    )

    assert isinstance(outcome, DeliveryOutcome)
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationUnbounded"
    assert "NWAVE_GATE_RUN_TIMEOUT" in outcome.failure.how


def test_an_over_long_argument_vector_is_a_non_answer_not_an_oserror(
    tmp_path: Path,
) -> None:
    """RED before the repair: ``OSError [Errno 7] Argument list too long``.

    The first version of this seam caught three NAMED subclasses of ``OSError``
    and its docstring claimed totality anyway.  An independent review falsified
    that claim in one line, and the world it named is reachable from production:
    the runner passes its owned paths as git arguments in ``git add``,
    ``git reset`` and ``git status`` -- the audit's row K3 -- so a Request
    owning enough paths reaches the kernel's ceiling on real work.

    Widening the catch is only half the repair.  The WHY must still tell an
    over-long vector apart from an absent tool, because the two ask for
    opposite repairs, so the reason and its HOW are asserted here too.
    """
    root = repo(tmp_path / "repo")

    observed = observe_text(root, "status", "--porcelain", "--", OVER_LONG_ARGUMENT)

    assert observed.unanswered is not None
    assert observed.returncode == GIT_UNANSWERED_RETURNCODE
    assert "argument vector is too long" in observed.unanswered.why
    assert "reduce how many paths" in observed.unanswered.how
    assert "could not be executed at all" not in observed.unanswered.why


def test_the_byte_seam_answers_the_same_over_long_vector(tmp_path: Path) -> None:
    """The byte form carried the identical gap and is repaired by the same seam."""
    root = repo(tmp_path / "repo")

    observed = observe_bytes(root, "status", "--porcelain", "--", OVER_LONG_ARGUMENT)

    assert observed.unanswered is not None
    assert "argument vector is too long" in observed.unanswered.why


def test_an_unenumerated_kernel_refusal_still_names_its_errno(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The catch is the whole ``OSError`` class, not a longer list of subclasses.

    A list of named worlds is what failed review the first time: the next world
    nobody enumerated makes the totality claim false again.  This asserts the
    honest-unknown branch -- an errno the seam has no opinion about is still a
    non-answer, and it reports the kernel's own code rather than guessing a
    repair.
    """

    def refusing_spawn(argv, **kwargs):
        raise OSError(errno.EMFILE, "Too many open files")

    monkeypatch.setattr("des.adapters.driven.git.git_observation.spawn", refusing_spawn)
    observed = observe_text(tmp_path, "rev-parse", "HEAD")

    assert observed.unanswered is not None
    assert "EMFILE" in observed.unanswered.why


def _integration_facts():
    from des.domain.integration_commit_message import IntegrationFacts

    return IntegrationFacts("Deliver value\n", ("Deliver value\n",), ("brief.md",))


def test_the_candidate_builder_does_not_inherit_a_parent_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RED before the repair: a parent ``GIT_DIR`` redirected the four writes.

    The candidate builder is the one caller that supplies its own ``env``, so
    the seam's declared environment never reached it: it started from
    ``os.environ`` and added a temporary ``GIT_INDEX_FILE``, which meant a
    ``GIT_DIR`` or ``GIT_WORK_TREE`` belonging to the parent silently pointed
    exactly the calls that WRITE at another repository.
    """
    root = repo(tmp_path / "repo")
    (root / "value.py").write_text("VALUE = 1\n")
    foreign = repo(tmp_path / "foreign")
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "base", "--allow-empty"],
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("GIT_DIR", str(foreign / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(foreign))

    built = DeliveryContinuationRunner()._candidate(
        root, "HEAD", ("value.py",), _integration_facts()
    )

    assert not isinstance(built, DeliveryOutcome), built
    _, diff = built
    assert "value.py" in diff


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores the mode bits under test")
def test_an_unobservable_owned_path_is_not_silently_dropped_from_the_candidate(
    tmp_path: Path,
) -> None:
    """RED before the repair: ``PermissionError`` out of ``Path.exists``.

    Answering "absent" would have been worse than raising.  An owned target
    dropped from the staged set produces a candidate missing a file the value
    declared, committed as if complete, so the third state is the only honest
    answer here.
    """
    root = repo(tmp_path / "repo")
    (root / "locked").mkdir()
    (root / "locked" / "value.py").write_text("VALUE = 1\n")
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "base", "--allow-empty"],
        check=True,
        capture_output=True,
    )
    (root / "locked").chmod(0o000)
    try:
        built = DeliveryContinuationRunner()._candidate(
            root, "HEAD", ("locked/value.py",), _integration_facts()
        )
    finally:
        (root / "locked").chmod(0o755)

    assert isinstance(built, DeliveryOutcome)
    assert built.disposition is Disposition.Indeterminate
    assert built.failure is not None
    assert built.failure.what == "OwnedScopeUnobservable"
