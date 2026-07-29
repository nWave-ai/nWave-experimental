"""Left-shift pin: the CI `file-quality` checks fire at COMMIT time, not after push.

Bug class (file-quality-discovered-only-after-push): the CI `file-quality` job
(`.github/workflows/ci.yml`) rejects trailing whitespace and missing end-of-file
newlines -- but only once the author has already spent a commit, a push, and a
full CI round-trip. Both producing scripts already exist in `scripts/hooks/`
(`check_trailing_whitespace.py`, `check_end_of_file.py`); neither was wired into
`.pre-commit-config.yaml`, so the cheapest interception point went unused.

Two gate-design principles are inverted by that arrangement:

- **GDP-1** (intercept EARLY, before the effort it guards is spent): a missing
  final newline is knowable in milliseconds at `git commit`, not ~25 minutes
  later in CI.
- **GDP-5** (cost on the SYSTEM, not the operator): a rejection that says
  "trailing whitespace on line 3" and leaves the operator to go delete it by
  hand is a half-measure. Per **GDP-4** the HOW must invoke the PRODUCING TOOL --
  one command that repairs every offender mechanically.

Two constraints bound the design, and these tests pin both:

1. The hook must NOT auto-modify-and-restage. Four auto-formatting hooks were
   deliberately removed on 2026-05-28 (commit 11a24c637, Ale directive) because
   concurrent auto-modifiers race across parallel worktrees. So the hook CHECKS
   and blocks; the operator runs the `--fix` route the message names.
2. The hook must scope to the STAGED files, not the whole tree. A whole-tree
   scan at commit time makes every author responsible for every pre-existing
   offender anywhere in the repo -- a lane cannot commit its own clean file
   because an unrelated lane left trailing whitespace in a doc. Whole-tree
   remains the CI job's business; the CI job is retained as the backstop for
   anyone who bypasses git hooks entirely.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

TRAILING_WS_SCRIPT = PROJECT_ROOT / "scripts" / "hooks" / "check_trailing_whitespace.py"
END_OF_FILE_SCRIPT = PROJECT_ROOT / "scripts" / "hooks" / "check_end_of_file.py"

# The producing script each CI `file-quality` check must also run at commit time.
CI_FILE_QUALITY_PRODUCERS = {
    "trailing whitespace": "check_trailing_whitespace.py",
    "end of file newlines": "check_end_of_file.py",
    "YAML syntax": "validate_yaml_files.py",
    "JSON syntax": "check_json_syntax.py",
}


def _hooks() -> list[dict]:
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    return [h for repo in config.get("repos", []) for h in repo.get("hooks", [])]


def _commit_stage_hooks() -> list[dict]:
    return [h for h in _hooks() if "pre-commit" in h.get("stages", ["pre-commit"])]


def _file_quality_hooks() -> list[dict]:
    """The two hooks this left-shift wires (whitespace + end-of-file)."""
    wanted = ("check_trailing_whitespace.py", "check_end_of_file.py")
    return [h for h in _hooks() if any(w in h.get("entry", "") for w in wanted)]


def _run(script: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# GDP-1 -- the check fires at the earliest point, not after the push
# ---------------------------------------------------------------------------


def test_precommit_never_omits_a_ci_file_quality_check():
    """Every CI `file-quality` check has a commit-stage counterpart.

    NEGATIVE: a check that exists only in CI is a check the author pays for
    with a full push round-trip.
    """
    entries = " ".join(h.get("entry", "") for h in _commit_stage_hooks())

    missing = [
        f"{label} (producer: {producer})"
        for label, producer in CI_FILE_QUALITY_PRODUCERS.items()
        if producer not in entries
    ]

    assert not missing, (
        "CI file-quality check(s) have no commit-stage counterpart, so the "
        "author only learns about them after committing AND pushing AND "
        "waiting for CI (GDP-1: intercept before the effort is spent):\n  "
        + "\n  ".join(missing)
    )


def test_precommit_rejects_a_staged_file_with_trailing_whitespace(tmp_path):
    """NEGATIVE: an offending file does not pass the check silently."""
    offender = tmp_path / "offender.md"
    offender.write_text("clean line\ntrailing spaces here   \n", encoding="utf-8")

    result = _run(TRAILING_WS_SCRIPT, "--check", str(offender))

    assert result.returncode != 0, (
        "check_trailing_whitespace.py accepted a file with trailing whitespace "
        f"when handed that file explicitly; stdout={result.stdout!r}"
    )
    # Naming the file pins that the verdict came from the file we HANDED it --
    # a whole-tree scan that ignores its arguments would also exit non-zero
    # while saying nothing about this file (a pass for the wrong reason).
    assert "offender.md" in result.stdout, (
        "check_trailing_whitespace.py exited non-zero but never mentions the "
        "file it was given -- it is scanning the whole tree and ignoring its "
        f"arguments; stdout={result.stdout!r}"
    )


def test_precommit_rejects_a_staged_file_missing_its_final_newline(tmp_path):
    """NEGATIVE: a file with no final newline does not pass the check."""
    offender = tmp_path / "offender.txt"
    offender.write_bytes(b"no newline at the end")

    result = _run(END_OF_FILE_SCRIPT, "--check", str(offender))

    assert result.returncode != 0, (
        "check_end_of_file.py accepted a file with no final newline when "
        f"handed that file explicitly; stdout={result.stdout!r}"
    )
    assert "offender.txt" in result.stdout, (
        "check_end_of_file.py exited non-zero but never mentions the file it "
        f"was given -- it ignored its arguments; stdout={result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# GDP-4 / GDP-5 -- the cost of repair sits on the system, not the operator
# ---------------------------------------------------------------------------


def test_trailing_whitespace_check_does_not_merely_report_without_repairing(tmp_path):
    """NEGATIVE: the check is not report-only -- a `--fix` route repairs it.

    A gate that names a defect and leaves the operator to hand-edit it puts
    the cost on the operator (GDP-5 inverted). The producing tool must be able
    to do the repair itself (GDP-4).
    """
    offender = tmp_path / "offender.md"
    offender.write_text("keep me\nstrip me   \n\ttabbed\t\n", encoding="utf-8")

    result = _run(TRAILING_WS_SCRIPT, "--fix", str(offender))

    assert result.returncode == 0, (
        "check_trailing_whitespace.py has no working `--fix` route, so the "
        "operator must hand-repair every offender (GDP-4: the HOW must invoke "
        f"the producing tool); stderr={result.stderr!r}"
    )
    assert offender.read_text(encoding="utf-8") == "keep me\nstrip me\n\ttabbed\n", (
        "`--fix` ran but did not actually strip the trailing whitespace: "
        f"{offender.read_text(encoding='utf-8')!r}"
    )


def test_end_of_file_check_does_not_merely_report_without_repairing(tmp_path):
    """NEGATIVE: the end-of-file check repairs rather than only reporting."""
    offender = tmp_path / "offender.txt"
    offender.write_bytes(b"no newline at the end")

    result = _run(END_OF_FILE_SCRIPT, "--fix", str(offender))

    assert result.returncode == 0, (
        "check_end_of_file.py `--fix` failed on an explicit file argument; "
        f"stderr={result.stderr!r}"
    )
    assert offender.read_bytes() == b"no newline at the end\n", (
        f"`--fix` did not append the missing newline: {offender.read_bytes()!r}"
    )


def test_file_quality_rejection_never_omits_the_command_that_repairs_it(tmp_path):
    """NEGATIVE: the rejection carries a runnable HOW, not just a WHAT.

    GDP-3: every failure explains WHAT / WHY / HOW. The HOW must be a command
    the operator can paste, not the prose instruction "add a newline".
    """
    offender = tmp_path / "offender.md"
    offender.write_text("trailing   \n", encoding="utf-8")
    ws_output = _run(TRAILING_WS_SCRIPT, "--check", str(offender)).stdout

    eof_offender = tmp_path / "offender.txt"
    eof_offender.write_bytes(b"no newline")
    eof_output = _run(END_OF_FILE_SCRIPT, "--check", str(eof_offender)).stdout

    for name, output, producer in (
        ("check_trailing_whitespace.py", ws_output, "check_trailing_whitespace.py"),
        ("check_end_of_file.py", eof_output, "check_end_of_file.py"),
    ):
        assert "--fix" in output and producer in output, (
            f"{name} rejected a file without naming the command that repairs "
            f"it -- the operator is left to hand-edit (GDP-3/GDP-4). "
            f"Output was:\n{output}"
        )


# ---------------------------------------------------------------------------
# Blast radius -- the commit-time hook grades the commit, not the whole repo
# ---------------------------------------------------------------------------


def test_file_quality_hooks_do_not_scan_the_whole_tree_at_commit_time():
    """NEGATIVE: the commit-stage hooks receive filenames rather than scanning all.

    With `pass_filenames: false` + `always_run: true` the hook re-scans every
    tracked file on every commit, so ONE pre-existing offender anywhere blocks
    EVERY author's unrelated commit until someone else's file is repaired.
    That is cost on the operator (GDP-5 inverted) for a defect they did not
    introduce. Whole-tree coverage is the CI job's role.
    """
    wired = _file_quality_hooks()
    assert wired, (
        "no pre-commit hook wires check_trailing_whitespace.py or "
        "check_end_of_file.py -- the left-shift is not in place"
    )

    whole_tree = [
        h.get("id", "<unknown>")
        for h in wired
        if h.get("pass_filenames") is False or h.get("always_run") is True
    ]

    assert not whole_tree, (
        "file-quality hook(s) scan the whole tree at commit time instead of "
        "the staged files, so an unrelated pre-existing offender blocks every "
        "commit in every worktree: " + ", ".join(whole_tree)
    )


def test_file_quality_hooks_never_auto_modify_and_restage():
    """NEGATIVE: the wired hooks check; they never rewrite files behind the author.

    Auto-modifying hooks were removed 2026-05-28 (commit 11a24c637) because
    concurrent rewrites race across parallel worktrees. The left-shift must not
    reintroduce that class: `--fix` is an operator-invoked route, never the
    hook's own entry.
    """
    auto_fixers = [
        f"{h.get('id', '<unknown>')}: {h.get('entry', '')!r}"
        for h in _file_quality_hooks()
        if "--fix" in h.get("entry", "")
    ]

    assert not auto_fixers, (
        "file-quality hook(s) run in auto-fix mode -- reintroduces the "
        "concurrent-auto-modifier race removed on 2026-05-28 (11a24c637). "
        "The hook must run `--check`; the rejection names `--fix` for the "
        "operator to run: " + ", ".join(auto_fixers)
    )


# ---------------------------------------------------------------------------
# The backstop stays -- left-shift ADDS an early gate, it does not move one
# ---------------------------------------------------------------------------


def test_ci_file_quality_job_is_never_dropped_when_the_check_left_shifts():
    """NEGATIVE: the CI job survives, covering anyone who bypasses git hooks.

    A contributor with hooks uninstalled, a different CI, or an authorized
    `--no-verify` must still be intercepted.
    """
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "file-quality:" in workflow, (
        "the CI `file-quality` job was removed -- the pre-commit hook is an "
        "EARLIER gate, not a replacement: anyone who bypasses git hooks would "
        "no longer be intercepted at all"
    )

    # CI expresses each check in its own way (two inline shell/python steps,
    # two script invocations), so the backstop is pinned on the check LABEL --
    # what CI still verifies -- not on how it happens to be spelled today.
    for label in CI_FILE_QUALITY_PRODUCERS:
        assert label.lower() in workflow.lower(), (
            f"CI file-quality no longer checks {label!r} -- the whole-tree "
            "backstop lost a check when it left-shifted to pre-commit"
        )
