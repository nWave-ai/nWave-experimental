"""Declared native verification must execute the CANDIDATE's code, never another
projection of the same tool.

MEASURED DEFECT (2026-09-05).  ``_native`` ran every declared argv with the
inherited environment and only ``cwd`` pointed at the candidate worktree.  A
bare name like ``des`` therefore resolved through ``PATH`` to the installer's
shim (``~/.claude/bin/des`` -> the recorded active runtime), and an ``import
des`` resolved through the development venv's editable ``.pth``, whose entries
are ABSOLUTE paths into the main checkout.  Both produce a real, exit-0 stdout
of the WRONG code, and the source-blind reviewer judges it as if it were the
candidate's: a candidate that repairs ``des code-fact`` is observed answering
exactly as it did before the repair.  That is the silent-wrong GDP-6 forbids,
and the model cannot avoid it -- how an argv resolves is enactment the runner
owns (``boundary:software-measures-model-decides``).
"""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    Disposition,
    NativeEvidence,
)


def _executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _competing_installation(tmp_path: Path, marker: str) -> Path:
    """A `des` on PATH that is NOT the candidate -- the installer's shim."""
    bin_dir = tmp_path / "installed-bin"
    _executable(bin_dir / "des", f"print({marker!r})\n")
    return bin_dir


def _candidate_tree(tmp_path: Path, marker: str) -> Path:
    """A candidate checkout shipping its own `des` package."""
    root = tmp_path / "candidate"
    package = root / "src" / "des"
    (package / "cli").mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli" / "__init__.py").write_text("", encoding="utf-8")
    (package / "cli" / "__main__.py").write_text(
        f"def main(argv=None):\n    print({marker!r})\n    return 0\n",
        encoding="utf-8",
    )
    return root


def _only_stdout(evidence: object) -> str:
    assert isinstance(evidence, tuple), evidence
    assert len(evidence) == 1, evidence
    item = evidence[0]
    assert isinstance(item, NativeEvidence)
    assert item.exit_status == 0, item
    return item.stdout.strip()


def test_a_declared_bare_name_executes_the_candidate_not_the_installed_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The whole defect in one line: same argv, two projections, candidate wins."""
    candidate = _candidate_tree(tmp_path, "CANDIDATE-ANSWERED")
    installed = _competing_installation(tmp_path, "INSTALLED-RUNTIME-ANSWERED")
    monkeypatch.setenv("PATH", f"{installed}{os.pathsep}{os.environ.get('PATH', '')}")

    evidence = DeliveryContinuationRunner()._native(
        candidate, (("des", "code-fact"),), candidate
    )

    assert _only_stdout(evidence) == "CANDIDATE-ANSWERED"


def test_an_interpreter_child_imports_the_candidate_over_an_inherited_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`PYTHONPATH` is prepended, so an inherited projection cannot shadow it.

    The editable install's `.pth` is the real-world instance of an inherited
    projection: absolute paths into the main checkout, processed at
    site-packages time and therefore AFTER `PYTHONPATH`.  A plain inherited
    `PYTHONPATH` is the same shape and the cheaper thing to measure.
    """
    candidate = _candidate_tree(tmp_path, "unused")
    foreign = tmp_path / "foreign"
    (foreign / "des").mkdir(parents=True)
    (foreign / "des" / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(foreign))

    evidence = DeliveryContinuationRunner()._native(
        candidate,
        (
            (
                sys.executable,
                "-c",
                "import des, sys; sys.stdout.write(des.__file__)",
            ),
        ),
        candidate,
    )

    assert _only_stdout(evidence) == str(candidate / "src" / "des" / "__init__.py")


def test_a_candidate_shipping_no_such_tool_shadows_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Parsimony, and the honest limit of the guarantee.

    A candidate that does not ship `des` is a repository where the declared
    `des` genuinely means the installed analysis tool.  Shadowing it there
    would break every non-DES subject to fix a defect none of them has.
    """
    plain = tmp_path / "plain-repo"
    plain.mkdir()
    installed = _competing_installation(tmp_path, "INSTALLED-RUNTIME-ANSWERED")
    monkeypatch.setenv("PATH", f"{installed}{os.pathsep}{os.environ.get('PATH', '')}")

    evidence = DeliveryContinuationRunner()._native(
        plain, (("des", "code-fact"),), plain
    )

    assert _only_stdout(evidence) == "INSTALLED-RUNTIME-ANSWERED"


def test_a_candidate_shipping_no_such_tool_keeps_the_inherited_import_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same limit, pinned on the OTHER half of the construction.

    An independent review measured the gap this closes: the docstring claimed
    both halves were conditional while `PYTHONPATH` was built unconditionally,
    so a non-DES subject received the candidate root on its import path anyway.
    A guarantee and its code cannot disagree, so the fact is asserted, not
    described -- a subject that ships no `des` leaves with the IMPORT PATH it
    inherited, byte for byte.  `PATH` is a separate question, answered by the
    interpreter shims below, which arm for every subject.
    """
    plain = tmp_path / "plain-repo"
    (plain / "src").mkdir(parents=True)
    monkeypatch.setenv("PYTHONPATH", str(tmp_path / "inherited"))

    evidence = DeliveryContinuationRunner()._native(
        plain,
        (
            (
                sys.executable,
                "-c",
                "import os, sys; sys.stdout.write(os.environ['PYTHONPATH'])",
            ),
        ),
        plain,
    )

    assert _only_stdout(evidence) == str(tmp_path / "inherited")


def _empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `PATH` carrying no interpreter at all -- run 18's box, minus `python3`.

    Measured on this box 2026-09-05: only `python3` exists, so a declared
    `python` never started.  Emptying `PATH` entirely is the same world for both
    spellings at once, and it is the world the shims must answer in.
    """
    bare = tmp_path / "no-tools-here"
    bare.mkdir()
    monkeypatch.setenv("PATH", str(bare))


@pytest.mark.parametrize("declared", ["python", "python3"])
def test_a_declared_interpreter_name_runs_the_runners_own_interpreter(
    declared: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MEASURED run 18: `python -m pytest ...` died at `execve` before anything ran.

    The model declared the common spelling; the box carried only the other one.
    Which name a box happens to carry is not a fact a model can know, and
    resolving a declared name is the runner's enactment.
    """
    _empty_path(tmp_path, monkeypatch)
    candidate = _candidate_tree(tmp_path, "unused")

    evidence = DeliveryContinuationRunner()._native(
        candidate,
        ((declared, "-c", "import sys; sys.stdout.write(sys.executable)"),),
        candidate,
    )

    assert _only_stdout(evidence) == sys.executable


def test_a_declared_pytest_runs_the_runners_interpreter_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The bare test-runner spelling resolves too, through `-m pytest`."""
    _empty_path(tmp_path, monkeypatch)
    candidate = _candidate_tree(tmp_path, "unused")

    evidence = DeliveryContinuationRunner()._native(
        candidate, (("pytest", "--version"),), candidate
    )

    assert isinstance(evidence, tuple), evidence
    reported = evidence[0]
    assert isinstance(reported, NativeEvidence)
    assert reported.exit_status == 0, reported
    assert "pytest" in reported.stdout + reported.stderr


def test_the_interpreter_shims_serve_a_candidate_that_ships_no_des(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The two arming conditions are SEPARATE, pinned on the subject that splits them.

    A candidate shipping no `src/des` gets no `des` shim -- that name means the
    installed tool there.  It still gets the interpreter shims, because
    `python` names no candidate tree at all.
    """
    _empty_path(tmp_path, monkeypatch)
    plain = tmp_path / "plain-repo"
    plain.mkdir()

    evidence = DeliveryContinuationRunner()._native(
        plain,
        (("python", "-c", "import sys; sys.stdout.write(sys.executable)"),),
        plain,
    )

    assert _only_stdout(evidence) == sys.executable


def test_an_absent_executable_is_indeterminate_and_names_the_working_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An executable the box cannot start is a NON-OUTCOME, never a Retry.

    Run 18 answered `Retry` / `restore verification`: a promise that a second
    identical spawn could differ, plus a HOW that restates the WHAT.  A second
    `execve` of an absent name fails identically, so the disposition asserted a
    fact the runner had not observed.
    """
    _empty_path(tmp_path, monkeypatch)
    candidate = _candidate_tree(tmp_path, "unused")

    outcome = DeliveryContinuationRunner()._native(
        candidate, (("nonexistent-tool", "--version"),), candidate
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationExecutableAbsent"
    assert "nonexistent-tool" in outcome.failure.why
    assert "python -m pytest" in outcome.failure.how


def test_a_declared_uv_run_degrades_loud_instead_of_being_translated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`uv` is not a runtime dependency, so it is never provided -- and says so.

    Translating `uv run <cmd>` into `<cmd>` was considered and rejected: `uv
    run` carries virtual-environment semantics the runner would be silently
    dropping, and a wrong-but-green verification is worse than a stop.  The
    stop has to tell the reader which form always works, or the next paid turn
    guesses again.
    """
    _empty_path(tmp_path, monkeypatch)
    candidate = _candidate_tree(tmp_path, "unused")

    outcome = DeliveryContinuationRunner()._native(
        candidate, (("uv", "run", "pytest", "-q"),), candidate
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.disposition is Disposition.Indeterminate
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationExecutableAbsent"
    assert "uv" in outcome.failure.how
    assert "python -m pytest" in outcome.failure.how


def test_the_operator_line_lists_the_armed_shims(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """`NATIVE-RUNTIME` says WHICH names the runner resolved, not just which python."""
    _empty_path(tmp_path, monkeypatch)
    candidate = _candidate_tree(tmp_path, "unused")

    DeliveryContinuationRunner()._native(
        candidate, (("python", "-c", "pass"),), candidate
    )

    line = next(
        row
        for row in capsys.readouterr().err.splitlines()
        if row.startswith("NATIVE-RUNTIME:")
    )
    assert "shims=python,python3,pytest,des" in line
