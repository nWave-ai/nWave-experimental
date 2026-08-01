"""Regression (GDP-3/GDP-4): the bounded-block terminal must name a concrete
HOW-to-recover command and hand off to a human, not stop at WHAT+WHY.

Charter: ``docs/product/expectations/fix-bounded-block-names-how/
the-terminal-names-how-and-escalates-to-a-human.md``.

Found in ``src/des/adapters/drivers/hooks/subagent_stop_handler.py``
``_emit_bounded_block_terminal`` (fires when the Nth=3 identical G_COMMIT
exit-gate block for the SAME ``(slice, pinned_sha, block_reason)`` key
recurs): it builds a WHAT+WHY diagnostic ("bounded-block terminal -- 3
identical exit-gate blocks for (slice=..., pinned commit, reason=...);
terminating the agent to break the re-fire loop (no progress across 3
attempts)") and routes it through the shared ``_emit_terminating_indeterminate``,
which (a) prints the diagnostic to ``sys.__stderr__`` -- WHAT+WHY only, no
HOW, no human-escalation statement -- and (b) appends a durable
``SliceCommitBlockedTerminal`` ledger record carrying ONLY
``{event, slice_id}``. Even if a HOW line were added to stderr only, it
would still never reach the ledger, so an operator reviewing the session
later (not watching it live) would never see it.

Driving surface (Mandate-13 driving-port-only, Layer 3 composition,
IN-PROCESS default): the REAL ``handle_subagent_stop`` SubagentStop hook,
driven in-process over its JSON stdin protocol via
``tests.common.in_process_cli.run_hook_in_process`` -- the same node-C
enabler the proven sibling
``tests/des/acceptance/oss_spine_watchdog/composition_slice_02.py`` uses. No
direct import of ``_emit_bounded_block_terminal`` /
``_emit_terminating_indeterminate`` -- only the hook entry point.

Fixture shape mirrored from that sibling composition
(``BoundedBlockFixture``): a real git repo whose HEAD commit is
E1-incomplete (the slice ``.feature`` AT authored on disk but kept out of the
commit), 2 prior identical ``SliceCommitBlocked`` records seeded through the
production ``AtCompletionLedger`` writer (precondition substrate, not the
SUT), and the production ``NWAVE_U2_FORCE_GATE_CODES`` speed seam so the hook
still runs for real but the 3 nested gate-subprocess forks per invocation are
replaced with the in-memory codes (``"0:1:0"``: precheck proceeds, E1 fails
=> ``slice-commit-completeness``, E2 irrelevant) the real fork would have
produced for this fixture's commit shape.

CRITICAL CONSTRAINT (preserved, do NOT change): the terminal still exits 0
(SubagentStop protocol: non-block, loud via stderr + durable record, never
via exit code) and still emits NO ``{"decision":"block"}`` body. Both ATs
below pin ``exit_code == 0``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger
from des.adapters.drivers.hooks.subagent_stop_handler import handle_subagent_stop
from tests.common.in_process_cli import run_hook_in_process


_FORCE_GATE_CODES_ENV = "NWAVE_U2_FORCE_GATE_CODES"
# precheck=0 (proceed) : e1=1 (fails -- the E1-incomplete commit shape) :
# e2=0 (irrelevant once e1 != 0) -- the codes a real fork would have produced
# for every scenario below (both arrange an E1-incomplete commit).
_FORCED_GATE_CODES = "0:1:0"

_FEATURE_ID = "fix-bounded-block-names-how-demo"
_SLICE_ID = "slice-09"
_BLOCK_REASON = "slice-commit-completeness"

# The bound: terminate ON the 3rd identical block (DISCUSS D-4 / DESIGN
# OQ-3), so 2 ordinary blocks precede it.
_N_BOUND = 3
_PRIOR_IDENTICAL_BLOCKS = _N_BOUND - 1  # = 2

# WHAT/WHY tokens already present today -- must survive unchanged per the
# charter's negative oracle. Reuse-first wording latitude, same discipline
# as the proven sibling's ``_BOUND_NAMING_TOKENS`` set.
_BOUND_NAMING_TOKENS: tuple[str, ...] = (
    "bounded",
    "indeterminate",
    "identical block",
    "no progress",
    "terminat",
)

# HOW -- a concrete ``des <subcommand>`` invocation token. Structural only:
# any "des " followed by a subcommand-shaped word counts, so DELIVER keeps
# wording latitude over which subcommand it names for the actual failing
# gate (e.g. ``des run-contract-gate``, ``des commit-slice``).
_DES_COMMAND_RE = re.compile(r"\bdes\s+[a-zA-Z][\w-]*")

# Human-escalation -- a phrase stating a human must decide the next step.
# Recognised under any of these tokens (case-insensitive), same wording
# latitude discipline.
_HUMAN_ESCALATION_TOKENS: tuple[str, ...] = (
    "human",
    "operator must",
    "manual intervention",
)


def _names_bound(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _BOUND_NAMING_TOKENS)


def _names_a_des_command(diagnostic: str) -> bool:
    return bool(_DES_COMMAND_RE.search(diagnostic))


def _names_human_escalation(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _HUMAN_ESCALATION_TOKENS)


@contextmanager
def _forced_gate_codes():
    """Set/restore the production SPEED seam around one hook invocation."""
    prior = os.environ.get(_FORCE_GATE_CODES_ENV)
    os.environ[_FORCE_GATE_CODES_ENV] = _FORCED_GATE_CODES
    try:
        yield
    finally:
        if prior is None:
            os.environ.pop(_FORCE_GATE_CODES_ENV, None)
        else:
            os.environ[_FORCE_GATE_CODES_ENV] = prior


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside ``repo`` (raises on non-zero), return stdout."""
    return subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    ).stdout


def _build_blocking_commit(repo: Path) -> str:
    """A real git repo whose HEAD commit FAILS the E1 exit gate.

    Mirrored from the proven sibling's ``build_blocking_commit``: the
    slice's ``.feature`` AT is authored on disk but kept OUT of the HEAD
    commit, so E1 (slice-commit completeness) fails and the block branch is
    reached. The commit still carries the ``Slice-Id:`` trailer.
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "--quiet")
    _git(repo, "config", "user.email", "bounded-block-how@example.test")
    _git(repo, "config", "user.name", "Bounded Block How AT")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "--quiet", "-m", "chore: seed")
    feature = repo / f"at_{_SLICE_ID}.feature"
    feature.write_text(
        f"@{_SLICE_ID}\nFeature: demo\n  Scenario: s\n    Given x\n",
        encoding="utf-8",
    )
    (repo / "code.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "add", "code.py")
    _git(
        repo,
        "commit",
        "--quiet",
        "-m",
        f"feat: deliver slice work\n\nSlice-Id: {_SLICE_ID}",
    )
    return _git(repo, "rev-parse", "HEAD").strip()


def _seed_blocks(repo: Path, *, pinned_sha: str, count: int) -> None:
    """Seed ``count`` prior identical ``SliceCommitBlocked`` records.

    Precondition substrate, NOT the SUT -- seeded through the production
    ``AtCompletionLedger`` writer, keyed on the SAME
    ``(slice_id, pinned_commit_sha, block_reason)`` the handler resolves.
    """
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    for _ in range(count):
        ledger._append_record(
            {
                "event": "SliceCommitBlocked",
                "slice_id": _SLICE_ID,
                "pinned_commit_sha": pinned_sha,
                "block_reason": _BLOCK_REASON,
            }
        )


def _write_g_commit_transcript(transcript_path: Path, repo: Path) -> None:
    """A transcript whose LAST atdd_pure block is a G_COMMIT return."""
    block = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PHASE : G_COMMIT -->\n"
        f"<!-- DES-SLICE : {_SLICE_ID} -->\n"
        f"<!-- DES-PROJECT-ID : {_FEATURE_ID} -->\n"
        f"<!-- DES-PROJECT-ROOT : {repo} -->\n"
    )
    line = json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": block},
            "uuid": "g-commit-return",
            "timestamp": "2026-07-28T10:00:00Z",
        }
    )
    transcript_path.write_text(line + "\n", encoding="utf-8")


def _fire_hook(repo: Path, transcript_path: Path) -> tuple[int, str, str]:
    """Fire the REAL ``handle_subagent_stop`` hook over its JSON protocol.

    Wrapped in ``_forced_gate_codes()`` so the handler's precheck/E1/E2
    subprocess forks are replaced with the in-memory codes this fixture's
    E1-incomplete commit shape would have produced for real -- the hook
    itself still runs (the driving port is unchanged).
    """
    hook_input = json.dumps(
        {
            "session_id": "bounded-block-how-session",
            "hook_event_name": "SubagentStop",
            "agent_id": "crafter-1",
            "agent_type": "software-crafter",
            "agent_transcript_path": str(transcript_path),
            "stop_hook_active": False,
            "cwd": str(repo),
            "transcript_path": "/tmp/session.jsonl",
            "permission_mode": "default",
        }
    )
    with _forced_gate_codes():
        return run_hook_in_process(
            handle_subagent_stop, stdin_text=hook_input, cwd=str(repo)
        )


def _terminal_ledger_records(repo: Path) -> list[dict[str, Any]]:
    """Read back every durable ``SliceCommitBlockedTerminal`` record."""
    ledger = AtCompletionLedger(_FEATURE_ID, repo)
    return ledger.read_records(event_type="SliceCommitBlockedTerminal")


def _block_decision(stdout: str) -> dict[str, Any] | None:
    """Parse the JSON `{decision: block}` body from stdout, if any."""
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if payload.get("decision") == "block":
            return payload
    return None


def test_third_identical_block_names_how_to_recover_and_escalates_to_human(
    tmp_path: Path,
) -> None:
    """POSITIVE AT (active-RED today): the 3rd identical G_COMMIT exit-gate
    block for the SAME ``(slice, pinned_sha, block_reason)`` key must
    terminate (no ``{decision:block}`` body) with a diagnostic that STILL
    names WHAT+WHY (already true today) AND ADDITIONALLY names a concrete
    ``des <subcommand>`` HOW-to-recover command and explicitly hands the
    decision to a human -- both MISSING today. The SAME HOW+escalation text
    must also land in the durable ``SliceCommitBlockedTerminal`` ledger
    record, which today carries only ``{event, slice_id}``.
    """
    repo = tmp_path / "deliver-repo"
    transcript_path = repo / "agent.jsonl"

    pinned_sha = _build_blocking_commit(repo)
    _seed_blocks(repo, pinned_sha=pinned_sha, count=_PRIOR_IDENTICAL_BLOCKS)
    _write_g_commit_transcript(transcript_path, repo)

    exit_code, stdout, stderr = _fire_hook(repo, transcript_path)

    # Asymmetric authority is preserved -- ALREADY true today, must stay true
    # after the fix (the fix adds HOW+escalation content, it never flips this).
    assert exit_code == 0, (
        "the bounded-block terminal must exit 0 (SubagentStop protocol: "
        f"loud via stderr + durable record, never via exit code) -- got {exit_code}"
    )
    assert _block_decision(stdout) is None, (
        "the 3rd identical block must TERMINATE (no `{decision:block}` "
        f"body) -- stdout still carries a block decision: {stdout!r}"
    )

    diagnostic = stderr

    # WHAT+WHY -- already present today (this assertion already passes; must
    # survive unchanged per the charter's negative oracle).
    assert _names_bound(diagnostic), (
        "the bounded-block terminal diagnostic must still name WHAT+WHY "
        f"(which gate blocked repeatedly and why) -- got {diagnostic!r}"
    )

    # HOW -- the part MISSING today (RED for the right reason: a semantic
    # AssertionError naming the absent remediation command, not a crash).
    assert _names_a_des_command(diagnostic), (
        "the bounded-block terminal diagnostic must name a concrete `des "
        "<subcommand>` command the operator can run to see the real, "
        f"underlying gate failure -- none found: {diagnostic!r}"
    )

    # Human escalation -- also MISSING today.
    assert _names_human_escalation(diagnostic), (
        "the bounded-block terminal diagnostic must explicitly state that a "
        f"human must decide the next step -- none found: {diagnostic!r}"
    )

    # The SAME HOW+escalation text must be durable (visible to a post-mortem
    # operator, not just the live stderr stream) -- also MISSING today
    # (`_emit_terminating_indeterminate` writes only `{event, slice_id}`).
    records = _terminal_ledger_records(repo)
    assert records, (
        "expected a durable `SliceCommitBlockedTerminal` ledger record for "
        f"the terminating 3rd identical block -- ledger has none: {records!r}"
    )
    persisted = " ".join(json.dumps(record) for record in records)
    assert _names_a_des_command(persisted), (
        "the durable `SliceCommitBlockedTerminal` ledger record must carry "
        "the SAME HOW-to-recover `des <subcommand>` command as the stderr "
        "diagnostic, so an operator reviewing the session later (not "
        f"watching it live) sees it too -- record(s): {records!r}"
    )
    assert _names_human_escalation(persisted), (
        "the durable `SliceCommitBlockedTerminal` ledger record must carry "
        "the SAME human-escalation statement as the stderr diagnostic, so "
        "an operator reviewing the session later (not watching it live) "
        f"sees it too -- record(s): {records!r}"
    )


@pytest.mark.negative_at
def test_non_terminal_block_never_carries_the_how_and_escalation_text(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT (control -- green today, stays green after the fix): the
    1st (non-terminal) identical G_COMMIT exit-gate block still re-fires via
    ``{decision:block}`` (unchanged) and its reason text carries NEITHER a
    ``des <subcommand>`` HOW command NOR a human-escalation phrase -- the new
    HOW+escalation content is scoped to the TERMINAL only, never leaking
    into an ordinary re-fire block. No terminal ledger record is written
    either, since only 1 of the required 3 identical blocks has occurred.
    """
    repo = tmp_path / "deliver-repo"
    transcript_path = repo / "agent.jsonl"

    # No prior identical blocks seeded -- this invocation IS the 1st
    # (non-terminal) block.
    _build_blocking_commit(repo)
    _write_g_commit_transcript(transcript_path, repo)

    exit_code, stdout, stderr = _fire_hook(repo, transcript_path)

    # stderr was unpacked and never inspected. A hook that exits 0 while
    # complaining on stderr is not the same thing as a hook that is silent,
    # and only one of the two is what "clean pass" means here.
    assert stderr == "", f"expected a silent pass, got on stderr: {stderr!r}"
    assert exit_code == 0

    block = _block_decision(stdout)
    assert block is not None, (
        "the 1st identical block must still re-fire via `{decision:block}` "
        f"(unchanged, non-terminal) -- stdout: {stdout!r}"
    )

    reason = str(block.get("reason", ""))
    assert not _names_a_des_command(reason), (
        "a non-terminal (1st/2nd) block's reason must NOT carry the new "
        "`des <subcommand>` HOW text -- that content is scoped to the "
        f"bounded-block TERMINAL only: {reason!r}"
    )
    assert not _names_human_escalation(reason), (
        "a non-terminal (1st/2nd) block's reason must NOT carry the new "
        f"human-escalation text -- that content is scoped to the terminal "
        f"only: {reason!r}"
    )

    records = _terminal_ledger_records(repo)
    assert not records, (
        "a non-terminal block must not emit a `SliceCommitBlockedTerminal` "
        f"record -- ledger already has one: {records!r}"
    )
