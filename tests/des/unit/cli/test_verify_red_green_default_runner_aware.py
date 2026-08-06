"""verify-red-green-default-runner-aware (#62, bugfix) -- active-RED AT.

Pins the DEFECT and the FIX contract from
docs/feature/verify-red-green-default-runner-aware/feature-delta.md:

The launcher-bound module default ``_DEFAULT_RUN_CMD`` binds to
``sys.executable`` -- the interpreter that LAUNCHED verify-red-green, not the
TARGET ``--repo``'s environment. On a uv/poetry/pipenv target repo that runs
pytest in the WRONG env. The fix derives the default from the target repo's
Python packaging manifest via a helper ``_default_run_cmd(repo: Path) -> str``
(filesystem-only, no shelling out):

  uv.lock (or pyproject.toml [tool.uv])  -> "uv run ... pytest ..."
  poetry.lock                            -> "poetry run pytest ..."
  Pipfile / Pipfile.lock                 -> "pipenv run pytest ..."
  else (no recognized manifest)          -> the CURRENT sys.executable -m
                                             pytest form, byte-unchanged
  an explicit --run-cmd ALWAYS wins over the derivation (unchanged).

RED-not-BROKEN: ``_default_run_cmd`` does not exist yet on the module, so
each scenario-1..4 test fails with AttributeError INSIDE the test body (a
semantic failure -- the missing derivation) rather than at collection time;
the module import itself (``from des.cli import verify_red_green``) succeeds
today.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

from des.cli import verify_red_green as vrg


def _tokens(cmd: object) -> list[str]:
    """Normalize a run-cmd (str template or tuple/list of parts) to tokens."""
    if isinstance(cmd, str):
        return shlex.split(cmd)
    return [str(part) for part in cmd]  # type: ignore[union-attr]


def _uv_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (tmp_path / "uv.lock").write_text("# uv lock file\n")
    return tmp_path


def _poetry_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text('[tool.poetry]\nname = "x"\n')
    (tmp_path / "poetry.lock").write_text("# poetry lock file\n")
    return tmp_path


def _pipenv_repo(tmp_path: Path) -> Path:
    (tmp_path / "Pipfile").write_text("[packages]\n")
    return tmp_path


def _plain_repo(tmp_path: Path) -> Path:
    # No uv.lock / poetry.lock / Pipfile anywhere -- deliberately unrecognized.
    (tmp_path / "setup.py").write_text("# legacy setup.py only\n")
    return tmp_path


def test_uv_target_repo_derives_uv_run_pytest_default(tmp_path: Path) -> None:
    repo = _uv_repo(tmp_path)

    tokens = _tokens(vrg._default_run_cmd(repo))

    assert tokens[0] == "uv"
    assert tokens[1] == "run"
    assert "pytest" in tokens
    assert any("{test_file}" in t for t in tokens)
    assert any("{junit_out}" in t for t in tokens)
    # Not the launcher-bound sys.executable form.
    assert sys.executable not in tokens
    assert "-m" not in tokens


def test_poetry_target_repo_derives_poetry_run_pytest_default(
    tmp_path: Path,
) -> None:
    repo = _poetry_repo(tmp_path)

    tokens = _tokens(vrg._default_run_cmd(repo))

    assert tokens[0] == "poetry"
    assert tokens[1] == "run"
    assert "pytest" in tokens
    assert any("{test_file}" in t for t in tokens)
    assert any("{junit_out}" in t for t in tokens)
    assert sys.executable not in tokens
    assert "uv" not in tokens


def test_pipenv_target_repo_derives_pipenv_run_pytest_default(
    tmp_path: Path,
) -> None:
    repo = _pipenv_repo(tmp_path)

    tokens = _tokens(vrg._default_run_cmd(repo))

    assert tokens[0] == "pipenv"
    assert tokens[1] == "run"
    assert "pytest" in tokens
    assert any("{test_file}" in t for t in tokens)
    assert any("{junit_out}" in t for t in tokens)
    assert sys.executable not in tokens
    assert "uv" not in tokens
    assert "poetry" not in tokens


def test_plain_repo_falls_back_to_sys_executable_not_uv(tmp_path: Path) -> None:
    """NEGATIVE: no recognized manifest -> current sys.executable -m pytest
    form, byte-unchanged -- never uv/poetry/pipenv, never bare 'pytest'."""
    repo = _plain_repo(tmp_path)

    tokens = _tokens(vrg._default_run_cmd(repo))

    assert tokens == list(vrg._DEFAULT_RUN_CMD)
    assert tokens[0] == sys.executable
    assert tokens[1] == "-m"
    assert tokens[2] == "pytest"
    assert "uv" not in tokens
    assert "poetry" not in tokens
    assert "pipenv" not in tokens


def test_explicit_run_cmd_overrides_manifest_derivation_passthrough(
    tmp_path: Path, monkeypatch
) -> None:
    """NEGATIVE: an explicit --run-cmd wins VERBATIM even on a repo whose
    manifest would otherwise derive a uv/poetry/pipenv default."""
    repo = _uv_repo(tmp_path)
    (repo / "test_x.py").write_text("# content v1\n")

    captured: dict[str, object] = {}

    def _fake_run_and_collect(
        repo_arg: Path, test_file_arg: Path, run_cmd: object
    ) -> int:
        captured["run_cmd"] = run_cmd
        return 0

    monkeypatch.setattr(vrg, "_run_and_collect", _fake_run_and_collect)

    exit_code = vrg.main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--record-red",
            "--run-cmd",
            "custom-runner {test_file} {junit_out}",
        ]
    )

    assert exit_code == 0
    tokens = _tokens(captured["run_cmd"])
    assert tokens[0] == "custom-runner"
    assert "uv" not in tokens
    assert "run" not in tokens


@pytest.mark.parametrize("foreign_manifest", ("Cargo.toml", "go.mod", "package.json"))
def test_default_refuses_ambiguous_polyglot_root_even_with_python_tooling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    foreign_manifest: str,
) -> None:
    """A Python tool file cannot authorize inferred pytest in a polyglot root."""
    repo = _uv_repo(tmp_path)
    (repo / foreign_manifest).write_text("# foreign project marker\n")
    (repo / "test_x.py").write_text("def test_x(): pass\n")

    def _must_not_run(*_args: object, **_kwargs: object) -> int:
        raise AssertionError("ambiguous layout must refuse before launching pytest")

    monkeypatch.setattr(vrg, "_run_and_collect", _must_not_run)

    exit_code = vrg.main(
        ["--repo", str(repo), "--test-file", "test_x.py", "--record-red"]
    )

    output = capsys.readouterr().out
    assert exit_code == 2
    assert foreign_manifest in output
    assert "will not infer pytest" in output
