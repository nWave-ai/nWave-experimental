"""D31a (a): arm the unarmed DoR-items drift gate at commit time.

Bug class (same shape as `test_file_quality_left_shifted_to_precommit.py`'s D08,
and today's third instance of "catalogued and documented, nothing invokes it"):
`scripts/cli/check_dor_items_drift.py` was built and AT-reviewed as slice-04 of
the `dor-items-ssot` feature (shipped `e3cb804c6`) -- its own K3 acceptance
criterion reads "a maintainer editing a DoR home is prevented from introducing a
divergent copy... the drift gate red-flags 100% of edits that desynchronize a
home from the SSOT." That is an edit-time guarantee, but nothing invoked the
gate at edit time: zero hits across `.pre-commit-config.yaml`, `.github/workflows/`,
`src/des/adapters/drivers/hooks/` + `src/des/application/` (the runtime-hook
call sites), and every `nWave/skills/` + `nWave/agents/` + `nWave/tasks/` prose
file (the "armed only via prose" surface this tree's D27 measurement already
named as a real wiring channel, so it had to be checked too). Only tests ever
called it.

This is a genuine build-but-never-armed gap, not a WIP-in-flight slice: the
`dor-items-ssot` feature has no `pending` slices left (all 4 shipped), so there
is no future slice that arms it -- either it stays permanently inert or it gets
armed now. The reason for existing is not spent (K3 is a locked, unmet
acceptance criterion), so RETIRE is not on the table; ARM is.

Verified BEFORE wiring that arming is additive, not a behavior change: running
`check_dor_items_drift.py` with zero args against the real repo state PASSes
today (3/3 homes agree with the SSOT), so the new commit-stage hook does not
turn any currently-clean commit red.

GDP-1 (intercept EARLY): a divergent DoR home is knowable at `git commit`, not
discovered later by a reviewer relying on stale skill prose.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PRE_COMMIT_CONFIG = PROJECT_ROOT / ".pre-commit-config.yaml"
DRIFT_SCRIPT = PROJECT_ROOT / "scripts" / "cli" / "check_dor_items_drift.py"

# The exact default homes `check_dor_items_drift.py` checks when invoked with no
# `--home` flags (mirrors its own `_DEFAULT_HOME_RELPATHS`) plus the SSOT it
# reads -- every path a commit-stage hook must actually watch.
_SSOT_RELPATH = "nWave/data/dor-items.yaml"
_HOME_RELPATHS = (
    "nWave/skills/nw-dor-validation/SKILL.md",
    "nWave/agents/nw-product-owner.md",
    "nWave/agents/nw-product-owner-reviewer.md",
)


def _hooks() -> list[dict]:
    config = yaml.safe_load(PRE_COMMIT_CONFIG.read_text(encoding="utf-8"))
    return [h for repo in config.get("repos", []) for h in repo.get("hooks", [])]


def _drift_gate_hook() -> dict | None:
    for hook in _hooks():
        if "check_dor_items_drift.py" in hook.get("entry", ""):
            return hook
    return None


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DRIFT_SCRIPT), *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=PROJECT_ROOT,
    )


# ---------------------------------------------------------------------------
# GDP-1 -- the gate fires at commit time, matching its own K3 acceptance claim
# ---------------------------------------------------------------------------


def test_precommit_wires_the_dor_items_drift_gate():
    """NEGATIVE: the drift gate has no commit-stage counterpart -> K3 unmet.

    Declared-fact check (GDP-8): asserts the hook DECLARATION exists (id, real
    entry, pre-commit stage, no filename-passing) rather than inferring arming
    from any indirect signal.
    """
    hook = _drift_gate_hook()

    assert hook is not None, (
        "no .pre-commit-config.yaml hook invokes check_dor_items_drift.py -- "
        "the dor-items-ssot feature's K3 acceptance criterion ('the drift gate "
        "red-flags 100% of edits that desynchronize a home from the SSOT') is "
        "declared shipped but unmet in production: the gate exists and passes "
        "its own AT suite, but nothing calls it at edit time."
    )
    assert "pre-commit" in hook.get("stages", ["pre-commit"]), (
        f"dor-items-drift-check hook is not staged at pre-commit: {hook!r}"
    )
    assert hook.get("pass_filenames") is False, (
        "dor-items-drift-check must not receive pass_filenames=true -- the "
        "script resolves its own default home-set and takes no positional "
        f"file arguments: {hook!r}"
    )


def test_dor_items_drift_gate_files_pattern_covers_ssot_and_every_home():
    """NEGATIVE: the hook's `files:` trigger misses the SSOT or a home.

    A `files:` regex that does not match one of these paths means an edit to
    that exact file never fires the check -- the same class of gap this gate
    exists to catch, just one level up (the TRIGGER diverging from its own
    watched set instead of a DoR home diverging from the item-count SSOT).
    """
    hook = _drift_gate_hook()
    assert hook is not None, (
        "precede this test with test_precommit_wires_the_dor_items_drift_gate"
    )

    pattern = re.compile(hook["files"])
    unmatched = [
        path for path in (_SSOT_RELPATH, *_HOME_RELPATHS) if not pattern.match(path)
    ]

    assert not unmatched, (
        f"dor-items-drift-check's files: {hook['files']!r} does not match: "
        f"{unmatched} -- an edit to any of these would not trigger the gate"
    )


# ---------------------------------------------------------------------------
# Behavioral proof -- the gate actually rejects a diverged home
# ---------------------------------------------------------------------------


def test_dor_items_drift_gate_rejects_a_diverged_home(tmp_path):
    """NEGATIVE: a home whose stated count disagrees with the SSOT does not
    pass silently. Isolated via --ssot/--home so this never touches the real
    repo's DoR files."""
    ssot = tmp_path / "dor-items.yaml"
    ssot.write_text(
        "items:\n  - one\n  - two\n  - three\n",
        encoding="utf-8",
    )
    diverged_home = tmp_path / "home.md"
    diverged_home.write_text(
        "## Definition of Ready Checklist (9 Items - Hard Gate)\n",
        encoding="utf-8",
    )

    result = _run("--ssot", str(ssot), "--home", str(diverged_home))

    assert result.returncode == 1, (
        f"check_dor_items_drift.py accepted a home stating 9 items against a "
        f"3-item SSOT; exit={result.returncode} stdout={result.stdout!r}"
    )
    assert "FAIL" in result.stdout and str(diverged_home) in result.stdout, (
        "check_dor_items_drift.py exited non-zero but did not name the "
        f"diverged home; stdout={result.stdout!r}"
    )


def test_dor_items_drift_gate_passes_a_consistent_home(tmp_path):
    """POSITIVE control for the negative above: a home that agrees passes."""
    ssot = tmp_path / "dor-items.yaml"
    ssot.write_text(
        "items:\n  - one\n  - two\n  - three\n",
        encoding="utf-8",
    )
    consistent_home = tmp_path / "home.md"
    consistent_home.write_text(
        "## Definition of Ready Checklist (3 Items - Hard Gate)\n",
        encoding="utf-8",
    )

    result = _run("--ssot", str(ssot), "--home", str(consistent_home))

    assert result.returncode == 0, (
        f"check_dor_items_drift.py rejected a home consistent with the SSOT; "
        f"stdout={result.stdout!r}"
    )
