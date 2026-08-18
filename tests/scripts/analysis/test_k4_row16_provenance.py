"""K4 matrix row 16 -- provenance gap.

First divergence: the packaged wheel's provenance was bound to the wheel's
own digest only, never to the clean exact commit it was built from. A
dirty-tree build could then be reproduced by digest alone with no way to
tell which source state produced it.

ADMISSION falsifier: a planted dirty-tree build must be REFUSED by the
provenance check, and `preflight.main` must never write `arms.json` for a
dirty checkout. `git` absence must degrade LOUD (INDETERMINATE), never a
silent pass -- portability: `git` is optional tooling, never this harness's
own runtime dependency.
"""

from __future__ import annotations

import shutil
import subprocess

import pytest

from scripts.analysis.k4 import preflight


def _git(*args: str, cwd) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_checkout(tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    _git("init", "-q", "-b", "master", cwd=checkout)
    _git("config", "user.email", "k4@example.test", cwd=checkout)
    _git("config", "user.name", "k4", cwd=checkout)
    (checkout / "README.md").write_text("seed\n")
    _git("add", "README.md", cwd=checkout)
    _git("commit", "-q", "-m", "seed", cwd=checkout)
    return checkout


def test_dirty_checkout_is_refused_with_what_why_how(tmp_path):
    checkout = _make_checkout(tmp_path)
    (checkout / "README.md").write_text("uncommitted change\n")

    with pytest.raises(SystemExit) as excinfo:
        preflight.resolve_clean_commit_sha(checkout)

    message = str(excinfo.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message
    assert "uncommitted" in message.lower() or "dirty" in message.lower()


def test_clean_checkout_resolves_the_exact_head_sha(tmp_path):
    checkout = _make_checkout(tmp_path)
    expected = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=checkout,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    assert preflight.resolve_clean_commit_sha(checkout) == expected


def test_git_absence_via_missing_executable_degrades_loud(tmp_path, monkeypatch):
    checkout = _make_checkout(tmp_path)
    monkeypatch.setattr(preflight.shutil, "which", lambda *a, **k: None)

    with pytest.raises(preflight.GitProvenanceUnavailable) as excinfo:
        preflight.resolve_clean_commit_sha(checkout)

    message = str(excinfo.value)
    assert "WHAT:" in message and "WHY:" in message and "HOW:" in message
    assert "INDETERMINATE" in message


def test_main_refuses_before_writing_arms_json_on_a_dirty_checkout(
    tmp_path, monkeypatch
):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name in ("claude", "socat"):
        exe = bin_dir / name
        exe.write_text("#!/bin/sh\nexit 0\n")
        exe.chmod(0o755)
    git_dir = shutil.which("git")
    assert git_dir is not None, "git must be present to test the dirty-tree branch"
    monkeypatch.setenv("PATH", f"{bin_dir}:{git_dir.rsplit('/', 1)[0]}")

    checkout = _make_checkout(tmp_path)
    (checkout / "README.md").write_text("uncommitted change\n")

    def _refuse_any_setup(*_args, **_kwargs):
        raise AssertionError("no packaging/probe step should run on a dirty checkout")

    monkeypatch.setattr(preflight, "build_arm_runtime", _refuse_any_setup)
    monkeypatch.setattr(preflight, "build_arm_runtime_from_wheel", _refuse_any_setup)
    monkeypatch.setattr(preflight, "probe_engagement", _refuse_any_setup)

    root = tmp_path / "root"
    task_file = tmp_path / "task.md"
    task_file.write_text("do the thing\n")

    with pytest.raises(SystemExit):
        preflight.main(
            [
                "--root",
                str(root),
                "--checkout",
                str(checkout),
                "--task-file",
                str(task_file),
            ]
        )

    assert not (root / "arms.json").exists()
