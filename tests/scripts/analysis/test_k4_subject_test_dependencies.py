"""K4 matrix row 4 continuation -- subject test dependency provisioning.

Real installed run 4, crafter #2 (subagent `aa7125e162c8f37b2`): BASELINE ran
the contract's literal verification command,
`k4-fixture-venv/bin/python manage.py test hc.api.tests.test_sendalerts
hc.api.tests.test_update_check`, and hit `ModuleNotFoundError: No module
named 'time_machine'` importing the SUBJECT's own pre-existing
`hc/api/tests/test_sendalerts.py:6`. `time-machine==3.2.0` is a REAL subject
dependency -- declared in the subject's own `requirements-dev.txt` at the
pinned revision, not something the contract invented (that would be a
different defect: an oracle depending on something the subject never
declares). The crafter tried `pip install time-machine==3.2.0` and hit a
sandboxed-network `ProxyError`/403: BASELINE cannot repair a missing test
dependency mid-delivery.

`prepare_examiner_fixture._ensure_venv` installed only `requirements.txt`
(production deps), never `requirements-dev.txt` (test-only deps) -- this is
the gap. A REAL scratch-venv reproduction (real clone of the pinned
`healthchecks` revision, real `pip install`) additionally found that
installing `requirements-dev.txt` VERBATIM fails: `mysqlclient` needs MySQL
client headers this sandbox does not carry ("Can not find valid pkg-config
name"), and nothing under `hc/` ever imports `MySQLdb`/`mysqlclient` (`grep
-rln "MySQLdb|mysqlclient" hc/` -- zero hits, verified against the pinned
checkout). `_DEV_REQUIREMENTS_SKIP` excludes exactly that one named package;
these tests exercise the exclusion logic and the two production seams
(`_ensure_venv`'s dev-requirements install, `_probe_subject_test_
dependencies`'s LOUD refusal) through captured/faked subprocess calls, per
this suite's own convention (see `test_k4_subject_revision_pin.py`) of never
spending a real network clone or pip install in the committed test suite --
that verification was done by hand against a real scratch venv instead.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.analysis.k4 import prepare_examiner_fixture as pef


def test_dev_requirement_lines_excludes_only_the_named_unbuildable_package():
    text = (
        "apprise==1.12.0\n"
        "# a comment line, dropped\n"
        "\n"
        "mysqlclient==2.2.8\n"
        "time-machine==3.2.0\n"
        "types-Markdown\n"
    )

    kept = pef._dev_requirement_lines_excluding_unbuildable(text)

    assert kept == ["apprise==1.12.0", "time-machine==3.2.0", "types-Markdown"], (
        "mysqlclient must be the ONLY line dropped; comments/blanks skipped, "
        "every other requirement line preserved verbatim"
    )


def test_dev_requirement_lines_is_a_no_op_without_the_skipped_package():
    text = "time-machine==3.2.0\nMarkdown==3.10.2\n"

    assert pef._dev_requirement_lines_excluding_unbuildable(text) == [
        "time-machine==3.2.0",
        "Markdown==3.10.2",
    ]


def test_ensure_venv_installs_requirements_dev_minus_the_skip_list(
    tmp_path, monkeypatch
):
    """Captures every `_run` invocation instead of touching pip/network --
    this suite's established convention for the pinned SUT (see
    `test_k4_subject_revision_pin.py`'s `_fake_clone_runner`)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "requirements.txt").write_text("Django==6.1\n", encoding="utf-8")
    (workspace / "requirements-dev.txt").write_text(
        "mysqlclient==2.2.8\ntime-machine==3.2.0\n", encoding="utf-8"
    )

    invoked: list[list[str]] = []

    def _fake_run(argv, cwd, timeout=None):
        invoked.append(list(argv))
        if argv[0] == pef.sys.executable and argv[1] == "-m" and argv[2] == "venv":
            # Real venv creation is cheap and needed so venv_dir/bin/pip
            # exists as a path venv_python.exists() can observe correctly.
            import subprocess

            subprocess.run(argv, check=True)
        return 0, ""

    monkeypatch.setattr(pef, "_run", _fake_run)

    venv_python = pef._ensure_venv(workspace)

    pip_calls = [c for c in invoked if len(c) > 1 and c[1] == "install"]
    assert len(pip_calls) == 2, f"expected exactly 2 pip installs, got {pip_calls}"
    assert pip_calls[0][-1] == "requirements.txt"

    filtered_req_path = Path(pip_calls[1][-1])
    assert filtered_req_path.parent == workspace / pef._VENV_DIR_NAME
    filtered_text = filtered_req_path.read_text(encoding="utf-8")
    assert "time-machine==3.2.0" in filtered_text
    assert "mysqlclient" not in filtered_text
    assert venv_python == workspace / pef.VENV_PYTHON


def test_ensure_venv_skips_dev_requirements_install_when_file_absent(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "requirements.txt").write_text("Django==6.1\n", encoding="utf-8")

    invoked: list[list[str]] = []

    def _fake_run(argv, cwd, timeout=None):
        invoked.append(list(argv))
        if argv[0] == pef.sys.executable and argv[1] == "-m" and argv[2] == "venv":
            import subprocess

            subprocess.run(argv, check=True)
        return 0, ""

    monkeypatch.setattr(pef, "_run", _fake_run)

    pef._ensure_venv(workspace)

    pip_calls = [c for c in invoked if len(c) > 1 and c[1] == "install"]
    assert len(pip_calls) == 1, (
        f"no requirements-dev.txt on disk must mean no second pip install, "
        f"got {pip_calls}"
    )


def test_probe_subject_test_dependencies_refuses_loud_on_modulenotfounderror(
    tmp_path, monkeypatch
):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    venv_python = workspace / "k4-fixture-venv" / "bin" / "python"

    monkeypatch.setattr(
        pef,
        "_run",
        lambda argv, cwd, timeout=None: (
            1,
            "ModuleNotFoundError: No module named 'time_machine'",
        ),
    )

    with pytest.raises(SystemExit) as excinfo:
        pef._probe_subject_test_dependencies(venv_python, workspace)

    message = str(excinfo.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message
    assert "ModuleNotFoundError" in message


def test_probe_subject_test_dependencies_passes_when_clean(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    venv_python = workspace / "k4-fixture-venv" / "bin" / "python"

    monkeypatch.setattr(
        pef,
        "_run",
        lambda argv, cwd, timeout=None: (0, "Ran 12 tests in 1.2s\n\nOK"),
    )

    pef._probe_subject_test_dependencies(venv_python, workspace)  # must not raise


def test_probe_subject_test_dependencies_ignores_unrelated_test_failures(
    tmp_path, monkeypatch
):
    """A genuine test FAILURE (not a missing dependency) is a different
    concern this probe does not own -- it must not raise on ordinary
    assertion failures."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    venv_python = workspace / "k4-fixture-venv" / "bin" / "python"

    monkeypatch.setattr(
        pef,
        "_run",
        lambda argv, cwd, timeout=None: (
            1,
            "FAIL: test_something (hc.api.tests.test_foo.FooTest)\n"
            "AssertionError: 1 != 2",
        ),
    )

    pef._probe_subject_test_dependencies(venv_python, workspace)  # must not raise


def test_prepare_delivery_runs_the_dependency_probe_between_migrate_and_exclude(
    tmp_path, monkeypatch
):
    """Wiring check: `prepare_delivery` must call the new probe -- a
    silent-skip here would leave the whole fix unreachable from the one
    real caller (`delivery_setup_step`, invoked by both arms)."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    calls: list[str] = []

    monkeypatch.setattr(
        pef, "_ensure_venv", lambda ws: calls.append("ensure_venv") or Path("/fake")
    )
    monkeypatch.setattr(
        pef, "_migrate", lambda venv_python, ws: calls.append("migrate")
    )
    monkeypatch.setattr(
        pef,
        "_probe_subject_test_dependencies",
        lambda venv_python, ws: calls.append("probe"),
    )
    monkeypatch.setattr(pef, "_add_exclude_entries", lambda ws: calls.append("exclude"))

    pef.prepare_delivery(workspace)

    assert calls == ["ensure_venv", "migrate", "probe", "exclude"], (
        "the dependency probe must run after migrate (needs a migrated DB) "
        "and before the exclude/cleanup step"
    )
