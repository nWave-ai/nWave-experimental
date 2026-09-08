"""The touched-file commit gate selects real tests, and is actually WIRED.

Guards ``scripts/hooks/pytest_touched_files.py``, the pre-commit gate that
replaced marker-based selection after the 2026-08-22 census measured the local
safety net at 78 of 6548 tests with NO tier covered
(``F-LOCAL-GATE-COVERAGE-1-2-PERCENT``).

Two properties are asserted, and the second is the one that rots: a gate that
exists but is not wired into ``.pre-commit-config.yaml`` at the ``pre-commit``
stage protects nothing (catalogued != wired).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = PROJECT_ROOT / "scripts" / "hooks" / "pytest_touched_files.py"


def _load_gate():
    spec = importlib.util.spec_from_file_location("pytest_touched_files", GATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def gate():
    return _load_gate()


def test_package_init_yields_no_module_name(gate):
    """``des`` as a bare package name matches every test file's text.

    Keying on it silently degenerates the selector into a full-suite run, which
    is exactly the box-saturating behaviour this gate exists to avoid.
    """
    assert gate.module_names("src/des/__init__.py") == set()


def test_source_file_resolves_to_both_import_spellings(gate):
    assert gate.module_names("src/des/application/capacity_snapshot.py") == {
        "des.application.capacity_snapshot",
        "src.des.application.capacity_snapshot",
    }


def test_touching_a_source_file_selects_the_test_that_references_it(gate):
    runnable, _deferred, uncovered = gate.select(
        ["src/des/application/capacity_snapshot.py"], PROJECT_ROOT
    )
    assert "tests/des/unit/application/test_capacity_snapshot.py" in runnable
    assert uncovered == []


def test_touching_a_test_file_always_runs_it(gate):
    target = "tests/des/unit/application/test_capacity_snapshot.py"
    runnable, _deferred, _uncovered = gate.select([target], PROJECT_ROOT)
    assert runnable == [target]


def test_docker_and_compile_tiers_are_deferred_not_run(gate):
    """The exclusion must be visible in ``deferred``, never silently dropped.

    The probe must be a COLLECTIBLE e2e file. An earlier version of this test
    took ``sorted(...)[0]``, which is ``tests/des/e2e/__init__.py`` -- not a
    file pytest collects, so the selector correctly expands it to its whole
    subtree instead of returning it. Asserting on a non-collectible probe made
    the test assert the selector's OLD, defective behaviour.
    """
    e2e_files = sorted(
        rel
        for rel in (
            p.relative_to(PROJECT_ROOT).as_posix()
            for p in (PROJECT_ROOT / "tests").rglob("*.py")
            if "/e2e/" in p.as_posix() and "__pycache__" not in p.parts
        )
        if gate.is_collectible(rel)
    )
    assert e2e_files, "no e2e test files found -- the exclusion rule would be vacuous"
    runnable, deferred, _uncovered = gate.select([e2e_files[0]], PROJECT_ROOT)
    assert runnable == []
    assert deferred == [e2e_files[0]]


def test_prose_only_paths_select_nothing_and_are_not_reported_uncovered(gate):
    runnable, deferred, uncovered = gate.select(
        ["docs/product/backlog.md"], PROJECT_ROOT
    )
    assert (runnable, deferred, uncovered) == ([], [], [])


def test_an_unmapped_path_is_declared_uncovered_out_loud(gate):
    _runnable, _deferred, uncovered = gate.select(
        ["some/unknown/place/thing.conf"], PROJECT_ROOT
    )
    assert any("some/unknown/place/thing.conf" in entry for entry in uncovered)


def test_the_gate_is_wired_at_the_precommit_stage():
    config = (PROJECT_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    assert "id: pytest-touched-files" in config, (
        "the touched-file gate is not registered in .pre-commit-config.yaml"
    )
    block = config.split("id: pytest-touched-files", 1)[1].split("- id:", 1)[0]
    assert "pytest_touched_files.py" in block
    assert "stages: [pre-commit]" in block, (
        "the gate must run at the pre-commit stage — a manual/pre-push-only "
        "stage is how pytest-quick-tiers became a gate that never fires"
    )
