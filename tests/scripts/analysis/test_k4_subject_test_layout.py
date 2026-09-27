"""The fixture declares the subject's real test layout, once, and hides it.

DES reads test paths from the subject's own `pyproject.toml` and otherwise
assumes `tests/`. This subject keeps 234 test files under `hc/<app>/tests/`
and ships no such file, so every acceptance-design write under `hc/api/tests/`
was refused as ProductionScopeDrift: one bought turn and one rework cycle per
run, measured in the first campaign where the method actually ran.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))

import prepare_examiner_fixture as pef

from des.domain.request_stimulus import declared_test_paths


def test_a_subject_without_a_declaration_gets_its_real_layout(tmp_path) -> None:
    written = pef._declare_subject_test_layout(tmp_path)
    assert written == ("pyproject.toml",)
    text = (tmp_path / "pyproject.toml").read_text(encoding="utf-8")
    assert declared_test_paths(text) == ("hc",)


def test_a_subjects_own_declaration_is_never_overruled(tmp_path) -> None:
    own = '[tool.pytest.ini_options]\ntestpaths = ["somewhere"]\n'
    (tmp_path / "pyproject.toml").write_text(own, encoding="utf-8")
    written = pef._declare_subject_test_layout(tmp_path)
    assert written == ()
    assert (tmp_path / "pyproject.toml").read_text(encoding="utf-8") == own


def test_what_the_fixture_wrote_is_excluded_from_the_delivery_diff(tmp_path) -> None:
    """Setup must never read as delivered work in the blind packet."""
    (tmp_path / ".git" / "info").mkdir(parents=True)
    pef._add_exclude_entries(tmp_path, extra=("pyproject.toml",))
    excluded = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert "pyproject.toml" in excluded.splitlines()


def test_the_default_without_a_declaration_is_the_wrong_one_for_this_subject() -> None:
    """The reason this file exists: DES alone would look in `tests/`."""
    assert "hc" not in declared_test_paths(None)


def test_the_declared_layout_names_the_settings_the_declared_runner_needs() -> None:
    """pytest-django reads DJANGO_SETTINGS_MODULE from the ini section; without it
    every Django TestCase errors before its first assertion."""
    assert 'DJANGO_SETTINGS_MODULE = "hc.settings"' in pef.SUBJECT_TEST_LAYOUT
    assert declared_test_paths(pef.SUBJECT_TEST_LAYOUT) == ("hc",)


def test_the_fixture_venv_answers_at_the_path_des_reads(tmp_path) -> None:
    """Run 13: DES found no `.venv`, fell back to its own interpreter, and every
    pytest oracle exited 1 on `No module named pytest`."""
    (tmp_path / pef._VENV_DIR_NAME / "bin").mkdir(parents=True)
    pef._link_subject_venv(tmp_path)
    link = tmp_path / pef.SUBJECT_VENV_LINK
    assert link.is_symlink()
    assert link.resolve() == (tmp_path / pef._VENV_DIR_NAME).resolve()
    assert (link / "bin").is_dir()


def test_a_subjects_own_venv_is_never_replaced(tmp_path) -> None:
    (tmp_path / pef.SUBJECT_VENV_LINK).mkdir()
    pef._link_subject_venv(tmp_path)
    assert not (tmp_path / pef.SUBJECT_VENV_LINK).is_symlink()


def test_the_link_is_excluded_from_the_delivery_diff(tmp_path) -> None:
    (tmp_path / ".git" / "info").mkdir(parents=True)
    pef._add_exclude_entries(tmp_path)
    excluded = (tmp_path / ".git" / "info" / "exclude").read_text(encoding="utf-8")
    assert pef.SUBJECT_VENV_LINK in excluded.splitlines()


def _runner_probe(monkeypatch, tmp_path, *, exit_code: int, writes_report: bool):
    (tmp_path / pef._VENV_DIR_NAME).mkdir()
    seen: list[list[str]] = []

    def _fake_run(argv, cwd, timeout=None):
        seen.append(list(argv))
        if writes_report:
            report = next(a for a in argv if a.startswith("--junitxml=")).split("=", 1)[
                1
            ]
            Path(report).write_text("<testsuite tests='1' errors='0' failures='0'/>")
        return exit_code, "tail"

    monkeypatch.setattr(pef, "_run", _fake_run)
    return seen


def test_the_declared_runner_probe_runs_the_form_des_uses(
    tmp_path, monkeypatch
) -> None:
    seen = _runner_probe(monkeypatch, tmp_path, exit_code=0, writes_report=True)
    pef._probe_declared_runner(tmp_path / "py", tmp_path)
    (argv,) = seen
    assert argv[1:4] == ["-m", "pytest", pef._DECLARED_RUNNER_PROBE_MODULE]
    assert any(a.startswith("--junitxml=") for a in argv)


def test_a_runner_that_exits_red_refuses_loud(tmp_path, monkeypatch) -> None:
    _runner_probe(monkeypatch, tmp_path, exit_code=1, writes_report=True)
    with pytest.raises(SystemExit) as refused:
        pef._probe_declared_runner(tmp_path / "py", tmp_path)
    assert "WHAT:" in str(refused.value) and "HOW:" in str(refused.value)


def test_a_green_exit_without_a_report_is_not_a_runner(tmp_path, monkeypatch) -> None:
    """Exit status alone cannot tell a passing session from one that never started."""
    _runner_probe(monkeypatch, tmp_path, exit_code=0, writes_report=False)
    with pytest.raises(SystemExit) as refused:
        pef._probe_declared_runner(tmp_path / "py", tmp_path)
    assert "report absent" in str(refused.value)


def test_the_fragment_names_the_interpreter_des_can_resolve_in_a_candidate(
    tmp_path, monkeypatch
) -> None:
    """2026-09-14 resume: every vector that copied `k4-fixture-venv/bin/python`
    from the fragment was refused at verify with VerificationExecutableAbsent."""
    monkeypatch.setattr(pef, "_installed_dependency_names", lambda *_: ["Django"])
    fragment = pef.render_project_fragment(tmp_path / "py", tmp_path)
    assert pef._VENV_DIR_NAME not in fragment
    assert "`python manage.py test" in fragment
    assert "`python -m pytest <oracle file> -q`" in fragment
