"""Regression -- the orchestrator-affordance refresh is DES-runtime-coupled,
30-minute (not 15), and never fires on `/clear`/`/compact`.

DEFECT (root-caused): the "how to use nWave" affordance (every `*.md` asset
under `nWave/data/orchestrator-affordance/`) is
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

EXTENSION (2026-07-30, `bugfix/affordance-injection-serves-stale-content`):
sections 7-8 below cover a SEPARATE, later-discovered defect in the SAME
resolver -- `_resolve_assets_dir()` returns the first candidate that merely
EXISTS, never the one that is CURRENT. Two properties:

  P1 (section 7) -- when BOTH an installed Claude-scoped root
  (`<claude_dir>/lib/nWave/data/orchestrator-affordance`) and a host-neutral
  root (`~/.nwave/nWave/data/orchestrator-affordance`) exist and disagree,
  the hook must never silently serve the staler one, and must announce the
  disagreement in-band (Claude Code discards hook stderr, so an in-band
  notice is the only observable channel). A dev-checkout root disagreeing
  with a global install is NOT a divergence -- that ordering
  (script-local beats machine-global) is intentional and must survive.

  P2 (section 8) -- the shipped `50-standing-loops.md` asset opens with a
  `<EXTREMELY-IMPORTANT>` / "TRUNCATED PREVIEW?" recovery pointer explaining
  what to do when the harness's ~2048-byte admission preview cuts the
  payload. Fixing P1 alone (reordering/deduping candidates) does nothing to
  guarantee this pointer's BYTE POSITION inside the assembled payload --
  measured (2026-07-30, real shipped assets) at ~15x past the preview
  window. Asserted on POSITION, never on WHICH FILE carries the pointer, so
  it cannot be satisfied by pinning a filename the fix is free to rename,
  relocate, or hoist.
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
# R-8: the shared reconciliation module the script imports as a
# same-directory sibling. Ships flat beside it via `DESPlugin.DES_HOOKS`.
_RESOLUTION_MODULE = (
    _REPO_ROOT / "scripts" / "hooks" / "orchestrator_affordance_resolution.py"
)
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
    env: dict[str, str] | None = None,
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
        env=env,
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
    concatenation of the `spine-discipline` and `des-command-catalog` role
    assets actually reaches the model's context, not just that a file was
    read.
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
        "additionalContext must contain the spine-discipline asset's "
        f"heading marker {_SPINE_DISCIPLINE_MARKER!r} -- got "
        f"additionalContext={additional_context!r}"
    )
    assert _CATALOG_DES_NEXT_MARKER in additional_context, (
        "additionalContext must contain the des-command-catalog asset's "
        f"marker {_CATALOG_DES_NEXT_MARKER!r} -- got "
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

    isolated_env = os.environ.copy()
    isolated_env["HOME"] = str(tmp_path / "empty-home")
    result = _run(
        isolated_script,
        "SessionStart",
        cwd=isolated_root,
        env=isolated_env,
    )

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


# ===========================================================================
# 6. HOST-NEUTRAL RESOLUTION -- Codex/Copilot/OpenCode installs (no ~/.claude)
# ===========================================================================


def test_session_start_resolves_assets_from_host_neutral_runtime_when_installed_and_dev_layouts_are_absent(
    tmp_path: Path,
) -> None:
    """A host-neutral install (Codex, Copilot, OpenCode -- `DESPlugin.
    _runtime_python_dir` ships runtime assets to `~/.nwave/nWave/`
    instead of `<claude_dir>/lib/nWave/`) must still resolve the shipped
    `orchestrator-affordance/` assets.

    THE DEFECT this guards: `_candidate_assets_dirs()` only tried the
    Claude-scoped installed path and the dev-checkout path. A host-neutral
    install populates NEITHER -- it populates `~/.nwave/nWave/data/
    orchestrator-affordance/` -- so the resolver diagnosed "assets not
    found" and injected nothing, even though the data had genuinely
    reached the operator's machine.

    Isolation: the script is copied to a location that resolves neither the
    installed-Claude-scoped candidate (no `lib/nWave/` two hops up) nor the
    dev-checkout candidate (no `nWave/data/` three hops up); `HOME` is
    pointed at a synthetic tmp_path carrying ONLY the host-neutral assets.
    """
    isolated_scripts_dir = tmp_path / "isolated" / "somewhere" / "scripts"
    isolated_scripts_dir.mkdir(parents=True)
    isolated_script = isolated_scripts_dir / _SCRIPT.name
    isolated_script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    fake_home = tmp_path / "fake-home"
    affordance_dir = fake_home / ".nwave" / "nWave" / "data" / "orchestrator-affordance"
    affordance_dir.mkdir(parents=True)
    (affordance_dir / "spine-discipline.md").write_text(
        f"# {_SPINE_DISCIPLINE_MARKER}\n", encoding="utf-8"
    )
    (affordance_dir / "des-command-catalog.md").write_text(
        f"Run {_CATALOG_DES_NEXT_MARKER}.\n", encoding="utf-8"
    )

    env = os.environ.copy()
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        [sys.executable, str(isolated_script), "SessionStart"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        input="",
        timeout=30,
        env=env,
    )

    assert result.returncode == 0, (
        "must exit 0 even when resolving via the host-neutral candidate -- "
        f"got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )
    assert _SPINE_DISCIPLINE_MARKER in additional_context, (
        "THE DEFECT: host-neutral install assets exist on disk but were "
        f"never found -- got additionalContext={additional_context!r}, "
        f"stderr={result.stderr!r}"
    )


# ===========================================================================
# 7. DIVERGED INSTALL ROOTS (P1) -- existence is not currency
#
# DEFECT (measured live, 2026-07-30): `_resolve_assets_dir()` returns the
# FIRST candidate that merely EXISTS. On a machine carrying BOTH install
# roots -- `<claude_dir>/lib/nWave/data/orchestrator-affordance/` (written
# only by an install whose target platforms include `claude_code`) and
# `~/.nwave/nWave/data/orchestrator-affordance/` (written only by a
# host-neutral install) -- the Claude-scoped root wins unconditionally.
# `DESPlugin._runtime_python_dir` ships the assets to exactly ONE of those
# roots per run and `_secondary_runtime_python_dir` mirrors only for a MIXED
# target, so a codex-only install refreshes one root and leaves the other
# frozen. Every hook firing then serves stale content, silently, at exit 0.
#
# The candidate ORDER is not the bug and is deliberately preserved: a
# dev-checkout tree must still outrank an unrelated global install (the
# shadowing protection `_candidate_assets_dirs()`'s docstring exists for).
# What is corrected is applying that order between two INSTALL outputs,
# which are obliged to agree.
# ===========================================================================


_DIVERGENCE_MARKER = "DIVERGED"
_STALE_MARKER = "STALE-CONTENT-MUST-NOT-BE-SERVED"
_FRESH_MARKER = "FRESH-CONTENT-MUST-BE-SERVED"


def _write_affordance_tree(root: Path, *, marker: str, mtime: float) -> Path:
    """One `orchestrator-affordance/` tree whose content and age are both pinned."""
    root.mkdir(parents=True, exist_ok=True)
    asset = root / "00-spine-discipline.md"
    asset.write_text(f"# {_SPINE_DISCIPLINE_MARKER}\n{marker}\n", encoding="utf-8")
    os.utime(asset, (mtime, mtime))
    return root


def _installed_layout_script(claude_dir: Path) -> Path:
    """The script at the exact path an install ships it to: `<claude_dir>/scripts/`.

    Candidate 1 (`<claude_dir>/lib/nWave/...`) is two `.parent` hops from
    here, so this layout is what makes the Claude-scoped install root
    reachable at all.

    Ships the R-8 shared reconciliation module as a same-directory sibling
    too: `DESPlugin.DES_HOOKS` puts both files flat in this same directory on
    a real install, and the script imports the sibling to reach the
    reconciliation rule. A fixture that omits it is not "an installed copy of
    this script" -- it is a relocated one, which exercises the fail-open
    degradation instead of the shipped behaviour.
    """
    scripts_dir = claude_dir / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    script = scripts_dir / _SCRIPT.name
    script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    (scripts_dir / _RESOLUTION_MODULE.name).write_text(
        _RESOLUTION_MODULE.read_text(encoding="utf-8"), encoding="utf-8"
    )
    return script


def _prompt_submit_context(script: Path, *, home: Path, cwd: Path) -> str:
    """`additionalContext` from a UserPromptSubmit firing (no sentinel => elapsed)."""
    env = os.environ.copy()
    env["HOME"] = str(home)
    result = _run(script, "UserPromptSubmit", cwd=cwd, env=env)
    assert result.returncode == 0, (
        "UserPromptSubmit must exit 0 (fail-open) -- got returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    return payload.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_stale_claude_scoped_install_root_never_shadows_a_fresher_host_neutral_one(
    tmp_path: Path,
) -> None:
    """THE DEFECT, byte-for-byte: both install roots present, the
    Claude-scoped one demonstrably older, and the resolver serves it anyway
    because it merely comes first in the candidate list.
    """
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    script = _installed_layout_script(claude_dir)
    now = time.time()
    _write_affordance_tree(
        claude_dir / "lib" / "nWave" / "data" / "orchestrator-affordance",
        marker=_STALE_MARKER,
        mtime=now - 34 * 3600,
    )
    _write_affordance_tree(
        home / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now,
    )

    context = _prompt_submit_context(script, home=home, cwd=tmp_path)

    assert _FRESH_MARKER in context, (
        f"the fresher INSTALL root must be served -- got additionalContext={context!r}"
    )
    assert _STALE_MARKER not in context, (
        "the 34-hour-stale INSTALL root must NOT be served -- got "
        f"additionalContext={context!r}"
    )
    assert _DIVERGENCE_MARKER in context, (
        "two disagreeing install roots must degrade LOUD in-band (GDP-6): "
        "Claude Code discards hook stderr, so a stderr-only diagnostic can "
        f"never be observed to fire -- got additionalContext={context!r}"
    )


def test_diverged_install_roots_are_announced_even_when_the_priority_pick_is_fresher(
    tmp_path: Path,
) -> None:
    """Divergence is the defect, not merely being served the older tree.

    When the Claude-scoped root happens to be the fresher one the session
    reads correct content, but the machine still carries an install root
    that a host-neutral session would read stale. Announcing only in the
    direction that hurts THIS session would make the notice a function of
    who is looking rather than of the machine's state.
    """
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    script = _installed_layout_script(claude_dir)
    now = time.time()
    _write_affordance_tree(
        claude_dir / "lib" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now,
    )
    _write_affordance_tree(
        home / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
        marker=_STALE_MARKER,
        mtime=now - 34 * 3600,
    )

    context = _prompt_submit_context(script, home=home, cwd=tmp_path)

    assert _FRESH_MARKER in context, f"got additionalContext={context!r}"
    assert _DIVERGENCE_MARKER in context, (
        "a diverged pair of install roots must be announced regardless of "
        f"which one won -- got additionalContext={context!r}"
    )


def test_agreeing_install_roots_produce_no_divergence_notice(tmp_path: Path) -> None:
    """No false positive: identical content in both roots is the healthy
    state a correct install produces, and must stay silent however far apart
    the two mtimes are. (Sibling-branch pin -- must keep passing after fix.)
    """
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    script = _installed_layout_script(claude_dir)
    now = time.time()
    _write_affordance_tree(
        claude_dir / "lib" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now - 34 * 3600,
    )
    _write_affordance_tree(
        home / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now,
    )

    context = _prompt_submit_context(script, home=home, cwd=tmp_path)

    assert _FRESH_MARKER in context, f"got additionalContext={context!r}"
    assert _DIVERGENCE_MARKER not in context, (
        "identical content in both install roots is NOT a divergence -- "
        f"got additionalContext={context!r}"
    )


def test_a_global_install_never_outranks_a_dev_checkout_even_when_fresher(
    tmp_path: Path,
) -> None:
    """The shadowing protection the candidate order exists for, held intact.

    A dev checkout is deliberately at whatever revision the operator checked
    out, so its assets being OLDER than a global install is expected, not a
    divergence. Reordering the candidates by freshness would have "fixed"
    the stale-install bug by reintroducing exactly this one. (Sibling-branch
    pin -- must keep passing after fix.)
    """
    home = tmp_path / "home"
    repo_root = tmp_path / "checkout"
    hooks_dir = repo_root / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    script = hooks_dir / _SCRIPT.name
    script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    now = time.time()
    _write_affordance_tree(
        repo_root / "nWave" / "data" / "orchestrator-affordance",
        marker=_STALE_MARKER,
        mtime=now - 34 * 3600,
    )
    _write_affordance_tree(
        home / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now,
    )

    context = _prompt_submit_context(script, home=home, cwd=tmp_path)

    assert _STALE_MARKER in context, (
        "the dev checkout's own assets must win over an unrelated global "
        f"install regardless of mtime -- got additionalContext={context!r}"
    )
    assert _FRESH_MARKER not in context, (
        "the global install must not shadow the dev checkout -- got "
        f"additionalContext={context!r}"
    )
    assert _DIVERGENCE_MARKER not in context, (
        "a checkout disagreeing with a global install is expected, not a "
        f"divergence -- got additionalContext={context!r}"
    )


def _prompt_submit_context_via_runpy(script: Path, *, home: Path, cwd: Path) -> str:
    """`additionalContext`, driven the way the REGISTERED hook command drives it.

    Claude Code's `settings.json` entry for this hook does not hand the script
    to the interpreter as a path -- it runs
    `python3 -c "... runpy.run_path(<script>, run_name='__main__')"` from
    whatever cwd the session happens to be in. `runpy.run_path` leaves
    `sys.path[0]` pointing at that cwd, NOT at the script's own directory.

    Driving via `_run` alone cannot observe the difference: passing a script
    path to the interpreter DOES put its directory on `sys.path`, so a
    same-directory sibling that the script fails to find in the SHIPPED
    invocation still resolves under the test's invocation and the whole suite
    stays green while the real install silently loses the behaviour.
    """
    env = os.environ.copy()
    env["HOME"] = str(home)
    program = (
        "import runpy, sys;"
        f"sys.argv=[{script.name!r}, 'UserPromptSubmit'];"
        f"runpy.run_path({str(script)!r}, run_name='__main__')"
    )
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=cwd,
        capture_output=True,
        text=True,
        input="",
        timeout=30,
        env=env,
    )
    assert result.returncode == 0, (
        "the registered runpy invocation must exit 0 (fail-open) -- got "
        f"returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    return payload.get("hookSpecificOutput", {}).get("additionalContext", "")


def test_divergence_is_still_announced_under_the_registered_runpy_invocation(
    tmp_path: Path,
) -> None:
    """The reconciliation must survive the invocation Claude Code actually uses.

    Measured 2026-08-01 on a real redirected-HOME install: the shipped
    `settings.json` command runs this script through `runpy.run_path` from the
    session's cwd, so a bare `import orchestrator_affordance_resolution`
    resolved to nothing and the hook degraded to an unreconciled,
    unannounced priority-order pick -- silently undoing the round-1 fix on
    every real install, while every path-driven test stayed green.
    """
    home = tmp_path / "home"
    claude_dir = home / ".claude"
    script = _installed_layout_script(claude_dir)
    now = time.time()
    _write_affordance_tree(
        claude_dir / "lib" / "nWave" / "data" / "orchestrator-affordance",
        marker=_STALE_MARKER,
        mtime=now - 34 * 3600,
    )
    _write_affordance_tree(
        home / ".nwave" / "nWave" / "data" / "orchestrator-affordance",
        marker=_FRESH_MARKER,
        mtime=now,
    )

    context = _prompt_submit_context_via_runpy(script, home=home, cwd=tmp_path)

    assert _FRESH_MARKER in context, (
        "the fresher INSTALL root must be served under the registered "
        f"invocation too -- got additionalContext={context!r}"
    )
    assert _DIVERGENCE_MARKER in context, (
        "the divergence notice must survive `runpy.run_path` -- its absence "
        "here means the shared reconciliation module was not reachable in the "
        f"shipped invocation -- got additionalContext={context!r}"
    )


# ===========================================================================
# 8. RECOVERY-POINTER ADMISSION-WINDOW SURVIVAL (P2)
#
# DEFECT: the `<EXTREMELY-IMPORTANT>` / question-form recovery block
# tells the reader what to do when the harness's ~2048-byte admission
# preview truncates the payload -- but that guidance is USELESS if it sits
# outside the very preview the truncation leaves behind. The assets are
# concatenated in `sorted(glob("*.md"))` order joined by `"\n\n"`, so a
# rename that changes sort order silently moves the pointer's byte offset.
# Measured on the real shipped assets (2026-07-30): the pointer sits far
# outside a 2048-byte window.
#
# Property, not mechanism: these tests assert the pointer's BYTE POSITION in
# the assembled `additionalContext`, never which asset file carries it or
# where in `_candidate_assets_dirs()` order it lives. A fix that renames,
# relocates, or hoists the block in the hook itself all satisfy this
# unchanged; a fix that only reorders/dedupes install-root candidates (P1)
# does not, because P1 never touches intra-payload byte position.
# ===========================================================================


_ADMITTED_PREVIEW_WINDOW_BYTES = 2048  # harness admission budget, RCA-measured
# The block's STRUCTURAL opening tag, not a sentence inside it. `ccf3c9679`
# rewrote the pointer's prose into question form and the old literal
# ("TRUNCATED PREVIEW?") vanished from the shipped assets, turning this test
# red without anything about the defect changing -- a marker that a wording
# edit can delete was never the property under test.
_RECOVERY_POINTER_MARKER = "<EXTREMELY-IMPORTANT>"


def _byte_offset(haystack: str, marker: str) -> int:
    """UTF-8 byte offset of `marker` in `haystack`, or -1 if absent.

    Byte-based (not char-based) to match `_collect_affordance_payloads`'s own
    `len(text.encode("utf-8"))` accounting -- the quantity the real harness
    truncates on is bytes, not characters.
    """
    return haystack.encode("utf-8").find(marker.encode("utf-8"))


def test_recovery_pointer_lands_within_the_admitted_preview_window_on_real_shipped_assets(
    tmp_path: Path,
) -> None:
    """THE DEFECT, on the REAL production assets: drives the actual shipped
    script against its actual shipped `nWave/data/orchestrator-affordance/`
    dev-checkout assets (candidate 2 -- the only candidate reachable from
    the real script's real repo location, verified absent-candidate-1 so
    this is deterministic regardless of host state) and asserts the
    recovery pointer's byte offset is within the admission window.
    """
    result = _run(_SCRIPT, "UserPromptSubmit", cwd=tmp_path)

    assert result.returncode == 0, (
        "UserPromptSubmit must exit 0 -- got returncode="
        f"{result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )
    assert additional_context, (
        "expected a non-empty UserPromptSubmit injection against the real "
        f"shipped assets -- got payload={payload!r}"
    )

    offset = _byte_offset(additional_context, _RECOVERY_POINTER_MARKER)
    total_bytes = len(additional_context.encode("utf-8"))

    assert offset != -1, (
        "the recovery-pointer marker "
        f"{_RECOVERY_POINTER_MARKER!r} must be present at all in the "
        f"assembled payload -- got additionalContext={additional_context!r}"
    )
    assert offset < _ADMITTED_PREVIEW_WINDOW_BYTES, (
        f"the recovery pointer sits at byte offset {offset} of "
        f"{total_bytes} total -- outside the harness's "
        f"{_ADMITTED_PREVIEW_WINDOW_BYTES}-byte admission preview window. "
        "A reader who only ever sees the preview never sees the guidance "
        "that tells them the rest was truncated and where to find it."
    )


def test_recovery_pointer_stays_within_window_when_its_asset_sorts_first(
    tmp_path: Path,
) -> None:
    """Sibling-branch pin / tautology guard: isolated, synthetic assets,
    decoupled from whatever the real `nWave/data/` content happens to be
    tomorrow. When the recovery-pointer asset sorts FIRST, its offset is
    small and the property holds TODAY -- proving the oracle is a genuine
    measurement (it can pass), not a check that fails unconditionally.
    """
    isolated_root = tmp_path / "isolated-first"
    isolated_script_dir = isolated_root / "scripts" / "hooks"
    isolated_script_dir.mkdir(parents=True)
    isolated_script = isolated_script_dir / _SCRIPT.name
    isolated_script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    assets_dir = isolated_root / "nWave" / "data" / "orchestrator-affordance"
    assets_dir.mkdir(parents=True)
    (assets_dir / "00-recovery.md").write_text(
        f"{_RECOVERY_POINTER_MARKER} synthetic control asset\n", encoding="utf-8"
    )
    (assets_dir / "10-filler.md").write_text("PADDING-" * 500, encoding="utf-8")

    isolated_env = os.environ.copy()
    isolated_env["HOME"] = str(tmp_path / "empty-home-first")
    result = _run(
        isolated_script, "UserPromptSubmit", cwd=isolated_root, env=isolated_env
    )

    assert result.returncode == 0, (
        f"must exit 0 -- got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )
    offset = _byte_offset(additional_context, _RECOVERY_POINTER_MARKER)

    assert offset != -1, f"got additionalContext={additional_context!r}"
    assert offset < _ADMITTED_PREVIEW_WINDOW_BYTES, (
        f"synthetic control: marker sorts first, offset={offset} must be "
        f"well within the window -- got additionalContext={additional_context!r}"
    )


def test_recovery_pointer_falls_outside_window_when_its_asset_sorts_last(
    tmp_path: Path,
) -> None:
    """Sibling-branch pin / tautology guard, FAIL branch: isolated, synthetic
    assets independent of the real repo's current content. When the
    recovery-pointer asset sorts LAST behind >2048 bytes of filler, the
    SAME oracle correctly reports the pointer outside the window --
    reproducing the defect class in a controlled, drift-proof form.
    """
    isolated_root = tmp_path / "isolated-last"
    isolated_script_dir = isolated_root / "scripts" / "hooks"
    isolated_script_dir.mkdir(parents=True)
    isolated_script = isolated_script_dir / _SCRIPT.name
    isolated_script.write_text(_SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")

    assets_dir = isolated_root / "nWave" / "data" / "orchestrator-affordance"
    assets_dir.mkdir(parents=True)
    (assets_dir / "00-filler.md").write_text("PADDING-" * 500, encoding="utf-8")
    (assets_dir / "10-recovery.md").write_text(
        f"{_RECOVERY_POINTER_MARKER} synthetic control asset\n", encoding="utf-8"
    )

    isolated_env = os.environ.copy()
    isolated_env["HOME"] = str(tmp_path / "empty-home-last")
    result = _run(
        isolated_script, "UserPromptSubmit", cwd=isolated_root, env=isolated_env
    )

    assert result.returncode == 0, (
        f"must exit 0 -- got returncode={result.returncode}, stderr={result.stderr!r}"
    )
    payload = _parse_json_or_fail(result.stdout)
    additional_context = payload.get("hookSpecificOutput", {}).get(
        "additionalContext", ""
    )
    offset = _byte_offset(additional_context, _RECOVERY_POINTER_MARKER)

    assert offset != -1, f"got additionalContext={additional_context!r}"
    assert offset >= _ADMITTED_PREVIEW_WINDOW_BYTES, (
        "synthetic control expected the marker OUTSIDE the window (filler "
        f"padding forces it there) -- got offset={offset}, "
        f"additionalContext={additional_context!r}"
    )
