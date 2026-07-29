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
    """Stub honouring the FULL ``docgen`` surface ``main()`` consults --
    four agreement legs (stale / disagreements / lane-drift / generated-
    region), each producing an empty-findings default so both tests below
    exercise ONLY the lane-drift leg their docstring promises.

    Kept in sync with ``scripts/docgen.py``'s real signatures deliberately
    (not import-bound) -- see ``test_fake_docgen_matches_real_docgen_surface``
    below, which fails loud the moment ``main()`` grows a 5th leg this stub
    does not yet cover, instead of the bare ``AttributeError`` this file's
    own history already produced once.
    """
    return SimpleNamespace(
        run_pipeline=lambda root, output_dir: [],
        check_pages=lambda pages, output_dir: [],
        check_registry_runtime_agreement=lambda root: [],
        scan=lambda root, *, public_only=False: {
            "agents": [],
            "commands": [],
            "skills": [],
            "templates": [],
            "orchestrator_affordance": [],
        },
        project_generated_regions=lambda root, asset_paths: [],
        check_generated_regions=lambda root, projections: [],
    )


def test_fake_docgen_matches_real_docgen_surface() -> None:
    """The stub must expose every ``docgen`` attribute ``main()`` reads --
    a future 5th leg growing ``main()`` without a matching stub attribute
    must fail HERE, with a named missing-attribute list, rather than as a
    bare ``AttributeError`` deep inside ``main()`` (this file's own history:
    slice-04 added the generated-region leg and the stub silently fell out
    of sync until the two tests above broke on an opaque trace)."""
    import ast

    tree = ast.parse(_HOOK_PATH.read_text(encoding="utf-8"))
    main_func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    )
    docgen_attrs = {
        node.attr
        for node in ast.walk(main_func)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "docgen"
    }

    stub_attrs = set(vars(_fake_docgen()).keys())
    missing = docgen_attrs - stub_attrs

    assert not missing, (
        f"_fake_docgen() is missing attribute(s) {sorted(missing)} that "
        f"main() now reads on the real docgen module -- extend the stub"
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
