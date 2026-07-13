"""Regression: `des verify-red-green --record-red` (and `--verify-green`),
when `--repo` points at a NON-EXISTENT directory, blames the wrong thing --
it reports "test file not found" instead of "repo not found".

RCA (src/des/cli/verify_red_green.py, `main()`):
- line 387: `repo = Path(args.repo).resolve()` -- resolves `--repo` but does
  NOT validate it is an existing directory.
- line 388: `test_file = (repo / args.test_file).resolve()` -- resolves the
  test-file AGAINST that (possibly non-existent) repo root.
- lines 389-394: `if not test_file.is_file(): return _indeterminate(what=
  f"test file not found: {args.test_file}", why="nothing to observe.",
  how="check the path.")` -- so a non-existent `--repo` makes `test_file`
  resolve against a ghost path that can never be a file, and the tool
  blames the TEST FILE, not the missing REPO. Misleading: the operator
  fixes the wrong thing.

The intended fix (NOT implemented here -- test-only): a guard inserted in
`main()` BETWEEN line 387 (repo resolve) and line 388 (test_file resolve):
`if not repo.is_dir(): return _indeterminate(what="--repo <repo> is not an
existing directory", why="...", how="pass --repo pointing at an existing
repository directory")`, reusing the existing `_indeterminate(what, why,
how)` helper (line 104) that already emits `RedGreenIndeterminate` and
returns `_EXIT_INDETERMINATE` (== 2).

Drives `verify_red_green.main(argv)` directly, in-process (no subprocess
fork) -- the cleanest observable: return code + stdout (capsys). The
negative control's declared `--run-cmd` copies canned JUnit XML into
`{junit_out}` so no real pytest-in-pytest subprocess is required (same
hermetic idiom as `tests/bugs/des/test_verify_red_green_seal_refuses_out_of_repo_test_file.py`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from des.cli.verify_red_green import _EXIT_INDETERMINATE, _EXIT_OK, main


_FAILING_XML = (
    '<testsuite><testcase classname="t" name="test_scenario">'
    '<failure message="red"/></testcase></testsuite>'
)


def _canned_xml_run_cmd(tmp_path: Path, xml: str) -> str:
    """A --run-cmd that copies canned JUnit XML to {junit_out} -- hermetic,
    no real pytest-in-pytest subprocess."""
    xml_src = tmp_path / "canned.xml"
    xml_src.write_text(xml)
    copier = tmp_path / "copier.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _json_event(stdout: str, event: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        candidate = json.loads(stripped)
        if candidate.get("event") == event:
            return candidate
    raise AssertionError(f"no {event!r} JSON line in stdout: {stdout!r}")


def test_nonexistent_repo_reports_repo_not_found_not_test_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): a `--repo` that does NOT exist must
    degrade LOUD with a message naming the REPO (repo directory does not
    exist / is not an existing directory), never the misleading "test file
    not found" message -- exit `_EXIT_INDETERMINATE` == 2 either way, but
    the `what` must be honest about WHAT is actually missing. Fails today
    because current code emits `what="test file not found: <test-file>"`
    instead of a repo-not-found message.
    """
    nonexistent_repo = tmp_path / "does-not-exist"
    assert not nonexistent_repo.exists()

    exit_code = main(
        [
            "--repo",
            str(nonexistent_repo),
            "--test-file",
            "test_x.py",
            "--record-red",
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == _EXIT_INDETERMINATE, (
        f"expected exit {_EXIT_INDETERMINATE} (INDETERMINATE degrade-LOUD) "
        f"for a non-existent --repo, got {exit_code}; stdout={stdout!r}"
    )
    payload = _json_event(stdout, "RedGreenIndeterminate")
    what = payload.get("what", "")
    assert str(nonexistent_repo) in what or "repo" in what.lower(), (
        "the degrade-LOUD message must be about the missing REPO directory, "
        f"not the test file; got what={what!r}"
    )
    assert "test file not found" not in what, (
        "must NOT blame the test file when the real problem is a "
        f"non-existent --repo directory; got what={what!r}"
    )


@pytest.mark.negative_at
def test_existing_repo_does_not_trigger_repo_not_found(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control -- green today, must stay green after the
    fix): a `--repo` that DOES exist must still seal RED normally
    (`RedObserved`) and must NEVER emit a repo-not-found message -- proves
    the fix, once implemented, stays scoped to the non-existent-repo case
    only (no over-correction against a perfectly valid repo)."""
    repo = tmp_path
    test_file = repo / "test_x.py"
    test_file.write_text("def test_x():\n    assert False\n")

    exit_code = main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--record-red",
            "--run-cmd",
            _canned_xml_run_cmd(tmp_path, _FAILING_XML),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == _EXIT_OK
    payload = _json_event(stdout, "RedObserved")
    assert payload["failing"] == ["t::test_scenario"]
    assert "RedGreenIndeterminate" not in stdout, (
        f"an existing --repo must never emit the repo-not-found degrade: {stdout!r}"
    )
