"""Spine-ledger PreToolUse hook -- slice-02 of atdd-spine-ledger-enforcement-gate-v2.

Wraps the slice-00+01 `spine_ledger_gate.py` for the Claude Code PreToolUse
protocol on the `Bash` matcher. The hook receives the tool invocation event
as JSON on stdin, inspects the `tool_input.command` field, and dispatches:

  Fast-path (non-git-commit Bash):
    Regex-match `^\\s*git\\s+commit\\b` on the command. If NO match, exit 0
    silently. NO gate spawn -- the marker file
    (`NWAVE_SPINE_LEDGER_GATE_INVOCATION_MARKER_FILE`) is NOT touched. This
    is the empirical "shell-fast-path" promise from slice-02 ATs: a bare
    Python early-exit before any heavy operation (no subprocess spawn,
    no filesystem write).

  Commit path:
    Extract the candidate commit message file from the bash command. The
    common patterns are `git commit -F <file>` (composition fixture's path)
    and `git commit -m "..."`/`git commit` (operator's direct path). The
    hook touches the marker file (proving the spawn-path was reached),
    then invokes `python -m scripts.hooks.spine_ledger_gate` as a real
    subprocess with the resolved message file + target/ledger roots.

  Decision translation:
    Gate exit 0 (commit-allowed) -> hook exit 0 (Claude Code approves).
    Gate exit 1 (commit-refused) -> hook prints `{"decision": "block",
    "reason": "..."}` to stdout + exits 2 (Claude Code refuses Bash).
    Gate exit anything else -> fail-closed: hook blocks with an error
    reason (the gate crashed; refuse the commit defensively).

Substrate (Ale 2026-05-28 framing-shift): Claude Code hook lifecycle.
This script is the PreToolUse entry point that wires slice-00+01's gate
into the path the orchestrating LLM actually takes (Bash -> git commit).
Slice-04 will ship the installer plugin registration; slice-02 lands
the entry-point script + the matcher-coexistence registration in
`hook_definitions.py`.

Matcher coexistence: this hook is registered as a NEW HookEvent adjacent
to the pre-existing `_BASH_EXECUTION_LOG_GUARD` in
`scripts/shared/hook_definitions.py`. Claude Code's PreToolUse protocol
permits multiple registrations per (event, matcher) tuple; execution is
registration-ordered; ANY hook returning `{decision: block}` blocks the
tool invocation. The execution-log guard does NOT block git-commit
commands (its `grep -q 'execution-log'` test fails), so the spine-
ledger hook's block decision wins by construction.

Stdlib-only (no PyYAML, no third-party deps). Mirrors the pattern of
`scripts/hooks/spine_ledger_gate.py` (slice-00+01, shipped) and
`src/des/adapters/drivers/hooks/pre_tool_use_handler.py` (the DES
adapter's PreToolUse contract reference).

Hook protocol contract (Claude Code PreToolUse on Bash):
    stdin = {"tool_name": "Bash", "tool_input": {"command": "...", ...}, ...}
    stdout (block) = {"decision": "block", "reason": "..."}
    stdout (approve) = "" (empty; exit code 0 is the signal)
    exit 0 = allow tool invocation
    exit 2 = block tool invocation (with stdout JSON for reason)

Test-harness env-var contract (slice-02 ATs):
    NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT -- target machine root override
    NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT -- spine telemetry dir override
    NWAVE_SPINE_LEDGER_GATE_INVOCATION_MARKER_FILE -- touched when the
        hook spawns the gate subprocess (proves AT-2's negative
        observable: marker absent <=> NO spawn)

In production (no env overrides), the hook uses `Path.cwd()` as the
target root and `<target>/.nwave/telemetry/atdd-pure/` as the ledger
root, mirroring `spine_ledger_gate.py`'s defaults.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


# Repo root: scripts/hooks/spine_ledger_pre_commit_hook.py -> up two levels.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_GATE_MODULE = "scripts.hooks.spine_ledger_gate"

# Env-var contract for test-harness parameter passing. In production these are
# unset and the hook falls back to Path.cwd() + the canonical telemetry path.
_ENV_TARGET_ROOT = "NWAVE_SPINE_LEDGER_GATE_TARGET_ROOT"
_ENV_LEDGER_ROOT = "NWAVE_SPINE_LEDGER_GATE_LEDGER_ROOT"
_ENV_INVOCATION_MARKER = "NWAVE_SPINE_LEDGER_GATE_INVOCATION_MARKER_FILE"

# Default telemetry path under a target root (mirrors spine_ledger_gate.py).
_TELEMETRY_RELPATH = Path(".nwave") / "telemetry" / "atdd-pure"

# Shell-fast-path discriminator: a bash command starts with `git commit` (with
# optional leading whitespace). The composition fixture's command literal is
# `git commit -F <file>`; the operator path is typically `git commit -m "..."`
# or bare `git commit`. The regex tolerates leading whitespace and requires a
# word boundary after `commit` so `git committed` (hypothetical) does not match.
_GIT_COMMIT_RE = re.compile(r"^\s*git\s+commit\b")

# `--no-verify` / `-n` detection (f-nonbypassable-attestation slice-02, DDD-3).
# `--no-verify` skips git's pre-commit/commit-msg hooks, so the Gate-Scope
# stamping never runs and the bypass leaves no trace -- UNLESS this PreToolUse
# hook (which fires BEFORE git, so `--no-verify` cannot skip it) records it. The
# short alias `-n` is matched only as a standalone token (a word boundary on both
# sides) so it does not false-match inside a `-m`-quoted message body.
_NO_VERIFY_RE = re.compile(r"(?:^|\s)(?:--no-verify|-n)(?:\s|$)")

# A `slice-NN` identifier carried by a `Slice-Id:`/`Step-Id:` commit trailer (the
# canonical binding) used to scope the bypass-debt record to its slice.
_SLICE_TRAILER_RE = re.compile(r"^(?:Slice-Id|Step-Id):\s*(slice-\d+[a-z]?)\s*$")
# Fallback: a `slice-NN` token anywhere in the commit message (the conventional
# `slice-NN: subject` form an LLM emits). Used only when no trailer is present.
_SLICE_TOKEN_RE = re.compile(r"\bslice-\d+[a-z]?\b")

# Commit-message-file source patterns parsed out of the bash command literal.
# Order matters: `-F` / `--file` are explicit file flags; `-m` / `--message`
# is an inline string; absent -> default `.git/COMMIT_EDITMSG`.
#
# Both flags accept three syntaxes:
#   -F <file>            short flag + whitespace separator
#   --file=<file>        long flag + equals separator
#   --file <file>        long flag + whitespace separator
# The (?:=|\s+) alternation MUST live INSIDE a wrapping group that ALSO
# spans the short-flag whitespace, otherwise `-F /tmp/x` does not match.
_F_FLAG_RE = re.compile(r"(?:^|\s)(?:-F\s+|--file(?:=|\s+))(\S+)")
_M_FLAG_RE = re.compile(
    r"""(?:^|\s)(?:-m\s+|--message(?:=|\s+))(?:"([^"]*)"|'([^']*)'|(\S+))"""
)


def _read_hook_event() -> dict:
    """Read the Claude Code PreToolUse hook event JSON from stdin.

    Returns `{}` if stdin is empty or malformed; the caller treats this as
    a non-actionable event (approve silently). The hook's contract is to
    fail OPEN on protocol violations -- a malformed event is a Claude Code
    bug, not an operator violation.
    """
    raw = sys.stdin.read()
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _bash_command(event: dict) -> str:
    """Extract the bash command literal from the hook event payload."""
    tool_input = event.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return ""
    command = tool_input.get("command", "")
    return command if isinstance(command, str) else ""


def _is_git_commit(command: str) -> bool:
    """True iff the bash command begins with `git commit` (word-boundary match)."""
    return _GIT_COMMIT_RE.match(command) is not None


def _resolve_commit_msg_file(command: str, target_root: Path) -> Path:
    """Resolve the candidate commit message file path from the bash command.

    Three sources, in priority order:
      1. `-F <file>` / `--file <file>` -- explicit file flag (composition
         fixture path: `git commit -F /tmp/.../candidate-commit-msg.txt`).
      2. `-m "..."` / `--message "..."` -- inline string. The hook writes
         the inline message to a synthesised temp file so the gate (which
         only consumes `--commit-msg-file`) sees a uniform input.
      3. Default: `<target>/.git/COMMIT_EDITMSG` -- the canonical staging
         path git itself uses when invoked without `-F`/`-m`.

    The synthesised temp file lives under `<target>/.nwave/des/` so it is
    co-located with the audit log and not orphaned in /tmp.
    """
    f_match = _F_FLAG_RE.search(command)
    if f_match:
        return Path(f_match.group(1))

    m_match = _M_FLAG_RE.search(command)
    if m_match:
        inline_message = m_match.group(1) or m_match.group(2) or m_match.group(3) or ""
        synth_dir = target_root / ".nwave" / "des"
        synth_dir.mkdir(parents=True, exist_ok=True)
        synth_path = synth_dir / "candidate-commit-msg-from-m-flag.txt"
        synth_path.write_text(inline_message, encoding="utf-8")
        return synth_path

    return target_root / ".git" / "COMMIT_EDITMSG"


def _target_root() -> Path:
    """Resolve the target machine root from env override or Path.cwd()."""
    override = os.environ.get(_ENV_TARGET_ROOT, "")
    return Path(override) if override else Path.cwd()


def _ledger_root(target_root: Path) -> Path:
    """Resolve the spine telemetry root from env override or the canonical path."""
    override = os.environ.get(_ENV_LEDGER_ROOT, "")
    return Path(override) if override else target_root / _TELEMETRY_RELPATH


def _touch_invocation_marker() -> None:
    """Touch the gate-invocation marker file when env var is set (test harness).

    AT-2's negative observable: when the hook does NOT spawn the gate
    (fast-path-skip path), the marker is absent. The marker is touched
    only here -- inside the spawn dispatch, BEFORE the subprocess runs --
    so the absence/presence test is unambiguous.
    """
    marker_path = os.environ.get(_ENV_INVOCATION_MARKER, "")
    if not marker_path:
        return
    path = Path(marker_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _is_no_verify(command: str) -> bool:
    """True iff the git-commit command carries `--no-verify` or a standalone `-n`."""
    return _NO_VERIFY_RE.search(command) is not None


def _resolve_commit_slice_id(command: str, target_root: Path) -> str | None:
    """Resolve the slice id the bypassed commit binds to (DDD-3).

    Priority: a `Slice-Id:`/`Step-Id:` trailer in the resolved commit message
    file (the canonical binding), else a `slice-NN` token anywhere in the
    message (the conventional `slice-NN: subject` form). Returns None when the
    commit names no slice -- a non-slice bypass leaves no slice-scoped debt.
    """
    try:
        message = _resolve_commit_msg_file(command, target_root).read_text(
            encoding="utf-8"
        )
    except OSError:
        return None
    for line in message.splitlines():
        match = _SLICE_TRAILER_RE.match(line.strip())
        if match:
            return match.group(1)
    token = _SLICE_TOKEN_RE.search(message)
    return token.group(0) if token else None


def _record_bypass_debt(command: str, target_root: Path) -> None:
    """Append a `SliceCommitBypassed` debt record for a `--no-verify` commit (DDD-3).

    Fires BEFORE git runs (so `--no-verify` cannot skip it). Resolves the bound
    slice from the commit message and the in-flight feature from the telemetry
    ledger (via the ONE canonical `active_feature_id` -- see
    `at_completion_ledger.active_feature_id`), then appends via the EXISTING
    `AtCompletionLedger` M7 writer so the record carries `seq` + `record_hash`.
    Fail-open on the write itself -- a ledger-write error must not change the
    commit decision (the gate verdict stands on its own).
    """
    slice_id = _resolve_commit_slice_id(command, target_root)
    if slice_id is None:
        return
    try:
        src_dir = _REPO_ROOT / "src"
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        from des.adapters.driven.logging.at_completion_ledger import (
            AtCompletionLedger,
            active_feature_id,
        )

        feature_id = active_feature_id(target_root)
        if feature_id is None:
            return
        AtCompletionLedger(feature_id, target_root).append_slice_commit_bypassed(
            slice_id
        )
    except Exception:
        # Fail-open: the bypass record is audit; a write failure must not change
        # the commit decision (mirrors the gate's fail-open ledger emission).
        pass


def _spawn_gate(
    commit_msg_file: Path, ledger_root: Path, target_root: Path
) -> subprocess.CompletedProcess[str]:
    """Invoke `spine_ledger_gate` as a real subprocess with resolved roots."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            _GATE_MODULE,
            "--commit-msg-file",
            str(commit_msg_file),
            "--ledger-root",
            str(ledger_root),
            "--target-root",
            str(target_root),
        ],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={**os.environ},
    )


def _emit_block(reason: str) -> None:
    """Print a single-line `{decision: block}` JSON object on stdout."""
    print(json.dumps({"decision": "block", "reason": reason}, sort_keys=True))


def _format_block_reason(gate_stdout: str) -> str:
    """Build the operator-facing reason string from the gate's stdout JSON.

    The gate emits `{"verdict": "commit-refused", "cause": "block-...",
    "unverified_slices": [...], "slice_id": "..."}` on refusal. The hook
    propagates BOTH the cause AND the slice id into the reason string so
    AT-1's `assert_block_reason_names_cause` and `assert_block_reason_names_slice`
    both pass without parsing the gate JSON twice.
    """
    payload = _parse_first_json_line(gate_stdout)
    cause = payload.get("cause", "unknown-cause")
    slice_id = payload.get("slice_id", "")
    unverified = payload.get("unverified_slices") or []
    slice_phrase = slice_id or (unverified[0] if unverified else "")
    if slice_phrase:
        return (
            f"spine-ledger gate refused commit: {cause} "
            f"(unverified slice: {slice_phrase})"
        )
    return f"spine-ledger gate refused commit: {cause}"


def _parse_first_json_line(text: str) -> dict:
    """Parse the first JSON object found in `text`, or return {}."""
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return {}


def _dispatch_commit_path(command: str) -> int:
    """Spawn the gate and translate its verdict to a Claude Code decision.

    Touches the gate-invocation marker FIRST (proves the spawn-path was
    reached for AT-2's negative observable test on a fast-path command).
    """
    _touch_invocation_marker()
    target_root = _target_root()
    # f-nonbypassable-attestation slice-02 (DDD-3): observe `--no-verify`/`-n`
    # BEFORE git runs (git's own hooks are skipped by --no-verify, so this is the
    # only surface that can see it) and convert the silent bypass into an
    # indelible, veto-able `SliceCommitBypassed` debt record. Pre-git so it
    # happens regardless of git hooks being skipped; fail-open so it never
    # changes the commit decision.
    if _is_no_verify(command):
        _record_bypass_debt(command, target_root)
    ledger_root = _ledger_root(target_root)
    commit_msg_file = _resolve_commit_msg_file(command, target_root)
    completed = _spawn_gate(commit_msg_file, ledger_root, target_root)

    if completed.returncode == 0:
        return 0

    if completed.returncode == 1:
        _emit_block(_format_block_reason(completed.stdout or ""))
        return 2

    # Fail-closed: any non-{0,1} exit means the gate crashed. Refuse the
    # commit defensively with a diagnostic reason carrying the gate's
    # stderr tail (truncated) so the operator sees the proximate cause.
    stderr_tail = (completed.stderr or "").strip().splitlines()
    tail = stderr_tail[-1] if stderr_tail else "<no stderr>"
    _emit_block(
        f"spine-ledger gate crashed (exit {completed.returncode}); "
        f"refusing commit defensively. stderr: {tail}"
    )
    return 2


def main() -> int:
    """Read the hook event, dispatch by command shape, return the exit code.

    Decision order:
        1. Read stdin event JSON (empty/malformed -> approve silently).
        2. Extract the bash command literal.
        3. Fast-path: non-git-commit command -> exit 0 (NO marker touch).
        4. Commit path: spawn the gate, translate its verdict to Claude
           Code's PreToolUse decision protocol.
    """
    event = _read_hook_event()
    command = _bash_command(event)
    if not _is_git_commit(command):
        return 0
    return _dispatch_commit_path(command)


if __name__ == "__main__":
    sys.exit(main())
