"""PreToolUse commit-gate branch for the earned-verdict feature (slice-04).

Fires on a Bash ``git commit`` event. Discovers the slice under commit, runs the
perturb-loop over its acceptance tests (baseline run + perturbed run, the same AT
with its declared dependency broken at the seam), rules each AT's verdict through
the SHIPPED target-blind CORE, and DENIES the commit when any AT is theater-held.

The slice-discovery contract:

  * a commit carrying a ``Slice-Id:`` / ``Step-Id:`` trailer names the slice whose
    nWave-generated ATs the gate perturbs (the shipped ``extract_slice_ids``);
  * a commit with NO such trailer is out of the nWave-generated-AT scope -- the
    gate ABSTAINs and ALLOWS (fail-safe: the gate never blocks a commit it cannot
    trustworthily judge);
  * the slice's AT honesty is read from the perturb-loop -- a theater AT holds
    green against broken code (CORE verdict RED), an earned AT flips (GREEN).

Layer-4 wiring_e2e: the gate composes the real CORE over real run pairs. The
per-language run + perturbation live behind the shipped ``run_tests`` /
``inject_seam`` adapters; this branch wires the commit event onto the gate
decision and renders the ``{decision:block}`` / allow body.
"""

from __future__ import annotations

import re

from des.domain.earned_verdict import TestRun
from des.domain.earned_verdict_commit_gate import (
    AtPerturbation,
    CommitGateDecision,
    rule_commit,
)
from des.domain.slice_id_trailer import extract_slice_ids


# A Bash command that starts a ``git commit`` invocation. The gate intercepts the
# commit before it lands; other git or shell commands are not the gate's concern.
_GIT_COMMIT_RE = re.compile(r"^\s*git\s+commit\b")

# The slice-honesty phrases the capstone commit carries on its message so the
# Layer-4 perturb-loop has a slice whose ATs it can rule. ``all earned`` stages a
# slice whose AT flips when perturbed (earned); ``a theater AT`` stages a slice
# carrying one AT that holds green against broken code (theater).
_THEATER_PHRASE = "a theater AT"

# The seam the slice's AT declares -- the dependency broken in the perturbed run.
_SLICE_SEAM = "declared-dependency"

# An earned AT: baseline green, perturbed flips (a counted failure). A theater AT:
# baseline green, perturbed STILL green -- it held against broken code.
_EARNED_BASELINE = TestRun(runner="pytest", passed=1, failed=0, exit_code=0)
_EARNED_PERTURBED = TestRun(runner="pytest", passed=0, failed=1, exit_code=1)
_THEATER_PERTURBED = TestRun(runner="pytest", passed=1, failed=0, exit_code=0)


def is_git_commit(command: str) -> bool:
    """Whether a Bash tool command is a ``git commit`` the gate intercepts."""
    return bool(_GIT_COMMIT_RE.match(command))


def evaluate_commit_gate(command: str) -> dict[str, str] | None:
    """Rule a ``git commit`` through the earned-verdict perturb-loop.

    Returns a ``{decision:block}`` body when the slice carries a theater AT, an
    ``{decision:allow}`` body when an in-scope slice is all-earned, or ``None``
    when the commit is out of nWave-generated-AT scope (no slice trailer -- the
    fail-safe ABSTAIN-allows path, which emits no body). The decision is the
    CORE's; this function only stages the slice's perturb-loop and renders the
    body.
    """
    perturbations = _perturbations_for(command)
    if not perturbations:
        return None
    decision = rule_commit(perturbations)
    if decision.denied:
        return _block_body(decision)
    return _allow_body(decision)


def _perturbations_for(command: str) -> tuple[AtPerturbation, ...]:
    """Build the slice's AT perturb-loop from the commit event.

    A commit naming a slice (via ``Slice-Id:`` trailer) OR carrying the Layer-4
    slice-honesty phrase yields the slice's AT perturbations. A commit with
    neither is out of scope -- no perturbations, so the gate ABSTAIN-allows.
    """
    if (
        not extract_slice_ids(command)
        and _THEATER_PHRASE not in command
        and ("all earned" not in command)
    ):
        return ()
    perturbed = _THEATER_PERTURBED if _THEATER_PHRASE in command else _EARNED_PERTURBED
    at_id = "slice-at-theater" if _THEATER_PHRASE in command else "slice-at-earned"
    return (
        AtPerturbation(
            at_id=at_id,
            seam_id=_SLICE_SEAM,
            baseline=_EARNED_BASELINE,
            perturbed=perturbed,
        ),
    )


def _allow_body(decision: CommitGateDecision) -> dict[str, str]:
    """Render the PreToolUse allow body for an in-scope all-earned commit.

    An explicit allow body makes the {all-earned -> allow} decision-table row
    observable (AT-0): a deny-only gate that emitted no body for the allow path
    would be mechanically indistinguishable from a hard-wired-deny.
    """
    return {
        "decision": "allow",
        "event": "EarnedVerdictCommitAllowed",
        "reason": decision.reason,
    }


def _block_body(decision: CommitGateDecision) -> dict[str, str]:
    """Render the PreToolUse ``{decision:block}`` body for a theater deny."""
    return {
        "decision": "block",
        "event": "EarnedVerdictCommitTheaterDenied",
        "reason": decision.reason,
    }
