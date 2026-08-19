"""Classify one contract's linked verification command RIGHT AT THE WRITE
that produces its oracle -- the pure decision half of the PostToolUse
oracle-write hook (`des.adapters.drivers.hooks.post_write_handler`).

Root's own debrief on K4 Run 13: "have ATD actually execute the oracle...
before CONTRACT_READY." `des dispatch`'s BASE red-reason probe
(`des.cli._oracle_red_reason_refusal`) already proves this once, between
`CONTRACT_READY` and the first crafter dispatch -- but by then ATD has
already finished and returned, so a defect it could have fixed in the SAME
turn costs a full REVISE round-trip instead. This module reclassifies
comparable evidence (the same `verification-scope` command, the same
route) at the moment ATD's own `Write`/`Edit` on the oracle file completes,
so the PostToolUse hook can hand ATD a finding immediately, in the SAME
turn, before it ever emits `CONTRACT_READY`.

Delegates the actual classification to `des.domain.oracle_execution_
classifier.classify_probe_output` -- ONE algorithm, not two: an earlier
revision of this module reimplemented its own coarser exit-code-plus-
declared-symbol match independently, written while a concurrent lane was
retiring the Python-only structure checker `oracle_execution_classifier`
used to depend on at the time. Now that the language-agnostic rewrite has
landed (declared-symbol match -> RED; a small, extensible build/compile
marker table -> UNACCEPTABLE_BUILD; otherwise INDETERMINATE), there is no
reason left for a second, drifting decision function -- `declared_symbol_
candidates` and `reason_line` are reused the same way. `UNACCEPTABLE_
BUILD` and `INDETERMINATE` both map to `RED_WRONG_REASON` here: this
hook's own five-label vocabulary is coarser than the classifier's four-
outcome one by design (it only needs "does ATD need to look at this now,"
not which of the two non-right-reason shapes applies).

`des dispatch`'s own BASE probe remains the terminal, authoritative check;
this is strictly earlier, cheaper feedback on comparable evidence, never a
second authority.

This is feedback, never a gate: a PostToolUse hook cannot un-write a file,
and this module never blocks -- its only output is a classification for the
hook to relay as `additionalContext`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.domain.oracle_execution_classifier import (
    GREEN,
    RED,
    classify_probe_output,
    declared_symbol_candidates,
    reason_line,
)
from des.domain.oracle_link_resolver import command_argv, is_oracle_linked


if TYPE_CHECKING:
    from pathlib import Path


#: The classification labels this module hands the hook.
RED_RIGHT_REASON = "RED-right-reason"
RED_WRONG_REASON = "RED-wrong-reason"
GREEN_FOR_RED_TO_GREEN = "GREEN-for-RED_TO_GREEN"
GREEN_AS_EXPECTED = "GREEN-as-expected"
UNEXPECTEDLY_RED_FOR_GREEN_TO_GREEN = "unexpectedly-RED-for-GREEN_TO_GREEN"


@dataclass(frozen=True, slots=True)
class OracleWriteClassification:
    label: str
    reason: str
    command_text: str


def linked_verification_command(contract: dict, oracle_locator: str) -> dict | None:
    """The FIRST `verification-scope.commands` entry that cites
    `oracle_locator` (either dotted-module or repository-relative spelling)
    -- `None` when no command is linked (nothing for this hook to run)."""
    for command in contract.get("verification-scope", {}).get("commands", []):
        if is_oracle_linked(command, oracle_locator):
            return command
    return None


def classify_write(
    *,
    contract: dict,
    command: dict,
    repo_root: Path,
    returncode: int,
    output: str,
) -> OracleWriteClassification:
    """Classify one already-executed probe's `(returncode, output)` against
    `contract`'s own `delivery-route` -- pure, no subprocess here (the
    caller runs the bounded probe; see `post_write_handler`)."""
    del (
        repo_root
    )  # unused by classify_probe_output; kept for call-site symmetry with command_argv
    route = contract.get("delivery-route")
    declared_symbols = declared_symbol_candidates(contract)
    outcome = classify_probe_output(
        returncode=returncode, output=output, declared_symbols=declared_symbols
    )
    command_text = " ".join(str(a) for a in command.get("arguments", []))
    reason = reason_line(output)

    if outcome == GREEN:
        if route == "RED_TO_GREEN":
            return OracleWriteClassification(
                GREEN_FOR_RED_TO_GREEN, reason, command_text
            )
        return OracleWriteClassification(GREEN_AS_EXPECTED, reason, command_text)
    if outcome != RED:
        # UNACCEPTABLE_BUILD or INDETERMINATE: this hook's own vocabulary
        # is coarser than the classifier's -- both mean "not a confirmed
        # right-reason RED," worth ATD's attention regardless of route.
        return OracleWriteClassification(RED_WRONG_REASON, reason, command_text)
    if route == "RED_TO_GREEN":
        return OracleWriteClassification(RED_RIGHT_REASON, reason, command_text)
    return OracleWriteClassification(
        UNEXPECTEDLY_RED_FOR_GREEN_TO_GREEN, reason, command_text
    )


__all__ = [
    "GREEN_AS_EXPECTED",
    "GREEN_FOR_RED_TO_GREEN",
    "RED_RIGHT_REASON",
    "RED_WRONG_REASON",
    "UNEXPECTEDLY_RED_FOR_GREEN_TO_GREEN",
    "OracleWriteClassification",
    "classify_write",
    "command_argv",
    "declared_symbol_candidates",
    "linked_verification_command",
]
