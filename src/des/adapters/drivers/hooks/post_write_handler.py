"""PostToolUse handler — classifies an ATD-authored oracle at the WRITE.

Root's own K4 Run 13 debrief (`des.domain.oracle_execution_classifier`
module docstring): "have ATD actually execute the oracle... before
CONTRACT_READY." `des dispatch`'s BASE red-reason probe
(`des.cli._oracle_red_reason_refusal`) already proves this once, but only
AFTER ATD has finished and returned `CONTRACT_READY` -- a defect ATD could
have fixed in the SAME turn instead costs a full REVISE round-trip. This
handler reclassifies the identical evidence at the moment the `Write`/`Edit`
on the oracle file itself completes, and hands ATD that finding immediately,
in the SAME turn, through `additionalContext`.

Advisory only, by construction: a PostToolUse hook cannot undo an already-
completed Write/Edit, so this handler NEVER returns a block decision --
every path exits 0. `des dispatch`'s own BASE probe remains the terminal,
authoritative check (unchanged, still wired); this is strictly earlier,
cheaper feedback on the SAME evidence, not a second authority.

Fires on every Write/Edit, not only ATD's (role-checked first, cheaply,
before any file/subprocess work) -- Claude Code has no per-role hook
registration, so the cost of an uninteresting call is one dict lookup, not
a subprocess.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

from des.adapters.drivers.hooks.hook_protocol import (
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.root_activation_context import (
    resolve_subagent_agent_type,
)
from des.domain.oracle_write_classifier import (
    OracleWriteClassification,
    classify_write,
    command_argv,
    linked_verification_command,
)
from des.runtime.test_execution import run_pytest_reaped


_ATD_ROLE = "nw-acceptance-designer"
_PROBE_TIMEOUT_SECONDS = 60.0


def _repo_relative(file_path: str, repo_root: Path) -> str | None:
    """`file_path` (absolute or already-relative) as a POSIX path relative
    to `repo_root`, or `None` when it does not resolve under it."""
    if not file_path:
        return None
    try:
        candidate = Path(file_path)
        resolved = candidate if candidate.is_absolute() else repo_root / candidate
        return resolved.resolve().relative_to(repo_root.resolve()).as_posix()
    except (OSError, ValueError):
        return None


def _find_contract_for_oracle(repo_root: Path, relative_path: str) -> dict | None:
    """The one `docs/delivery-contracts/*.json` whose `acceptance-tests.
    locator` equals `relative_path` -- `None` when no contract names this
    exact file as its oracle (an ordinary write this hook has nothing to
    say about). A malformed/unreadable candidate contract is skipped, never
    raised -- this hook degrades LOUD only for a write it has already
    identified as in-scope, not for every unrelated JSON file on disk."""
    contracts_dir = repo_root / "docs" / "delivery-contracts"
    if not contracts_dir.is_dir():
        return None
    for path in sorted(contracts_dir.glob("*.json")):
        try:
            contract = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(contract, dict):
            continue
        if contract.get("acceptance-tests", {}).get("locator") == relative_path:
            return contract
    return None


def _additional_context(text: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": text,
                }
            }
        )
    )


def _classification_message(classification: OracleWriteClassification) -> str:
    reason_suffix = f" ({classification.reason!r})" if classification.reason else ""
    return (
        f"ORACLE-WRITE-CLASSIFICATION: {classification.label}\n"
        f"COMMAND: {classification.command_text}\n"
        f"REASON:{reason_suffix or ' (none captured)'}"
    )


def handle_post_write() -> int:
    """Handle PostToolUse for Write/Edit: classify an ATD oracle write.

    Always returns 0 -- see module docstring. Any classification (or the
    reason none could be produced) is relayed via `additionalContext`;
    silence means either the write is not in this hook's scope (not ATD, or
    not a known contract's own oracle locator) or an unexpected internal
    error the caller cannot act on.
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    try:
        stdin_result = read_and_parse_stdin("post_write", json_error_fallback="allow")
        if stdin_result.is_empty or stdin_result.parse_error:
            return 0
        hook_input = stdin_result.hook_input
        assert hook_input is not None

        agent_type = resolve_subagent_agent_type(hook_input)
        if agent_type != _ATD_ROLE:
            return 0

        tool_input = hook_input.get("tool_input", {})
        file_path = (
            tool_input.get("file_path", "") if isinstance(tool_input, dict) else ""
        )
        repo_root = Path(str(hook_input.get("cwd") or Path.cwd()))

        relative_path = _repo_relative(file_path, repo_root)
        if relative_path is None:
            return 0

        contract = _find_contract_for_oracle(repo_root, relative_path)
        if contract is None:
            return 0

        log_hook_invoked(
            "post_write",
            {"file_path": relative_path, "agent_type": agent_type},
            hook_id=hook_id,
        )

        command = linked_verification_command(contract, relative_path)
        if command is None:
            _additional_context(
                "ORACLE-WRITE-CLASSIFICATION: could-not-verify\n"
                "REASON: the compiled contract names this file as its "
                "acceptance-tests.locator, but no verification-scope.commands "
                "entry cites it -- des dispatch's own BASE probe will still "
                "run before any crafter is dispatched."
            )
            return 0

        argv = command_argv(repo_root, command)
        try:
            result = run_pytest_reaped(
                argv,
                cwd=repo_root,
                timeout=_PROBE_TIMEOUT_SECONDS,
                capture_output=True,
                text=True,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            _additional_context(
                "ORACLE-WRITE-CLASSIFICATION: could-not-verify\n"
                f"REASON: the verification command could not be run ({exc}) -- "
                "des dispatch's own BASE probe will still run before any "
                "crafter is dispatched."
            )
            return 0

        output = f"{result.stdout or ''}\n{result.stderr or ''}"
        classification = classify_write(
            contract=contract,
            command=command,
            repo_root=repo_root,
            returncode=result.returncode,
            output=output,
        )
        _additional_context(_classification_message(classification))
        return 0
    except Exception as exc:  # pragma: no cover - defensive, mirrors pre_write
        log_hook_error("post_write", exc, "")
        return 0
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        log_hook_completed(
            hook_id=hook_id,
            handler="post_write",
            exit_code=exit_code,
            decision="allow",
            duration_ms=duration_ms,
        )
