"""Regression: verify_red_green's "no parseable JUnit XML" HOW message must
name the ACTUAL junit path, not the literal "{junit_out}" placeholder text.

Found in ``src/des/cli/verify_red_green.py`` ~line 122-128: the ``how=``
argument to ``_indeterminate(...)`` in the "no parseable JUnit XML produced"
branch is built as a PLAIN string, not an f-string --
``"...at {junit_out} ..."`` -- so ``{junit_out}`` renders LITERALLY in the
emitted JSON/CLI message instead of interpolating the real resolved path. A
self-explaining HOW (the standing what/why/how rule) must name the actual
path so the operator can go look at it without re-deriving it.

Hermetic, same style as ``tests/des/unit/cli/test_verify_red_green.py``: a
fake ``--run-cmd`` script, ``main()`` driven in-process, JSON line parsed from
captured stdout. Additionally monkeypatches ``tempfile.NamedTemporaryFile``
inside the module to a FIXED, known path so the test can assert the HOW
message names that EXACT path (not just "some path-looking string"), and
drives a ``--run-cmd`` that deletes that file before the module tries to
parse it -- forcing the ``FileNotFoundError`` branch of ``_run_and_collect``
deterministically (the same branch the "no parseable JUnit XML produced"
``_indeterminate`` call guards).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from des.cli import verify_red_green
from des.cli.verify_red_green import main


class _FixedNamedTemporaryFile:
    """Stand-in for ``tempfile.NamedTemporaryFile`` with a KNOWN, fixed path."""

    def __init__(self, path: Path) -> None:
        self.name = str(path)

    def __enter__(self) -> _FixedNamedTemporaryFile:
        Path(self.name).touch()
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


def _repo_with_test(tmp_path: Path) -> Path:
    (tmp_path / "test_x.py").write_text("# content v1\n")
    return tmp_path


def _fixed_junit_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Force verify_red_green's internal tempfile to a KNOWN path."""
    fixed = tmp_path / "controlled_junit_out.xml"
    monkeypatch.setattr(
        verify_red_green.tempfile,
        "NamedTemporaryFile",
        lambda *a, **k: _FixedNamedTemporaryFile(fixed),
    )
    return fixed


def _deleting_run_cmd(tmp_path: Path) -> str:
    """A --run-cmd whose only job is to DELETE {junit_out} before parse --
    forces the "no parseable JUnit XML produced" (FileNotFoundError) branch
    deterministically, no malformed-XML guessing required."""
    remover = tmp_path / "remover.py"
    remover.write_text("import os, sys\nos.remove(sys.argv[1])\n")
    return f"{sys.executable} {remover} {{junit_out}}"


def _copying_run_cmd(tmp_path: Path, xml: str) -> str:
    xml_src = tmp_path / "canned.xml"
    xml_src.write_text(xml)
    copier = tmp_path / "copier.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _record_red_indeterminate(
    capsys: pytest.CaptureFixture[str], repo: Path, run_cmd: str
) -> dict[str, Any]:
    exit_code = main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--record-red",
            "--run-cmd",
            run_cmd,
        ]
    )
    out = capsys.readouterr().out
    payload: dict[str, Any] | None = None
    for line in out.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        candidate = json.loads(line)
        if candidate.get("event") == "RedGreenIndeterminate":
            payload = candidate
            break
    assert payload is not None, f"no RedGreenIndeterminate JSON line in stdout: {out!r}"
    payload["exit_code"] = exit_code
    return payload


def test_no_parseable_junit_how_message_names_the_actual_junit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): the HOW message must contain the REAL
    resolved junit path and must NOT contain the literal placeholder text
    "{junit_out}" -- today it contains ONLY the literal placeholder, never
    the real path, so this fails for the right (semantic) reason."""
    repo = _repo_with_test(tmp_path)
    junit_out = _fixed_junit_out(monkeypatch, tmp_path)
    run_cmd = _deleting_run_cmd(tmp_path)

    result = _record_red_indeterminate(capsys, repo, run_cmd)

    assert result["exit_code"] == 2  # INDETERMINATE, never a silent pass
    assert result["what"] == "no parseable JUnit XML produced"
    how = result["how"]
    assert str(junit_out) in how, (
        f"HOW message must name the actual junit path {junit_out!r}; got {how!r}"
    )
    assert "{junit_out}" not in how, (
        "HOW message must not leak the literal '{junit_out}' placeholder; "
        f"got {how!r}"
    )


@pytest.mark.negative_at
def test_zero_testcases_how_message_never_mentions_junit_out_placeholder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): a
    SIBLING INDETERMINATE branch ("zero test cases collected") never mentions
    junit_out at all in its HOW message -- proving the fix to the "no
    parseable JUnit XML" branch's HOW string is correctly SCOPED and does not
    spuriously leak the placeholder text into an unrelated message."""
    repo = _repo_with_test(tmp_path)
    # A well-formed but EMPTY testsuite -- parses fine, yields zero testcases.
    run_cmd = _copying_run_cmd(tmp_path, "<testsuite></testsuite>")

    result = _record_red_indeterminate(capsys, repo, run_cmd)

    assert result["exit_code"] == 2  # INDETERMINATE, never a silent pass
    assert result["what"] == "zero test cases collected"
    how = result["how"]
    assert "{junit_out}" not in how
    assert "junit_out" not in how  # this sibling branch never names junit_out
