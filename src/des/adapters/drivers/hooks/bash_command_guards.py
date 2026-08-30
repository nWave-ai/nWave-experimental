"""Shared Bash PreToolUse decision authority for guarded git operations.

Single algorithm for the existing decisions formerly duplicated across the
standalone `scripts/hooks/git_stash_guard.py` and
`scripts/hooks/worktree_removal_guard.py` PreToolUse/Bash hook
registrations (fix-execution-log-bash-guard-consolidation follow-on,
Ale-authorised). Both standalone scripts and the universal `src/des`
PreToolUse/Bash handler call the SAME functions here, so there is exactly
one place either decision is made.

Fast-path contract: each evaluator returns `None` immediately when its git
shape is absent. Worktree creation additionally measures the destination
through the residence admission port before any WIP can exist there.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.domain.worktree_anti_rot_triage import WorktreeAntiRotReceipt


@dataclass(frozen=True)
class BashGuardDecision:
    """The outcome of one Bash guard evaluation.

    `allow=False` carries the human-readable block reason. An allow that
    happened via an audited override carries `audit_event`/`audit_data`;
    the caller is responsible for actually writing the audit record (kept
    outside this pure decision function so it stays synchronously testable).
    """

    allow: bool
    reason: str | None = None
    audit_event: str | None = None
    audit_data: dict[str, object] | None = None


_AUDIT_LOG_DIR_RELPATH = Path(".nwave") / "des" / "logs"


def _audit_log_path(target_root: Path) -> Path:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return target_root / _AUDIT_LOG_DIR_RELPATH / f"audit-{today}.log"


def write_bash_guard_audit_event(
    target_root: Path, event: str, data: dict[str, object]
) -> None:
    """Append one audit event to today's JSONL audit log under `target_root`."""
    log_path = _audit_log_path(target_root)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "event": event,
        "ts": datetime.now(timezone.utc).isoformat(),
        **data,
    }
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


# --------------------------------------------------------------------------
# git stash
# --------------------------------------------------------------------------

_GIT_STASH_ALLOW_ENV = "NWAVE_GIT_STASH_ALLOW"
_GIT_STASH_GUARD_TARGET_ROOT_ENV = "NWAVE_GIT_STASH_GUARD_TARGET_ROOT"
_GIT_STASH_RE = re.compile(r"^\s*git\s+stash\b")
_STASH_READ_ONLY_SUBCOMMANDS = frozenset({"list", "show"})
_STASH_HELP_FLAGS = frozenset({"--help", "-h"})
_FALSY_ENV_VALUES = frozenset({"0", "false", "no", "off"})

_STASH_BLOCK_REASON = (
    "git stash is forbidden per STANDING (10 cumulative violations); "
    "use `des worktree-admit --repo <root> --lane <name>` for clean-tree "
    "isolation instead. "
    "To bypass deliberately, set NWAVE_GIT_STASH_ALLOW=1 "
    "(audited GitStashBypassUsed event)."
)

STASH_BYPASS_EVENT = "GitStashBypassUsed"


def is_git_stash_command(command: str) -> bool:
    """True iff `command` begins with `git stash` (word-boundary match)."""
    return _GIT_STASH_RE.match(command) is not None


def _first_subcommand_after_stash(tokens: list[str]) -> str | None:
    seen_stash = False
    for token in tokens:
        if not seen_stash:
            if token == "stash":
                seen_stash = True
            continue
        if token.startswith("-"):
            continue
        return token
    return None


def is_mutating_git_stash_command(command: str) -> bool:
    """True iff a `git stash` command mutates state (block candidate).

    Read-only forms: `list`, `show` (any flags), and any invocation carrying
    `--help`/`-h`. Everything else -- including bare `git stash` -- mutates.
    """
    tokens = command.split()
    if any(token in _STASH_HELP_FLAGS for token in tokens):
        return False
    subcommand = _first_subcommand_after_stash(tokens)
    return subcommand not in _STASH_READ_ONLY_SUBCOMMANDS


def git_stash_allow_env_active() -> bool:
    """True when NWAVE_GIT_STASH_ALLOW carries a truthy value."""
    raw = os.environ.get(_GIT_STASH_ALLOW_ENV, "")
    if not raw:
        return False
    return raw.strip().lower() not in _FALSY_ENV_VALUES


def git_stash_guard_target_root() -> Path:
    override = os.environ.get(_GIT_STASH_GUARD_TARGET_ROOT_ENV, "")
    return Path(override) if override else Path.cwd()


def evaluate_git_stash_command(command: str) -> BashGuardDecision | None:
    """Decide a Bash command against the git-stash guard's rule.

    Returns `None` on the fast path (not a `git stash` invocation at all)
    -- no further work is owed. Returns an allow decision for read-only
    forms and for a validly-overridden mutating form (carrying the audit
    event the caller must write), and a block decision otherwise.
    """
    if not is_git_stash_command(command):
        return None
    if not is_mutating_git_stash_command(command):
        return BashGuardDecision(allow=True)
    if git_stash_allow_env_active():
        return BashGuardDecision(
            allow=True,
            audit_event=STASH_BYPASS_EVENT,
            audit_data={"command": command},
        )
    return BashGuardDecision(allow=False, reason=_STASH_BLOCK_REASON)


# --------------------------------------------------------------------------
# git worktree remove
# --------------------------------------------------------------------------

_WORKTREE_REASON_ENV = "NWAVE_WORKTREE_REMOVE_REASON"
_WORKTREE_MIN_REASON_LENGTH = 15
_WORKTREE_TARGET_BRANCH_ENV = "NWAVE_WORKTREE_GUARD_TARGET_BRANCH"
_WORKTREE_GUARD_TARGET_ROOT_ENV = "NWAVE_WORKTREE_GUARD_TARGET_ROOT"
_WORKTREE_SEPARATORS = frozenset({"&&", "||", ";", "|", "&"})

WORKTREE_BYPASS_EVENT = "WorktreeRemovalBypassUsed"


def _split_subcommands(command: str) -> list[list[str]] | None:
    # `shlex.split` runs `whitespace_split=True`, which glues any
    # non-whitespace run into one token -- a separator attached to a
    # redirection with no intervening space (`2>/dev/null;`) never becomes
    # its own token and the argv stays rooted at the command before it.
    # `punctuation_chars` restores shell-accurate tokenization: `;`/`&&`/
    # `||`/`|`/`&` (plus `()<>`) always end a token even mid-run, multi-char
    # operators (`&&`, `||`) still group into one token, and a quoted
    # separator stays literal data (posix quote handling takes precedence).
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return None
    sub_commands: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token in _WORKTREE_SEPARATORS:
            if current:
                sub_commands.append(current)
                current = []
        else:
            current.append(token)
    if current:
        sub_commands.append(current)
    return sub_commands


# --------------------------------------------------------------------------
# git worktree add
# --------------------------------------------------------------------------

_WORKTREE_ADD_LOOKS_PRESENT = re.compile(r"\bgit\b.*\bworktree\s+add\b")
_WORKTREE_ADMIT_HOW = (
    "HOW: create the lane through `des worktree-admit --repo <root> --lane "
    "<name>` so nWave chooses and proves its durable residence."
)
_WORKTREE_DYNAMIC_SUBCOMMAND_REASON = (
    "WHAT: a `git worktree` invocation with a variable- or command-substitution-"
    "built subcommand was blocked. "
    "WHY: nWave cannot prove a dynamically constructed subcommand does not "
    f"evaluate to `add`. {_WORKTREE_ADMIT_HOW}"
)


def _worktree_add_positions(argv: list[str]) -> tuple[int, ...]:
    return tuple(
        index
        for index in range(len(argv) - 1)
        if argv[index] == "worktree" and argv[index + 1] == "add"
    )


def _looks_dynamically_constructed(token: str) -> bool:
    """True iff `token` contains a variable expansion or command-substitution
    shard anywhere, not just at its start.

    `shlex(punctuation_chars=True)` splits `$(...)`/`` `...` `` into several
    tokens (`$`, `(`, `echo`, `add`, `)`), so a literal-string comparison
    against `"add"` never sees the unquoted form; a quoted or bare-variable
    form (`"$(echo add)"`, `$SUBCMD`) instead survives as one token that is
    still not the literal string `"add"`. A literal prefix concatenated with
    a variable suffix (`ad$SUFFIX`) survives as one token too, and does not
    start with `$` -- checking only the token's start would let it through
    even though the shell can still evaluate it to `add`. Both shapes
    evaluate at the real shell before git ever runs, so their subcommand
    cannot be classified -- it must refuse, not be silently treated as "not
    `worktree add`".
    """
    return "$" in token or "`" in token


def _dynamic_worktree_at(argv: list[str], index: int) -> int | None:
    if index >= len(argv) - 1 or argv[index] != "worktree":
        return None
    if _looks_dynamically_constructed(argv[index + 1]):
        return index
    return None


def _worktree_dynamic_subcommand_index(argv: list[str]) -> int | None:
    """Refuse a `git` sub-command carrying a literal `worktree` token
    immediately followed by a token carrying a shell-expansion shard.

    A linear scan over every adjacent index pair -- no git option grammar,
    no arity, no global-flag table, so no flag chain can walk the rule past
    it (D7a-R). `worktree` appearing elsewhere in argv (e.g. `git log --
    worktree $BRANCH`) is pathspec/argument data belonging to a real
    subcommand; the rule is deliberately text-only and costs exactly that
    class of false positive (EF-9a(c)), never silently narrowed to avoid it.
    """
    for index in range(len(argv) - 1):
        found = _dynamic_worktree_at(argv, index)
        if found is not None:
            return found
    return None


def _worktree_add_shape_refusal(argv: list[str]) -> str | None:
    positions = _worktree_add_positions(argv)
    if not positions:
        return None
    if len(positions) != 1 or positions[0] != 1 or len(argv) not in {4, 5}:
        return (
            "WHAT: a non-canonical `git worktree add` invocation was blocked. "
            "WHY: nWave only classifies the exact shape `git worktree add "
            "<absolute-destination> [<commit-ish>]`; prefixes, options and "
            "other arities cannot prove which residence receives WIP. "
            f"{_WORKTREE_ADMIT_HOW}"
        )
    trailing = argv[3:]
    if any(token.startswith("-") for token in trailing):
        return (
            "WHAT: an option-bearing `git worktree add` invocation was blocked. "
            "WHY: option interpretation is deliberately outside the admission "
            f"guard's exact shape. {_WORKTREE_ADMIT_HOW}"
        )
    if not Path(argv[3]).is_absolute():
        return (
            "WHAT: a relative `git worktree add` destination was blocked. "
            "WHY: a relative path cannot be classified without reproducing shell "
            f"state. {_WORKTREE_ADMIT_HOW}"
        )
    if _looks_dynamically_constructed(argv[3]):
        return (
            "WHAT: a `git worktree add` destination carrying a shell-expansion "
            "shard was blocked. "
            "WHY: nWave classifies only the literal destination token; a "
            "durable-looking absolute prefix with an expanding suffix redirects "
            "to a path git receives only after the real shell expands it, so no "
            f"durability verdict may be computed from it. {_WORKTREE_ADMIT_HOW}"
        )
    return ""


def evaluate_worktree_add_command(command: str, repo: Path) -> BashGuardDecision | None:
    """Admit only the exact argv shape whose destination measures durable."""

    sub_commands = _split_subcommands(command)
    if sub_commands is None:
        if _WORKTREE_ADD_LOOKS_PRESENT.search(command):
            return BashGuardDecision(
                allow=False,
                reason=(
                    "WHAT: an unparsable `git worktree add` invocation was blocked. "
                    "WHY: its destination cannot be measured safely. "
                    f"{_WORKTREE_ADMIT_HOW}"
                ),
            )
        return None

    matched = False
    for argv in sub_commands:
        if not argv or Path(argv[0]).name != "git":
            continue
        if _worktree_dynamic_subcommand_index(argv) is not None:
            return BashGuardDecision(
                allow=False, reason=_WORKTREE_DYNAMIC_SUBCOMMAND_REASON
            )
        if not _worktree_add_positions(argv):
            continue
        matched = True
        shape_refusal = _worktree_add_shape_refusal(argv)
        if shape_refusal:
            return BashGuardDecision(allow=False, reason=shape_refusal)
        from des.adapters.driven.platform_residence_durability_adapter import (
            PlatformResidenceDurabilityAdapter,
        )
        from des.domain.worktree_residence import ResidenceAdmission, ResidenceRefusal

        result = ResidenceAdmission(PlatformResidenceDurabilityAdapter(repo)).admit(
            Path(argv[3])
        )
        if isinstance(result, ResidenceRefusal):
            return BashGuardDecision(
                allow=False,
                reason=(
                    f"WHAT: {result.what}. WHY: {result.why}. {_WORKTREE_ADMIT_HOW}"
                ),
            )
    return BashGuardDecision(allow=True) if matched else None


def _worktree_remove_target(sub_command: list[str]) -> str | None:
    if len(sub_command) < 3:
        return None
    if (
        sub_command[0] != "git"
        or sub_command[1] != "worktree"
        or sub_command[2] != "remove"
    ):
        return None
    for token in sub_command[3:]:
        if not token.startswith("-"):
            return token
    return None


def find_worktree_remove_target(command: str) -> str | None:
    """Return the target path of the FIRST `git worktree remove <path>`
    sub-command in `command`, or `None` if there is none (or the command is
    unparsable -- fails open, no probes run)."""
    sub_commands = _split_subcommands(command)
    if sub_commands is None:
        return None
    for sub in sub_commands:
        target = _worktree_remove_target(sub)
        if target is not None:
            return target
    return None


def worktree_remove_reason_is_valid(raw: str) -> bool:
    return len(raw.strip()) >= _WORKTREE_MIN_REASON_LENGTH


def worktree_guard_target_root() -> Path:
    override = os.environ.get(_WORKTREE_GUARD_TARGET_ROOT_ENV, "")
    return Path(override) if override else Path.cwd()


def resolve_worktree_target_branch(repo: Path) -> str | None:
    override = os.environ.get(_WORKTREE_TARGET_BRANCH_ENV, "").strip()
    if override:
        return override
    from des.application.worktree_triage_collector import resolve_target_branch

    return resolve_target_branch(repo)


def format_worktree_block_reason(receipt: WorktreeAntiRotReceipt, target: str) -> str:
    lines = [
        f"⛔ WORKTREE REMOVAL REFUSED — triage state {receipt.state.value} for "
        f"{target!r} (CLEAN is required to remove).",
        "",
    ]
    for finding in receipt.evidence:
        lines.append(f"- WHAT: {finding.what}")
        lines.append(f"  WHY:  {finding.why}")
    if receipt.actions:
        lines.append("")
        lines.append(
            f"Recommended actions (human picks ONE): {', '.join(receipt.actions)}"
        )
    lines.append("")
    lines.append(f"HOW: {receipt.how}")
    lines.append(
        "NOTE: evidence categories not yet mechanically available: "
        f"{', '.join(receipt.unavailable_evidence)}."
    )
    return "\n".join(lines)


def format_worktree_predicate_failure_reason(exc: Exception, target: str) -> str:
    return (
        f"⛔ WORKTREE REMOVAL REFUSED — the triage predicate itself could "
        f"not run ({type(exc).__name__}: {exc}) for {target!r}.\n\n"
        "WHY: a guard that cannot see and lets you through is worse than "
        "no guard -- an internal failure here degrades LOUD (refuse), "
        "never silently allow.\n\n"
        "HOW: fix the `des` install (this hook imports `des.adapters`/"
        "`des.domain` lazily and this is the failure boundary), or -- "
        "ONLY after a HUMAN has confirmed removal is safe -- set "
        f'{_WORKTREE_REASON_ENV}="<why a human confirmed this is safe>" '
        "(audited) and re-run."
    )


def evaluate_worktree_remove_command(
    command: str, repo: Path
) -> BashGuardDecision | None:
    """Decide a Bash command against the worktree-removal guard's rule.

    Returns `None` on the fast path (not a `git worktree remove`
    invocation) -- no triage predicate call, no filesystem work. A
    predicate failure is converted into a loud block decision, never
    raised past this function (GDP-6: refuse loud, never silent-allow).
    """
    target = find_worktree_remove_target(command)
    if target is None:
        return None

    target_path = Path(target)
    if not target_path.is_absolute():
        target_path = repo / target_path

    raw_reason = os.environ.get(_WORKTREE_REASON_ENV, "")
    if raw_reason and worktree_remove_reason_is_valid(raw_reason):
        return BashGuardDecision(
            allow=True,
            audit_event=WORKTREE_BYPASS_EVENT,
            audit_data={"command": command, "reason": raw_reason.strip()},
        )

    try:
        from des.adapters.driven.marker_file_owner_lease_adapter import (
            MarkerFileOwnerLeaseAdapter,
        )
        from des.application.worktree_triage_collector import (
            collect_worktree_triage_receipt,
        )
        from des.domain.worktree_anti_rot_triage import TriageState
        from des.domain.worktree_residence import (
            LaneIdentity,
            LeaseEvidence,
            lease_from_receipt,
        )

        receipt = collect_worktree_triage_receipt(
            repo=repo,
            target_path=target_path,
            target_branch=resolve_worktree_target_branch(repo),
        )
        owner = MarkerFileOwnerLeaseAdapter().observe(
            target_path, LaneIdentity.observe(target_path)
        )
        lease = lease_from_receipt(receipt, owner)
    except Exception as exc:
        return BashGuardDecision(
            allow=False,
            reason=format_worktree_predicate_failure_reason(exc, str(target_path)),
        )

    if receipt.state is not TriageState.CLEAN:
        return BashGuardDecision(
            allow=False,
            reason=format_worktree_block_reason(receipt, str(target_path)),
        )

    if lease is not LeaseEvidence.FREE:
        return BashGuardDecision(
            allow=False,
            reason=(
                f"⛔ WORKTREE REMOVAL REFUSED — owner lease is {lease.value} "
                f"for {str(target_path)!r}.\n\n"
                "WHY: removal requires a positive RELEASED assertion plus "
                "known-empty process and lock signals; absence or unreadability "
                "never means free.\n\n"
                "HOW: after terminal integration, run `des worktree-release "
                "--repo <root> --worktree <path>`, then re-run the cleanup "
                "check."
            ),
        )

    return BashGuardDecision(allow=True)
