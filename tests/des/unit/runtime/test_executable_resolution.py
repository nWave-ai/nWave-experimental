"""An ``argv[0]`` is resolved to the program that will REALLY run -- or to nothing.

The observation this corpus measures: the spawn boundary can answer "which
absolute program does this ``argv[0]`` name?" BEFORE anything is spawned, so a
caller can execute the ANSWER and then report it as the runtime that ran by
construction. Three properties make that answer trustworthy, and each is checked
against a real file on disk rather than a stubbed lookup:

* the answer is ABSOLUTE, so it is reportable to an operator;
* it PRESERVES THE DECLARED BASENAME -- symlinks are NOT followed, because a
  multi-call binary dispatches on ``argv[0]`` and rewriting the name would
  execute a different program than the one declared;
* a SEPARATOR-BEARING ``argv[0]`` is resolved against the CHILD's working
  directory, which is where POSIX resolves it, and never against the caller's.

And the honest negative: a name nothing answers to resolves to ``None`` rather
than to a path that would only fail at ``execve``.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

from des.runtime.spawn import resolve_executable


def _executable(path: Path, body: str = "#!/bin/sh\nexit 0\n") -> Path:
    """A real, really-executable program on disk."""
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def test_a_bare_name_resolves_on_path_to_an_absolute_program(tmp_path, monkeypatch):
    tool_directory = tmp_path / "bin"
    tool_directory.mkdir()
    _executable(tool_directory / "declared-tool")
    monkeypatch.setenv("PATH", str(tool_directory))

    resolved = resolve_executable("declared-tool")

    assert resolved is not None
    assert Path(resolved).is_absolute(), (
        f"a runtime is only reportable to an operator if it is absolute, "
        f"got {resolved!r}"
    )
    assert Path(resolved) == tool_directory / "declared-tool"


def test_resolution_does_not_follow_symlinks_so_the_declared_basename_survives(
    tmp_path, monkeypatch
):
    """A multi-call binary dispatches on ``argv[0]``; rewriting it runs another program.

    This is the real shape of ``sh`` on many systems (``/usr/bin/sh`` ->
    ``/usr/bin/dash``) and of ``awk`` (-> ``gawk``). Resolving through the link
    would both NAME and EXECUTE a different program than the declaration asked
    for, so the property is checked here rather than trusted.
    """
    tool_directory = tmp_path / "bin"
    tool_directory.mkdir()
    _executable(tool_directory / "real-program")
    (tool_directory / "declared-alias").symlink_to(tool_directory / "real-program")
    monkeypatch.setenv("PATH", str(tool_directory))

    resolved = resolve_executable("declared-alias")

    assert resolved is not None
    assert os.path.basename(resolved) == "declared-alias", (
        f"resolution must preserve the declared basename; a resolved "
        f"{resolved!r} would dispatch a multi-call binary as another program"
    )
    assert Path(resolved) == tool_directory / "declared-alias"


def test_a_separator_bearing_argv0_resolves_against_the_childs_working_directory(
    tmp_path, monkeypatch
):
    """POSIX resolves it against the CHILD's cwd, and so does this.

    The caller stands somewhere else on purpose: a ``PATH`` search -- or a
    resolution against the caller's own cwd -- would answer ``None`` for a
    repository-relative tool the child really executes and really exits 0 on.
    """
    child_root = tmp_path / "repository"
    (child_root / "tools").mkdir(parents=True)
    _executable(child_root / "tools" / "checker")

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setenv("PATH", str(tmp_path / "nothing-here"))

    assert resolve_executable("tools/checker") is None, (
        "resolved against the CALLER's cwd, where the tool does not exist"
    )

    resolved = resolve_executable("tools/checker", cwd=child_root)

    assert resolved is not None
    assert Path(resolved) == child_root / "tools" / "checker"
    assert Path(resolved).is_absolute()


def test_a_name_nothing_answers_to_resolves_to_nothing(tmp_path, monkeypatch):
    """``None``, never a guessed path that would only fail at ``execve``.

    A non-executable regular file counts as "nothing answers": it is on the
    declared path and still cannot be run, and reporting it as a runtime would
    name a program that never produced anything.
    """
    tool_directory = tmp_path / "bin"
    tool_directory.mkdir()
    (tool_directory / "not-executable").write_text("data\n", encoding="utf-8")
    monkeypatch.setenv("PATH", str(tool_directory))

    assert resolve_executable("no-such-tool-anywhere") is None
    assert resolve_executable("not-executable") is None
    assert resolve_executable(str(tool_directory / "not-executable")) is None
    assert resolve_executable(str(tool_directory / "absent"), cwd=tmp_path) is None
    assert resolve_executable("") is None
