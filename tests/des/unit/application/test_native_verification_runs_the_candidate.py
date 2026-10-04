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

import json
import os
import signal
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


@pytest.mark.skipif(
    os.name != "posix", reason="managed reuse requires POSIX process groups"
)
def test_unproven_descendant_exit_keeps_reused_workspace_blocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        '{"verification":{"reuse":{"outputs":["generated"]}}}'
    )
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()
    monkeypatch.setattr("des.runtime.spawn.default_timeout_seconds", lambda: 0.5)

    def terminate_only_leader(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    monkeypatch.setattr("des.runtime.spawn._reap_process_group", terminate_only_leader)
    command = (
        sys.executable,
        "-c",
        "import os, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print(os.getpgrp(), child.pid, flush=True); time.sleep(20)",
    )
    group = None
    try:
        outcome = DeliveryContinuationRunner()._with_candidate_worktree(
            root, candidate, (command,)
        )
        records = list((root / ".nwave/des/logs/native").glob("*.json"))
        assert len(records) == 1
        evidence = json.loads(records[0].read_bytes())[0]
        group, child = map(int, evidence["stdout"].split())
        # The printed group is bound to KERNEL metadata: the recorded child
        # must actually sit in that session before any signal is trusted.
        assert os.getsid(child) == group
        # Defense: the reuse workspace owns a SEPARATE process group; a
        # child that inherited THIS group means a product regression --
        # fail the ASSERT and clean up pid-safely, never killpg the runner.
        assert group != os.getpgrp(), (
            "native verification child inherited the runner's process "
            "group; reuse verification must own its own group"
        )
        os.killpg(group, 0)
        assert isinstance(outcome, DeliveryOutcome), outcome
        assert outcome.failure.what == "VerificationWritersUnquiescent"
        metadata = json.loads(
            (root / ".nwave/des/verification-reuse.json").read_bytes()
        )
        assert metadata["phase"] == "running"
        refused = DeliveryContinuationRunner()._with_candidate_worktree(
            root, candidate, ((sys.executable, "-c", "print('must not run')"),)
        )
        assert isinstance(refused, DeliveryOutcome), refused
        assert "interrupted native execution" in refused.failure.why
    finally:
        if group is not None:
            if group == os.getpgrp():
                os.kill(child, signal.SIGKILL)
            else:
                try:
                    os.killpg(group, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


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


def test_cold_candidate_measures_inside_the_configured_workspace(
    tmp_path: Path,
) -> None:
    """Cold isolation is a registered worktree under the configured root.

    The pre-workspace behaviour materialized the candidate under a fresh
    tmp directory; real candidate work now lives -- and is cleaned up --
    inside the project's own workspace, exactly like reuse.
    """
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()
    command = (sys.executable, "-c", "import os; print(os.getcwd())")

    outcome = DeliveryContinuationRunner()._with_candidate_worktree(
        root, candidate, (command,)
    )

    assert not isinstance(outcome, DeliveryOutcome), outcome
    _, evidence = outcome
    measured = Path(_only_stdout(evidence)).resolve()
    assert measured.is_relative_to((root / "lanes" / ".des-candidate").resolve())
    # The disposable checkout is gone: no residue, no registration.
    assert not measured.exists()
    registered = DeliveryContinuationRunner._git(
        root, "worktree", "list", "--porcelain"
    ).stdout
    assert measured.as_posix() not in registered


def test_cold_refuses_invalid_workspace_configuration_before_any_worktree(
    tmp_path: Path,
) -> None:
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        '{"verification":{"reuse":{"workspace":{"root":"/tmp/escape"}}}}'
    )
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()

    outcome = DeliveryContinuationRunner()._with_candidate_worktree(
        root,
        candidate,
        ((sys.executable, "-c", "print('must not run')"),),
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    assert outcome.failure.what == "VerificationWorkspaceUnavailable"
    assert not (root / "lanes").exists()


def test_cold_refuses_new_growth_when_budget_is_unmet(
    tmp_path: Path,
) -> None:
    """An unmet configured budget refuses NEW growth instead of stacking."""
    import json as json_module

    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        json_module.dumps(
            {"verification": {"reuse": {"workspace": {"cache_limit_bytes": 1}}}}
        )
    )
    # Unknown (unowned) bytes under the candidate root: preserved blockers.
    (root / "lanes" / ".des-candidate").mkdir(parents=True)
    (root / "lanes" / ".des-candidate" / "unknown-cache").write_text("x\n")
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()

    outcome = DeliveryContinuationRunner()._with_candidate_worktree(
        root,
        candidate,
        ((sys.executable, "-c", "print('must not run')"),),
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    assert outcome.failure.what == "WorkspaceBudgetExhausted"
    assert "budget unmet" in outcome.failure.why
    assert sorted(
        item.name for item in (root / "lanes" / ".des-candidate").iterdir()
    ) == ["unknown-cache"]


def test_reuse_refuses_measurement_when_budget_is_unmet(
    tmp_path: Path,
) -> None:
    """A warm reuse run also grows caches: budget failure gates it too."""
    import json as json_module

    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        json_module.dumps(
            {
                "verification": {
                    "reuse": {
                        "outputs": ["generated"],
                        "workspace": {"cache_limit_bytes": 1},
                    }
                }
            }
        )
    )
    # Unknown (unowned) generated bytes: preserved blockers over the limit.
    (root / "generated").mkdir()
    (root / "generated" / "unknown.bin").write_text("xx\n")
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()

    outcome = DeliveryContinuationRunner()._with_candidate_worktree(
        root,
        candidate,
        ((sys.executable, "-c", "print('must not run')"),),
    )

    assert isinstance(outcome, DeliveryOutcome), outcome
    assert outcome.failure is not None
    assert outcome.failure.what == "WorkspaceBudgetExhausted"
    assert not (root / "lanes").exists()


def test_cold_measurement_owns_its_process_group(tmp_path: Path) -> None:
    """The measured cold child is its OWN session leader, never the caller's.

    Positive group isolation: before this fix only the reuse path set the
    spawn reaping flags, so a cold verify's child inherited the CALLER's
    process group and any group cleanup could kill the runner.
    """
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()
    command = (sys.executable, "-c", "import os; print(os.getpgrp())")

    outcome = DeliveryContinuationRunner()._with_candidate_worktree(
        root, candidate, (command,)
    )

    assert not isinstance(outcome, DeliveryOutcome), outcome
    _, evidence = outcome
    child_group = int(_only_stdout(evidence))
    assert child_group != os.getpgrp()


def test_cold_keeps_worktree_and_names_recovery_when_writers_unquiescent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A receipt proves WHO; only the phase proves IDLE after a crash."""
    from des.adapters.driven.config.workspace_paths import CANDIDATE_RECEIPT
    from tests.des.unit.application.test_delivery_continuation import repo

    root = repo(tmp_path / "subject", "value.txt", "one\n")
    candidate = DeliveryContinuationRunner._git(
        root, "rev-parse", "HEAD"
    ).stdout.strip()
    monkeypatch.setattr("des.runtime.spawn.default_timeout_seconds", lambda: 0.5)

    def terminate_only_leader(pid: int) -> None:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    monkeypatch.setattr("des.runtime.spawn._reap_process_group", terminate_only_leader)
    command = (
        sys.executable,
        "-c",
        "import os, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(20)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "print(os.getpgrp(), child.pid, flush=True); time.sleep(20)",
    )
    group = None
    try:
        outcome = DeliveryContinuationRunner()._with_candidate_worktree(
            root, candidate, (command,)
        )
        records = list((root / ".nwave/des/logs/native").glob("*.json"))
        assert len(records) == 1
        evidence = json.loads(records[0].read_bytes())[0]
        group, child = map(int, evidence["stdout"].split())
        # The printed group is bound to KERNEL metadata: the recorded child
        # must actually sit in that session before any signal is trusted.
        assert os.getsid(child) == group
        # Defense: the product must own a SEPARATE process group. If a
        # regression makes the measured child inherit THIS group, the test
        # fails its ASSERT and cleans up pid-safely -- it never killpgs the
        # runner.
        assert group != os.getpgrp(), (
            "native verification child inherited the runner's process "
            "group; cold verification must own its own group"
        )
        os.killpg(group, 0)
        kept = sorted((root / "lanes" / ".des-candidate").iterdir())
        assert len(kept) == 1, kept
        receipt = json.loads((kept[0] / CANDIDATE_RECEIPT).read_text())
        assert receipt["phase"] != "idle"
        assert receipt["candidate"] == candidate
        assert receipt["workspace"] == str(kept[0])
        assert isinstance(outcome, DeliveryOutcome), outcome
        assert outcome.failure is not None
        assert outcome.failure.what == "CandidateWritersUnquiescent"
        assert str(kept[0]) in outcome.failure.why
        assert str(kept[0]) in outcome.failure.how
    finally:
        if group is not None:
            if group == os.getpgrp():
                os.kill(child, signal.SIGKILL)
            else:
                try:
                    os.killpg(group, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    pass


def test_cold_refuses_candidate_placement_across_git_owners(
    tmp_path: Path,
) -> None:
    """A configured workspace of another repository never receives real work."""
    from des.adapters.driven.config.workspace_paths import (
        DEFAULT_WORKSPACE_ROOT,
        WorkspacePaths,
    )
    from tests.des.unit.application.test_delivery_continuation import repo

    principal = repo(tmp_path / "principal", "value.txt", "one\n")
    foreign = repo(tmp_path / "foreign", "other.txt", "two\n")
    runner = DeliveryContinuationRunner()
    paths = WorkspacePaths(
        root=foreign,
        lanes=foreign / DEFAULT_WORKSPACE_ROOT,
        candidate=foreign / DEFAULT_WORKSPACE_ROOT / ".des-candidate",
        verification=foreign / DEFAULT_WORKSPACE_ROOT / ".des-verification",
        evidence=foreign / ".nwave" / "des",
        outputs=None,
        adopted=(),
        cache_limit_bytes=None,
        automatic=False,
    )

    with pytest.raises(ValueError, match="different Git repository"):
        runner._cold_candidate_directory(paths, principal)
