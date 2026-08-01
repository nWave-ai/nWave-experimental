"""Regression: the SubagentStop hook must degrade LOUD, not silent, when a
DECLARED ``agent_transcript_path`` cannot be resolved to a readable file.

Charter: ``docs/product/expectations/fix-subagent-stop-silent-transcript/
loud-degrade-on-unreadable-transcript.md``.
RCA: ``docs/feature/fix-subagent-stop-silent-transcript/rca.md``.

Found in ``src/des/adapters/drivers/hooks/subagent_stop_handler.py``:
``extract_des_context_from_transcript`` (:166) and ``_read_transcript_entries``
(:659) both collapse "transcript inaccessible" (path absent, or
present-but-unreadable) and "transcript accessible but marker-free" into the
SAME return value (``None`` / ``[]``). ``_resolve_des_context`` (:370) maps
that single ``None`` to the non-DES passthrough
``(None, {"decision": "allow"}, 0)`` at :437-455, and ``handle_subagent_stop``
(:2807) returns ``exit_code=0`` at :2975-2991 -- BEFORE the
``_AtddPureResolvedContext`` branch (:2917), the ONLY branch that can reach
``_handle_g_commit_exit_gate`` (:1533), ``_handle_feature_end_gate`` (:2074)
and ``_handle_distill_exit_gate`` (:2316). A genuine atdd_pure dispatch whose
transcript becomes unreadable therefore BYPASSES those three exit gates
silently -- indistinguishable, at exit 0 / empty stdout / empty stderr, from a
harmless non-DES agent completing normally.

Driving surface (Mandate-13 driving-port-only): the REAL CLI surface,
``python3 -m des.adapters.drivers.hooks.hook_router subagent-stop`` over its
JSON stdin protocol, driven via a real ``subprocess.run`` (NOT the usual
in-process default) per this bugfix's explicit dispatch instruction. This is
NOT a style choice: two of the observable properties under test key off the
REAL OS process ``cwd`` rather than the envelope's declared ``"cwd"`` field --
the activation gate (``hook_router.apply_gate`` / ``DESConfig``) and the
audit-log side effect (``JsonlAuditLogWriter`` / ``AuditLogPathResolver``,
via ``resolve_nwave_root()`` -> ``Path.cwd()``) both resolve against the
process's actual working directory. An in-process call that merely swaps
``sys.stdin`` would not exercise (or would silently bypass) the activation
gate a real operator invocation always goes through, so AT4's audit-aggregate
assertion would not be observing what an operator observes. Verified
empirically (manual repro, 2026-07-30): the SAME envelope produces DIFFERENT
audit-log placement depending on whether ``cwd=`` the subprocess and the
envelope's ``"cwd"`` field agree -- the fixture below keeps them in lock-step.

Every fixture repo carries an ``enabled_for_repo: true`` activation marker
(``.nwave/local-config.json``) -- a fresh, unmarked project defaults to
INACTIVE (opt-in), and an inactive project's ``apply_gate`` exits 0 BEFORE
``handle_subagent_stop`` ever runs, which would make every case in this file
"pass" for the wrong reason (the activation gate, not the defect under test).

CRITICAL CONSTRAINT (Q5 in the RCA, preserved -- do NOT change): an ABSENT
``agent_transcript_path`` key is not a broken promise, it is the routine shape
of a SubagentStop event from an agent-type that never populates transcript
paths. It must keep the existing silent allow, byte-stable, forever (AT6).
Only a DECLARED (non-empty) path that fails to resolve is "declared-but-
broken" and gets the new LOUD treatment (AT1-AT4).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC_DIR = _REPO_ROOT / "src"

# --- WHAT/WHY/HOW + reason-distinguishing token sets -----------------------
# Structural, wording-latitude checks (same discipline as the proven sibling
# ``test_bounded_block_terminal_names_how_and_escalates_to_human.py``'s
# ``_BOUND_NAMING_TOKENS`` / ``_DES_COMMAND_RE``): DELIVER keeps latitude over
# the exact prose, these only pin the STRUCTURAL properties the charter demands.

_INDETERMINATE_RE = re.compile(r"\bindeterminate\b", re.IGNORECASE)

_ABSENCE_TOKENS: tuple[str, ...] = (
    "does not exist",
    "not found",
    "no such file",
    "missing",
    "cannot find",
    "could not find",
)

_INCAPACITY_TOKENS: tuple[str, ...] = (
    "cannot read",
    "could not read",
    "unreadable",
    "permission",
    "cannot open",
    "could not open",
    "denied",
    "incapacity",
)

# Negative oracle (charter): the message must NOT claim "no DES markers were
# found" (an absence-of-content claim) when the true problem is that the file
# could never be read at all (an incapacity-to-read).
_NO_MARKERS_CLAIM_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"no\s+\S*\s*markers?\s+(were\s+)?found", re.IGNORECASE),
    re.compile(r"found\s+no\s+\S*\s*markers?", re.IGNORECASE),
)

_WHY_TOKENS: tuple[str, ...] = (
    "cannot tell",
    "cannot determine",
    "cannot verify",
    "unable to determine",
    "cannot know",
    "gate",
)

# HOW -- a concrete corrective action, structural only (verb near the
# problem), never a bare "ask a human" deferral (that phrasing is explicitly
# banned by the charter for THIS gate -- unlike the bounded-block terminal
# precedent, which correctly DOES escalate to a human).
_CORRECTIVE_ACTION_RE = re.compile(
    r"\b(check|verify|regenerate|restore|recreate|re-?run|fix|correct|inspect)\b",
    re.IGNORECASE,
)

_HUMAN_ESCALATION_TOKENS: tuple[str, ...] = (
    "ask a human",
    "human must",
    "manual intervention",
    "escalate to a human",
    "human intervention",
    "notify a human",
)


def _names_indeterminate(diagnostic: str) -> bool:
    return bool(_INDETERMINATE_RE.search(diagnostic))


def _names_absence(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _ABSENCE_TOKENS)


def _names_incapacity(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _INCAPACITY_TOKENS)


def _falsely_claims_no_markers(diagnostic: str) -> bool:
    return any(p.search(diagnostic) for p in _NO_MARKERS_CLAIM_PATTERNS)


def _names_why(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _WHY_TOKENS)


def _names_a_corrective_action(diagnostic: str) -> bool:
    return bool(_CORRECTIVE_ACTION_RE.search(diagnostic))


def _names_human_escalation(diagnostic: str) -> bool:
    low = diagnostic.lower()
    return any(token in low for token in _HUMAN_ESCALATION_TOKENS)


# --- fixture + driving-port helpers -----------------------------------------


def _activate(repo: Path) -> None:
    """Mark ``repo`` active (``enabled_for_repo: true``) so the hook's own
    activation gate dispatches into ``handle_subagent_stop`` for real, instead
    of exiting 0 before the handler ever runs (a fresh/unmarked project
    defaults to inactive, opt-in)."""
    nwave_dir = repo / ".nwave"
    nwave_dir.mkdir(parents=True, exist_ok=True)
    (nwave_dir / "local-config.json").write_text(
        json.dumps({"enabled_for_repo": True}), encoding="utf-8"
    )


def _envelope(
    transcript_path: str | None,
    cwd: str,
    *,
    stop_hook_active: bool = False,
    include_transcript_key: bool = True,
) -> dict:
    """The Claude Code SubagentStop JSON envelope, varying only the field(s)
    under test -- mirrors the shape the real hook lifecycle sends."""
    envelope: dict = {
        "session_id": "bugsilent-session",
        "hook_event_name": "SubagentStop",
        "agent_id": "crafter-1",
        "agent_type": "software-crafter",
        "stop_hook_active": stop_hook_active,
        "cwd": cwd,
        "transcript_path": "/tmp/session.jsonl",
        "permission_mode": "default",
    }
    if include_transcript_key:
        envelope["agent_transcript_path"] = transcript_path
    return envelope


def _fire(repo: Path, envelope: dict) -> tuple[int, str, str]:
    """Fire the REAL hook CLI surface over its JSON stdin protocol.

    ``cwd=repo`` for the subprocess itself (not just the envelope's ``"cwd"``
    field) -- see the module docstring: the activation gate and the audit-log
    writer both key off the process's actual working directory.

    ``DES_PROJECT_DIR`` is explicitly popped: this suite's own
    ``tests/conftest.py`` autouse fixture (``_isolate_nwave_root``) sets it to
    a PER-TEST isolation tmp dir for the OUTER pytest process, and a naive
    ``env=dict(os.environ)`` would leak that unrelated var into the
    subprocess, silently redirecting ``resolve_nwave_root()`` (and therefore
    the audit-log write ``JsonlAuditLogWriter``/``AuditLogPathResolver``
    resolve against) away from ``repo`` and into that leaked directory --
    a real Claude Code hook invocation never sets this var, so popping it
    keeps this fixture faithful to production.
    """
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SRC_DIR)
    env.pop("DES_AUDIT_LOG_DIR", None)
    env.pop("DES_PROJECT_DIR", None)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "des.adapters.drivers.hooks.hook_router",
            "subagent-stop",
        ],
        input=json.dumps(envelope),
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    return result.returncode, result.stdout, result.stderr


def _write_readable_no_markers(path: Path) -> None:
    """A readable transcript carrying zero DES dispatch markers (row case 1
    -- the legitimate no-op that must stay boringly silent, forever)."""
    line = json.dumps(
        {
            "message": {
                "role": "user",
                "content": "just some ordinary text, nothing DES about it",
            },
            "uuid": "readable-no-markers",
        }
    )
    path.write_text(line + "\n", encoding="utf-8")


def _write_valid_atdd_pure_markers(path: Path) -> None:
    """A readable transcript carrying a genuine atdd_pure marker block."""
    block = (
        "<!-- DES-VALIDATION : required -->\n"
        "<!-- DES-MODE : atdd_pure -->\n"
        "<!-- DES-PROJECT-ID : demo-feature -->\n"
        "<!-- DES-SLICE : slice-01 -->\n"
        "<!-- DES-PHASE : B_GREEN -->\n"
    )
    line = json.dumps(
        {
            "message": {"role": "user", "content": block},
            "uuid": "valid-atdd-pure-markers",
        }
    )
    path.write_text(line + "\n", encoding="utf-8")


def _hook_invoked_handlers(repo: Path) -> list[str]:
    """Every ``HOOK_INVOKED`` audit record's ``handler`` field, in write
    order, from this repo's project-local audit log
    (``.nwave/des/logs/audit-*.log``)."""
    log_dir = repo / ".nwave" / "des" / "logs"
    handlers: list[str] = []
    if not log_dir.exists():
        return handlers
    for log_file in sorted(log_dir.glob("audit-*.log")):
        for line in log_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            entry = json.loads(stripped)
            if entry.get("event") == "HOOK_INVOKED":
                handlers.append(entry.get("handler"))
    return handlers


def _block_decision(stdout: str) -> dict | None:
    """Parse a JSON ``{"decision": "block"}`` body from stdout, if any."""
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


# =============================================================================
# POSITIVE ATs (active-RED today -- the hook must start degrading LOUD)
# =============================================================================


def test_missing_declared_transcript_path_degrades_loud_and_distinguishable_from_marker_free_allow(
    tmp_path: Path,
) -> None:
    """AT1: a DECLARED ``agent_transcript_path`` pointing at a NONEXISTENT
    file must NOT produce the same byte-identical silent allow as the
    legitimate marker-free no-op -- it must degrade LOUD, naming a third
    (INDETERMINATE) state and echoing the offending path verbatim."""
    repo_allow = tmp_path / "repo-allow"
    repo_missing = tmp_path / "repo-missing"
    _activate(repo_allow)
    _activate(repo_missing)

    readable_path = repo_allow / "readable_no_markers.jsonl"
    _write_readable_no_markers(readable_path)
    allow_result = _fire(repo_allow, _envelope(str(readable_path), str(repo_allow)))
    assert allow_result == (0, "", ""), (
        "sanity baseline: a readable marker-free transcript must be the "
        f"silent allow this AT compares against -- got {allow_result!r}"
    )

    missing_path = repo_missing / "does-not-exist.jsonl"
    exit_code, stdout, stderr = _fire(
        repo_missing, _envelope(str(missing_path), str(repo_missing))
    )
    diagnostic = stdout + stderr

    assert exit_code == 0, (
        "the SubagentStop protocol never blocks via exit code (loud via "
        f"stdout/stderr + a durable record instead) -- got exit {exit_code}"
    )
    assert (exit_code, stdout, stderr) != allow_result, (
        "a DECLARED-but-nonexistent transcript path must NOT be byte-"
        "identical to the legitimate marker-free silent allow -- got the "
        f"exact same (exit_code, stdout, stderr) as the no-op: {allow_result!r}"
    )
    assert diagnostic != "", (
        "a declared-but-nonexistent transcript path must produce SOME "
        "visible output (stdout or stderr) -- got total silence"
    )
    assert _names_indeterminate(diagnostic), (
        "the loud diagnostic must name a third (INDETERMINATE) state, not "
        f"a bare pass/fail -- got {diagnostic!r}"
    )
    assert str(missing_path) in diagnostic, (
        "the loud diagnostic must echo the offending path verbatim so the "
        f"operator can act on it -- got {diagnostic!r}"
    )


def test_unreadable_declared_transcript_path_distinguishes_incapacity_from_absence(
    tmp_path: Path,
) -> None:
    """AT2: a declared path that EXISTS but cannot be READ (chmod 000) must
    ALSO degrade loud, and its stated REASON must be distinguishable from the
    missing-path case -- incapacity-to-read, never a false "no markers found"
    claim (the charter's absence-vs-incapacity negative oracle)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip(
            "running as root: chmod 000 is not enforced for root, so the "
            "unreadable-file condition this AT depends on cannot be observed "
            "-- skipping LOUDLY rather than silently reporting a false pass"
        )

    repo_missing = tmp_path / "repo-missing"
    repo_unreadable = tmp_path / "repo-unreadable"
    _activate(repo_missing)
    _activate(repo_unreadable)

    missing_path = repo_missing / "does-not-exist.jsonl"
    _, missing_out, missing_err = _fire(
        repo_missing, _envelope(str(missing_path), str(repo_missing))
    )
    missing_diag = missing_out + missing_err

    unreadable_path = repo_unreadable / "unreadable.jsonl"
    _write_valid_atdd_pure_markers(unreadable_path)
    unreadable_path.chmod(0o000)
    try:
        _, unreadable_out, unreadable_err = _fire(
            repo_unreadable, _envelope(str(unreadable_path), str(repo_unreadable))
        )
    finally:
        unreadable_path.chmod(0o644)  # restore so tmp_path teardown can clean up
    unreadable_diag = unreadable_out + unreadable_err

    assert missing_diag != "", "the missing-path case must degrade loud (AT1)"
    assert unreadable_diag != "", (
        "an existing-but-unreadable declared path must ALSO degrade loud, "
        "not stay silent -- got total silence"
    )
    assert missing_diag != unreadable_diag, (
        "the two distinct failure conditions (absence vs incapacity) must "
        "not produce byte-identical diagnostics -- "
        f"missing={missing_diag!r} unreadable={unreadable_diag!r}"
    )

    # Negative oracle (charter): NEITHER case may falsely claim "no DES
    # markers were found" -- that is an absence-of-content claim, and the
    # true condition in both cases is that the file could never be read at
    # all (the unreadable case genuinely CARRIES real markers -- they are
    # simply unreachable).
    assert not _falsely_claims_no_markers(missing_diag), (
        "the missing-path diagnostic must not falsely claim 'no markers "
        f"found' -- got {missing_diag!r}"
    )
    assert not _falsely_claims_no_markers(unreadable_diag), (
        "the unreadable-path diagnostic must not falsely claim 'no markers "
        "found' when the true problem is that the file could never be read "
        f"at all -- got {unreadable_diag!r}"
    )

    assert _names_incapacity(unreadable_diag), (
        "the unreadable-path diagnostic must name INCAPACITY-to-read as its "
        f"reason (distinct from mere absence) -- got {unreadable_diag!r}"
    )


def test_loud_diagnostic_names_what_why_how_never_escalates_to_human(
    tmp_path: Path,
) -> None:
    """AT3: the loud diagnostic must carry WHAT (the transcript/path that
    failed), WHY (DES cannot tell whether anything needed doing), and HOW (a
    concrete corrective action) -- and the HOW must NEVER be a bare "ask a
    human to repair it" deferral."""
    repo = tmp_path / "repo"
    _activate(repo)
    missing_path = repo / "does-not-exist.jsonl"

    _, stdout, stderr = _fire(repo, _envelope(str(missing_path), str(repo)))
    diagnostic = stdout + stderr

    assert diagnostic != "", "expected a loud diagnostic (see AT1)"

    # WHAT
    assert "transcript" in diagnostic.lower(), (
        f"the diagnostic must name WHAT failed (the transcript) -- got {diagnostic!r}"
    )
    assert str(missing_path) in diagnostic, (
        f"the diagnostic must name the offending path -- got {diagnostic!r}"
    )

    # WHY
    assert _names_why(diagnostic), (
        "the diagnostic must explain WHY it matters (DES cannot tell "
        f"whether anything needed doing) -- got {diagnostic!r}"
    )

    # HOW -- concrete, never a human deferral
    assert _names_a_corrective_action(diagnostic), (
        "the diagnostic must name a concrete corrective action (a producing "
        f"tool or command), not merely restate the problem -- got {diagnostic!r}"
    )
    assert not _names_human_escalation(diagnostic), (
        "the diagnostic must NEVER defer to 'ask a human to repair it' -- "
        f"a concrete corrective action is required instead -- got {diagnostic!r}"
    )


def test_third_state_reaches_the_audit_aggregate_distinct_from_plain_allow(
    tmp_path: Path,
) -> None:
    """AT4: the loud outcome must reach a durable, observable RECORD distinct
    from the plain allow -- an operator reviewing the audit log afterward
    must NOT find a declared-but-inaccessible transcript filed under the
    SAME ``subagent_stop_passthrough`` / ``non_des_or_error`` record a
    legitimate no-op gets. Mirrors how the sibling loud path
    (``subagent_stop_wave_only_unresolved``, :2771) is observed."""
    repo_allow = tmp_path / "repo-allow"
    repo_missing = tmp_path / "repo-missing"
    _activate(repo_allow)
    _activate(repo_missing)

    readable_path = repo_allow / "readable_no_markers.jsonl"
    _write_readable_no_markers(readable_path)
    _fire(repo_allow, _envelope(str(readable_path), str(repo_allow)))
    allow_handlers = _hook_invoked_handlers(repo_allow)
    assert "subagent_stop_passthrough" in allow_handlers, (
        "sanity baseline: the legitimate no-op must still be filed under "
        f"'subagent_stop_passthrough' -- got {allow_handlers!r}"
    )

    missing_path = repo_missing / "does-not-exist.jsonl"
    _fire(repo_missing, _envelope(str(missing_path), str(repo_missing)))
    missing_handlers = _hook_invoked_handlers(repo_missing)

    assert len(missing_handlers) >= 2, (
        "expected at least the initial invocation record plus a decision "
        f"record -- got {missing_handlers!r}"
    )
    assert "subagent_stop_passthrough" not in missing_handlers, (
        "a declared-but-inaccessible transcript must NOT be filed under the "
        "SAME 'subagent_stop_passthrough' / non_des_or_error record as a "
        "legitimate no-op -- the run must be distinguishable in the audit "
        f"aggregate, not folded into the same success bucket -- got {missing_handlers!r}"
    )


# =============================================================================
# NEGATIVE ATs (control -- GREEN today, must stay GREEN after the fix)
# =============================================================================


@pytest.mark.negative_at
def test_marker_free_readable_transcript_never_becomes_noisy(tmp_path: Path) -> None:
    """AT5: a readable transcript with NO DES markers is the legitimate
    no-op -- it must keep producing the byte-identical silent allow (empty
    stdout, empty stderr, exit 0). The cure for the OTHER cases must not make
    this one noisy."""
    repo = tmp_path / "repo"
    _activate(repo)
    path = repo / "readable_no_markers.jsonl"
    _write_readable_no_markers(path)

    exit_code, stdout, stderr = _fire(repo, _envelope(str(path), str(repo)))

    assert (exit_code, stdout, stderr) == (0, "", ""), (
        "a readable, marker-free transcript must stay the boringly-silent "
        f"allow -- got (exit={exit_code}, stdout={stdout!r}, stderr={stderr!r})"
    )


@pytest.mark.negative_at
def test_absent_transcript_path_key_never_triggers_a_refusal(tmp_path: Path) -> None:
    """AT6: an envelope that never DECLARES ``agent_transcript_path`` at all
    (the routine shape from an agent-type that never populates it) must keep
    the existing silent allow -- absence of a promise is not a broken
    promise (RCA Q5). Existing tests depend on this byte-stable shape:
    ``test_hook_id_generation.py:53-58`` and
    ``test_hook_completed_event.py:52-58``."""
    repo = tmp_path / "repo"
    _activate(repo)
    envelope = _envelope(None, str(repo), include_transcript_key=False)

    exit_code, stdout, stderr = _fire(repo, envelope)

    assert (exit_code, stdout, stderr) == (0, "", ""), (
        "an envelope with NO 'agent_transcript_path' key must stay the "
        f"silent allow -- got (exit={exit_code}, stdout={stdout!r}, stderr={stderr!r})"
    )


@pytest.mark.negative_at
def test_broken_declared_path_never_loops_the_block_decision_on_refire(
    tmp_path: Path,
) -> None:
    """AT7: re-firing the SAME declared-but-broken transcript path (Claude
    Code's ``stop_hook_active: true`` re-invocation) must NEVER emit a
    ``{"decision": "block"}`` body -- that would re-trigger Claude Code into
    an unbounded loop. This must hold on the FIRST fire too (the loud fix
    must not accidentally introduce a block body where none existed) --
    pinning the blast radius against a naive/looping implementation, exactly
    the class of bug ``_emit_wave_only_refire_terminal`` (:2630) /
    ``_handle_wave_only_unresolved`` (:2752) already avoid for the sibling
    wave-only conflation."""
    repo = tmp_path / "repo"
    _activate(repo)
    missing_path = repo / "does-not-exist.jsonl"

    first_exit, first_stdout, _ = _fire(
        repo, _envelope(str(missing_path), str(repo), stop_hook_active=False)
    )
    second_exit, second_stdout, _ = _fire(
        repo, _envelope(str(missing_path), str(repo), stop_hook_active=True)
    )

    for label, exit_code, stdout in (
        ("first fire", first_exit, first_stdout),
        ("re-fire", second_exit, second_stdout),
    ):
        assert exit_code == 0, (
            f"the SubagentStop protocol never blocks via exit code ({label}) "
            f"-- got exit {exit_code}"
        )
        assert _block_decision(stdout) is None, (
            f"a broken declared transcript path must NEVER emit a "
            f"`{{'decision': 'block'}}` body ({label}) -- that would "
            f"re-trigger Claude Code into an infinite re-fire loop -- got {stdout!r}"
        )


@pytest.mark.negative_at
def test_valid_atdd_pure_markers_still_emit_the_causal_envelope(
    tmp_path: Path,
) -> None:
    """AT8: a readable transcript that DOES carry valid atdd_pure markers
    must keep emitting its ``causal_envelope`` unchanged -- the fix for the
    inaccessible-transcript cases must never regress the genuine, resolvable
    dispatch return."""
    repo = tmp_path / "repo"
    _activate(repo)
    path = repo / "valid_markers.jsonl"
    _write_valid_atdd_pure_markers(path)

    exit_code, stdout, stderr = _fire(repo, _envelope(str(path), str(repo)))

    assert exit_code == 0, f"expected exit 0 -- got {exit_code} (stderr={stderr!r})"
    assert stderr == "", f"expected a silent stderr -- got {stderr!r}"
    payload = json.loads(stdout.strip())
    assert "causal_envelope" in payload, (
        f"expected the unchanged causal_envelope projection -- got {payload!r}"
    )
