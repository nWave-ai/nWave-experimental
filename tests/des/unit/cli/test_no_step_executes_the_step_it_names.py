"""Actual DES entrypoints neither re-enter another command nor launch a model."""

from __future__ import annotations

import importlib
import io
import subprocess
import sys
from pathlib import Path

from des.cli.__main__ import _REGISTRY


def test_running_every_step_for_real_starts_no_des_process_and_re_enters_nothing(
    tmp_path, monkeypatch
):
    root = tmp_path / "root"
    root.mkdir()
    for argv in (
        ("init", "-q"),
        ("config", "user.email", "a@b"),
        ("config", "user.name", "a"),
    ):
        subprocess.run(["git", "-C", str(root), *argv], check=True, capture_output=True)
    (root / "README.md").write_text("subject\n")
    subprocess.run(
        ["git", "-C", str(root), "add", "."], check=True, capture_output=True
    )
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "base"],
        check=True,
        capture_output=True,
    )

    dispatched = []
    forbidden_processes = []
    import des.cli.__main__ as dispatcher

    monkeypatch.setattr(
        dispatcher, "main", lambda argv=None: dispatched.append(list(argv or [])) or 0
    )
    real_popen = subprocess.Popen

    def spy(args, *rest, **kwargs):
        vector = list(args) if isinstance(args, (list, tuple)) else [str(args)]
        if vector and Path(str(vector[0])).name in {
            "des",
            "des.exe",
            "claude",
            "codex",
        }:
            forbidden_processes.append(vector)
        return real_popen(args, *rest, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", spy)
    invocations = {
        "state": ["--repo-root", str(root)],
        "po": ["--repo-root", str(root), "--project", "--input", "-"],
        "design": ["--repo-root", str(root), "--value", "1", "--input", "-"],
        "oracle": ["--repo-root", str(root), "--value", "1", "--input", "-"],
        "craft": ["--repo-root", str(root), "--value", "1", "--input", "-"],
        "verify": ["--repo-root", str(root)],
        "integrate": ["--repo-root", str(root), "--candidate", "0" * 40],
    }
    for row in _REGISTRY:
        arguments = invocations.get(row.name)
        if arguments is None:
            continue
        monkeypatch.setattr(sys, "stdin", io.StringIO("{}"))
        module = importlib.import_module(row.module_path)
        assert module.main(arguments) in (0, 1)

    assert dispatched == []
    assert forbidden_processes == []
