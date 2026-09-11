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
import json
import os
import shutil
import subprocess
import sys
import uuid
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


def _native_gate_probe(
    paths: list[str],
    *options: str,
    pytest_addopts: str = "-x",
    evidence_dir: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    """Drive the public hook script, including its real pytest subprocess."""
    env = {
        **os.environ,
        # The diagnostic command must override this ambient early-stop option.
        "PYTEST_ADDOPTS": pytest_addopts,
    }
    if evidence_dir is not None:
        env["NWAVE_TOUCHED_FILES_EVIDENCE_DIR"] = str(evidence_dir)
    return subprocess.run(
        [sys.executable, str(GATE), *options, *paths],
        cwd=PROJECT_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=60,
    )


def test_public_diagnostic_mode_runs_the_complete_selected_scope():
    """Two unrelated failures distinguish diagnosis from the fail-fast hook.

    This is a public-script probe: the hook chooses its files and launches the
    repository's real pytest command. It does not assert implementation kwargs
    or replace the subprocess with a mock.
    """
    probe_dir = PROJECT_ROOT / "tests" / "build" / f"p2_native_probe_{uuid.uuid4().hex}"
    probe_dir.mkdir()
    first = probe_dir / "test_first_failure.py"
    second = probe_dir / "test_second_failure.py"
    empty = probe_dir / "test_empty.py"
    relative = [path.relative_to(PROJECT_ROOT).as_posix() for path in (first, second)]
    try:
        first.write_text("def test_first_independent_failure():\n    assert False\n")
        second.write_text("def test_second_independent_failure():\n    assert False\n")

        diagnostic = _native_gate_probe(
            relative,
            "--diagnose",
            pytest_addopts="-x -k test_name_that_does_not_exist",
        )
        diagnostic_output = diagnostic.stdout + diagnostic.stderr
        assert diagnostic.returncode == 1
        assert "test_first_independent_failure" in diagnostic_output
        assert "test_second_independent_failure" in diagnostic_output
        assert "--maxfail=0" in diagnostic_output
        assert "not whole-project or full-case coverage" in diagnostic_output

        ordinary = _native_gate_probe(relative)
        ordinary_output = ordinary.stdout + ordinary.stderr
        assert ordinary.returncode == 1
        assert "test_first_independent_failure" in ordinary_output
        assert "test_second_independent_failure" not in ordinary_output

        first.write_text("def test_first_independent_success():\n    assert True\n")
        second.write_text("def test_second_independent_success():\n    assert True\n")
        successful = _native_gate_probe(relative, "--diagnose")
        assert successful.returncode == 0
        assert "Diagnostic touched-file scope: green." in successful.stdout

        mixed = _native_gate_probe(
            [relative[0], "some/unknown/place/thing.conf"], "--diagnose"
        )
        mixed_output = mixed.stdout + mixed.stderr
        assert mixed.returncode == 1
        assert "UNCOVERED: some/unknown/place/thing.conf" in mixed_output
        assert (
            "DIAGNOSTIC INCOMPLETE: selected runnable test files passed" in mixed_output
        )
        assert "Diagnostic touched-file scope: green." not in mixed_output

        empty.write_text("VALUE = 1\n")
        empty_relative = empty.relative_to(PROJECT_ROOT).as_posix()
        zero_collected = _native_gate_probe([empty_relative], "--diagnose")
        assert zero_collected.returncode == 1
        assert "DIAGNOSTIC INCOMPLETE: pytest collected zero tests" in (
            zero_collected.stdout + zero_collected.stderr
        )
        assert "green" not in (zero_collected.stdout + zero_collected.stderr).lower()
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def test_diagnostic_empty_or_deferred_scope_is_loud_and_incomplete(gate, capsys):
    """No launched test run is distinguishable from pytest collecting zero."""
    deferred_target = next(
        path.relative_to(PROJECT_ROOT).as_posix()
        for path in sorted((PROJECT_ROOT / "tests" / "e2e").rglob("*.py"))
        if gate.is_collectible(path.relative_to(PROJECT_ROOT).as_posix())
    )
    status = gate.main(["--diagnose", deferred_target])
    captured = capsys.readouterr()
    assert status == 1
    assert f"DEFERRED to pre-push/CI: {deferred_target}" in captured.err
    assert (
        "no runnable test files were selected; no pytest run was launched"
        in captured.err
    )


def test_diagnostic_scope_above_the_ceiling_is_not_launched(gate, monkeypatch, capsys):
    """A conftest-sized selected scope remains bounded in diagnostic mode."""
    oversized = [f"tests/build/test_probe_{number}.py" for number in range(201)]
    monkeypatch.setattr(gate, "select", lambda _paths, _root: (oversized, [], []))

    def must_not_launch(*_args, **_kwargs):
        pytest.fail("an oversized diagnostic scope must not launch pytest")

    monkeypatch.setattr(gate, "run_pytest_reaped", must_not_launch)

    status = gate.main(["--diagnose", "tests/conftest.py"])
    captured = capsys.readouterr()
    assert status == 1
    assert (
        "above the bounded ceiling of 200; no pytest run was launched" in captured.err
    )


def test_opt_in_receipt_records_the_selected_public_probe(tmp_path):
    """The public hook writes a complete receipt for the actual selected command."""
    probe_dir = (
        PROJECT_ROOT / "tests" / "build" / f"p4_receipt_probe_{uuid.uuid4().hex}"
    )
    probe_dir.mkdir()
    selected = probe_dir / "test_receipt.py"
    evidence = tmp_path / "evidence"
    try:
        selected.write_text("def test_receipt_probe():\n    assert True\n")
        result = _native_gate_probe(
            [selected.relative_to(PROJECT_ROOT).as_posix()],
            "--diagnose",
            evidence_dir=evidence,
        )
        first_attempt = next(evidence.iterdir())
        receipt = json.loads(
            (first_attempt / "receipt.json").read_text(encoding="utf-8")
        )
        assert result.returncode == 0
        assert receipt["state"] == "complete"
        assert receipt["exit_code"] == 0
        assert receipt["argv"][:4] == ["uv", "run", "python3", "-m"]
        assert receipt["selected_sources"][0]["path"].endswith("test_receipt.py")
        assert receipt["selected_sources"][0]["sha256"]
        assert receipt["candidate_identity"] == {
            "kind": "unknown",
            "reason": (
                "observed_git_and_input_subset_cannot_identify_complete_"
                "executed_candidate"
            ),
            "observed_git": receipt["candidate_identity"]["observed_git"],
        }
        assert (
            receipt["candidate_identity"]["observed_git"]["head"]["identity"] == "known"
        )
        assert (
            receipt["candidate_identity"]["observed_git"]["worktree_dirty"]["identity"]
            == "known"
        )
        assert (
            receipt["declared_touched_inputs"]
            == receipt["declared_touched_inputs_after"]
        )
        assert receipt["input_identity_drift"] is False
        assert "selected test files only" in receipt["receipt_scope"]
        assert set(receipt["declared_environment"]) <= {"PYTHONPATH", "PYTEST_ADDOPTS"}

        selected.write_text("def test_receipt_probe():\n    assert False\n")
        failed = _native_gate_probe(
            [selected.relative_to(PROJECT_ROOT).as_posix()],
            "--diagnose",
            evidence_dir=evidence,
        )
        second_attempt = next(
            path for path in evidence.iterdir() if path != first_attempt
        )
        receipt = json.loads(
            (second_attempt / "receipt.json").read_text(encoding="utf-8")
        )
        assert failed.returncode == 1
        assert receipt["state"] == "complete"
        assert receipt["exit_code"] == 1
        assert "test_receipt_probe" in receipt["stdout"] + receipt["stderr"]
        assert (
            json.loads((first_attempt / "receipt.json").read_text(encoding="utf-8"))[
                "exit_code"
            ]
            == 0
        )
    finally:
        shutil.rmtree(probe_dir, ignore_errors=True)


def test_input_identity_changes_when_product_input_changes_but_test_does_not(
    gate, tmp_path
):
    """Input identity cannot be substituted with unchanged selected-test hashes."""
    root = tmp_path
    product = root / "src" / "product.py"
    selected_test = root / "tests" / "test_static.py"
    product.parent.mkdir()
    selected_test.parent.mkdir()
    product.write_text("value = 1\n", encoding="utf-8")
    selected_test.write_text("def test_static(): pass\n", encoding="utf-8")

    initial_cache = {}
    initial_inputs = gate._source_snapshots(root, ["src/product.py"], initial_cache)
    selected_before = gate._source_snapshots(
        root, ["tests/test_static.py"], initial_cache
    )

    product.write_text("value = 2\n", encoding="utf-8")
    changed_inputs = gate._source_snapshots(root, ["src/product.py"])
    selected_after = gate._source_snapshots(root, ["tests/test_static.py"])

    assert selected_after == selected_before
    assert changed_inputs != initial_inputs


def test_missing_declared_input_is_explicitly_unknown(gate, tmp_path):
    snapshot = gate._source_snapshots(tmp_path, ["src/deleted.py"])
    assert snapshot == [
        {
            "path": "src/deleted.py",
            "sha256": None,
            "identity": "unknown",
            "reason": "path_missing_or_deleted",
        }
    ]


def test_interrupted_hook_keeps_its_initial_receipt(gate, monkeypatch, tmp_path):
    """An interruption before a terminal result leaves an honest incomplete record."""
    evidence = tmp_path / "evidence"
    selected = "tests/build/test_pytest_touched_files_gate.py"
    source = PROJECT_ROOT / selected
    original = source.read_text(encoding="utf-8")
    monkeypatch.setenv("NWAVE_TOUCHED_FILES_EVIDENCE_DIR", str(evidence))
    monkeypatch.setattr(gate, "select", lambda _paths, _root: ([selected], [], []))

    def interrupt(*_args, **kwargs):
        kwargs["stdout"].write(b"partial before interruption\n")
        kwargs["stdout"].flush()
        source.write_text(original + "\n# P4 identity-drift probe\n", encoding="utf-8")
        raise KeyboardInterrupt

    monkeypatch.setattr(gate, "run_pytest_reaped", interrupt)
    try:
        with pytest.raises(KeyboardInterrupt):
            gate.main(["--diagnose", selected])
        attempt = next(evidence.iterdir())
        receipt = json.loads((attempt / "receipt.json").read_text(encoding="utf-8"))
        assert receipt["state"] == "incomplete"
        assert receipt["exit_code"] is None
        assert receipt["candidate_identity"]["kind"] == "unknown"
        assert "declared_touched_inputs_after" not in receipt
        assert (
            receipt["declared_touched_inputs"][0]["sha256"]
            == receipt["selected_sources"][0]["sha256"]
        )
        assert "partial before interruption" in (
            attempt / "stdout-stderr.txt"
        ).read_text(encoding="utf-8")
        assert (
            receipt["selected_sources"][0]["sha256"]
            != __import__("hashlib").sha256(source.read_bytes()).hexdigest()
        )
    finally:
        source.write_text(original, encoding="utf-8")
