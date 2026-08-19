"""PreToolUse handler — validates Task/Agent tool invocations.

Translates Claude Code's PreToolUse hook event (JSON stdin) into
PreToolUseService decisions (allow/block), manages DES task signal creation,
and emits audit events through hook_protocol.

Extracted from claude_code_hook_adapter.py as part of P4 decomposition.

The U1 carpaccio entry-gate intercept that used to run here is gone: a dispatch
is no longer refused by a hook for slice order, readiness, or marker
completeness. Reuse, architecture conformance and AT-first are practices carried
in the dispatch itself, not preconditions a hook re-litigates.
"""

import contextlib
import io
import json
import shlex
import time
import uuid
from pathlib import Path, PurePosixPath, PureWindowsPath

from des.adapters.drivers.hooks import des_task_signal
from des.adapters.drivers.hooks.bash_command_guards import (
    _split_subcommands,
    evaluate_git_stash_command,
    evaluate_worktree_remove_command,
    git_stash_guard_target_root,
    worktree_guard_target_root,
    write_bash_guard_audit_event,
)
from des.adapters.drivers.hooks.hook_protocol import (
    EXIT_CODE_TO_DECISION,
    STDERR_CAPTURE_MAX_CHARS,
    extract_transcript_path,
    log_hook_completed,
    log_hook_error,
    log_hook_invoked,
    read_and_parse_stdin,
)
from des.adapters.drivers.hooks.root_activation_context import (
    build_root_mode_select_context,
    hook_input_has_agent_identity,
    resolve_subagent_agent_type,
    resolve_subagent_own_transcript_path,
    root_mode_handoff_block_reason,
)
from des.application.commit_attribution_service import CommitAttributionService
from des.application.ordinary_request import (
    ATD_BODY_LINE_COUNT,
    DELIVERY_ID_HEX_LEN,
    DELIVERY_ID_PREFIX,
    compute_delivery_id,
    contract_locator_for,
    is_lexical_repo_relative_json_locator,
    is_valid_arch_header_line,
    is_well_formed_po_envelope,
)
from des.application.skill_tracking_service import (
    RootModeState,
    resolve_root_mode_state,
)
from des.domain.agent_capability import resolve_declared_max_turns


# Non-zero exit code paired with a `{decision:block}` body for an atdd_pure
# U1 intercept block (matches the existing block path's exit_code convention).
_ATDD_PURE_BLOCK_EXIT_CODE = 2

# Auto-root Bash lockdown (K4 architecture gap): tool names that carry DES
# task-signal authority. Auto's root process must never call these directly
# once nw-auto is engaged -- that authority belongs to a dispatched role.
_AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES = ("TaskCreate", "TaskUpdate")
_ROOT_MODE_HANDOFF_TOOL_NAMES = frozenset(
    {"Agent", "Bash", "SendMessage", "TaskCreate", "TaskUpdate"}
)

# Auto-root crafter first-dispatch THIN header gate (K4 architecture gap):
# the exact role names for which an Auto-root Agent dispatch must carry a
# well-formed THIN-DELIVERY-CONTRACT authority as the prompt's first bytes.
# Deliberately exact match -- a reviewer or any other nw-* role is untouched.
_AUTO_ROOT_CRAFTER_ROLES = frozenset(
    {"nw-software-crafter", "nw-functional-software-crafter"}
)

_THIN_HEADER_LOCATOR_PREFIX = "THIN-DELIVERY-CONTRACT: "
_THIN_HEADER_DIGEST_PREFIX = "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
_THIN_HEADER_DIGEST_HEX_LEN = 64
_THIN_HEADER_DIGEST_HEX_ALPHABET = frozenset("0123456789abcdef")

# K4: exact-match roles whose Auto-root Agent dispatch must carry the
# value-only four-line PO envelope `des resolve-charters` prints on AUTHOR
# (`des.application.ordinary_request.build_po_envelope`) -- never an
# ARCHITECTURE-COVERED anchor, which disqualifies `nw-product-owner` as
# charter author by its own role logic the instant its context carries one.
_AUTO_ROOT_PO_ENVELOPE_ROLES = frozenset({"nw-product-owner"})
_ATD_ROLE_NAME = "nw-acceptance-designer"


_DELIVERY_ROUTE_TOKENS = frozenset({"RED_TO_GREEN", "GREEN_TO_GREEN"})
_ARCHITECT_ROLE_NAME = "nw-solution-architect"
_AUTO_ARCH_CONSULT_LINE_PREFIX = "AUTO-ARCHITECTURE-CONSULT: "
_AUTO_ARCH_ROOT_LINE_PREFIX = "AUTO-ARCHITECTURE-ROOT: "
_AUTO_ARCH_DELIVERY_ROUTE_LINE_PREFIX = "AUTO-DELIVERY-ROUTE: "
_ATD_ROOT_LINE_PREFIX = "ROOT: "
_ATD_VALUE_SEED_LINE_PREFIX = "VALUE-SEED: "
_ATD_DELIVERY_ROUTE_LINE_PREFIX = "DELIVERY-ROUTE: "

# Run 4 evidence / ADR-SSOT-002 Section 4c/4d: a crafter INDETERMINATE
# citing the contract/oracle itself routes back to ATD for a revision on
# the SAME already-produced DeliveryId/locator -- never a fresh
# `prepare-ordinary-request` run (that producer now refuses a second run
# for the same seed, naming this exact two-line shape). This is an
# alternate, equally strict, lexical-only ATD dispatch body -- no value
# seed to recompute a hash against, so unlike the fourteen-line envelope
# it does not cross-validate the locator against a DeliveryId; it only
# proves the locator has the one shape ATD ever legitimately writes to.
_ATD_REVISE_CONTRACT_LINE_PREFIX = "REVISE-CONTRACT: "
_ATD_CITATION_LINE_PREFIX = "CITATION: "
_ATD_REVISION_BODY_LINE_COUNT = 2
_CONTRACT_LOCATOR_DIR_PREFIX = "docs/delivery-contracts/"

# K4 (nw-auto ADR-SSOT-002 Section 4c total constructor): the twelve named
# non-empty facts an Auto-root ATD dispatch body must carry, each on its own
# line and in this exact order, after the architecture authority line and one
# blank line.
_ATD_CONTRACT_LOCATOR_LINE_PREFIX = "CONTRACT-LOCATOR: "
_ATD_CONTRACT_SCHEMA_LINE_PREFIX = "CONTRACT-SCHEMA: "
_ATD_DELIVERY_ID_LINE_PREFIX = "DELIVERY-ID: "
_ATD_OUTCOME_LINE_PREFIX = "OUTCOME: "
_ATD_BASE_REVISION_LINE_PREFIX = "BASE-REVISION: "
_ATD_EXAMINE_LINE_PREFIX = "EXAMINE: "
_ATD_INDEPENDENT_REVIEW_LINE_PREFIX = "INDEPENDENT-REVIEW: "
_ATD_BUDGET_TOKEN_LIMIT_LINE_PREFIX = "BUDGET-TOKEN-LIMIT: "
_ATD_BUDGET_WALL_CLOCK_MINUTES_LINE_PREFIX = "BUDGET-WALL-CLOCK-MINUTES: "

_ATD_BASE_REVISION_TAGS = {"git-sha1:": 40, "git-sha256:": 64}
_HEX_ALPHABET = frozenset("0123456789abcdef")

# Tool names for which the resolved Auto-root lockdown applies. Root mode is
# projected once per root tool event and reused by every decision below.
_AUTO_ROOT_TASK_TOOL_LOCKDOWN_NAMES = ("Bash", *_AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES)

# Shell-composition operators rejected BEFORE `shlex.split` runs: `shlex` has
# no concept of &&/||/pipe/redirection/command-substitution/newline, so a
# smuggled second command would otherwise survive tokenization undetected.
_AUTO_ROOT_BASH_INJECTION_MARKERS = (
    "&&",
    "||",
    ";",
    "|",
    "&",
    "`",
    "$(",
    "<",
    ">",
    "\n",
    "\r",
)

# The closed set of git subcommands an Auto-root Bash call may run: read-only
# inspection (status/diff/rev-parse/branch/worktree) plus the two staging/
# commit verbs Auto's own commit-attribution flow needs.
_AUTO_ROOT_BASH_ALLOWED_GIT_SUBCOMMANDS = frozenset(
    {"status", "diff", "rev-parse", "branch", "worktree", "add", "commit"}
)

# The closed set of `des` CLI subcommands an Auto-root Bash call may run
# directly (K4: the direct-cutover spine has no hook controller between
# Auto-root and the dispatched role's own DES CLI invocation). Arguments
# after this verb are literal argv already protected by the injection-marker
# and shlex tokenization above -- never re-interpreted as shell.
_AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS = frozenset(
    {
        "dispatch",
        "validate-delivery-contract",
        "charter-scaffold",
        "prepare-ordinary-request",
        "resolve-charters",
        "code-fact",
    }
)


def _auto_root_task_tool_block(tool_name: str) -> dict[str, str]:
    """Render the block payload for an Auto-root TaskCreate/TaskUpdate call."""
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an Auto-root {tool_name} call was blocked. "
            "WHY: Auto's root process owns no task-signal authority once "
            "nw-auto is engaged -- TaskCreate/TaskUpdate belong to a "
            "dispatched role, not the root orchestrator. "
            f"HOW: dispatch the appropriate nw-* role instead of calling "
            f"{tool_name} directly from Auto root."
        ),
    }


def _auto_root_bash_block(reason: str) -> dict[str, str]:
    return {"decision": "block", "reason": reason}


# ADR-SSOT-002 "VALUE-SEED transport": the value seed must reach every
# producer that consumes it as raw UTF-8 bytes on stdin -- never argv,
# env, temp file or transcript scrape, and never re-interpreted by the
# shell (the seed is arbitrary human text, not a safe shell token). The
# blanket injection-marker block above would otherwise make those
# producers permanently unreachable from Auto-root Bash: every
# stdin-feeding construct needs either `|` or `<<`, both unconditionally
# rejected.
#
# Exactly one shape is carved out below, generalized over the CLOSED SET
# of seed-bearing producers nw-auto/SKILL.md's route mandates root run
# with the seed on stdin (Run 7: `des resolve-charters` joined `des
# prepare-ordinary-request` here once it started building the PO envelope
# and needed the same seed -- the carve-out must generalize to every such
# producer, not be hand-extended one subcommand at a time; THE one place
# both this hook and the SKILL.md-coverage guard read is the dict below):
# a single `des <one of these subcommands> <ITS OWN bounded argv>` header
# line ending in a QUOTED heredoc redirect (`<<'NW_SEED'` or `<<"NW_SEED"`
# -- quoting is mandatory so the shell performs zero expansion inside the
# body, the same "opaque bytes" guarantee a pipe would give), followed by
# an arbitrary-content body, terminated by a line that is exactly the
# delimiter and nothing after it. A quoted heredoc body is never
# shell-interpreted, so it is the one construct that can carry a seed
# containing quotes, `|`, backticks or any other byte without escaping.
# Every other shape -- a subcommand outside this set, a flag from a
# DIFFERENT producer's vocabulary, an unquoted delimiter, unterminated
# body, trailing content after the terminator, any composition marker in
# the header -- still falls through to the generic block.
_VALUE_SEED_HEREDOC_DELIMITER = "NW_SEED"
_VALUE_SEED_HEREDOC_HEADER_SUFFIXES = (
    f" <<'{_VALUE_SEED_HEREDOC_DELIMITER}'",
    f' <<"{_VALUE_SEED_HEREDOC_DELIMITER}"',
)
# THE one place naming which `des` subcommands may take the seed heredoc,
# and each one's own closed flag vocabulary (never shared across
# subcommands -- prepare-ordinary-request's `--size` must never leak into
# resolve-charters' argv, and vice versa). `des <sub> --help`
# (src/des/cli/prepare_ordinary_request.py `_parser`,
# src/des/cli/resolve_charters.py `_build_parser`) is each vocabulary's
# own source. `tests/build/test_des_examples_are_executable.py` imports
# this SAME dict to assert nw-auto/SKILL.md's fenced heredoc examples
# name exactly this set, in both directions -- one drift class, one fix.
_VALUE_SEED_HEREDOC_ALLOWED_COMMANDS: dict[str, frozenset[str]] = {
    "prepare-ordinary-request": frozenset(
        {
            "--size",
            "--repo-root",
            "--architecture-authority",
            "--delivery-route",
            "--examine",
            "--independent-review",
            "--budget-token-limit",
            "--budget-wall-clock-minutes",
        }
    ),
    "resolve-charters": frozenset(
        {
            "--repo-root",
            "--delivery-id",
            "--examine",
        }
    ),
}


def _value_seed_heredoc_header_argv(header: str) -> list[str] | None:
    """`shlex`-tokenized argv of a matched heredoc header's pre-`<<` argv
    prefix, or `None` if the prefix carries any composition marker, fails
    to tokenize, is not `des <allowed-subcommand>`, or carries any flag
    token outside THAT subcommand's own closed vocabulary."""
    prefix = None
    for suffix in _VALUE_SEED_HEREDOC_HEADER_SUFFIXES:
        if header.endswith(suffix):
            prefix = header[: -len(suffix)]
            break
    if prefix is None:
        return None
    if any(marker in prefix for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return None
    try:
        argv = shlex.split(prefix)
    except ValueError:
        return None
    if len(argv) < 2 or argv[0] != "des":
        return None
    allowed_flags = _VALUE_SEED_HEREDOC_ALLOWED_COMMANDS.get(argv[1])
    if allowed_flags is None:
        return None
    flags = argv[2:]
    i = 0
    while i < len(flags):
        token = flags[i]
        flag_name = token.partition("=")[0]
        if flag_name not in allowed_flags:
            return None
        if "=" in token:
            # `--flag=value` is one self-contained token.
            i += 1
            continue
        # `--flag value` is two tokens -- a flag with no following value
        # token is malformed, not a value-less flag in this vocabulary.
        if i + 1 >= len(flags):
            return None
        i += 2
    return argv


def _is_value_seed_stdin_heredoc(command: str) -> bool:
    """True iff `command` is one hook-permitted seed-transport heredoc: a
    bounded `des <subcommand>` header, where `<subcommand>` is one of
    `_VALUE_SEED_HEREDOC_ALLOWED_COMMANDS`, ending in a quoted
    `<<'NW_SEED'`/`<<"NW_SEED"` redirect, an opaque body, and a terminator
    line that is exactly the delimiter with nothing after it. Fails closed
    (`False`) on anything else -- an unquoted delimiter, a missing/
    duplicated terminator, trailing content past it, or a header that does
    not tokenize into `des <allowed-subcommand>` plus THAT subcommand's own
    closed flag vocabulary.
    """
    if "\r" in command or "\n" not in command:
        return False
    header, _, rest = command.partition("\n")
    if _value_seed_heredoc_header_argv(header) is None:
        return False
    body_lines = rest.split("\n")
    try:
        terminator_index = body_lines.index(_VALUE_SEED_HEREDOC_DELIMITER)
    except ValueError:
        return False
    return terminator_index == len(body_lines) - 1


def _evaluate_auto_root_bash_command(command: object) -> dict[str, str] | None:
    """Pure Auto-root Bash allowlist decision.

    Restricts Auto-root's OWN Bash calls to either a single, literal `git
    status|diff|rev-parse|branch|worktree|add|commit` invocation, or a
    single, literal `des dispatch|validate-delivery-contract|
    charter-scaffold|prepare-ordinary-request|resolve-charters|code-fact`
    invocation
    (the direct-cutover spine has no hook controller between Auto-root and
    the dispatched role's own DES CLI call). Lexically rejects any
    shell-composition operator (see
    `_AUTO_ROOT_BASH_INJECTION_MARKERS`) BEFORE `shlex.split` runs -- a
    string like ``"git status; rm -rf /"`` tokenizes cleanly under shlex,
    so the composition check must happen on the raw string first. Returns
    `None` (allow) or a `{decision: block, reason: ...}` payload. A missing,
    empty, whitespace-only, or non-string command fails CLOSED (blocked),
    not allowed: once Auto-root is armed, there is no well-formed command
    to fall through to the allowlist below on. Arguments after the allowed
    `git`/`des` verb are literal argv, already protected from shell
    composition by the injection-marker check above -- never re-interpreted
    as shell.
    """
    if not isinstance(command, str) or not command.strip():
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash call carried no usable command. "
            "WHY: Auto-root Bash is restricted to a single, literal git or "
            "des call -- a missing, empty, or whitespace-only command "
            "cannot be that call. "
            "HOW: run one git or des subcommand per Bash call, or dispatch "
            "a role instead."
        )
    if _is_value_seed_stdin_heredoc(command):
        return None
    if any(marker in command for marker in _AUTO_ROOT_BASH_INJECTION_MARKERS):
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command carrying a shell-composition "
            "operator (&&, ||, ;, |, &, `, $(...), <, >, or a newline/CR) was "
            "blocked. "
            "WHY: Auto-root Bash is restricted to a single, literal git or "
            "des call -- composition operators can smuggle a second "
            "command past that allowlist. "
            "HOW: run one git or des subcommand per Bash call; drop the "
            "operator."
        )
    try:
        argv = shlex.split(command)
    except ValueError:
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command failed to tokenize. "
            "WHY: Auto-root Bash must be a single well-formed git or des "
            "call. "
            "HOW: fix the quoting, or dispatch a role to run it."
        )
    if not argv or argv[0] not in ("git", "des"):
        return _auto_root_bash_block(
            "WHAT: an Auto-root Bash command is not a `git` or `des` "
            "invocation. "
            "WHY: Auto-root Bash is restricted to git status/diff/"
            "rev-parse/branch/worktree/add/commit, or des dispatch/"
            "validate-delivery-contract/charter-scaffold/"
            "prepare-ordinary-request/resolve-charters/code-fact. "
            "HOW: dispatch a role for other work, or run the equivalent "
            "git/des subcommand."
        )
    subcommand = argv[1] if len(argv) > 1 else None
    if argv[0] == "git":
        if subcommand not in _AUTO_ROOT_BASH_ALLOWED_GIT_SUBCOMMANDS:
            return _auto_root_bash_block(
                f"WHAT: an Auto-root `git {subcommand}` call was blocked. "
                "WHY: Auto-root Bash only allows git status/diff/rev-parse/"
                "branch/worktree/add/commit. "
                "HOW: dispatch the appropriate nw-* role for any other git "
                "subcommand."
            )
        return None
    if subcommand not in _AUTO_ROOT_BASH_ALLOWED_DES_SUBCOMMANDS:
        return _auto_root_bash_block(
            f"WHAT: an Auto-root `des {subcommand}` call was blocked. "
            "WHY: Auto-root Bash only allows des dispatch/"
            "validate-delivery-contract/charter-scaffold/"
            "prepare-ordinary-request/resolve-charters/code-fact. "
            "HOW: dispatch the appropriate nw-* role for any other des "
            "subcommand."
        )
    return None


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


# Run 8 (Vera hit maxTurns:40 mid-work, zero terminal result -- the same
# silent-kill class as ATD in run 3): a subagent's OWN declared `maxTurns`
# is a hard boundary Claude Code enforces by simply stopping the agent --
# no terminal <ROLE>-RESULT, and root cannot tell that apart from "still
# working". A subagent must never be killed silently: once its own
# transcript shows its budget nearly exhausted, every further tool call is
# denied so its NEXT turn has no option left but the terminal text result
# (INDETERMINATE, with the reason, if the work genuinely is not done).
#
# Margin: `maxTurns - 2`, not `- 1` or `- 0` -- the agent needs the CURRENT
# turn free to actually emit the terminal result text, and one turn of
# slack for a hook round-trip; team lead's own spec ("allow up to N-3, deny
# at N-2") is the exact threshold this implements.
_SUBAGENT_BUDGET_MARGIN = 2


def _subagent_transcript_turn_count(transcript_path: str) -> int | None:
    """Tool-use count so far in a subagent's OWN transcript -- calibrated
    live against three real killed transcripts (run 8's nw-user-examiner,
    maxTurns 40; run 3's two nw-acceptance-designer dispatches, maxTurns
    12): counting `tool_use` content BLOCKS across every recorded
    assistant message reproduces the SDK's OWN self-reported `tool_uses`
    usage field EXACTLY in all three (40, 17, 18) -- raw assistant-entry
    count does not (it also counts pure thinking/text-only assistant
    messages that carry no tool call at all, and was found ~2x inflated
    against the real kill point in the same evidence). Blocks, not
    tool-use-bearing MESSAGES, so a future batched turn (several
    `tool_use` blocks in one assistant message) is still counted
    faithfully rather than undercounted by one. `None` on a missing,
    unreadable or non-UTF-8 transcript -- the caller must never guess a
    count it cannot observe.

    Residual, disclosed limitation: this reproduces the SDK's own
    `tool_uses` counter exactly, but that counter is not always identical
    to the declared `maxTurns` AT THE ACTUAL KILL POINT -- run 3's two
    ATD dispatches were cut off at `tool_uses` 17 and 18 against a
    declared `maxTurns: 12` (5-6 over), an older build's enforcement
    apparently allowing some slack this hook cannot see or control. This
    guard's margin (`_SUBAGENT_BUDGET_MARGIN`) denies well before either
    the declared budget or that observed slack in both real cases, but a
    third SDK behavior this evidence does not cover remains possible.
    """
    count = 0
    try:
        with open(transcript_path, encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("type") != "assistant":
                    continue
                message = entry.get("message")
                content = message.get("content") if isinstance(message, dict) else None
                if not isinstance(content, list):
                    continue
                count += sum(
                    1
                    for block in content
                    if isinstance(block, dict) and block.get("type") == "tool_use"
                )
    except (OSError, UnicodeDecodeError):
        return None
    return count


def _subagent_budget_exhaustion_block(
    role: str, *, max_turns: int, turn_count: int
) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            f"WHAT: {role}'s declared budget (maxTurns: {max_turns}) is "
            f"nearly exhausted -- {turn_count} assistant turns already "
            "observed in its own transcript. "
            "WHY: a subagent silently stopped at its hard maxTurns boundary "
            "mid-work returns NO terminal result at all -- root cannot "
            "distinguish that from a subagent still working, and the whole "
            "dispatch becomes unusable evidence. "
            f"HOW: emit your terminal {role.upper()}-RESULT now -- verdict "
            "INDETERMINATE with the exact reason it is unfinished if the "
            "work genuinely is not done -- instead of spending another tool "
            "call; this is the last turn with budget to do so."
        ),
    }


def _evaluate_subagent_budget_exhaustion(
    hook_input: dict[str, object],
) -> dict[str, str] | None:
    """Pure budget-exhaustion decision for a dispatched nw-* subagent's OWN
    tool call. `None` (allow) unless ALL of: this is a real nWave subagent
    (`root_activation_context.resolve_subagent_agent_type` -- live envelope
    field OR transcript meta-sidecar, see Run 9/10 correction), its own
    published spec declares a positive `maxTurns` (`resolve_declared_max_turns`
    -- `None` for a role that declares none is never gated here, matching
    Claude Code's own unlimited-turn default), and its OWN transcript
    already shows `maxTurns - _SUBAGENT_BUDGET_MARGIN` or more assistant
    turns. Applies to every tool call uniformly -- there is no "terminal"
    tool call to exempt; the terminal result is plain text, never a tool
    call, so this guard denying every tool call is exactly what forces it.

    Run 10 correction: turn-counting reads the subagent's OWN transcript
    (`resolve_subagent_own_transcript_path`), never the raw envelope field
    on faith -- a real crafter's `transcript_path` was verified to name the
    PARENT/root session log, not her own file; counting tool_use blocks
    there would count ROOT's activity, not hers."""
    agent_type = resolve_subagent_agent_type(hook_input)
    if agent_type is None:
        return None
    own_transcript_path = resolve_subagent_own_transcript_path(hook_input)
    if own_transcript_path is None:
        return None
    cwd = hook_input.get("cwd")
    repo_root = Path(cwd) if isinstance(cwd, str) and cwd else Path.cwd()
    max_turns = resolve_declared_max_turns(agent_type, repo_root=repo_root)
    if max_turns is None:
        return None
    turn_count = _subagent_transcript_turn_count(own_transcript_path)
    if turn_count is None:
        return None
    if turn_count < max_turns - _SUBAGENT_BUDGET_MARGIN:
        return None
    return _subagent_budget_exhaustion_block(
        agent_type, max_turns=max_turns, turn_count=turn_count
    )


# Run 8 (B): root Read four test files plus models.py, drafted a full test
# addition, THEN had its Edit denied for touching role-owned source -- the
# denial arrived after the wasted reads, not before (GDP-1 violated). Root
# never Reads implementation/test source at all: only the docs/config
# authority roots below, or a physical path outside the repo entirely (the
# arm's own installed config, never this repo's source). Everything else is
# denied -- `nw-auto`'s "Root verification discipline" names the one
# permitted deterministic spot-check (`des code-fact`) and the only other
# route (dispatch the owning role) for anything a code-fact query cannot
# answer.
_AUTO_ROOT_SOURCE_READ_TOOL_NAMES = frozenset({"Read", "Grep", "Glob"})
_AUTO_ROOT_ALLOWED_READ_PATH_ROOTS = ("docs", "templates/docs", ".nwave")
_AUTO_ROOT_ALLOWED_READ_PATH_PREFIXES = tuple(
    f"{root}/" for root in _AUTO_ROOT_ALLOWED_READ_PATH_ROOTS
)
_AUTO_ROOT_ALLOWED_TOP_LEVEL_FILES = frozenset({"CLAUDE.md", "AGENTS.md"})


def _is_auto_root_allowed_read_path(relative_posix: str) -> bool:
    """True iff a repo-relative POSIX path sits under a docs/config
    authority root: `docs` itself or anything under `docs/**` (which
    already covers `docs/delivery-contracts/**`; `templates/docs` is
    separate since that tree does not nest under `docs/`), `.nwave` itself
    or anything under `.nwave/**`, or a top-level `CLAUDE.md`/`AGENTS.md`/
    `README*`/`*.md`. Bare `relative_posix in _AUTO_ROOT_ALLOWED_READ_PATH_
    ROOTS` covers a `Grep`/`Glob` `path` naming the directory ITSELF with
    no trailing content (`"docs"`, not `"docs/x"`) -- `startswith` alone
    never matches that exact string. A "top-level" file has no `/` in its
    relative path -- a same-named file nested in a subdirectory (a
    package's own README, a vendored CLAUDE.md) is NOT this repo's own
    root-level authority file and is not exempted by name alone."""
    if relative_posix in _AUTO_ROOT_ALLOWED_READ_PATH_ROOTS:
        return True
    if relative_posix.startswith(_AUTO_ROOT_ALLOWED_READ_PATH_PREFIXES):
        return True
    if "/" in relative_posix:
        return False
    return (
        relative_posix in _AUTO_ROOT_ALLOWED_TOP_LEVEL_FILES
        or relative_posix.startswith("README")
        or relative_posix.endswith(".md")
    )


def _auto_root_source_read_block(tool_name: str, relative_posix: str) -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            f"WHAT: an Auto-root {tool_name} of {relative_posix!r} was "
            "blocked -- outside the docs/config authority roots root may "
            "read. "
            "WHY: root fact-checking implementation/test source duplicates "
            "work the architect/ATD/crafter already do and do again "
            "downstream (Run 5: 263s/185K tokens root spent re-reading "
            "files a role reads again); Run 8: root Read four test files "
            "plus models.py and drafted a test addition before its own Edit "
            "was denied for the same reason -- the wasted reads must never "
            "happen at all, not merely be caught one tool later. "
            "HOW: for a structural code fact, run the one bounded "
            "`des code-fact` call (`nw-auto`, 'Root verification "
            "discipline'); for anything needing real judgment about the "
            "source, dispatch the owning nw-* role instead of reading it "
            "yourself."
        ),
    }


def _evaluate_auto_root_source_read(
    tool_name: str, tool_input: dict[str, object], hook_input: dict[str, object]
) -> dict[str, str] | None:
    """Pure Auto-root Read/Grep/Glob allowlist decision. `None` (allow) for
    a path under a docs/config authority root, or a path resolving OUTSIDE
    the repo entirely (the arm's own installed config, never this repo's
    source). Denies everything else under the repo. `Grep`/`Glob` with no
    explicit `path` (their default, unscoped cwd search) is outside this
    guard's evidenced scope -- Run 8's own defect was `Read` of named
    files, never an unscoped Grep/Glob -- and is never denied here."""
    raw_path = (
        tool_input.get("file_path") if tool_name == "Read" else tool_input.get("path")
    )
    if not isinstance(raw_path, str) or not raw_path:
        return None
    cwd_raw = hook_input.get("cwd")
    repo_root = Path(cwd_raw) if isinstance(cwd_raw, str) and cwd_raw else Path.cwd()
    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    try:
        resolved = candidate.resolve()
        resolved_repo_root = repo_root.resolve()
    except OSError:
        return None
    if not resolved.is_relative_to(resolved_repo_root):
        return None
    relative_posix = resolved.relative_to(resolved_repo_root).as_posix()
    if _is_auto_root_allowed_read_path(relative_posix):
        return None
    return _auto_root_source_read_block(tool_name, relative_posix)


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
    unparsable command, matching `find_worktree_remove_target`'s contract.
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


# Lexical locator/anchor/header-line checks and the deterministic
# `DeliveryId` projection are shared with `des.cli.prepare_ordinary_request`
# (the producer for this gate's input) via `des.application.ordinary_request`, so the
# two sides of the same boundary cannot drift apart.


def _auto_root_crafter_thin_header_block() -> dict[str, str]:
    """Render the block payload for a malformed Auto-root crafter THIN header."""
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root crafter thin authority malformed -- the Agent "
            "prompt's first bytes are not exactly the two-line "
            "THIN-DELIVERY-CONTRACT / THIN-DELIVERY-CONTRACT-DIGEST header. "
            "WHY: the first bytes are the deterministic authority boundary "
            "-- no prose, fence, BOM, duplication, or reconstructed JSON may "
            "precede or follow it; validating this only downstream, inside "
            "the crafter itself, wastes an entire wave/service activation on "
            "a dispatch that was already doomed to AUTHORITY_REFUSED. "
            "HOW: forward ATD's exact two-line THIN-DELIVERY-CONTRACT / "
            "THIN-DELIVERY-CONTRACT-DIGEST block verbatim as the prompt's "
            "first bytes, with no reconstruction, hashing, or repair."
        ),
    }


def _evaluate_auto_root_crafter_thin_header(prompt: object) -> dict[str, str] | None:
    """Pure lexical Auto-root crafter THIN-header gate.

    Validates ONLY the shape of the prompt's first bytes -- never reads,
    hashes, opens, or schema-validates the referenced contract file. Returns
    `None` (allow -- fall through unchanged) when the prompt's first two
    lines are exactly a well-formed THIN-DELIVERY-CONTRACT /
    THIN-DELIVERY-CONTRACT-DIGEST pair, optionally followed by one blank
    line and unrelated context carrying no duplicate header. Otherwise
    returns the block payload.
    """
    if not isinstance(prompt, str):
        return _auto_root_crafter_thin_header_block()
    lines = prompt.split("\n")
    if len(lines) < 2:
        return _auto_root_crafter_thin_header_block()

    locator_line, digest_line = lines[0], lines[1]
    if not locator_line.startswith(_THIN_HEADER_LOCATOR_PREFIX):
        return _auto_root_crafter_thin_header_block()
    locator = locator_line[len(_THIN_HEADER_LOCATOR_PREFIX) :]
    if not is_lexical_repo_relative_json_locator(locator):
        return _auto_root_crafter_thin_header_block()

    if not digest_line.startswith(_THIN_HEADER_DIGEST_PREFIX):
        return _auto_root_crafter_thin_header_block()
    digest_hex = digest_line[len(_THIN_HEADER_DIGEST_PREFIX) :]
    if (
        len(digest_hex) != _THIN_HEADER_DIGEST_HEX_LEN
        or not set(digest_hex) <= _THIN_HEADER_DIGEST_HEX_ALPHABET
    ):
        return _auto_root_crafter_thin_header_block()

    remainder = lines[2:]
    if remainder:
        if remainder[0] != "":
            return _auto_root_crafter_thin_header_block()
        context = "\n".join(remainder[1:])
        if (
            _THIN_HEADER_LOCATOR_PREFIX.rstrip() in context
            or _THIN_HEADER_DIGEST_PREFIX.rstrip() in context
        ):
            return _auto_root_crafter_thin_header_block()

    return None


def _auto_root_po_envelope_block() -> dict[str, str]:
    """Render the block payload for a malformed/hand-authored Auto-root PO
    dispatch prompt."""
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root PO dispatch envelope malformed -- the Agent "
            "prompt is not exactly the four-line value-only "
            "DELIVERY-ID/NAMESPACE/ROOT/VALUE-SEED envelope, or it carries "
            "an ARCHITECTURE-COVERED anchor. "
            "WHY: `nw-product-owner` disqualifies itself as charter author "
            "the instant its own context carries an architecture-authority "
            "anchor (ADR-SSOT-002 Section 2 authority typing, Section 4c "
            "single-author route); root must never hand-compose this "
            "envelope -- a malformed or contaminated retry burns a full PO "
            "activation before the role's own refusal is even reached. "
            "HOW: run `des resolve-charters --repo-root <root> "
            "--delivery-id <id> --examine <true|false>` with the SAME "
            "VALUE-SEED bytes on stdin already piped to "
            "`des prepare-ordinary-request`, then paste its printed "
            "`AUTHOR` envelope verbatim as the prompt -- never author, "
            "reconstruct or augment it by hand."
        ),
    }


def _evaluate_auto_root_po_envelope(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root PO envelope gate: shape-only. `None` (allow) iff
    `prompt` is exactly the four-line value-only envelope
    `des.application.ordinary_request.build_po_envelope` emits, with no
    ARCHITECTURE-COVERED-shaped line anywhere; else the block payload."""
    if not isinstance(prompt, str) or not is_well_formed_po_envelope(prompt):
        return _auto_root_po_envelope_block()
    return None


def _auto_root_atd_body_block() -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root ATD dispatch body malformed. "
            "WHY: extra, missing, reordered or invalid facts make ATD infer "
            "or default upstream authority it must never guess. "
            "HOW: send exactly the architecture authority line, one blank "
            "line, then CONTRACT-LOCATOR, CONTRACT-SCHEMA, DELIVERY-ID, "
            "OUTCOME, ROOT, BASE-REVISION, DELIVERY-ROUTE, EXAMINE, "
            "INDEPENDENT-REVIEW, BUDGET-TOKEN-LIMIT, "
            "BUDGET-WALL-CLOCK-MINUTES, VALUE-SEED, each on its own line in "
            "that exact order, and nothing else; OR, to revise an "
            "already-produced contract on a crafter's contract/oracle "
            "citation, send exactly REVISE-CONTRACT then CITATION, each on "
            "its own line and nothing else."
        ),
    }


def _is_well_formed_contract_locator_for_revision(locator: str) -> bool:
    """True iff `locator` has the ONE shape `contract_locator_for` ever
    produces (`docs/delivery-contracts/auto-<16 lowercase hex>.json`) --
    lexical only, no filesystem I/O, no delivery-id/seed cross-check (a
    revision dispatch carries no value seed to recompute a hash against)."""
    if not is_lexical_repo_relative_json_locator(locator):
        return False
    if not locator.startswith(_CONTRACT_LOCATOR_DIR_PREFIX):
        return False
    stem = locator[len(_CONTRACT_LOCATOR_DIR_PREFIX) : -len(".json")]
    if not stem.startswith(DELIVERY_ID_PREFIX):
        return False
    hex_part = stem[len(DELIVERY_ID_PREFIX) :]
    return len(hex_part) == DELIVERY_ID_HEX_LEN and set(hex_part) <= _HEX_ALPHABET


def _is_well_formed_atd_revision_body(prompt: str) -> bool:
    """True iff `prompt` is exactly the two-line contract-revision shape:
    `REVISE-CONTRACT: <locator>` then `CITATION: <non-empty JSON string>`,
    nothing else."""
    lines = prompt.split("\n")
    if len(lines) != _ATD_REVISION_BODY_LINE_COUNT:
        return False
    locator_line, citation_line = lines
    if not locator_line.startswith(_ATD_REVISE_CONTRACT_LINE_PREFIX):
        return False
    locator = locator_line[len(_ATD_REVISE_CONTRACT_LINE_PREFIX) :]
    if not _is_well_formed_contract_locator_for_revision(locator):
        return False
    citation = _has_json_string_value(citation_line, _ATD_CITATION_LINE_PREFIX)
    return bool(citation) and bool(citation.strip())


def _evaluate_auto_root_atd_body(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root ATD full-body gate: exactly the architecture header,
    one blank line, then the twelve named non-empty facts (ADR-SSOT-002
    Section 4c) in this exact order -- and nothing else. Shape, enum and
    numeric-format validation only, no referenced-file I/O."""
    if not isinstance(prompt, str):
        return _auto_root_atd_body_block()
    if _is_well_formed_atd_revision_body(prompt):
        return None
    lines = prompt.split("\n")
    if len(lines) != ATD_BODY_LINE_COUNT:
        return _auto_root_atd_body_block()

    header_line, blank_line, *fact_lines = lines
    if not is_valid_arch_header_line(header_line):
        return _auto_root_atd_body_block()
    if blank_line != "":
        return _auto_root_atd_body_block()

    (
        contract_locator_line,
        contract_schema_line,
        delivery_id_line,
        outcome_line,
        root_line,
        base_revision_line,
        delivery_route_line,
        examine_line,
        independent_review_line,
        budget_token_limit_line,
        budget_wall_clock_minutes_line,
        value_seed_line,
    ) = fact_lines

    # Shape-only checks for every fact except CONTRACT-LOCATOR, DELIVERY-ID,
    # OUTCOME and VALUE-SEED, which are cross-validated below instead of
    # trusted at face value -- ATD must never infer/default the delivery
    # identity from an unverified pair of independently-typed strings.
    fact_checks = (
        _has_absolute_schema_path_value(
            contract_schema_line, _ATD_CONTRACT_SCHEMA_LINE_PREFIX
        ),
        _has_absolute_value(root_line, _ATD_ROOT_LINE_PREFIX),
        _has_schema_tagged_base_revision(
            base_revision_line, _ATD_BASE_REVISION_LINE_PREFIX
        ),
        _has_route(delivery_route_line, _ATD_DELIVERY_ROUTE_LINE_PREFIX),
        _has_bool_value(examine_line, _ATD_EXAMINE_LINE_PREFIX),
        _has_bool_value(independent_review_line, _ATD_INDEPENDENT_REVIEW_LINE_PREFIX),
        _has_positive_integer_value(
            budget_token_limit_line, _ATD_BUDGET_TOKEN_LIMIT_LINE_PREFIX
        ),
        _has_positive_integer_value(
            budget_wall_clock_minutes_line,
            _ATD_BUDGET_WALL_CLOCK_MINUTES_LINE_PREFIX,
        ),
    )
    if not all(fact_checks):
        return _auto_root_atd_body_block()

    # OUTCOME and VALUE-SEED are compact JSON string literals (produced by
    # `des prepare-ordinary-request` with `ensure_ascii=False`) so arbitrary
    # newlines/quotes/shell metacharacters in the value seed cannot break the
    # fixed 14-line shape. Both must decode to the SAME exact Unicode text --
    # a producer that let them diverge could smuggle an unobserved outcome
    # past ATD. DELIVERY-ID and CONTRACT-LOCATOR are then required to equal
    # the deterministic projection recomputed from that decoded text, never
    # merely lexically well-formed on their own.
    outcome_value = _has_json_string_value(outcome_line, _ATD_OUTCOME_LINE_PREFIX)
    value_seed_value = _has_json_string_value(
        value_seed_line, _ATD_VALUE_SEED_LINE_PREFIX
    )
    if (
        outcome_value is None
        or value_seed_value is None
        or outcome_value != value_seed_value
    ):
        return _auto_root_atd_body_block()

    recomputed_delivery_id = compute_delivery_id(value_seed_value)
    if delivery_id_line != f"{_ATD_DELIVERY_ID_LINE_PREFIX}{recomputed_delivery_id}":
        return _auto_root_atd_body_block()

    recomputed_locator = contract_locator_for(recomputed_delivery_id)
    if (
        contract_locator_line
        != f"{_ATD_CONTRACT_LOCATOR_LINE_PREFIX}{recomputed_locator}"
    ):
        return _auto_root_atd_body_block()

    return None


def _auto_root_architect_envelope_block() -> dict[str, str]:
    return {
        "decision": "block",
        "reason": (
            "WHAT: Auto-root architect envelope malformed. "
            "WHY: DESIGN must consume, never infer, the upstream route. "
            "HOW: send exactly AUTO-ARCHITECTURE-CONSULT, "
            "AUTO-ARCHITECTURE-ROOT, and AUTO-DELIVERY-ROUTE."
        ),
    }


def _has_value(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and bool(line[len(prefix) :].strip())


def _has_json_string_value(line: str, prefix: str) -> str | None:
    """Decode `line`'s value as a compact JSON string literal, or `None`.

    `des prepare-ordinary-request` emits OUTCOME/VALUE-SEED as
    `json.dumps(text, ensure_ascii=False)` so an arbitrary Unicode value
    seed (quotes, newlines, `$()`, globs) survives on one line without a new
    transport carrier. Rejects anything that is not itself a JSON string
    (e.g. a bare unquoted line, or a JSON number/object smuggled in).
    """
    if not line.startswith(prefix):
        return None
    try:
        decoded = json.loads(line[len(prefix) :])
    except json.JSONDecodeError:
        return None
    return decoded if isinstance(decoded, str) else None


def _has_absolute_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _has_route(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and line[len(prefix) :] in _DELIVERY_ROUTE_TOKENS


def _has_bool_value(line: str, prefix: str) -> bool:
    return line.startswith(prefix) and line[len(prefix) :] in ("true", "false")


def _has_positive_integer_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    return bool(value) and value.isdigit() and value[0] != "0"


def _has_schema_tagged_base_revision(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    for tag, hex_len in _ATD_BASE_REVISION_TAGS.items():
        if value.startswith(tag):
            hex_part = value[len(tag) :]
            return len(hex_part) == hex_len and set(hex_part) <= _HEX_ALPHABET
    return False


def _has_absolute_schema_path_value(line: str, prefix: str) -> bool:
    if not line.startswith(prefix):
        return False
    value = line[len(prefix) :]
    if not value.endswith(".json"):
        return False
    return PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()


def _evaluate_auto_root_architect_envelope(prompt: object) -> dict[str, str] | None:
    """Lexical Auto-root architect envelope gate: exactly three non-empty
    lines -- AUTO-ARCHITECTURE-CONSULT, AUTO-ARCHITECTURE-ROOT,
    AUTO-DELIVERY-ROUTE -- and nothing else. Shape and route vocabulary
    only, no referenced-file I/O."""
    if not isinstance(prompt, str):
        return _auto_root_architect_envelope_block()
    lines = prompt.split("\n")
    if len(lines) != 3:
        return _auto_root_architect_envelope_block()

    consult_line, root_line, route_line = lines
    if not _has_value(consult_line, _AUTO_ARCH_CONSULT_LINE_PREFIX):
        return _auto_root_architect_envelope_block()
    if not _has_absolute_value(root_line, _AUTO_ARCH_ROOT_LINE_PREFIX):
        return _auto_root_architect_envelope_block()
    if not _has_route(route_line, _AUTO_ARCH_DELIVERY_ROUTE_LINE_PREFIX):
        return _auto_root_architect_envelope_block()

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
        from des.adapters.driven.config.des_config import DESConfig

        config = DESConfig(
            cwd=cwd or Path.cwd(),
            global_config_path=Path.home() / ".nwave" / "global-config.json",
        )
        if not config.attribution_enabled:
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
    """The git-stash + worktree-remove Bash guard decisions (consolidated).

    Formerly two standalone PreToolUse/Bash hook registrations
    (`scripts/hooks/git_stash_guard.py`, `scripts/hooks/worktree_removal_guard.py`).
    The single decision authority is `des.adapters.drivers.hooks.bash_command_guards`
    (`evaluate_git_stash_command` / `evaluate_worktree_remove_command`); this
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

    repo = Path(str(hook_input.get("cwd") or Path.cwd()))
    worktree_decision = evaluate_worktree_remove_command(command, repo)
    if worktree_decision is not None:
        if worktree_decision.audit_event is not None:
            write_bash_guard_audit_event(
                worktree_guard_target_root(),
                worktree_decision.audit_event,
                {
                    **(worktree_decision.audit_data or {}),
                    "session_id": str(hook_input.get("session_id", "")),
                },
            )
        if not worktree_decision.allow:
            return {"decision": "block", "reason": worktree_decision.reason or ""}
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
            # Run 9/10 correction: `not agent_id and not agent_type` alone
            # misreads a real subagent's own call as root's whenever the
            # live envelope carries neither field (proven true for every
            # ordinary PreToolUse call in run 9 -- see
            # `root_activation_context.hook_input_has_agent_identity`). The
            # shared resolver adds the transcript meta-sidecar as a second
            # axis before concluding "no identity at all -> root".
            is_root_invocation = not hook_input_has_agent_identity(hook_input)
            transcript_path = (
                extract_transcript_path(hook_input) if is_root_invocation else None
            )
            root_mode_state = RootModeState.UNSELECTED
            if transcript_path:
                root_mode_state = resolve_root_mode_state(transcript_path)

            # Run 8: a dispatched nw-* subagent's own declared maxTurns
            # budget nearly exhausted -- deny every further tool call so its
            # terminal result is forced out as text, never silently killed.
            # Runs before every other gate below: no other check should get
            # a chance to allow one more wasted tool call past this point.
            budget_block = _evaluate_subagent_budget_exhaustion(hook_input)
            if budget_block is not None:
                print(json.dumps(budget_block))
                exit_code = 2
                return exit_code

            # Close the state gap between selecting Auto M/L and engaging
            # nw-auto. The selection marker is ephemeral transcript evidence;
            # no controller, receipt, or file is introduced. Established
            # deliver sessions retain their existing route.
            if (
                is_root_invocation
                and tool_name in _ROOT_MODE_HANDOFF_TOOL_NAMES
                and not des_task_signal.DES_DELIVER_SESSION_FILE.exists()
            ):
                handoff_reason = root_mode_handoff_block_reason(root_mode_state)
                if handoff_reason is not None:
                    print(json.dumps({"decision": "block", "reason": handoff_reason}))
                    exit_code = 2
                    return exit_code

            # K4 architecture gap: Auto-root lockdown. Runs BEFORE the
            # existing mode-select observation gate and commit-attribution
            # mutation below (both scoped to "Bash"), so a locked-down call
            # never reaches either -- an armed but disallowed call is a
            # terminal block, not a fall-through to the general path.
            if (
                tool_name in _AUTO_ROOT_TASK_TOOL_LOCKDOWN_NAMES
                and root_mode_state is RootModeState.AUTO_ENGAGED
                and is_root_invocation
            ):
                if tool_name in _AUTO_ROOT_BLOCKED_TASK_TOOL_NAMES:
                    print(json.dumps(_auto_root_task_tool_block(tool_name)))
                    exit_code = 2
                    return exit_code
                if tool_name == "Bash":
                    auto_root_bash_block = _evaluate_auto_root_bash_command(
                        tool_input.get("command")
                    )
                    if auto_root_bash_block is not None:
                        print(json.dumps(auto_root_bash_block))
                        exit_code = 2
                        return exit_code

            # Run 8 (B): Auto-root Read/Grep/Glob of implementation/test
            # source is denied before the read happens, not caught later at
            # an Edit denial that arrives after the reads already ran.
            if (
                tool_name in _AUTO_ROOT_SOURCE_READ_TOOL_NAMES
                and root_mode_state is RootModeState.AUTO_ENGAGED
                and is_root_invocation
            ):
                source_read_block = _evaluate_auto_root_source_read(
                    tool_name, tool_input, hook_input
                )
                if source_read_block is not None:
                    print(json.dumps(source_read_block))
                    exit_code = 2
                    return exit_code

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

            if hook_input.get("tool_name") == "SendMessage":
                if root_mode_state is RootModeState.AUTO_ENGAGED:
                    print(
                        json.dumps(
                            {
                                "decision": "block",
                                "reason": (
                                    "Auto roles are single-pass: do not "
                                    "SendMessage, resume, retry, or correct a "
                                    "role within the same Auto run."
                                ),
                            }
                        )
                    )
                    exit_code = 2
                    return exit_code

            if hook_input.get("tool_name") == "Agent":
                if root_mode_state is RootModeState.AUTO_ENGAGED:
                    role = tool_input.get("subagent_type")
                    if not isinstance(role, str) or not role.startswith("nw-"):
                        print(
                            json.dumps(
                                {
                                    "decision": "block",
                                    "reason": (
                                        f"Auto-root Agent dispatch to "
                                        f"'{role}' was blocked. "
                                        "WHY: Auto-root may only dispatch "
                                        "nWave (nw-*) roles -- a non-nWave "
                                        "subagent_type escapes Auto's own "
                                        "role authority. "
                                        "HOW: dispatch an nw-* role instead "
                                        f"of '{role}'."
                                    ),
                                }
                            )
                        )
                        exit_code = 2
                        return exit_code
                    if role in _AUTO_ROOT_CRAFTER_ROLES and is_root_invocation:
                        crafter_thin_block = _evaluate_auto_root_crafter_thin_header(
                            tool_input.get("prompt")
                        )
                        if crafter_thin_block is not None:
                            print(json.dumps(crafter_thin_block))
                            exit_code = 2
                            return exit_code
                    if role == _ARCHITECT_ROLE_NAME and is_root_invocation:
                        architect_envelope_block = (
                            _evaluate_auto_root_architect_envelope(
                                tool_input.get("prompt")
                            )
                        )
                        if architect_envelope_block is not None:
                            print(json.dumps(architect_envelope_block))
                            exit_code = 2
                            return exit_code
                    if role == _ATD_ROLE_NAME and is_root_invocation:
                        design_consult_block = _evaluate_auto_root_atd_body(
                            tool_input.get("prompt")
                        )
                        if design_consult_block is not None:
                            print(json.dumps(design_consult_block))
                            exit_code = 2
                            return exit_code
                    if role in _AUTO_ROOT_PO_ENVELOPE_ROLES and is_root_invocation:
                        po_envelope_block = _evaluate_auto_root_po_envelope(
                            tool_input.get("prompt")
                        )
                        if po_envelope_block is not None:
                            print(json.dumps(po_envelope_block))
                            exit_code = 2
                            return exit_code

            if hook_input.get("tool_name") == "Bash":
                # The git-stash / worktree-remove safety decision already ran
                # once, pre-activation, in `hook_router.main()` (before
                # `apply_gate`) -- see `evaluate_bash_safety_guards`. Do not
                # re-run it here; that would be a duplicate second evaluation
                # of the same command on the active path.
                if (
                    is_root_invocation
                    and not des_task_signal.DES_DELIVER_SESSION_FILE.exists()
                ):
                    if root_mode_state is RootModeState.UNSELECTED:
                        print(
                            json.dumps(
                                {
                                    "decision": "block",
                                    "reason": (
                                        "Invoke nw-mode-select before the "
                                        "first Bash/Write/Edit."
                                    ),
                                }
                            )
                        )
                        exit_code = 2
                        return exit_code

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

            # The direct-cutover spine has no marker, slice-order, readiness,
            # review-ledger, or feature-end hook controller.  The explicit
            # Auto envelopes above are the only dispatch-shape checks at this
            # boundary; the validated DeliveryContract is consumed by the
            # dispatched role itself.  Preserve the existing root context
            # projection without re-deriving workflow state.
            prompt = tool_input.get("prompt", "")
            root_context = build_root_mode_select_context(
                prompt=prompt,
                subagent_type=tool_input.get("subagent_type"),
            )
            if root_context:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "PreToolUse",
                                "permissionDecision": "allow",
                                "additionalContext": root_context,
                            }
                        }
                    )
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
            hook_id=hook_id,
            handler="pre_tool_use",
            exit_code=exit_code,
            decision=decision_str,
            duration_ms=duration_ms,
            task_correlation_id=task_correlation_id,
        )
