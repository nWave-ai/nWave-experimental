"""P0.2 RED->GREEN seal — the observed proofs, pinned as regression.

Hermetic: the declared --run-cmd is a tiny copier script that writes a CANNED
JUnit XML to {junit_out} (no pytest-in-pytest). Each test reproduces one
observed proof from the evolution plan's P0.2 evidence row.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

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


def test_missing_red_record_degrades_indeterminate(tmp_path: Path) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--verify-green", _XML_ALL_PASS) == 2  # never-red, LOUD
