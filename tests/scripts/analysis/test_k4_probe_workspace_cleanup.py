"""The K4 probe workspace (`<root>/probe-nwave`) must be removed after a PASS
engagement check, and ONLY after a PASS -- otherwise the leftover clone under
`<root>/probe-nwave` sits there to be picked up later by an unrelated agent
instead of the measured campaign arm (observed on the installed K4 run).

On `broke` or `absent`-with-detail, the failure messages `main` prints point a
reader at `<root>/probe-nwave` for the HOW; deleting it there would make that
pointer a lie, so cleanup must not fire on those verdicts.

Run: uv run pytest -q tests/scripts/analysis/test_k4_probe_workspace_cleanup.py
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.analysis.k4 import preflight


@pytest.fixture(autouse=True)
def _bounded_sandbox_prerequisites(tmp_path_factory, monkeypatch):
    """`preflight.main` now refuses before writing `arms.json` unless `claude`
    and `socat` resolve on PATH (see `test_k4_runner_sandbox.py` for the gate
    itself). These tests exercise the packaging/probe pipeline downstream of
    that gate, not the gate, so a bounded stand-in satisfies it regardless of
    what happens to be globally installed on the host running the suite.
    """
    bin_dir = tmp_path_factory.mktemp("bounded-sandbox-bin")
    for name in ("claude", "socat"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")


def _make_checkout(tmp_path):
    """A disposable, always-clean git repo for `--checkout`.

    `preflight.main`'s `--checkout` defaults to `Path.cwd()`, and row 16's
    `resolve_clean_commit_sha` refuses a dirty tree BEFORE any packaging or
    probe step -- so a test that omits `--checkout` couples its own pass/fail
    to whatever state the SUITE'S OWN working tree happens to be in at the
    moment it runs, not to the packaging/probe behavior under test. Every
    call below passes this instead.
    """
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    for args in (
        ["init", "-q", "-b", "master"],
        ["config", "user.email", "k4@example.test"],
        ["config", "user.name", "k4"],
    ):
        subprocess.run(["git", *args], cwd=checkout, check=True, capture_output=True)
    (checkout / "README.md").write_text("seed\n")
    subprocess.run(
        ["git", "add", "README.md"], cwd=checkout, check=True, capture_output=True
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=checkout,
        check=True,
        capture_output=True,
    )
    return checkout


def _make_probe(root):
    probe = root / "probe-nwave"
    probe.mkdir(parents=True)
    (probe / "marker").write_text("probe contents")
    return probe


def _make_sibling_sentinel(root):
    sibling = root / "sibling-sentinel"
    sibling.mkdir(parents=True)
    (sibling / "keep").write_text("must survive cleanup")
    return sibling


def test_pass_removes_exact_probe_and_leaves_sibling_untouched(tmp_path):
    probe = _make_probe(tmp_path)
    sibling = _make_sibling_sentinel(tmp_path)

    removed = preflight.cleanup_probe_workspace(tmp_path, "absent", [])

    assert removed is True
    assert not probe.exists()
    assert sibling.exists()
    assert (sibling / "keep").read_text() == "must survive cleanup"


@pytest.mark.parametrize(
    "verdict,detail",
    [
        pytest.param("broke", ["`git clone` exited 128", "fatal: ..."], id="broke"),
        pytest.param(
            "absent", ["no CLAUDE.md in the workspace"], id="absent-with-detail"
        ),
        pytest.param(
            "unsafe", ["Write escaped into provider config"], id="unsafe-runner"
        ),
    ],
)
def test_failure_verdicts_preserve_the_probe(tmp_path, verdict, detail):
    probe = _make_probe(tmp_path)

    removed = preflight.cleanup_probe_workspace(tmp_path, verdict, detail)

    assert removed is False
    assert probe.exists()
    assert (probe / "marker").read_text() == "probe contents"


def test_main_removes_probe_and_still_writes_arms_json_on_pass(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    probe = _make_probe(root)
    sibling = _make_sibling_sentinel(root)

    monkeypatch.setattr(
        preflight,
        "build_arm_runtime",
        lambda root, checkout: (root / "venv-stub", _make_wheel(root)),
    )
    monkeypatch.setattr(
        preflight,
        "probe_engagement",
        lambda root, venv, auth_profile, model: ("absent", []),
    )

    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")
    checkout = _make_checkout(tmp_path)

    code = preflight.main(
        [
            "--root",
            str(root),
            "--task-file",
            str(task_file),
            "--checkout",
            str(checkout),
        ]
    )

    assert code == 0
    assert not probe.exists()
    assert sibling.exists()
    assert (root / "arms.json").exists()


def _make_wheel(
    tmp_path, name="nwave_ai-0.0.0-py3-none-any.whl", contents=b"wheel bytes"
):
    wheel = tmp_path / name
    wheel.write_bytes(contents)
    return wheel


def test_wheel_flag_reaches_exact_wheel_branch_without_build_arm_runtime(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    root.mkdir()
    wheel = _make_wheel(tmp_path)
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")

    def _refuse_checkout_build(root, checkout):
        raise AssertionError("build_arm_runtime must not run when --wheel is given")

    monkeypatch.setattr(preflight, "build_arm_runtime", _refuse_checkout_build)
    monkeypatch.setattr(
        preflight,
        "build_arm_runtime_from_wheel",
        lambda root, wheel: root / "venv-stub",
    )
    monkeypatch.setattr(
        preflight,
        "probe_engagement",
        lambda root, venv, auth_profile, model: ("absent", []),
    )

    checkout = _make_checkout(tmp_path)
    code = preflight.main(
        [
            "--root",
            str(root),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
            "--checkout",
            str(checkout),
        ]
    )

    assert code == 0
    assert (root / "arms.json").exists()


def test_checkout_branch_unchanged_when_wheel_flag_absent(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")
    calls = []

    monkeypatch.setattr(
        preflight,
        "build_arm_runtime",
        lambda root, checkout: (
            calls.append("checkout"),
            (root / "venv-stub", _make_wheel(root)),
        )[1],
    )

    def _refuse_wheel_build(root, wheel):
        raise AssertionError(
            "build_arm_runtime_from_wheel must not run without --wheel"
        )

    monkeypatch.setattr(preflight, "build_arm_runtime_from_wheel", _refuse_wheel_build)
    monkeypatch.setattr(
        preflight,
        "probe_engagement",
        lambda root, venv, auth_profile, model: ("absent", []),
    )

    checkout = _make_checkout(tmp_path)
    code = preflight.main(
        [
            "--root",
            str(root),
            "--task-file",
            str(task_file),
            "--checkout",
            str(checkout),
        ]
    )

    assert code == 0
    assert calls == ["checkout"]
    artifact = json.loads((root / "arms.json").read_text())["artifact"]
    assert artifact["sha256"] == preflight._sha256(Path(artifact["path"]))


@pytest.mark.parametrize(
    "build_path,name",
    [
        pytest.param(
            lambda tmp_path: tmp_path / "missing.whl", "missing", id="missing"
        ),
        pytest.param(lambda tmp_path: tmp_path, "directory", id="not-a-file"),
        pytest.param(
            lambda tmp_path: _make_wheel(tmp_path, name="not-a-wheel.tar.gz"),
            "wrong-suffix",
            id="non-wheel-suffix",
        ),
    ],
)
def test_invalid_wheel_path_refuses_before_probe_setup(
    tmp_path, monkeypatch, build_path, name
):
    root = tmp_path / "root"
    root.mkdir()
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")
    bad_path = build_path(tmp_path)

    def _refuse_any_setup(*_args, **_kwargs):
        raise AssertionError(
            f"no setup call should run for an invalid --wheel ({name})"
        )

    monkeypatch.setattr(preflight, "build_arm_runtime", _refuse_any_setup)
    monkeypatch.setattr(preflight, "build_arm_runtime_from_wheel", _refuse_any_setup)
    monkeypatch.setattr(preflight, "probe_engagement", _refuse_any_setup)

    checkout = _make_checkout(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        preflight.main(
            [
                "--root",
                str(root),
                "--task-file",
                str(task_file),
                "--wheel",
                str(bad_path),
                "--checkout",
                str(checkout),
            ]
        )

    message = str(excinfo.value)
    assert message.startswith("WHAT:")
    assert "WHY:" in message
    assert "HOW:" in message
    assert not (root / "nwave-venv").exists()
    assert not (root / "arms.json").exists()


def test_wheel_identity_path_and_digest_are_emitted(tmp_path, monkeypatch, capsys):
    root = tmp_path / "root"
    root.mkdir()
    wheel = _make_wheel(tmp_path, contents=b"deterministic wheel bytes")
    expected_digest = preflight._sha256(wheel)
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")

    monkeypatch.setattr(
        preflight,
        "build_arm_runtime_from_wheel",
        lambda root, wheel: root / "venv-stub",
    )
    monkeypatch.setattr(
        preflight,
        "probe_engagement",
        lambda root, venv, auth_profile, model: ("absent", []),
    )

    checkout = _make_checkout(tmp_path)
    code = preflight.main(
        [
            "--root",
            str(root),
            "--task-file",
            str(task_file),
            "--wheel",
            str(wheel),
            "--checkout",
            str(checkout),
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert str(wheel.resolve()) in out
    assert expected_digest in out
