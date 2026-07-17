"""Regression -- the orchestrator-affordance refresh is DES-runtime-coupled,
30-minute (not 15), and never fires on `/clear`/`/compact`.

DEFECT (root-caused): the "how to use nWave" affordance (`nWave/data/
orchestrator-affordance/{spine-discipline.md, des-command-catalog.md}`) is
injected into the model's context ONLY by the DES runtime hooks
(`src/des/adapters/drivers/hooks/{session_start_handler,
user_prompt_submit_handler}.py`), which means:

  (A) the UserPromptSubmit refresh cadence is `_ORCHESTRATOR_AFFORDANCE_
      REFRESH_SECONDS = 1800` (30 min), not the mandated ~15 min;
  (B) it depends on the DES runtime being importable -- a session in a
      non-DES repo (or one where `des` cannot be imported) gets nothing;
  (C) the SessionStart injection is registered with `matcher="startup"`
      only (`scripts/shared/hook_definitions.py`), so it never fires on
      Claude Code's `resume`/`clear`/`compact` SessionStart sub-events.

FIX (crafter's job, NOT implemented by this AT -- test-authoring only, zero
`src/`/`scripts/` edits): a NEW standalone hook script
`scripts/hooks/orchestrator_affordance_refresh.py` -- stdlib-only, zero
`des` import, mirroring `~/.claude/hooks/load_persona.py` -- invoked as
`orchestrator_affordance_refresh.py <SessionStart|UserPromptSubmit>`. It
resolves the shipped `nWave/data/orchestrator-affordance/` assets relative
to its OWN `__file__` location (never cwd-dependent), reads both `*.md`
files, and prints the Claude Code `hookSpecificOutput.additionalContext`
JSON envelope. Registered in `scripts/shared/hook_definitions.py` (2 new
`HookEvent` entries, both `matcher=None` so SessionStart fires on
startup|resume|clear|compact) and shipped via `DESPlugin.DES_HOOKS`
(`scripts/install/plugins/des_plugin.py`). UserPromptSubmit self-gates on a
900-second (~15-minute) sentinel file
(`.nwave/orchestrator-affordance-last-injected`). A missing assets
directory degrades LOUD (non-silent stderr diagnostic), never a silent
clean exit. The DES-side constant `_ORCHESTRATOR_AFFORDANCE_REFRESH_
SECONDS` also moves 1800 -> 900 (out of scope for this AT file: the 2
existing DES acceptance tests re-declaring 1800/1799 are the crafter's job
to update at GREEN).

Driving port (Mandate 16, no-direct-domain-testing): every AT below drives
the REAL standalone script as Claude Code invokes it -- subprocess with
`argv[1]` = the hook event name, reading the JSON envelope from stdout.
This artifact's shipped surface IS the subprocess boundary (a Claude Code
hook has no other entry point), so subprocess-driving here is the L2
"composition root" for this artifact class, not a Layer-3 e2e shortcut.
The two purely-structural checks (the DES-side constant, the installer
wiring in `hook_definitions.py`/`des_plugin.py`) are driven in-process via
direct import, since those are plain Python data/constants, not the hook's
own runtime behaviour.

RED-for-right-reason: `scripts/hooks/orchestrator_affordance_refresh.py`
does not exist yet. Every subprocess-driven scenario below asserts
`returncode == 0` (or `Path.exists()`) BEFORE any content assertion, so the
current failure is a genuine, semantic `AssertionError` naming the missing
script/behaviour -- never a bare interpreter traceback or an import error
on THIS test file itself (this file imports only stdlib + already-existing
`des`/`scripts.*` modules).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "orchestrator_affordance_refresh.py"
_SPINE_DISCIPLINE_MARKER = "Orchestrator discipline"
_CATALOG_DES_NEXT_MARKER = "des next"
_CATALOG_EXAMINE_FIXTURE_MARKER = "des examine-fixture"
_REFRESH_SECONDS = 900


# ===========================================================================
# Shared driving helpers -- subprocess IS the real entry for this artifact
# ===========================================================================


def _run(
    script: Path,
    event: str,
    *,
    cwd: Path,
    python_flags: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Invoke the hook script exactly as Claude Code would: argv[1] = event."""
    cmd = [sys.executable, *(python_flags or []), str(script), event]
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        input="",
        timeout=30,
    )


def _parse_json_or_fail(stdout: str) -> dict:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"expected exactly one JSON object on stdout -- got {stdout!r}"
        ) from exc


# ===========================================================================
# 1. POSITIVE -- SessionStart injection (proves the artifact is wired at all)
# ===========================================================================


def test_session_start_injects_valid_json_containing_the_affordance_markers(
    tmp_path: Path,
) -> None:
    """`orchestrator_affordance_refresh.py SessionStart` must print a valid
    Claude Code `hookSpecificOutput` envelope whose `additionalContext`
    contains a stable marker from BOTH shipped assets -- proving the
    concatenation of `spine-discipline.md` + `des-command-catalog.md`
    actually reaches the model's context, not just that a file was read.
    """
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)

    assert result.returncode == 0, (
        "orchestrator_affordance_refresh.py SessionStart must exit 0 -- got "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )

    payload = _parse_json_or_fail(result.stdout)
    hook_output = payload.get("hookSpecificOutput", {})

    assert hook_output.get("hookEventName") == "SessionStart", (
        f"expected hookEventName='SessionStart' -- got payload={payload!r}"
    )

    additional_context = hook_output.get("additionalContext", "")
    assert _SPINE_DISCIPLINE_MARKER in additional_context, (
        "additionalContext must contain the spine-discipline.md heading "
        f"marker {_SPINE_DISCIPLINE_MARKER!r} -- got "
        f"additionalContext={additional_context!r}"
    )
    assert _CATALOG_DES_NEXT_MARKER in additional_context, (
        "additionalContext must contain the des-command-catalog.md marker "
        f"{_CATALOG_DES_NEXT_MARKER!r} -- got "
        f"additionalContext={additional_context!r}"
    )


# ===========================================================================
# 2. SPINE-INDEPENDENCE -- must work even when `des` cannot be imported
# ===========================================================================


def test_script_never_imports_the_des_runtime_package_at_module_level() -> None:
    """Static proof: the script's own source carries zero `import des` /
    `from des import ...` at module level -- the spine-coupling this bug
    fixes.
    """
    assert _SCRIPT.exists(), (
        f"expected the standalone hook script at {_SCRIPT} -- not found yet "
        "(the whole point of this bug fix is that it exists independent of "
        "the DES runtime)"
    )

    source = _SCRIPT.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_SCRIPT))

    imported_top_level_modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_top_level_modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_top_level_modules.add(node.module.split(".")[0])

    assert "des" not in imported_top_level_modules, (
        "orchestrator_affordance_refresh.py must NEVER import the `des` "
        "package -- it must work in a repo where DES is not installed. Got "
        f"imports={sorted(imported_top_level_modules)!r}"
    )


def test_script_runs_when_the_des_package_is_not_importable(tmp_path: Path) -> None:
    """Dynamic proof (stronger than the static AST check): run the script
    under `python -S` (site-packages / editable-install `.pth` files never
    processed, so `import des` would raise `ModuleNotFoundError` if
    attempted) in an isolated tmp cwd with no `.nwave/` -- it must still
    succeed and emit the affordance.
    """
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path, python_flags=["-S"])

    assert result.returncode == 0, (
        "the script must succeed even when the `des` package is NOT "
        f"importable (python -S) -- got returncode={result.returncode}, "
        f"stderr={result.stderr!r}"
    )

    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )
    assert _SPINE_DISCIPLINE_MARKER in additional_context, (
        "the affordance must still be produced with `des` unimportable -- "
        f"got additionalContext={additional_context!r}"
    )


# ===========================================================================
# 3. 900-SECOND CADENCE (UserPromptSubmit) -- pin the 899-vs-900 boundary
# ===========================================================================


def test_user_prompt_submit_never_injects_before_900_seconds_elapsed(
    tmp_path: Path,
) -> None:
    """A sentinel younger than 900s must produce NO injection at all."""
    sentinel = tmp_path / ".nwave" / "orchestrator-affordance-last-injected"
    sentinel.parent.mkdir(parents=True)
    sentinel.touch()
    fresh_mtime = time.time() - 100  # comfortably < 900s old
    os.utime(sentinel, (fresh_mtime, fresh_mtime))

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        "UserPromptSubmit must always exit 0 (fail-open) -- got "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    assert result.stdout.strip() == "", (
        "a sentinel younger than 900s must produce NO stdout injection -- "
        f"got stdout={result.stdout!r}"
    )


def test_user_prompt_submit_injects_once_the_900_second_sentinel_has_elapsed(
    tmp_path: Path,
) -> None:
    """A sentinel >= 900s old must inject AND refresh (touch) the sentinel."""
    sentinel = tmp_path / ".nwave" / "orchestrator-affordance-last-injected"
    sentinel.parent.mkdir(parents=True)
    sentinel.touch()
    stale_mtime = time.time() - 1_000  # comfortably >= 900s old
    os.utime(sentinel, (stale_mtime, stale_mtime))

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        "UserPromptSubmit must exit 0 -- got returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    hook_output = payload.get("hookSpecificOutput", {})
    assert hook_output.get("hookEventName") == "UserPromptSubmit", (
        f"expected hookEventName='UserPromptSubmit' -- got payload={payload!r}"
    )
    assert _SPINE_DISCIPLINE_MARKER in hook_output.get("additionalContext", ""), (
        f"expected the affordance content -- got payload={payload!r}"
    )

    refreshed_mtime = sentinel.stat().st_mtime
    assert refreshed_mtime > stale_mtime + 1, (
        "the elapsed sentinel must be touched (refreshed to ~now) after "
        f"injecting -- stale_mtime={stale_mtime}, "
        f"refreshed_mtime={refreshed_mtime}"
    )


@pytest.mark.parametrize(
    ("elapsed_seconds", "expect_injection"),
    [
        pytest.param(899, False, id="899s-not-yet-elapsed-no-injection"),
        pytest.param(900, True, id="900s-elapsed-injects"),
    ],
)
def test_user_prompt_submit_899_vs_900_second_boundary(
    tmp_path: Path, elapsed_seconds: int, expect_injection: bool
) -> None:
    """Pin the EXACT boundary: `elapsed >= 900` injects, `elapsed < 900`
    does not -- the off-by-one the DES-side constant swap must preserve.
    """
    sentinel = tmp_path / ".nwave" / "orchestrator-affordance-last-injected"
    sentinel.parent.mkdir(parents=True)
    sentinel.touch()
    backdated_mtime = time.time() - elapsed_seconds
    os.utime(sentinel, (backdated_mtime, backdated_mtime))

    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        f"UserPromptSubmit must exit 0 (elapsed_seconds={elapsed_seconds}) "
        f"-- got returncode={result.returncode}, stderr={result.stderr!r}"
    )

    if expect_injection:
        assert result.stdout.strip() != "", (
            f"elapsed_seconds={elapsed_seconds} (>= {_REFRESH_SECONDS}) must "
            f"inject -- got EMPTY stdout"
        )
    else:
        assert result.stdout.strip() == "", (
            f"elapsed_seconds={elapsed_seconds} (< {_REFRESH_SECONDS}) must "
            f"NOT inject -- got stdout={result.stdout!r}"
        )


# ===========================================================================
# 4. DEGRADE-LOUD -- a missing assets directory must never be a silent no-op
# ===========================================================================


def test_missing_assets_dir_never_silently_exits_clean(tmp_path: Path) -> None:
    """Copy the (future) script into an isolated tree that deliberately
    ships NO `nWave/data/orchestrator-affordance/` assets anywhere under
    it -- whatever depth the script resolves its assets dir relative to its
    own `__file__`, that path cannot exist here. The script must still emit
    a non-silent, one-line diagnostic on stderr -- never behave as if
    "nothing to inject" were the correct, quiet outcome.
    """
    assert _SCRIPT.exists(), (
        f"expected the standalone hook script at {_SCRIPT} -- not found yet"
    )

    isolated_root = tmp_path / "isolated-install"
    isolated_script_dir = isolated_root / "scripts" / "hooks"
    isolated_script_dir.mkdir(parents=True)
    isolated_script = isolated_script_dir / _SCRIPT.name
    isolated_script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    # No `nWave/`, no `lib/`, nothing else created under isolated_root --
    # the assets dir the script computes from its own __file__ is
    # guaranteed absent here.

    result = _run(isolated_script, "SessionStart", cwd=isolated_root)

    assert result.stderr.strip() != "", (
        "a missing assets directory must produce a non-silent stderr "
        f"diagnostic -- got EMPTY stderr (stdout={result.stdout!r}, "
        f"returncode={result.returncode})"
    )
    lowered_stderr = result.stderr.lower()
    assert "asset" in lowered_stderr or "affordance" in lowered_stderr, (
        "the stderr diagnostic must actually NAME the problem (assets/"
        f"affordance) -- got stderr={result.stderr!r}"
    )


# ===========================================================================
# 5. CONSTANT + completeness guard against the omission that caused the
#    whole discoverability defect
# ===========================================================================


def test_des_refresh_constant_is_900_seconds() -> None:
    """The DES-side `UserPromptSubmit` mirror constant must match the
    independent hook's 900s (15-minute) cadence, not the old 1800s
    (30-minute) value.
    """
    from des.adapters.drivers.hooks.user_prompt_submit_handler import (
        _ORCHESTRATOR_AFFORDANCE_REFRESH_SECONDS,
    )

    assert _ORCHESTRATOR_AFFORDANCE_REFRESH_SECONDS == _REFRESH_SECONDS, (
        "the DES-side refresh cadence constant must be 900 (15 minutes) -- "
        f"got {_ORCHESTRATOR_AFFORDANCE_REFRESH_SECONDS} (still the old "
        "1800s/30-minute value)"
    )


def test_session_start_output_never_omits_des_next_or_examine_fixture(
    tmp_path: Path,
) -> None:
    """Guard against the exact omission that caused the discoverability
    defect: an affordance that teaches wave commands but drops `des next`
    or `des examine-fixture` is a false-complete and must fail this check.
    """
    result = _run(_SCRIPT, "SessionStart", cwd=tmp_path)

    assert result.returncode == 0, (
        f"SessionStart must exit 0 -- got returncode={result.returncode}, "
        f"stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )

    assert _CATALOG_DES_NEXT_MARKER in additional_context, (
        f"the affordance must NAME {_CATALOG_DES_NEXT_MARKER!r} -- got "
        f"additionalContext={additional_context!r}"
    )
    assert _CATALOG_EXAMINE_FIXTURE_MARKER in additional_context, (
        f"the affordance must NAME {_CATALOG_EXAMINE_FIXTURE_MARKER!r} -- "
        f"got additionalContext={additional_context!r}"
    )


# ===========================================================================
# 6. INSTALLER WIRING -- registered + shipped independent of the DES gate
# ===========================================================================


def test_hook_definitions_registers_two_orchestrator_affordance_refresh_entries_with_no_matcher() -> (
    None
):
    """`hook_definitions.HOOK_EVENTS` must carry exactly 2 new entries for
    the standalone hook -- one `SessionStart` (matcher=None, so it fires on
    startup|resume|clear|compact per Claude Code's SessionStart schema, NOT
    the DES `session-start` entry's `matcher="startup"`-only) and one
    `UserPromptSubmit` (matcher=None, self-gated by the 900s sentinel
    inside the script itself).
    """
    from scripts.shared.hook_definitions import HOOK_EVENTS

    def _mentions_new_script(hook) -> bool:
        haystack = " ".join(filter(None, [hook.action, hook.shell_command]))
        return (
            "orchestrator_affordance_refresh" in haystack
            or "orchestrator-affordance-refresh" in haystack
        )

    matches = [h for h in HOOK_EVENTS if _mentions_new_script(h)]

    assert len(matches) == 2, (
        "expected exactly 2 new HOOK_EVENTS entries wiring the standalone "
        "orchestrator_affordance_refresh.py hook (one SessionStart, one "
        f"UserPromptSubmit) -- got {len(matches)} matching entries: "
        f"{matches!r}"
    )

    by_event = {h.event: h for h in matches}
    assert "SessionStart" in by_event, (
        f"expected a SessionStart entry among {matches!r}"
    )
    assert "UserPromptSubmit" in by_event, (
        f"expected a UserPromptSubmit entry among {matches!r}"
    )
    assert by_event["SessionStart"].matcher is None, (
        "the new SessionStart entry must carry matcher=None (fires on "
        "startup|resume|clear|compact) -- the existing DES `session-start` "
        "entry's matcher='startup' is exactly the defect this fix "
        f"corrects. Got matcher={by_event['SessionStart'].matcher!r}"
    )
    assert by_event["UserPromptSubmit"].matcher is None, (
        "the new UserPromptSubmit entry must carry matcher=None -- got "
        f"matcher={by_event['UserPromptSubmit'].matcher!r}"
    )


def test_des_plugin_ships_the_orchestrator_affordance_refresh_script() -> None:
    """`DESPlugin.DES_HOOKS` must list the new script so it is deployed to
    `~/.claude/scripts/` on install (the same mechanism that ships
    `git_stash_guard.py` / `no_verify_reminder.py`).
    """
    from scripts.install.plugins.des_plugin import DESPlugin

    assert "orchestrator_affordance_refresh.py" in DESPlugin.DES_HOOKS, (
        "the new standalone hook must be added to DESPlugin.DES_HOOKS so it "
        "is shipped independent of the DES gate mechanism -- got "
        f"DES_HOOKS={DESPlugin.DES_HOOKS!r}"
    )
