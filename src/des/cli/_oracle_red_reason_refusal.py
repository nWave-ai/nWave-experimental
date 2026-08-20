"""Execution probe: prove the oracle is RED for the right reason (K4 Run 13).

Run 13 debrief: 4 crafter dispatches, 3 wasted -- each burned 4-9 minutes
implementing against the oracle before failing on a defect IN THE ORACLE
ITSELF (an FK field colliding with Django's own system-check hook; two
fixture gaps). Root's own debrief: "have ATD actually execute the oracle...
before CONTRACT_READY." ATD's own Bash surface is locked to `des
fill-contract` alone (Ale's construction-over-file correction, 2026-08-20)
-- it cannot run this probe itself; the deterministic place remains `des
dispatch` -- the one boundary between `CONTRACT_READY` and the first
crafter dispatch, already the home of every other contract-content check
(`_placeholder_refusal`, `_whole_suite_scope_refusal`; the sibling
`_declared_import_refusal`/`_verification_command_refusal` this probe used
to sit beside were DELETED, "the contract has one writer -- `des
fill-contract` is the constructor", Agda-proved vacuous -- ~/nwave-formal/
2026-08-19-gates).

ONE language-agnostic check (roadmap: "language agnostic is an outcome
constraint, not authorization to build or retain a universal language-
adapter framework"; "removal before refactoring" -- a Python-AST structure
checker and an `OracleCheckPort`/per-language-adapter pair were both built
and then deleted here; their build/vet-marker logic was PROMOTED into the
single classifier instead of deleted with them). `already green` (exit 0)
is refused for a `RED_TO_GREEN` oracle-linked command -- that oracle
proves nothing new. A nonzero exit whose output names a symbol the
contract's own targets declare it will create is the missing-feature
reason -- accepted, any language, a plain token match. A nonzero exit
matching the small, extensible, language-neutral build/compile-broken
marker table is `UNACCEPTABLE_BUILD` -- refused, quoting the real tool's
own output, never diagnosing it (never claiming "SyntaxError" against
output that was never Python's -- the K4 sister defect's lying-refusal
shape, one language over). Every other nonzero exit is `INDETERMINATE`:
informational only, the last lines quoted, never a refusal -- the
crafter's own BASELINE remains the one real test. A broken oracle (a
nested-test splice, say) that fails to import/collect for a reason
matching no build marker and naming no declared symbol still degrades to
an informational note, never a fabricated diagnosis.

Unlike every static check above, this one EXECUTES: it runs each
`verification-scope.commands` entry, bounded, and classifies the outcome
(`des.domain.oracle_execution_classifier`). Two consequences follow,
both deliberate:

1. Wired ONLY into `des dispatch`, never into `des validate-delivery-
   contract`'s two crafter-boundary calls -- the crafter's own BASELINE
   already runs these same commands for real immediately after; re-running
   them again at both crafter call sites would be pure duplicated cost for
   zero additional evidence (GDP-10).
2. NEVER switchable off (GDP-7: an execution-observing gate is a fixed
   floor, never rigor-gated). An earlier revision skipped this probe
   whenever `PYTEST_CURRENT_TEST` was set, to dodge a real, separate
   problem: this repo's own shared dispatch-test fixture
   (`tests/common/delivery_contract_fixture.py`) reused this repo's own
   already-green schema test as a stand-in oracle, so an always-on probe
   correctly refused ~35 of this repo's OWN tests as "already green" --
   true positives against a fixture that predated this probe, not a bug in
   the probe. CI caught the actual bug: a gate that disables itself under
   test cannot be trusted to fire in production either. The fix landed in
   the fixture instead: `seed_referenced_oracle` writes a genuinely
   RED-for-the-right-reason oracle body (a plain `AssertionError`, needing
   no declared-symbol correlation) rather than copying the real,
   already-passing schema test's bytes -- this module has no test-only
   branch at all.

`ALREADY_GREEN` detection stays scoped to Python-shaped oracle-linked
commands (`django_test_labels`/`pytest_file_arguments` matching the
contract's own `acceptance-tests.locator`) -- unqualified "any exit-0
command under RED_TO_GREEN is a defect" would flag an unrelated already-
green command (this repo's own shared fixture also declares `git diff
--check`, which legitimately passes) as a false ALREADY_GREEN refusal,
exactly the class of regression CI caught once already for the shared
fixture. Extending oracle-linkage detection to a non-Python command would
need a reliable non-Python file/package-to-oracle-locator signal this
project has none of yet -- deferred, not silently dropped.
"""

from __future__ import annotations

import os
import subprocess
from typing import TYPE_CHECKING

from des.domain.oracle_execution_classifier import (
    GREEN,
    INDETERMINATE,
    UNACCEPTABLE_BUILD,
    classify_probe_output,
    declared_symbol_candidates,
)
from des.domain.oracle_execution_classifier import (
    reason_line as _reason_line,
)
from des.domain.oracle_link_resolver import command_argv as _command_argv
from des.domain.oracle_link_resolver import is_oracle_linked as _is_oracle_linked
from des.runtime.test_execution import run_pytest_reaped


if TYPE_CHECKING:
    from pathlib import Path


def _probe_timeout_seconds() -> float:
    try:
        return float(os.environ.get("NWAVE_ORACLE_PROBE_TIMEOUT_SECONDS", "120"))
    except ValueError:
        return 120.0


def _already_green_finding(command_text: str) -> tuple[str, str, str]:
    return (
        f"verification command {command_text!r} for a RED_TO_GREEN delivery "
        "already passes at BASE, before any crafter mutation",
        "RED_TO_GREEN requires the oracle to fail only for the missing "
        "promised behavior; an oracle that is already green proves nothing "
        "new and gives the crafter no falsifiable target",
        "confirm the oracle actually exercises the new behavior (a Run "
        "10-style splice can silently not run at all) and that "
        "verification-scope cites it correctly, or switch delivery-route to "
        "GREEN_TO_GREEN if the behavior genuinely already exists",
    )


def _indeterminate_note(command_text: str, reason: str) -> str:
    return (
        f"INFO: verification command {command_text!r} fails at BASE with "
        f"no declared symbol named in its output ({reason!r}) -- "
        "INDETERMINATE, not a refusal: this probe makes no claim about "
        "why (a real syntax/build error, a fixture gap, or a legitimately "
        "unfinished dependency all look the same from here); the crafter's "
        "own BASELINE remains the RED/GREEN authority for it"
    )


def _could_not_run_note(command_text: str, exc: OSError) -> str:
    """A command that never even STARTED (a missing executable, an
    unresolvable interpreter) is never the same as one that ran and
    passed -- GDP-6: no silent-wrong. CI caught this exact confusion once
    already for a test fixture whose interpreter symlink broke venv self-
    detection under a stripped PATH: the subprocess failed with
    `FileNotFoundError`, this branch silently `continue`d, and dispatch
    read the resulting empty (findings, notes) as nothing to report --
    exit 0, indistinguishable from a genuinely verified GREEN."""
    return (
        f"INFO: verification command {command_text!r} could not even START "
        f"at BASE ({exc}) -- COULD-NOT-RUN, never green and never a "
        "confirmed RED reason either: a missing executable or an "
        "unresolvable interpreter proves nothing about the oracle itself; "
        "the crafter's own BASELINE remains the RED/GREEN authority for it"
    )


def _unacceptable_build_finding(command_text: str, reason: str) -> tuple[str, str, str]:
    return (
        f"verification command {command_text!r} fails to build/vet at BASE, "
        f"before any crafter mutation -- quoted output: {reason!r}",
        "a build/compile failure blocks every test run regardless of "
        "whether the promised feature is implemented, and cites no symbol "
        "this contract's own targets declare it will create (this is the "
        "real tool's own output, never a guessed diagnosis against output "
        "that was never Python's)",
        "fix the reported build/vet error before CONTRACT_READY -- an ATD "
        "REVISE, never a crafter concern; if the cited name is meant to be "
        "new production substrate, name it in the target's own "
        "justification so this probe recognizes it",
    )


def oracle_red_reason_check(
    repo_root: Path, contract: dict
) -> tuple[list[tuple[str, str, str]], list[str]]:
    """`(defect findings, informational notes)` from ONE bounded execution
    pass over every `verification-scope.commands` entry.

    Never switchable off (GDP-7). A timed-out command is silently skipped
    (could-not-verify defers to the crafter's own BASELINE, never blocks
    on ambiguity, bounded so a hung command can never wedge dispatch). A
    command that could not even START (a missing executable, an
    unresolvable interpreter -- `OSError`) is NEVER silent: it surfaces as
    an informational COULD-NOT-RUN note, distinct from both an acceptable
    RED and a green pass (GDP-6)."""
    route = contract.get("delivery-route")
    oracle_locator = str(contract.get("acceptance-tests", {}).get("locator", ""))
    declared_symbols = declared_symbol_candidates(contract)
    timeout = _probe_timeout_seconds()

    findings: list[tuple[str, str, str]] = []
    notes: list[str] = []
    for command in contract.get("verification-scope", {}).get("commands", []):
        argv = _command_argv(repo_root, command)
        if not argv or not argv[0]:
            continue
        command_text = " ".join(command.get("arguments", []))
        try:
            result = run_pytest_reaped(
                argv, cwd=repo_root, timeout=timeout, capture_output=True, text=True
            )
        except subprocess.TimeoutExpired:
            continue
        except OSError as exc:
            notes.append(_could_not_run_note(command_text, exc))
            continue
        output = f"{result.stdout or ''}\n{result.stderr or ''}"
        outcome = classify_probe_output(
            returncode=result.returncode,
            output=output,
            declared_symbols=declared_symbols,
        )
        if (
            outcome == GREEN
            and route == "RED_TO_GREEN"
            and _is_oracle_linked(command, oracle_locator)
        ):
            findings.append(_already_green_finding(command_text))
        elif outcome == UNACCEPTABLE_BUILD:
            findings.append(
                _unacceptable_build_finding(command_text, _reason_line(output))
            )
        elif outcome == INDETERMINATE:
            notes.append(_indeterminate_note(command_text, _reason_line(output)))
    return findings, notes
