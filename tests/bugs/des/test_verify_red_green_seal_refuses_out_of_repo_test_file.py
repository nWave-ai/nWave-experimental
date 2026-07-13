"""Regression: `des verify-red-green --record-red` (and `--verify-green`),
when `--test-file` resolves to a path OUTSIDE `--repo`, crashes with a RAW
uncaught `ValueError` (`Path.relative_to` raising `... is not in the
subpath of ...`) instead of degrading LOUD.

RCA (src/des/cli/verify_red_green.py):
- `_seal_path(repo, test_file)` (line 110-113) does
  `test_file.relative_to(repo)` unconditionally. When `test_file` is not a
  subpath of `repo` this raises `ValueError`, uncaught.
- The same unguarded `.relative_to(repo)` also appears inside `_record_red`
  (lines 281, 291) and `_verify_green` (lines 301, 351) -- BOTH the
  record-red and verify-green code paths crash on an out-of-repo test file.
- `main()` (line 363+) resolves `repo = Path(args.repo).resolve()` (line
  387) and `test_file = (repo / args.test_file).resolve()` (line 388).
  When `--test-file` is an ABSOLUTE path outside `repo`, Python's `/`
  operator on a `Path` returns the right-hand absolute operand VERBATIM
  (left operand discarded), so `test_file` lands outside `repo` and every
  downstream `.relative_to(repo)` call throws a raw traceback, exit 1 --
  never the self-explaining `RedGreenIndeterminate` degrade-LOUD channel
  `_indeterminate` (line 104-107) already provides for every OTHER failure
  mode in this module.

The intended fix (NOT implemented here -- test-only): a degrade-LOUD guard
in `main()` right after `test_file` is resolved, before dispatching to
`_record_red`/`_verify_green`, that emits `RedGreenIndeterminate` (exit
`_EXIT_INDETERMINATE` == 2) when `test_file` is not within `repo` --
self-explaining what/why/how, never a raw traceback.

Drives `verify_red_green.main(argv)` directly, in-process (no subprocess
fork) -- the cleanest observable: return code + stdout (capsys). The
declared `--run-cmd` copies canned JUnit XML into `{junit_out}` so no real
pytest-in-pytest subprocess is required (same hermetic idiom as
`tests/des/unit/cli/test_verify_red_green.py` and
`tests/bugs/des/test_verify_red_green_names_compiled_lang_alternative.py`).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from des.cli.verify_red_green import _EXIT_INDETERMINATE, main


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


def test_out_of_repo_test_file_degrades_loud_instead_of_raw_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """POSITIVE AT (active-RED today): a `--test-file` OUTSIDE `--repo`
    must degrade LOUD (`RedGreenIndeterminate`, exit `_EXIT_INDETERMINATE`
    == 2, self-explaining what/why/how naming the offending path) instead
    of crashing with an uncaught `ValueError` from `Path.relative_to`.
    Fails today because current code raises the raw `ValueError` before
    ever returning a controlled exit code."""
    repo = tmp_path / "repo"
    repo.mkdir()
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    test_file = outside_dir / "test_x.py"
    test_file.write_text("def test_x():\n    assert False\n")

    exit_code = main(
        [
            "--repo",
            str(repo),
            "--test-file",
            str(test_file),
            "--record-red",
            "--run-cmd",
            _canned_xml_run_cmd(tmp_path, _FAILING_XML),
        ]
    )

    stdout = capsys.readouterr().out
    assert exit_code == _EXIT_INDETERMINATE, (
        f"expected exit {_EXIT_INDETERMINATE} (INDETERMINATE degrade-LOUD) "
        f"for an out-of-repo --test-file, got {exit_code}; stdout={stdout!r}"
    )
    payload = _json_event(stdout, "RedGreenIndeterminate")
    haystack = (
        f"{payload.get('what', '')} {payload.get('why', '')} {payload.get('how', '')}"
    )
    assert str(test_file) in haystack or str(repo) in haystack, (
        "the degrade-LOUD message must name the offending test-file path "
        f"or the repo root so an operator can act on it; got: {haystack!r}"
    )
    assert "relative_to" not in stdout and "Traceback" not in stdout, (
        f"must never leak a raw Python traceback onto stdout: {stdout!r}"
    )


@pytest.mark.negative_at
def test_in_repo_test_file_does_not_trigger_out_of_repo_degrade(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE AT (control -- green today, must stay green after the
    fix): a `--test-file` INSIDE `--repo` must still seal RED normally
    (`RedObserved`) and must NEVER emit the out-of-repo
    `RedGreenIndeterminate` degrade -- proves the fix, once implemented,
    stays scoped to the out-of-repo case only (no over-correction).
    """
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
    assert exit_code == 0
    payload = _json_event(stdout, "RedObserved")
    assert payload["failing"] == ["t::test_scenario"]
    assert "RedGreenIndeterminate" not in stdout, (
        "the out-of-repo degrade must never leak onto a normal in-repo "
        f"RED seal: {stdout!r}"
    )
