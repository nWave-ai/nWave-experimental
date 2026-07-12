"""Regression net — backlog #105: `des verify-red-green` duplicate-testcase
false all-pass.

RCA (2026-07-12): `_run_and_collect` (src/des/cli/verify_red_green.py:120-206)
keys outcomes on ``classname::name`` and assigns unconditionally
(``outcomes[test_id] = "fail" if failed else "pass"``, :197) -- last write
wins. Two JUnit ``<testcase>`` elements sharing classname+name (the confirmed
real vector: a pytest-bdd Scenario Outline with 2 Examples rows) collapse to
one key; a later PASS silently overwrites an earlier FAIL, and
``--verify-green`` reports SEALED while the run genuinely failed.

Hermetic, same idiom as tests/des/unit/cli/test_verify_red_green.py: the
declared --run-cmd is a tiny copier script writing a CANNED JUnit XML to
{junit_out} (no pytest-in-pytest).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from des.cli.verify_red_green import main


_EXIT_OK = 0

# One prior RED record: a single, distinct, genuinely-failing test.
_XML_RED_BASELINE = (
    '<testsuite><testcase classname="t" name="test_scenario">'
    '<failure message="red"/></testcase></testsuite>'
)

# The real vector: two <testcase> elements, SAME classname::name, fail FIRST
# (real pytest-bdd execution order) then pass.
_XML_GREEN_DUP_FAIL_THEN_PASS = (
    "<testsuite>"
    '<testcase classname="t" name="test_scenario"><failure message="red"/></testcase>'
    '<testcase classname="t" name="test_scenario"/>'
    "</testsuite>"
)

# All-distinct ids -- the well-formed path the fix must not disturb.
_XML_ALL_PASS = (
    '<testsuite><testcase classname="t" name="test_a"/>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_ONE_FAIL = (
    '<testsuite><testcase classname="t" name="test_a">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)

# A duplicate-id group where BOTH entries pass, alongside one real distinct
# failure -- the fold must not fabricate a failure for the all-passing group.
_XML_RED_WITH_ALL_PASS_DUP_GROUP = (
    "<testsuite>"
    '<testcase classname="t" name="test_real"><failure message="red"/></testcase>'
    '<testcase classname="t" name="test_dup"/>'
    '<testcase classname="t" name="test_dup"/>'
    "</testsuite>"
)


def _fake_runner(tmp_path: Path, xml: str) -> str:
    """A single-string --run-cmd that copies canned XML to {junit_out}."""
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


def _seal_outcomes(repo: Path) -> dict[str, str]:
    seal = repo / ".nwave" / "telemetry" / "red-green" / "test_x.py.json"
    return json.loads(seal.read_text())["outcomes"]


def test_duplicate_fail_then_pass_is_not_reported_all_green_and_declares_collapse(
    tmp_path: Path, capsys
) -> None:
    """WITNESS 1+2: a duplicate-id fail-then-pass run must not SEAL as
    all-green (the fold is fail-dominant), AND the id-collapse (2 raw
    <testcase> elements folding to 1 test id) must be declared loudly in
    the gate's output -- not proceed silently.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_RED_BASELINE) == _EXIT_OK

    exit_code = _run(repo, "--verify-green", _XML_GREEN_DUP_FAIL_THEN_PASS)
    out = capsys.readouterr().out

    # WITNESS 1 -- fail-dominant fold: never reported all-green/SEALED.
    assert exit_code != _EXIT_OK, (
        "duplicate-id fail-then-pass was reported as GREEN/SEALED "
        f"(exit={exit_code}); the fold must be fail-dominant"
    )
    assert "SEALED" not in out

    # WITNESS 2 -- the collapse is declared loudly (what collapsed, not
    # proceeding silently). Exact wording is the crafter's to choose
    # (module's existing self-explaining conventions); assert presence of
    # a collapse declaration naming the folded id, not exact phrasing.
    lowered = out.lower()
    assert any(kw in lowered for kw in ("collaps", "duplicate")), (
        f"no collapse/duplicate declaration found in gate output: {out!r}"
    )
    assert "t::test_scenario" in out, (
        f"collapse declaration does not name the folded test id: {out!r}"
    )


def test_all_distinct_ids_never_declare_a_collapse(tmp_path: Path, capsys) -> None:
    """NEGATIVE: an all-distinct-id JUnit run keeps today's verdict
    byte-identical -- no new noise, no collapse declaration on the
    well-formed path.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL) == _EXIT_OK
    capsys.readouterr()  # drain the RED-phase output before the assertion

    exit_code = _run(repo, "--verify-green", _XML_ALL_PASS)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_OK
    assert "SEALED" in out
    lowered = out.lower()
    assert not any(kw in lowered for kw in ("collaps", "duplicate")), (
        f"spurious collapse declaration on an all-distinct-id run: {out!r}"
    )


def test_all_passing_duplicate_group_never_fabricates_a_failure(
    tmp_path: Path,
) -> None:
    """NEGATIVE: a duplicate-id group whose entries ALL pass must not
    manufacture a failure -- at most a declared collapse, never a
    fabricated red for that id.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_RED_WITH_ALL_PASS_DUP_GROUP)

    assert exit_code == _EXIT_OK  # the real distinct failure witnesses RED
    outcomes = _seal_outcomes(repo)
    assert outcomes["t::test_real"] == "fail"
    assert outcomes["t::test_dup"] == "pass", (
        "an all-passing duplicate-id group must not be fabricated as a "
        f"failure: {outcomes}"
    )
