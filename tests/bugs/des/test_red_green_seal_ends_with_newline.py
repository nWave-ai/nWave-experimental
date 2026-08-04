"""Regression: `des verify-red-green --record-red` writes the RED seal via
raw `json.dumps(...)` (`src/des/cli/verify_red_green.py`, `_record_red`,
lines 442-453) -- `json.dumps` never emits a trailing newline.

`.nwave/telemetry/red-green/` is git-tracked (since commit eab6041b5), and the
pre-commit hook `check-end-of-file` (`scripts/hooks/check_end_of_file.py
--check`, wired with no `files:` filter, so it runs against every staged
non-binary file) REJECTS a commit carrying a seal produced this way with
"Missing newline at end of file". It is a CHECKER, not a fixer -- the same
commit retried unchanged fails identically and never converges on its own.
Every seal already in the tree has a trailing newline only because it was
hand-repaired in a prior commit, never because the writer emits one.

Oracles:

  POSITIVE (primary) -- a freshly written RED seal ends with a trailing
  `\\n`, and REMAINS so across repeated (retried) `--record-red` invocations
  on the same file (idempotent on the final byte -- never 0, never 2+).

  POSITIVE (second axis, GDP-8 witness corollary) -- the seal is not merely
  asserted to end in `\\n` by re-implementing the hook's own rule; it is fed
  to the REAL gate, `scripts/hooks/check_end_of_file.py --check`, and that
  gate must accept it (exit 0). The gate defines the property; this AT
  witnesses conformance to the actual gate, not a private restatement of it.

  NEGATIVE (the cure must not become a new disease):
    * the seal stays valid, re-parseable JSON regardless of the trailing
      newline (a missing OR single trailing `\\n` never corrupts the JSON
      body)
    * the seal's semantic payload (`test_file` / `content_sha256` /
      `outcomes`) is unaffected by the newline -- inert to the consumer
    * the seal remains consumable by its real reader: `--verify-green` must
      still accept a seal carrying a trailing newline (proves the fix does
      not break the RED->GREEN round trip -- the highest-value negative
      oracle here, because it verifies the CONSUMER, not just the producer)

Hermetic: reuses the `_fake_runner`/`_repo_with_test` idiom already
established in `tests/des/unit/cli/test_verify_red_green.py` -- a canned-
JUnit-XML copier `--run-cmd`, no pytest-in-pytest subprocess. Every seal is
written under `tmp_path`; this file never touches the real worktree's
`.nwave/telemetry/red-green/`.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from des.cli.verify_red_green import _seal_path, main


PROJECT_ROOT = Path(__file__).resolve().parents[3]
END_OF_FILE_SCRIPT = PROJECT_ROOT / "scripts" / "hooks" / "check_end_of_file.py"

_XML_ONE_FAIL = (
    '<testsuite><testcase classname="t" name="test_a">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_ALL_PASS = (
    '<testsuite><testcase classname="t" name="test_a"/>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)


def _fake_runner(tmp_path: Path, xml: str, slug: str) -> str:
    """A single-string --run-cmd that copies canned XML to {junit_out} --
    same hermetic idiom as tests/des/unit/cli/test_verify_red_green.py."""
    xml_src = tmp_path / f"canned_{slug}.xml"
    xml_src.write_text(xml)
    copier = tmp_path / "copier.py"
    if not copier.is_file():
        copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _repo_with_test(tmp_path: Path) -> Path:
    (tmp_path / "test_x.py").write_text("# content v1\n")
    return tmp_path


def _record_red(repo: Path, xml: str, slug: str) -> int:
    return main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--record-red",
            "--run-cmd",
            _fake_runner(repo, xml, slug),
        ]
    )


def _verify_green(repo: Path, xml: str, slug: str) -> int:
    return main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            "--verify-green",
            "--run-cmd",
            _fake_runner(repo, xml, slug),
        ]
    )


@pytest.mark.parametrize("record_attempts", [1, 2, 3])
def test_record_red_seal_ends_with_exactly_one_trailing_newline(
    tmp_path: Path, record_attempts: int
) -> None:
    """POSITIVE (primary): however many times `--record-red` is (re)run
    against the SAME test file (a rejected-commit retry, per the bug
    narrative), the on-disk seal ends with exactly one trailing `\\n` --
    never zero (today's defect) and never an accumulating two-or-more (a
    naive append-mode fix would regress this). Fails today: `json.dumps`
    emits no trailing newline at all, for any attempt count.
    """
    repo = _repo_with_test(tmp_path)
    for attempt in range(record_attempts):
        exit_code = _record_red(repo, _XML_ONE_FAIL, f"fail-{attempt}")
        assert exit_code == 0, f"attempt {attempt}: --record-red did not succeed"

    seal = _seal_path(repo, repo / "test_x.py")
    raw = seal.read_bytes()
    assert raw.endswith(b"\n") and not raw.endswith(b"\n\n"), (
        f"after {record_attempts} --record-red invocation(s), the seal "
        f"{seal} must end with EXACTLY one trailing newline; got last 5 "
        f"bytes: {raw[-5:]!r}"
    )


def test_record_red_seal_is_accepted_by_the_real_end_of_file_gate(
    tmp_path: Path,
) -> None:
    """POSITIVE (second axis, GDP-8 witness corollary): the freshly written
    seal must be ACCEPTED by the real pre-commit gate
    (`check_end_of_file.py --check <seal>`, exit 0) -- not merely pass a
    private `endswith("\\n")` re-implementation of that gate's rule. Fails
    today: the gate rejects the seal with "Missing newline at end of file".
    """
    repo = _repo_with_test(tmp_path)
    assert _record_red(repo, _XML_ONE_FAIL, "gate") == 0

    seal = _seal_path(repo, repo / "test_x.py")
    result = subprocess.run(
        [sys.executable, str(END_OF_FILE_SCRIPT), "--check", str(seal)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, (
        f"check_end_of_file.py --check rejected the RED seal {seal} -- the "
        f"exact pre-commit failure this defect reproduces: "
        f"stdout={result.stdout!r}"
    )


@pytest.mark.negative_at
def test_record_red_seal_content_is_not_corrupted_by_the_trailing_newline(
    tmp_path: Path,
) -> None:
    """NEGATIVE: the seal must stay valid, re-parseable JSON, and its
    semantic payload (`test_file` / `content_sha256` / `outcomes`) must be
    exactly the pre-newline values -- the trailing newline is inert to the
    consumer, never a corruption of the record. Passes both before and
    after the fix (a newline appended after valid JSON text never breaks
    `json.loads`); pinned here so a bad fix (e.g. writing malformed
    boilerplate around the JSON to force a newline) is caught.
    """
    repo = _repo_with_test(tmp_path)
    assert _record_red(repo, _XML_ONE_FAIL, "content") == 0

    seal = _seal_path(repo, repo / "test_x.py")
    record = json.loads(seal.read_text())

    assert record["test_file"] == "test_x.py"
    assert record["content_sha256"], "content_sha256 must not be blanked out"
    assert record["outcomes"] == {"t::test_a": "fail", "t::test_pin": "pass"}


@pytest.mark.negative_at
def test_verify_green_still_accepts_a_seal_carrying_a_trailing_newline(
    tmp_path: Path,
) -> None:
    """NEGATIVE (highest-value oracle): a seal carrying a trailing newline
    -- the exact shape the fix will produce -- must still be ACCEPTED by
    its real consumer, `--verify-green` (RedGreenSealed, exit 0). This
    proves the newline fix cannot break the RED->GREEN round trip: it
    exercises the CONSUMER of the seal, not only its producer. The trailing
    newline is appended manually here (simulating the fixed writer's
    output) so this control is independent of, and passes before, the
    production fix landing.
    """
    repo = _repo_with_test(tmp_path)
    assert _record_red(repo, _XML_ONE_FAIL, "roundtrip") == 0

    seal = _seal_path(repo, repo / "test_x.py")
    seal.write_bytes(seal.read_bytes() + b"\n")  # simulate the fixed writer

    assert _verify_green(repo, _XML_ALL_PASS, "roundtrip-green") == 0, (
        "a RED seal carrying a trailing newline must still be accepted by "
        "--verify-green -- the newline fix must not break the RED->GREEN "
        "consumer round trip"
    )
