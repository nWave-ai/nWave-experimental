"""Regression: `des verify-red-green --verify-green` fabricates a RED verdict
for a recorded test id that is simply ABSENT from the current run, instead of
recognizing the two runs are not comparable.

RCA (src/des/cli/verify_red_green.py, `_verify_green`, ~line 550):

    still_failing = sorted(t for t in was_red if outcomes.get(t, "fail") == "fail")

`outcomes.get(t, "fail")` collapses two distinct facts into one:
  (a) the recorded id ran in THIS run and genuinely FAILED -> a real red,
      refusal is correct.
  (b) the recorded id is ABSENT from THIS run's outcomes entirely -> the two
      runs are not comparable, nothing was witnessed either way.
Case (b) is silently defaulted to "fail" and reported as case (a):
`RedGreenRefused`, exit 1, "N red test(s) still failing", why "the
implementation does not satisfy the witnessed ATs", how "fix the
implementation; the tests are the contract" -- a confident lie that sends the
developer to fix code that may be perfectly correct.

Demonstrated real-world vector (confirmed live on this repo): the project's
pytest config loads a `pspec` plugin whose UNGUARDED
`pytest_collection_modifyitems` rewrites JUnit `classname`/`name` on every
run. With `-p no:pspec` (the des default `--run-cmd`): classname
`tests.bugs.des.test_x`, name = the FUNCTION name. Without it (a custom
`--run-cmd`): classname `tests.bugs.des.test_x.` (trailing dot), name = the
DOCSTRING. A seal recorded under one shape is therefore never found in a run
under the other shape -- every recorded id is "absent" from the other run's
outcomes, and the bug fires on every single test.

Target behaviour (currently ABSENT -- this is what makes test 1 active-RED):
when a recorded red id cannot be found in the current run's outcomes,
`_verify_green` must degrade LOUD as INDETERMINATE (`_indeterminate`, exit
`_EXIT_INDETERMINATE == 2`, event `RedGreenIndeterminate`) -- never fabricate
a red. The message must NAME the uncomparable id(s) and its `how` must tell
the developer what to actually do (re-record RED under the SAME run
configuration used for --verify-green, or reconcile the divergent
`--run-cmd`), not shrug.

Hermetic: drives `des.cli.verify_red_green.main(argv)` in-process (capsys +
JSON-line parsing), same idiom as
`tests/des/unit/cli/test_verify_red_green.py` -- the declared `--run-cmd` is
a tiny copier script writing CANNED JUnit XML to `{junit_out}`, no
pytest-in-pytest, no git needed (the seal is plain filesystem).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from des.cli.verify_red_green import _EXIT_INDETERMINATE, _EXIT_OK, _EXIT_REFUSED, main


# The recorded RED id, shaped like the des-default `-p no:pspec` run: plain
# dotted classname, FUNCTION name.
_RECORDED_CLASSNAME = (
    "tests.bugs.des.test_verify_green_indeterminate_on_uncomparable_ids"
)
_RECORDED_NAME = "test_scenario_under_pspec_isolated_run"
_RECORDED_ID = f"{_RECORDED_CLASSNAME}::{_RECORDED_NAME}"

_XML_RECORD_RED = (
    "<testsuite>"
    f'<testcase classname="{_RECORDED_CLASSNAME}" name="{_RECORDED_NAME}">'
    '<failure message="red"/></testcase>'
    "</testsuite>"
)

# The verifying run's id, shaped like the run WITHOUT `-p no:pspec`: trailing
# dot on the classname, docstring-shaped name. Genuinely PASSES -- but it is
# a completely different composed id, so `_RECORDED_ID` is absent here.
_VERIFY_CLASSNAME = _RECORDED_CLASSNAME + "."
_VERIFY_NAME = (
    "Verify that the scenario under test now genuinely passes once the "
    "implementation exists."
)
_XML_VERIFY_GREEN_DIVERGENT_IDS = (
    "<testsuite>"
    f'<testcase classname="{_VERIFY_CLASSNAME}" name="{_VERIFY_NAME}"/>'
    "</testsuite>"
)

# Comparable-id fixtures (same composed id in both runs) for the two
# negative controls below.
_COMPARABLE_CLASSNAME = "t"
_COMPARABLE_NAME = "test_scenario"
_COMPARABLE_ID = f"{_COMPARABLE_CLASSNAME}::{_COMPARABLE_NAME}"
_XML_RECORD_RED_COMPARABLE = (
    "<testsuite>"
    f'<testcase classname="{_COMPARABLE_CLASSNAME}" name="{_COMPARABLE_NAME}">'
    '<failure message="red"/></testcase>'
    "</testsuite>"
)
_XML_STILL_FAILING_COMPARABLE = (
    "<testsuite>"
    f'<testcase classname="{_COMPARABLE_CLASSNAME}" name="{_COMPARABLE_NAME}">'
    '<failure message="still red"/></testcase>'
    "</testsuite>"
)
_XML_NOW_PASSING_COMPARABLE = (
    "<testsuite>"
    f'<testcase classname="{_COMPARABLE_CLASSNAME}" name="{_COMPARABLE_NAME}"/>'
    "</testsuite>"
)


def _fake_runner(tmp_path: Path, xml: str) -> str:
    """A single-string --run-cmd that copies canned XML to {junit_out} --
    hermetic, no real pytest-in-pytest subprocess (idiom shared with
    tests/des/unit/cli/test_verify_red_green.py)."""
    slug = hashlib.md5(xml.encode()).hexdigest()[:8]
    xml_src = tmp_path / f"canned_{slug}.xml"
    xml_src.write_text(xml)
    copier = tmp_path / f"copier_{slug}.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _repo_with_test(tmp_path: Path) -> Path:
    (tmp_path / "test_x.py").write_text("# content v1\n")
    return tmp_path


def _run(repo: Path, phase: str, xml: str) -> int:
    return main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            phase,
            "--run-cmd",
            _fake_runner(repo, xml),
        ]
    )


def _json_events(stdout: str) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in stdout.splitlines() if line.strip().startswith("{")
    ]


def _json_event(stdout: str, event: str) -> dict[str, Any]:
    for payload in _json_events(stdout):
        if payload.get("event") == event:
            return payload
    raise AssertionError(f"no {event!r} JSON line in stdout: {stdout!r}")


def test_uncomparable_recorded_id_degrades_indeterminate_not_fabricated_red(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """THE DEFECT (active-RED today): a recorded RED id that is genuinely
    ABSENT from the verifying run's outcomes (the pspec/no-pspec id-shape
    divergence) must degrade LOUD as INDETERMINATE naming the uncomparable
    id -- never be silently defaulted to "fail" and reported as a real red.

    Today this FAILS: `outcomes.get(t, "fail")` defaults the missing id to
    "fail", so `_verify_green` emits `RedGreenRefused` / exit 1 / "1 red
    test(s) still failing" -- a confident lie, since the recorded test never
    ran at all in this configuration and the underlying behaviour was never
    re-witnessed either way.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_RECORD_RED) == _EXIT_OK
    capsys.readouterr()  # drain the RED-phase output before the assertion

    exit_code = _run(repo, "--verify-green", _XML_VERIFY_GREEN_DIVERGENT_IDS)
    stdout = capsys.readouterr().out

    assert exit_code == _EXIT_INDETERMINATE, (
        "a recorded id absent from the verifying run must degrade "
        f"INDETERMINATE (exit {_EXIT_INDETERMINATE}), not be fabricated as "
        f"a real red -- got exit={exit_code}, stdout={stdout!r}"
    )
    payload = _json_event(stdout, "RedGreenIndeterminate")
    haystack = (
        f"{payload.get('what', '')} {payload.get('why', '')} {payload.get('how', '')}"
    )
    assert _RECORDED_ID in haystack, (
        "the INDETERMINATE message must NAME the uncomparable recorded id "
        f"so the developer knows which witness could not be found: {haystack!r}"
    )
    assert payload.get("how"), "the INDETERMINATE payload must carry a how"
    assert "RedGreenRefused" not in stdout, (
        "the uncomparable-id case must never ALSO fabricate a "
        f"RedGreenRefused refusal: {stdout!r}"
    )


@pytest.mark.negative_at
def test_comparable_ids_with_genuine_failure_still_refuses_not_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE control (must stay green after the fix): when the recorded
    id IS present in the verifying run's outcomes and genuinely still
    fails, `_verify_green` must keep refusing (`RedGreenRefused`, exit 1) --
    the fix for the uncomparable-id case must not start rubber-stamping a
    real, comparable, still-failing red as INDETERMINATE or as green.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_RECORD_RED_COMPARABLE) == _EXIT_OK
    capsys.readouterr()

    exit_code = _run(repo, "--verify-green", _XML_STILL_FAILING_COMPARABLE)
    stdout = capsys.readouterr().out

    assert exit_code == _EXIT_REFUSED, (
        f"a genuinely still-failing, ID-COMPARABLE red must refuse (exit "
        f"{_EXIT_REFUSED}), got exit={exit_code}, stdout={stdout!r}"
    )
    payload = _json_event(stdout, "RedGreenRefused")
    assert _COMPARABLE_ID in payload.get("still_failing", []), (
        f"expected {_COMPARABLE_ID!r} in still_failing: {payload!r}"
    )
    assert "RedGreenIndeterminate" not in stdout, (
        f"a comparable, genuinely-failing id must never be reported "
        f"INDETERMINATE: {stdout!r}"
    )


@pytest.mark.negative_at
def test_comparable_ids_with_genuine_pass_still_seals_not_indeterminate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """NEGATIVE control (must stay green after the fix): when the recorded
    id IS present in the verifying run's outcomes and genuinely now passes,
    `_verify_green` must keep sealing (`RedGreenSealed`, exit 0) -- the fix
    must not turn an honest, comparable red->green transition into a
    spurious INDETERMINATE.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_RECORD_RED_COMPARABLE) == _EXIT_OK
    capsys.readouterr()

    exit_code = _run(repo, "--verify-green", _XML_NOW_PASSING_COMPARABLE)
    stdout = capsys.readouterr().out

    assert exit_code == _EXIT_OK, (
        f"a genuinely passing, ID-COMPARABLE red must seal (exit "
        f"{_EXIT_OK}), got exit={exit_code}, stdout={stdout!r}"
    )
    payload = _json_event(stdout, "RedGreenSealed")
    assert _COMPARABLE_ID in payload.get("sealed", []), (
        f"expected {_COMPARABLE_ID!r} in sealed: {payload!r}"
    )
    assert "RedGreenIndeterminate" not in stdout, (
        f"a comparable, genuinely-passing id must never be reported "
        f"INDETERMINATE: {stdout!r}"
    )
