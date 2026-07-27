"""Tests for the dispatch-lane SSOT drift leg wired into
scripts/hooks/check_documentation_freshness.py.

techdebt.md row dispatch-lane-ssot-drift-check-never-invoked-outside-its-own-test:
``check_lane_profile_drift`` (src/des/application/dispatch_lane_ssot.py) was
called ONLY by its own unit test -- no CLI, no CI job, no pre-push hook -- so a
real YAML<->LANE_PROFILES drift could ship silently. This pre-push hook is the
wiring: it now consults ``check_lane_profile_drift`` as a third agreement leg
alongside the existing doc-staleness and registry<->runtime legs, and fails
loud (non-zero exit, named disagreements) when the two sources disagree.

``_load_docgen`` and ``check_lane_profile_drift`` are monkeypatched so this
test is deterministic and independent of the real repo's current doc/registry
state -- only the NEW lane-drift leg is under test here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest


_HOOK_PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "hooks"
    / "check_documentation_freshness.py"
)


def _load():
    spec = importlib.util.spec_from_file_location(
        "check_documentation_freshness", _HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


_HOOK = _load()


def _fake_docgen():
    return SimpleNamespace(
        run_pipeline=lambda root, output_dir: [],
        check_pages=lambda pages, output_dir: [],
        check_registry_runtime_agreement=lambda root: [],
    )


def test_no_lane_drift_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """No stale docs, no registry disagreement, no lane drift -> exit 0."""
    monkeypatch.setattr(_HOOK, "_load_docgen", _fake_docgen)
    monkeypatch.setattr(_HOOK, "check_lane_profile_drift", lambda root: [])

    assert _HOOK.main() == 0


def test_lane_drift_fails_and_names_the_disagreement(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A non-empty lane-drift list fails the hook and names the drift."""
    monkeypatch.setattr(_HOOK, "_load_docgen", _fake_docgen)
    monkeypatch.setattr(
        _HOOK,
        "check_lane_profile_drift",
        lambda root: ["lane 'prefactoring' required_sections differ: only-in-YAML=()"],
    )

    exit_code = _HOOK.main()
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "dispatch-lane SSOT drift detected" in captured.err
    assert "prefactoring" in captured.err
