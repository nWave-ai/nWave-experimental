"""Hidden-suite hygiene: `run_acceptance.examine` must never leave the
generated `hc/api/tests/test_k4_acceptance.py` behind, and must never delete
one that was already there.

Contaminated blind review found this: the hidden test stayed in the delivery
tree after every run, so a reviewer reading the tree could see it. The base
version copies the suite in and never removes it -- these tests go RED against
that and GREEN once `examine` cleans up in a `finally`, regardless of whether
the hidden suite passed, failed, raised, or timed out.

Run: uv run pytest -q tests/scripts/analysis/test_run_acceptance_hygiene.py
"""

from __future__ import annotations

import pytest

from scripts.analysis.k4 import run_acceptance as ra


_TARGET = ra._SUITE_TARGET  # hc/api/tests/test_k4_acceptance.py, relative


def _workspace(tmp_path):
    workspace = tmp_path / "delivery"
    (workspace / "hc" / "api" / "tests").mkdir(parents=True)
    (workspace / "manage.py").write_text("# django manage.py stub\n")
    suite = tmp_path / "suite.py"
    suite.write_text("# hidden suite\n")
    return workspace, suite


def _stub_run(*, feature=(0, "OK"), regression=(0, "OK"), raise_on=None):
    """A drop-in for `_run` that skips real subprocesses entirely."""

    def fake(argv, cwd, timeout=2400):
        joined = " ".join(argv)
        if raise_on and raise_on in joined:
            raise RuntimeError(f"boom during: {joined}")
        if "venv" in argv:
            return 0, ""
        if "install" in argv:
            return 0, ""
        if ra._SUITE_LABEL in argv:
            return feature
        if "--exclude-tag" in argv:
            return regression
        raise AssertionError(f"unexpected argv: {argv}")

    return fake


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="both-suites-pass"),
        pytest.param({"feature": (1, "FAILED (failures=1)")}, id="hidden-suite-fails"),
        pytest.param(
            {"regression": (1, "FAILED (failures=2)")}, id="subject-suite-fails"
        ),
        pytest.param(
            {"feature": (124, "TIMEOUT after 2400s")}, id="hidden-suite-times-out"
        ),
    ],
)
def test_generated_suite_is_always_removed(tmp_path, monkeypatch, kwargs):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run(**kwargs))

    ra.examine(workspace, suite)

    assert not (workspace / _TARGET).exists()


def test_generated_suite_is_removed_even_if_the_run_raises(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run(raise_on=ra._SUITE_LABEL))

    with pytest.raises(RuntimeError):
        ra.examine(workspace, suite)

    assert not (workspace / _TARGET).exists()


def test_preexisting_suite_file_is_a_refusal_not_a_deletion(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    preexisting = workspace / _TARGET
    preexisting.write_text("pre-existing content, not ours to touch\n")
    monkeypatch.setattr(
        ra,
        "_run",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    accepted, evidence = ra.examine(workspace, suite)

    assert accepted is False
    assert "already contains" in evidence
    assert preexisting.read_text() == "pre-existing content, not ours to touch\n"


def test_accepted_requires_both_suites_to_pass(tmp_path, monkeypatch):
    workspace, suite = _workspace(tmp_path)
    monkeypatch.setattr(ra, "_run", _stub_run())

    accepted, _ = ra.examine(workspace, suite)

    assert accepted is True
    assert not (workspace / _TARGET).exists()
