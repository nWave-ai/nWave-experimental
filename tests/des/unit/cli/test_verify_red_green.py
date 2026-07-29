"""P0.2 RED->GREEN seal — the observed proofs, pinned as regression.

Hermetic: the declared --run-cmd is a tiny copier script that writes a CANNED
JUnit XML to {junit_out} (no pytest-in-pytest). Each test reproduces one
observed proof from the evolution plan's P0.2 evidence row.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from des.cli.verify_red_green import main


_XML_ALL_PASS = (
    '<testsuite><testcase classname="t" name="test_a"/>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_ONE_FAIL = (
    '<testsuite><testcase classname="t" name="test_a">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_COLLECT_ERROR = (
    '<testsuite><testcase classname="" name="test_mod">'
    '<error message="import error"/></testcase></testsuite>'
)


def _fake_runner(tmp_path: Path, xml: str) -> str:
    """A single-string --run-cmd that copies canned XML to {junit_out}."""
    slug = hashlib.md5(xml.encode()).hexdigest()[:8]
    xml_src = tmp_path / f"canned_{slug}.xml"
    xml_src.write_text(xml)
    copier = tmp_path / "copier.py"
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


def test_vacuous_all_pass_red_is_refused(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ALL_PASS) == 1  # witnesses nothing


def test_broken_collection_error_is_refused_not_red(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_COLLECT_ERROR) == 1  # BROKEN, not RED


def test_red_then_green_is_sealed(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL) == 0
    assert _run(repo, "--verify-green", _XML_ALL_PASS) == 0


def test_tampered_test_file_voids_the_seal(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL) == 0
    (repo / "test_x.py").write_text("# content v2 — tampered\n")
    assert _run(repo, "--verify-green", _XML_ALL_PASS) == 1  # evidence void


def test_tampered_test_file_refusal_names_the_file_and_both_hashes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Regression (AUDIT-gate-cli.md G1): the `RedGreenRefused`/phase=green
    payload used to omit `test_file` and the two sha256 hashes it had
    ALREADY computed, leaving the operator to guess which file changed --
    the sibling refusal 6 lines above it (`no RED record for {name}`) named
    the file. This pins that the tampered-content refusal now names the
    same facts it already holds: the file, the RED-recorded hash, and the
    current hash -- so an operator sees exactly what diverged, not just
    that something did.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL) == 0
    recorded_sha = hashlib.sha256((repo / "test_x.py").read_bytes()).hexdigest()
    (repo / "test_x.py").write_text("# content v2 — tampered\n")
    current_sha = hashlib.sha256((repo / "test_x.py").read_bytes()).hexdigest()

    assert _run(repo, "--verify-green", _XML_ALL_PASS) == 1

    events = [
        json.loads(line)
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]
    refusals = [e for e in events if e.get("event") == "RedGreenRefused"]
    assert len(refusals) == 1, f"expected exactly one RedGreenRefused event: {events}"
    refusal = refusals[0]
    assert refusal["test_file"] == "test_x.py"
    assert refusal["recorded_content_sha256"] == recorded_sha
    assert refusal["current_content_sha256"] == current_sha
    assert recorded_sha != current_sha  # sanity: the two hashes must differ
    assert "test_x.py" in refusal["what"]


def test_missing_red_record_degrades_indeterminate(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--verify-green", _XML_ALL_PASS) == 2  # never-red, LOUD
