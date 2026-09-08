"""Declared native verification must run under the SUBJECT's own interpreter.

MEASURED DEFECT (run 19, 2026-09-05 07:40).  ``NATIVE-RUNTIME`` reported
``python=/usr/bin/python3``: the interpreter shims resolved to ``sys.executable``,
which for the installed runner (``~/.claude/bin/des``) is the SYSTEM interpreter.
The declared ``python -m pytest ...`` therefore started, collected nothing and
exited 4 with ``ERROR: Unknown config option: asyncio_mode`` -- the system
interpreter carries none of the subject's test dependencies, which live in the
``.venv`` the subject builds at its own root.  The runner passed the failure to
the crafter as a finding; the crafter answered that the implementation was
present and correct and the verification inconclusive, and the run ended
``Indeterminate``.  Two paid turns bought nothing, for a defect of FORM.

The subject declares its own test environment.  Resolving a declared interpreter
name against that declaration is ENACTMENT, which the runner owns
(``boundary:software-measures-model-decides``), and the fact it enacts on is
PRIMITIVE: ``<subject>/.venv/bin/python`` either exists and is executable, or it
does not.  Where it does not, ``sys.executable`` remains the answer and the
operator line SAYS which of the two answered -- an incomplete measurement that
degrades loud, never a silent substitution (GDP-6).
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import pytest

from des.adapters.driven.codefact.graphify_code_fact_adapter import (
    GRAPH_INDEX_DIR_NAME,
)
from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    NativeEvidence,
)


def _subject_with_venv(tmp_path: Path, marker: str) -> Path:
    """A subject repository declaring its test environment the way ours does.

    The fake ``.venv/bin/python`` ignores its argv and prints a marker, so any
    argv that reaches it is attributable to THIS interpreter and to no other.
    """
    subject = tmp_path / "subject"
    interpreter = subject / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text(f"#!{sys.executable}\nprint({marker!r})\n", encoding="utf-8")
    interpreter.chmod(interpreter.stat().st_mode | stat.S_IXUSR)
    return subject


def _candidate_tree(root: Path) -> Path:
    """A candidate worktree: the delivered tree, and no ``.venv`` of its own."""
    (root / "src").mkdir(parents=True, exist_ok=True)
    return root


def _stdout(evidence: object) -> str:
    assert isinstance(evidence, tuple), evidence
    item = evidence[0]
    assert isinstance(item, NativeEvidence)
    return item.stdout.strip()


def _runtime_line(captured: str) -> str:
    return next(
        row for row in captured.splitlines() if row.startswith("NATIVE-RUNTIME:")
    )


def test_a_declared_interpreter_runs_the_subject_venv_not_the_runners_own(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The whole defect in one line: same declared name, two interpreters."""
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")

    evidence = DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    assert _stdout(evidence) == "SUBJECT-VENV-ANSWERED"
    line = _runtime_line(capsys.readouterr().err)
    assert f"python={subject / '.venv' / 'bin' / 'python'}" in line
    assert "python-source=subject-venv" in line


@pytest.mark.parametrize("declared", ["python3", "pytest"])
def test_every_interpreter_spelling_reaches_the_same_subject_interpreter(
    declared: str, tmp_path: Path
) -> None:
    """One subject, one interpreter -- whichever spelling the model declared."""
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")

    evidence = DeliveryContinuationRunner()._native(
        candidate, ((declared, "--version"),), subject
    )

    assert _stdout(evidence) == "SUBJECT-VENV-ANSWERED"


def test_a_subject_declaring_no_environment_falls_back_and_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Incompleteness degrades LOUD: the fallback is named, never silent.

    A subject with no ``.venv`` has declared nothing, so the runner's own
    interpreter is the only interpreter there is.  That is a legitimate answer
    and an operator reading ``NATIVE-RUNTIME`` can tell it apart from the other
    one, which is the whole difference between this and run 19.
    """
    subject = tmp_path / "subject"
    subject.mkdir()
    candidate = _candidate_tree(tmp_path / "candidate")

    evidence = DeliveryContinuationRunner()._native(
        candidate,
        (("python", "-c", "import sys; sys.stdout.write(sys.executable)"),),
        subject,
    )

    assert _stdout(evidence) == sys.executable
    line = _runtime_line(capsys.readouterr().err)
    assert f"python={sys.executable}" in line
    assert "python-source=runner" in line


def test_a_venv_path_that_is_not_executable_is_not_an_interpreter(
    tmp_path: Path,
) -> None:
    """Decide on the PROPERTY, never the designation (GDP-8).

    A ``.venv/bin/python`` that exists but cannot be started is not an
    interpreter, and treating the NAME as the fact would turn a working fallback
    into a refused spawn.
    """
    subject = tmp_path / "subject"
    interpreter = subject / ".venv" / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text("not an interpreter\n", encoding="utf-8")
    interpreter.chmod(0o644)
    candidate = _candidate_tree(tmp_path / "candidate")

    evidence = DeliveryContinuationRunner()._native(
        candidate,
        (("python", "-c", "import sys; sys.stdout.write(sys.executable)"),),
        subject,
    )

    assert _stdout(evidence) == sys.executable


def test_the_candidate_worktree_carries_the_subjects_declared_venv_path(
    tmp_path: Path,
) -> None:
    """The literal ``.venv/bin/python`` a brief or an ADR names must START.

    Both faces of one cause were measured on 2026-09-05: the venv-relative form
    was rejected because no ``.venv`` exists inside an ephemeral candidate
    worktree, and the bare form then ran under the wrong interpreter.  Linking
    the subject's declaration into the candidate answers both -- and it answers
    for every path under ``.venv``, not only the interpreter, which an argv
    rewrite keyed on one spelling would not.
    """
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")

    linked = DeliveryContinuationRunner._link_subject_venv(subject, candidate)

    assert linked == "linked"
    assert (candidate / ".venv" / "bin" / "python").is_file()
    DeliveryContinuationRunner._unlink_subject_venv(candidate)
    assert not (candidate / ".venv").exists()
    assert (subject / ".venv" / "bin" / "python").is_file()


def test_linking_a_subject_that_declares_no_environment_is_a_no_op(
    tmp_path: Path,
) -> None:
    """Nothing to link, nothing linked, and no directory invented."""
    subject = tmp_path / "subject"
    subject.mkdir()
    candidate = _candidate_tree(tmp_path / "candidate")

    linked = DeliveryContinuationRunner._link_subject_venv(subject, candidate)

    assert linked == "skipped:subject-declares-none"
    assert not (candidate / ".venv").exists()


def test_the_operator_line_carries_the_link_outcome_in_every_world(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The stated limit must be VISIBLE, not only documented.

    The docstring said the link degrades loud in the operator line while
    `NATIVE-RUNTIME` carried no field about it at all and the return value was
    discarded -- a guarantee and its code disagreeing, which is the same shape
    an earlier review already found in this method's `PYTHONPATH` half.  Three
    worlds leave the link unmade and they are not one condition, so the field
    names WHICH.
    """
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    assert "subject-venv-link=linked" in _runtime_line(capsys.readouterr().err)
    assert not (candidate / ".venv").exists()


def test_a_candidate_carrying_its_own_environment_is_never_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Its own `.venv` stays its own, and the line says the link was skipped."""
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")
    own = candidate / ".venv" / "bin" / "python"
    own.parent.mkdir(parents=True)
    own.write_text("#!/bin/sh\n", encoding="utf-8")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    line = _runtime_line(capsys.readouterr().err)
    assert "subject-venv-link=skipped:candidate-declares-its-own" in line
    assert own.read_text(encoding="utf-8") == "#!/bin/sh\n"


def _refusal(candidate: Path, subject: Path) -> DeliveryOutcome:
    outcome = DeliveryContinuationRunner()._native(
        candidate, (("nonexistent-tool", "--version"),), subject
    )
    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    return outcome


def test_the_refusal_promises_the_venv_relative_form_only_where_it_resolves(
    tmp_path: Path,
) -> None:
    """A HOW that names a form which then dies at `execve` is a lying rejection.

    The unconditional sentence promised the venv-relative form through "the link
    the runner places in the candidate worktree", in a world where the link is
    not always placed.  The promise is now a function of the measured property.
    """
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    candidate = _candidate_tree(tmp_path / "candidate")

    how = _refusal(candidate, subject).failure.how

    assert "python -m pytest" in how
    assert ".venv/bin/python -m pytest" in how


def test_the_refusal_says_so_where_no_venv_relative_interpreter_resolves(
    tmp_path: Path,
) -> None:
    """The other half of the same promise, in the world the link never reached."""
    subject = tmp_path / "subject"
    subject.mkdir()
    candidate = _candidate_tree(tmp_path / "candidate")

    how = _refusal(candidate, subject).failure.how

    assert "python -m pytest" in how
    assert "carries no `.venv`" in how


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


def _subject_repository(tmp_path: Path, ignored: str = "") -> Path:
    """A subject that is a real repository, because ignoring is a Git fact.

    ``git check-ignore`` is the only thing that knows whether a directory is
    ignored; a fixture that faked it would decide over the NAME and could not
    discriminate the two worlds this file now separates.
    """
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    _git(subject, "init", "-q")
    _git(subject, "config", "user.email", "a@b")
    _git(subject, "config", "user.name", "a")
    (subject / ".gitignore").write_text(ignored, encoding="utf-8")
    return subject


def _index_at(root: Path) -> Path:
    """The directory the code-fact port reads, holding one recognisable byte."""
    index = root / GRAPH_INDEX_DIR_NAME
    index.mkdir(parents=True)
    (index / "graph.json").write_text("{}\n", encoding="utf-8")
    return index


def test_the_candidate_carries_the_subjects_ignored_code_fact_index(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """MEASURED, runs 20 and 27: the index is a precondition OF MEASUREMENT.

    The candidate is an ephemeral worktree, so it holds only tracked bytes.  In
    run 27 both the declared verification argv and the Request stimulus were
    ``des code-fact query.callers-of ...``, and both answered ``provider:
    textsearch, confidence: noisy`` because the index the code-fact port reads
    is ignored by Git and therefore absent from the candidate.  The examiner
    read that as "promise not observed on the product" and refused candidate
    ``77b9e120c`` -- the same candidate that answers a resolved, binding-level
    provider once the index is reachable.  Same class as the ``.venv`` the
    runner already carries: the software builds the formal preconditions it
    OWNS, and materialises nothing on the model's behalf.
    """
    subject = _subject_repository(tmp_path, ignored=f"{GRAPH_INDEX_DIR_NAME}/\n")
    _index_at(subject)
    candidate = _candidate_tree(tmp_path / "candidate")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    line = _runtime_line(capsys.readouterr().err)
    assert f"subject-index-link=linked:{GRAPH_INDEX_DIR_NAME}" in line
    assert not (candidate / GRAPH_INDEX_DIR_NAME).exists()
    assert (subject / GRAPH_INDEX_DIR_NAME / "graph.json").is_file()


def test_the_linked_index_is_readable_from_inside_the_candidate(
    tmp_path: Path,
) -> None:
    """The link is only worth making if a command run IN the candidate sees it."""
    subject = _subject_repository(tmp_path, ignored=f"{GRAPH_INDEX_DIR_NAME}/\n")
    _index_at(subject)
    candidate = _candidate_tree(tmp_path / "candidate")

    linked = DeliveryContinuationRunner()._link_subject_index(subject, candidate)

    assert linked == f"linked:{GRAPH_INDEX_DIR_NAME}"
    assert (candidate / GRAPH_INDEX_DIR_NAME / "graph.json").is_file()
    DeliveryContinuationRunner._unlink_subject_index(candidate)
    assert not (candidate / GRAPH_INDEX_DIR_NAME).exists()
    assert (subject / GRAPH_INDEX_DIR_NAME / "graph.json").is_file()


def test_a_subject_without_the_index_says_absent_and_invents_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """The runner carries what the subject HAS; it never materialises an index."""
    subject = _subject_repository(tmp_path, ignored=f"{GRAPH_INDEX_DIR_NAME}/\n")
    candidate = _candidate_tree(tmp_path / "candidate")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    assert "subject-index-link=skipped:absent" in _runtime_line(capsys.readouterr().err)
    assert not (candidate / GRAPH_INDEX_DIR_NAME).exists()


def test_an_index_git_already_tracks_is_not_carried_and_says_why(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A tracked directory travels with the checkout, so linking it is wrong.

    Decide on the PROPERTY (GDP-8): ignored-ness, observed through Git, is what
    makes a directory missing from an ephemeral worktree.  A directory of the
    same NAME that Git tracks is already in the candidate at the right revision,
    and shadowing it with the subject's copy would verify the wrong bytes.
    """
    subject = _subject_repository(tmp_path)
    _index_at(subject)
    candidate = _candidate_tree(tmp_path / "candidate")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    line = _runtime_line(capsys.readouterr().err)
    assert "subject-index-link=skipped:not-ignored" in line
    assert not (candidate / GRAPH_INDEX_DIR_NAME).exists()


def test_a_candidate_carrying_its_own_index_is_never_overwritten(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Its own index stays its own, exactly as its own ``.venv`` does."""
    subject = _subject_repository(tmp_path, ignored=f"{GRAPH_INDEX_DIR_NAME}/\n")
    _index_at(subject)
    candidate = _candidate_tree(tmp_path / "candidate")
    own = _index_at(candidate) / "graph.json"
    own.write_text("OWN\n", encoding="utf-8")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    line = _runtime_line(capsys.readouterr().err)
    assert "subject-index-link=skipped:candidate-declares-its-own" in line
    assert own.read_text(encoding="utf-8") == "OWN\n"


def test_an_unobservable_ignore_rule_degrades_loud_and_links_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Git never answered, so the runner claims neither ignored nor tracked.

    Reporting ``not-ignored`` for a non-answer would be a property claim the
    runner never observed (GDP-6, GDP-8): the third state reaches the operator
    line under its own name.  The subject here is a directory Git does not
    govern, which is the reachable spelling of that world.
    """
    subject = _subject_with_venv(tmp_path, "SUBJECT-VENV-ANSWERED")
    _index_at(subject)
    candidate = _candidate_tree(tmp_path / "candidate")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), subject
    )

    line = _runtime_line(capsys.readouterr().err)
    assert "subject-index-link=skipped:ignore-unobserved" in line
    assert not (candidate / GRAPH_INDEX_DIR_NAME).exists()
