"""PreToolUse handler — validates Task/Agent tool invocations.

Translates Claude Code's PreToolUse hook event (JSON stdin) into
PreToolUseService decisions (allow/block), manages DES task signal creation,
and emits audit events through hook_protocol.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.

No hook re-litigates wave order, readiness, or route selection here: the
resident DES runner owns sequencing. What remains are independent safety
boundaries -- the nWave subagent host-scan limit, the git-stash guard, and
commit attribution.
"""

import contextlib
import io
import json
import os
import time
import uuid
from pathlib import Path

from des.adapters.drivers.hooks.bash_command_guards import (
    _split_subcommands,
    evaluate_git_stash_command,
    git_stash_guard_target_root,
    write_bash_guard_audit_event,
)
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    HookCompletion,
    TaskAccounting,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.root_activation_context import (
    resolve_subagent_agent_type,
)
from des.application.commit_attribution_service import CommitAttributionService
from des.domain.nwave_locations import NWaveLocations
from des.domain.result import Failure


# nWave subagent host-scan lockdown (K4 architecture gap): a dispatched nw-*
# subagent's own Bash `find`/`bfs` call is restricted to a repo-scoped
# traversal root -- `find /` (or an option-prefixed equivalent) walks the
# whole host instead of the active project. Root/user Bash and non-nWave
# agents are untouched (see `_is_nwave_subagent`).
_HOST_SCAN_COMMAND_NAMES = frozenset({"find", "bfs"})


def _is_nwave_subagent(hook_input: dict[str, object]) -> bool:
    """True iff this dispatch is a running nWave subagent -- resolved via
    `root_activation_context.resolve_subagent_agent_type` (the ONE shared
    resolver: live envelope field, or its transcript meta-sidecar; see Run
    9/10 correction there) -- never root/user (neither source resolves) and
    never a non-nWave agent (some other prefix on both sources)."""
    return resolve_subagent_agent_type(hook_input) is not None


def _host_scan_traversal_roots(argv: list[str]) -> list[str]:
    """The traversal-root path arguments of a `find`/`bfs` argv.

    Options may precede the roots (`find -H /`); once at least one root has
    been collected, the next `-`-prefixed token starts the predicate/
    expression list and ends the scan -- `find /repo -name find` must not
    see a later bare `find` token in a predicate as a second root.
    """
    roots: list[str] = []
    for token in argv[1:]:
        if token.startswith("-"):
            if roots:
                break
            continue
        roots.append(token)
    return roots


def _is_host_wide_traversal_root(root: str) -> bool:
    """True iff `root` is the filesystem root itself (`/`, `//`, ...) --
    never a scoped path like `/repo`, `/tmp/project`, `.`, or `AUTO-ARCHITECTURE-ROOT`."""
    return root.rstrip("/") == ""


def _nwave_host_scan_block(command: str) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an nWave subagent Bash call ({command!r}) traverses the "
            "filesystem root instead of the active project. "
            "WHY: a host-wide find/bfs scan can spend minutes walking the "
            "entire machine instead of the project tree -- discovery must "
            "stay repo-scoped so a consult's critical path is not spent "
            "scanning the host. "
            "HOW: use repo-scoped Glob/Grep/find rooted at the project "
            "directory or the absolute AUTO-ARCHITECTURE-ROOT, or inspect "
            "the exact module path directly (e.g. `python -c "
            '"import inspect, <module>; print(inspect.getsourcefile(<module>))"` '
            "and read the returned path)."
        ),
    }


def _evaluate_nwave_subagent_host_scan(command: object) -> dict[str, str] | None:
    """Pure nWave-subagent `find`/`bfs` host-scan decision.

    Returns `None` (allow) for anything that is not, in some `&&`/`||`/`;`/
    `|`/`&`-separated sub-command, an actual `find`/`bfs` invocation whose
    traversal root is the filesystem root -- including quoted mentions
    (shlex tokenizes those into one non-command argument, never `argv[0]`)
    and repo-/cwd-/AUTO-root-scoped invocations. Fails open (`None`) on an
    unparsable command, which fails open so the safety hook stays local to
    commands it can classify.
    """
    if not isinstance(command, str) or not command.strip():
        return None
    sub_commands = _split_subcommands(command)
    if sub_commands is None:
        return None
    for argv in sub_commands:
        if not argv or argv[0] not in _HOST_SCAN_COMMAND_NAMES:
            continue
        roots = _host_scan_traversal_roots(argv)
        if any(_is_host_wide_traversal_root(root) for root in roots):
            return _nwave_host_scan_block(command)
    return None


def emit_commit_attribution_mutation(
    tool_input: dict[str, object], *, cwd: Path | None = None
) -> int | None:
    """Net-new mutation branch: rewrite a Bash `git commit` to carry the trailer.

    ADR-CA-006 D4 (Reuse row R4). On a Bash `git commit` command, asks
    :class:`CommitAttributionService` for a :class:`CommitRewritePlan`. On a
    mutate Plan, emits the protocol JSON
    ``{"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "permissionDecision":"allow","updatedInput":{<full tool_input, command
    rewritten>}}}`` on stdout and returns exit 0. On a passthrough Plan, returns
    ``None`` so the caller falls through to the existing validation path
    unchanged.

    This is the ONLY net-new branch in the handler; the existing block/allow
    validation path is not modified.

    Args:
        tool_input: the ``tool_input`` object from the PreToolUse payload. Its
            ``command`` field is the Bash command to consider.
        cwd: Optional working directory for attribution config resolution.

    Returns:
        ``0`` after emitting a mutation; ``None`` to fall through to the existing
        validation path (passthrough / non-Bash / non-commit).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    # Fail-safe (ADR-CA-006): attribution is best-effort. ANY error here — a
    # raising rewrite core, a JSON-serialization failure — must NOT propagate to
    # the outer `handle_pre_tool_use` `except Exception`, which fail-closes to
    # exit 1 and BLOCKS the commit. A missed trailer is recoverable; a blocked
    # commit is not. On any failure, return None so the caller falls through to
    # the existing validation path and the original command runs unchanged.
    try:
        from des.application.commit_message_attribution import attribution_is_due

        # ONE condition, shared with the producing-tool path (`des commit` /
        # `des commit-slice` -> `attribute_commit_message`): ACTIVE repo AND
        # attribution preference on. Rewriting the user's `git commit` is an
        # action ON THE USER'S WORK, so ADR-AG-005 (opt-in ratified) governs it
        # exactly as it governs the producing tools -- this branch previously
        # read `attribution_enabled` alone and acted in repositories the user
        # never activated (F-ATTRIBUTION-GATING-ASYMMETRY-PRETOOLUSE). The
        # router's `activation_gate` resolving activation upstream is a property
        # of the CONTAINER, not of this seam: it is called directly, and its
        # `cwd` comes from the hook envelope, which need not name the root the
        # gate resolved (GDP-8 witness corollary).
        #
        # Resolve per call through the same selected-home carrier as install.
        # A hook can retain the system HOME while an operator deliberately
        # installs nWave beneath NWAVE_AGENTS_HOME.
        locations = NWaveLocations.resolve(
            home=Path.home(),
            repo_root=cwd or Path.cwd(),
            agents_home_override=os.environ.get("NWAVE_AGENTS_HOME") or None,
            claude_config_override=os.environ.get("CLAUDE_CONFIG_DIR") or None,
            codex_config_override=os.environ.get("CODEX_HOME") or None,
        )
        if isinstance(locations, Failure):
            return None
        if not attribution_is_due(
            cwd or Path.cwd(),
            global_config_path=locations.unwrap().agents_home
            / ".nwave"
            / "config.json",
        ):
            return None

        plan = _commit_attribution_service.plan_rewrite(command)
        if plan.action != "mutate" or plan.rewritten_command is None:
            return None

        updated_input = {**tool_input, "command": plan.rewritten_command}
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                        "updatedInput": updated_input,
                    }
                }
            )
        )
        return 0
    except Exception:
        return None


# Bound so step-composition / future wiring reference a single seam, not a free
# constructor call. DELIVER injects the real service here.
_commit_attribution_service = CommitAttributionService()


def evaluate_bash_safety_guards(
    hook_input: dict[str, object], tool_input: dict[str, object]
) -> dict[str, str] | None:
    """The git-stash Bash guard decision.

    Formerly two standalone PreToolUse/Bash hook registrations
    (`scripts/hooks/git_stash_guard.py`). The single decision authority is
    `des.adapters.drivers.hooks.bash_command_guards` (`evaluate_git_stash_command`); this
    function is one envelope-parsing wrapper around it. The standalone scripts
    call the shared predicate authority directly (their own CLI envelope
    shape), NOT necessarily this helper. `hook_router.main()` calls THIS
    helper by name, once, BEFORE `activation_gate.apply_gate` (ADR-AG-001
    ordering repair), so an inactive project cannot exit 0 past a live
    stash/worktree mutation -- see the router's pre-activation call site for
    the ordering contract. Returns a `{decision: block, reason: ...}` payload,
    or `None` to allow (paying no triage/filesystem work when neither guard's
    command shape matched).
    """
    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return None

    stash_decision = evaluate_git_stash_command(command)
    if stash_decision is not None:
        if stash_decision.audit_event is not None:
            write_bash_guard_audit_event(
                git_stash_guard_target_root(),
                stash_decision.audit_event,
                {
                    **(stash_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not stash_decision.allow:
            return {"decision": "block", "reason": stash_decision.reason or ""}
        return None

    return None


def handle_pre_tool_use() -> int:
    """Handle PreToolUse command: validate Task tool invocation.

    Protocol translation only -- all decisions delegated to PreToolUseService.

    Returns:
        0 if validation passes (allow)
        1 if error occurs (fail-closed)
        2 if validation fails (block)
    """
    hook_id = str(uuid.uuid4())
    start_ns = time.perf_counter_ns()
    exit_code = 0
    task_correlation_id: str | None = None
    stderr_buffer = io.StringIO()
    try:
        with contextlib.redirect_stderr(stderr_buffer):
            stdin_result = read_and_parse_stdin("pre_tool_use")

            if stdin_result.is_empty:
                return 0

            if stdin_result.parse_error:
                response = {"status": "error", "reason": stdin_result.parse_error}
                print(json.dumps(response))
                exit_code = 1
                return exit_code

            # The is_empty / parse_error guards above guarantee a parsed dict.
            hook_input = stdin_result.hook_input
            assert hook_input is not None  # narrowed by the guards above

            # Diagnostic: confirm hook was invoked
            tool_input = hook_input.get("tool_input", {})

            tool_name = hook_input.get("tool_name")

            # K4 architecture gap: nWave subagent host-scan lockdown. Cheap
            # for the overwhelming majority of Bash calls (non-find/bfs
            # commands, or a non-nWave-subagent caller) -- `_is_nwave_subagent`
            # is a dict-get + prefix check, no I/O.
            if tool_name == "Bash" and _is_nwave_subagent(hook_input):
                host_scan_block = _evaluate_nwave_subagent_host_scan(
                    tool_input.get("command")
                )
                if host_scan_block is not None:
                    print(json.dumps(host_scan_block))
                    exit_code = 2
                    return exit_code

            if hook_input.get("tool_name") == "Bash":
                # The git-stash / worktree-remove safety decision already ran
                # once, pre-activation, in `hook_router.main()` (before
                # `apply_gate`) -- see `evaluate_bash_safety_guards`. Do not
                # re-run it here; that would be a duplicate second evaluation
                # of the same command on the active path.
                mutation_cwd = None
                if isinstance(hook_input.get("cwd"), str):
                    cwd_str = hook_input.get("cwd")
                    if cwd_str:
                        mutation_cwd = Path(cwd_str)
                mutation_exit = emit_commit_attribution_mutation(
                    tool_input, cwd=mutation_cwd
                )
                if mutation_exit is not None:
                    exit_code = mutation_exit
                    return exit_code
            log_hook_invoked(
                "pre_tool_use",
                {
                    "subagent_type": tool_input.get("subagent_type"),
                },
                hook_id=hook_id,
            )

            exit_code = 0
            return exit_code

    except Exception as e:
        # Fail-closed: any error blocks execution
        stderr_capture = stderr_buffer.getvalue()[:STDERR_CAPTURE_MAX_CHARS]
        log_hook_error("pre_tool_use", e, stderr_capture)
        response = {"status": "error", "reason": f"Unexpected error: {e!s}"}
        print(json.dumps(response))
        exit_code = 1
        return exit_code
    finally:
        duration_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        decision_str = EXIT_CODE_TO_DECISION.get(exit_code, "error")
        log_hook_completed(
            HookCompletion(
                hook_id=hook_id,
                handler="pre_tool_use",
                exit_code=exit_code,
                decision=decision_str,
                duration_ms=duration_ms,
            ),
            TaskAccounting(task_correlation_id=task_correlation_id),
        )
