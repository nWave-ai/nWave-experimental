"""slice-06 (declared-facts-reachable-recorded, F2) -- active-RED AT.

RedObserved / RedGreenSealed reach the AT-completion ledger keyed by
feature_id+slice_id, closing the "no common key with SliceCommitVerified"
defect (git-free -- no git join needed to compute time-to-green).

Design (docs/feature/declared-facts-reachable-recorded/feature-delta.md,
DD-6): ``des verify-red-green`` gains optional ``--feature-id``/``--slice-id``.
On ``_record_red`` success, calls the EXISTING
``AtCompletionLedger.append_gate_event(event="RedObserved", slice_id,
feature_id=, gate="verify-red-green")`` -- zero new ledger method. Same for
``_verify_green`` with ``event="RedGreenSealed"``. When both flags are
omitted, behavior is BYTE-IDENTICAL to today: the file-seal write (a
SEPARATE question -- "was the test edited between RED and GREEN") is
unconditional and untouched.

RED-not-BROKEN: ``--feature-id``/``--slice-id`` are not yet recognized
argparse options, so calling ``main([...])`` with them fails INSIDE the test
body via ``argparse``'s own ``SystemExit(2)`` (a real, observed pytest
``<failure>`` -- verified empirically: pytest's ``CallInfo.from_call`` catches
a ``SystemExit`` raised by test code and reports it as a normal failure, not a
collection error) -- a semantic witness that the flags do not exist yet, not
a collection/import accident. This file is intentionally standalone (does not
import fixtures from the pre-existing ``test_verify_red_green*.py`` files) so
the pytest-regression AT-discovery facet (``des carpaccio-slice-gate
--at-kind pytest-regression --regression-test-file <this file>``) counts
ONLY this slice's own ATs, not unrelated pre-existing regression pins.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.cli.verify_red_green import main


_FEATURE_ID = "declared-facts-reachable-recorded"
_SLICE_ID = "slice-06"

_XML_ALL_PASS = (
    '<testsuite><testcase classname="t" name="test_a"/>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_ONE_FAIL = (
    '<testsuite><testcase classname="t" name="test_a">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
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


def _run(repo: Path, phase: str, xml: str, *, with_flags: bool) -> int:
    argv = [
        "--repo",
        str(repo),
        "--test-file",
        "test_x.py",
        phase,
        "--run-cmd",
        _fake_runner(repo, xml),
    ]
    if with_flags:
        argv += ["--feature-id", _FEATURE_ID, "--slice-id", _SLICE_ID]
    return main(argv)


def _ledger_records(repo: Path, event: str) -> list[dict[str, object]]:
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    return [
        r
        for r in ledger.read_records(feature_id=_FEATURE_ID)
        if r.get("event") == event
    ]


def test_record_red_with_feature_and_slice_appends_redobserved_ledger_event(
    tmp_path: Path,
) -> None:
    repo = _repo_with_test(tmp_path)

    exit_code = _run(repo, "--record-red", _XML_ONE_FAIL, with_flags=True)

    assert exit_code == 0
    events = _ledger_records(repo, "RedObserved")
    assert len(events) == 1
    assert events[0]["slice_id"] == _SLICE_ID
    assert events[0]["gate"] == "verify-red-green"


def test_verify_green_with_feature_and_slice_appends_redgreensealed_ledger_event(
    tmp_path: Path,
) -> None:
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL, with_flags=True) == 0

    exit_code = _run(repo, "--verify-green", _XML_ALL_PASS, with_flags=True)

    assert exit_code == 0
    events = _ledger_records(repo, "RedGreenSealed")
    assert len(events) == 1
    assert events[0]["slice_id"] == _SLICE_ID
    assert events[0]["gate"] == "verify-red-green"


def test_flags_omitted_never_writes_a_ledger_event(tmp_path: Path) -> None:
    """NEGATIVE: unchanged behavior when --feature-id/--slice-id are not
    supplied -- no ledger event is ever written."""
    repo = _repo_with_test(tmp_path)

    assert _run(repo, "--record-red", _XML_ONE_FAIL, with_flags=False) == 0
    assert _run(repo, "--verify-green", _XML_ALL_PASS, with_flags=False) == 0

    ledger_path = AtCompletionLedger(_FEATURE_ID, repo).ledger_path()
    assert not ledger_path.exists()


def test_seal_file_bytes_identical_with_and_without_feature_slice_flags(
    tmp_path: Path,
) -> None:
    """Architecture-test: the content-seal file write is UNCONDITIONAL and
    byte-identical regardless of the new optional flags -- the seal answers a
    different question ("was the test edited between RED and GREEN") than the
    ledger event, and both must survive untouched."""
    repo_a = tmp_path / "a"
    repo_a.mkdir()
    (repo_a / "test_x.py").write_text("# content v1\n")
    repo_b = tmp_path / "b"
    repo_b.mkdir()
    (repo_b / "test_x.py").write_text("# content v1\n")

    assert _run(repo_a, "--record-red", _XML_ONE_FAIL, with_flags=False) == 0
    assert _run(repo_b, "--record-red", _XML_ONE_FAIL, with_flags=True) == 0

    seal_a = repo_a / ".nwave" / "telemetry" / "red-green" / "test_x.py.json"
    seal_b = repo_b / ".nwave" / "telemetry" / "red-green" / "test_x.py.json"
    assert json.loads(seal_a.read_text()) == json.loads(seal_b.read_text())
