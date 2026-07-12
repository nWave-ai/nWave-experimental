"""Regression: `des verify-red-green --record-red`, on the NO-XML branch
(``RedGreenIndeterminate``, "no parseable JUnit XML produced"), must ALSO
name the compiled-language alternative -- `des record-at-review-verdict`
(the two-part attestation route) -- inline in its message.

RCA (src/des/cli/verify_red_green.py ~157-158, inside ``_run_and_collect``):
when the declared ``--run-cmd`` produces no parseable JUnit XML,
``_indeterminate`` is called with a ``how`` that lists only test-runner
alternatives (pytest --junitxml / cargo-nextest / vitest). It never mentions
that on a compiled language (Rust/Go/Java/C#), an acceptance test's RED
*before* the production code exists is a COMPILE ERROR -- no per-test
outcomes are produced, so no XML, and the mechanical seal structurally
cannot apply there -- and that ``des record-at-review-verdict`` (two-part
attestation) is the supported alternative in that case. An operator hitting
this branch on a compiled-language repo has no inline pointer to the escape
hatch that already exists (GDP-2/GDP-3: the HOW must route to the producing
tool, self-explaining what/why/how).

Hermetic, same idiom as
``tests/bugs/des/test_verify_red_green_how_message_junit_out_placeholder.py``
and ``tests/bugs/des/test_red_green_duplicate_testcase_false_pass.py``:
drives the REAL ``des verify-red-green`` CLI in-process via
``tests.common.in_process_cli.run_cli_in_process`` (the dispatcher-level
in-process analogue of ``python -m des.cli.__main__ verify-red-green ...``),
with a declared ``--run-cmd`` that controls whether JUnit XML is produced --
no pytest-in-pytest subprocess forking required.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.common.in_process_cli import run_cli_in_process


# A --run-cmd that runs successfully but writes NOTHING to {junit_out} --
# the tempfile verify_red_green pre-creates stays empty, so
# ElementTree.parse raises ElementTree.ParseError -> the "no parseable
# JUnit XML produced" branch. This is the faithful stand-in for "a
# compiled-language RED before the production code exists is a compile
# error, so the runner never emits per-test JUnit XML at all".
_NO_XML_RUN_CMD = f"{sys.executable} -c pass"


def _repo_with_test(tmp_path: Path) -> Path:
    (tmp_path / "test_x.py").write_text("# placeholder AT content\n")
    return tmp_path


def _canned_xml_run_cmd(tmp_path: Path, xml: str) -> str:
    """A --run-cmd that copies canned JUnit XML to {junit_out} -- no
    pytest-in-pytest, hermetic (same idiom as the duplicate-testcase
    regression test, test_red_green_duplicate_testcase_false_pass.py)."""
    xml_src = tmp_path / "canned.xml"
    xml_src.write_text(xml)
    copier = tmp_path / "copier.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _record_red(tmp_path: Path, repo: Path, run_cmd: str) -> tuple[int, str]:
    """Drive the REAL `des verify-red-green --record-red` in-process through
    the production dispatcher edge; return (exit_code, captured stdout)."""
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-red-green",
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--record-red",
            "--run-cmd",
            run_cmd,
        ],
        cwd=tmp_path,
    )
    assert stdout, f"no stdout captured -- stderr={stderr!r}"
    return exit_code, stdout


def _json_event(stdout: str, event: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        candidate = json.loads(stripped)
        if candidate.get("event") == event:
            return candidate
    raise AssertionError(f"no {event!r} JSON line in stdout: {stdout!r}")


def test_no_xml_indeterminate_names_record_at_review_verdict_alternative(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): the no-XML RedGreenIndeterminate must
    name `record-at-review-verdict` as the compiled-language alternative --
    today it lists only test-runner options (pytest/cargo-nextest/vitest),
    never the two-part attestation escape hatch, so this fails for the
    right (semantic, message-content) reason."""
    repo = _repo_with_test(tmp_path)

    exit_code, stdout = _record_red(tmp_path, repo, _NO_XML_RUN_CMD)

    assert exit_code == 2  # INDETERMINATE, never a silent pass
    payload = _json_event(stdout, "RedGreenIndeterminate")
    assert payload["what"] == "no parseable JUnit XML produced"
    haystack = f"{payload.get('how', '')} {payload.get('why', '')} {stdout}"
    assert "record-at-review-verdict" in haystack, (
        "the no-XML INDETERMINATE message must name the "
        "`des record-at-review-verdict` two-part-attestation alternative "
        "for a pre-implementation compile-error RED on a compiled "
        f"language; got: {haystack!r}"
    )


@pytest.mark.negative_at
def test_verify_red_green_normal_red_still_seals_without_alternative_noise(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): a
    genuine RED run (parseable JUnit XML with a real failing test) must
    still emit the normal `RedObserved` seal, NOT `RedGreenIndeterminate` --
    and the `record-at-review-verdict` advisory must NOT leak onto this
    unrelated success path (proves the fix is correctly scoped to the
    no-XML branch only, no overcorrection)."""
    repo = _repo_with_test(tmp_path)
    xml_red = (
        '<testsuite><testcase classname="t" name="test_scenario">'
        '<failure message="red"/></testcase></testsuite>'
    )

    exit_code, stdout = _record_red(
        tmp_path, repo, _canned_xml_run_cmd(tmp_path, xml_red)
    )

    assert exit_code == 0
    payload = _json_event(stdout, "RedObserved")
    assert payload["failing"] == ["t::test_scenario"]
    assert "RedGreenIndeterminate" not in stdout
    assert "record-at-review-verdict" not in stdout, (
        "the compiled-language alternative advisory must be scoped to the "
        f"no-XML branch only, not leak onto a normal RED seal: {stdout!r}"
    )
