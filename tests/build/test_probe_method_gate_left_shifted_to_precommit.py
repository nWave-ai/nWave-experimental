"""Left-shift pin: the CI `probe-method-check` job fires at COMMIT time too.

Bug class (documented-as-precommit-but-never-wired): `scripts/hooks/check_probe_method.py`
walks `nwave_ai/feature_delta/adapters/*.py` and fails if any adapter class is
missing a `probe()` method (DD-A5 structural layer). Its own docstring already
says `Usage (pre-commit):` and calls itself "layer 2 of 3: Structural -- this
AST walker (pre-commit + CI)" -- but it was only invoked from
`.github/workflows/ci.yml` (`probe-method-check` job), never from
`.pre-commit-config.yaml`. An author writing an adapter class without `probe()`
learned about it ~25 minutes later in CI, after a commit and a push, for a
check that runs in well under a second locally.

**GDP-1** (intercept EARLY, before the effort it guards is spent): a missing
`probe()` method is knowable in milliseconds at `git commit`, not after a full
CI round-trip.

Same two constraints as the file-quality left-shift
(`test_file_quality_left_shifted_to_precommit.py`) bound this design, and this
test pins both:

1. STAGED-SCOPED, not whole-tree. `files:` restricts the hook to adapter files,
   and `pass_filenames` is NOT forced false, so pre-commit hands it only the
   staged files -- a commit is graded on its own adapters, not blocked by a
   pre-existing offender elsewhere in the adapters directory.
2. The CI job is NOT dropped. It runs with no arguments (whole-tree scan of
   the adapters directory) and stays as the backstop for anyone who bypasses
   git hooks (`--no-verify`, a different CI, hooks never installed).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
PROBE_SCRIPT = PROJECT_ROOT / "scripts" / "hooks" / "check_probe_method.py"


def _hooks() -> list[dict]:
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    return [h for repo in config.get("repos", []) for h in repo.get("hooks", [])]


def _probe_method_hook() -> dict | None:
    for hook in _hooks():
        if "check_probe_method.py" in hook.get("entry", ""):
            return hook
    return None


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROBE_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# GDP-1 -- the gate fires at commit time, matching its own docstring's claim
# ---------------------------------------------------------------------------


def test_precommit_wires_the_probe_method_gate():
    """NEGATIVE: check_probe_method.py has no commit-stage counterpart.

    Declared-fact check (GDP-8): asserts the hook DECLARATION exists (id, real
    entry, pre-commit stage) rather than inferring arming from any indirect
    signal such as the script's own docstring.
    """
    hook = _probe_method_hook()

    assert hook is not None, (
        "no .pre-commit-config.yaml hook invokes check_probe_method.py -- the "
        "script's own docstring says 'Usage (pre-commit):' and calls itself "
        "layer 2 of 3 (Structural: pre-commit + CI), but only the CI job "
        "actually runs it -- an author only learns about a missing probe() "
        "after a full push + CI round trip"
    )
    assert "pre-commit" in hook.get("stages", ["pre-commit"]), (
        f"check-probe-method hook is not staged at pre-commit: {hook!r}"
    )


def test_probe_method_gate_files_pattern_covers_the_adapters_directory():
    """NEGATIVE: the hook's `files:` trigger misses the adapters directory.

    A `files:` regex that does not match a real adapter file means an edit to
    that file never fires the check at commit time.
    """
    hook = _probe_method_hook()
    assert hook is not None, (
        "precede this test with test_precommit_wires_the_probe_method_gate"
    )

    import re

    pattern = re.compile(hook["files"])
    sample_adapter = "nwave_ai/feature_delta/adapters/clock.py"
    assert pattern.match(sample_adapter), (
        f"check-probe-method's files: {hook['files']!r} does not match a real "
        f"adapter path {sample_adapter!r} -- editing that file would never "
        "trigger the gate"
    )


# ---------------------------------------------------------------------------
# Blast radius -- the commit-time hook grades the commit, not the whole repo
# ---------------------------------------------------------------------------


def test_probe_method_hook_does_not_scan_the_whole_tree_at_commit_time():
    """NEGATIVE: the commit-stage hook receives filenames rather than scanning all.

    With `pass_filenames: false` the hook re-scans the whole adapters directory
    on every commit, so ONE pre-existing offender blocks every author's
    unrelated commit until someone else's class is fixed. Whole-tree coverage
    is the CI job's role.
    """
    hook = _probe_method_hook()
    assert hook is not None, (
        "precede this test with test_precommit_wires_the_probe_method_gate"
    )

    assert hook.get("pass_filenames") is not False, (
        "check-probe-method sets pass_filenames: false -- it now scans the "
        "whole adapters directory at commit time instead of the staged "
        f"files, blocking commits on pre-existing offenders: {hook!r}"
    )


# ---------------------------------------------------------------------------
# Behavioral proof -- the gate actually rejects a missing probe()
# ---------------------------------------------------------------------------


def test_probe_method_gate_rejects_an_adapter_class_missing_probe(tmp_path):
    """NEGATIVE: an adapter class without probe() does not pass silently."""
    offender = tmp_path / "adapters" / "offender_adapter.py"
    offender.parent.mkdir(parents=True, exist_ok=True)
    offender.write_text(
        "class OffenderAdapter:\n    def do_thing(self) -> None:\n        pass\n",
        encoding="utf-8",
    )

    result = _run(str(offender))

    assert result.returncode == 1, (
        "check_probe_method.py accepted an adapter class with no probe() "
        f"method; returncode={result.returncode} stderr={result.stderr!r}"
    )
    assert "OffenderAdapter" in result.stderr and "probe()" in result.stderr, (
        "check_probe_method.py rejected the file but did not name the "
        f"offending class; stderr={result.stderr!r}"
    )


def test_probe_method_gate_passes_an_adapter_class_with_probe(tmp_path):
    """POSITIVE control for the negative above: a compliant class passes."""
    compliant = tmp_path / "adapters" / "compliant_adapter.py"
    compliant.parent.mkdir(parents=True, exist_ok=True)
    compliant.write_text(
        "class CompliantAdapter:\n"
        "    def do_thing(self) -> None:\n"
        "        pass\n\n"
        "    def probe(self) -> None:\n"
        "        pass\n",
        encoding="utf-8",
    )

    result = _run(str(compliant))

    assert result.returncode == 0, (
        "check_probe_method.py rejected an adapter class that does implement "
        f"probe(); stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# The backstop stays -- left-shift ADDS an early gate, it does not move one
# ---------------------------------------------------------------------------


def test_ci_probe_method_job_is_never_dropped_when_the_check_left_shifts():
    """NEGATIVE: the CI job survives, covering anyone who bypasses git hooks.

    A contributor with hooks uninstalled, a different CI, or an authorized
    `--no-verify` must still be intercepted.
    """
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "probe-method-check:" in workflow, (
        "the CI probe-method-check job was removed -- the pre-commit hook is "
        "an EARLIER gate, not a replacement: anyone who bypasses git hooks "
        "would no longer be intercepted at all"
    )
    assert "check_probe_method.py" in workflow, (
        "the CI probe-method-check job no longer invokes check_probe_method.py"
    )
