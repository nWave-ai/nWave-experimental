"""PreToolUse commit-gate branch for the earned-verdict feature (slice-04).

RETIRED FROM DECIDING REAL COMMIT TRAFFIC (2026-07-29, hook-audit fix, GDP-8).

``evaluate_commit_gate`` stays wired on the ``git commit`` path (deny-wins
ordering, ADR-CA-006 D4) but now ALWAYS returns ``None`` (ABSTAIN). Prior to
this fix it decided a commit's honesty by matching literal substrings
(``"a theater AT"`` / ``"all earned"``) in the raw ``git commit`` command text,
or by fabricating a hard-coded ``TestRun`` pair the instant a ``Slice-Id:``
trailer was present -- deciding on the commit's DESIGNATION (its text) rather
than the PROPERTY the gate exists to measure (whether the slice's acceptance
tests actually flip red when their dependency is broken). Every real slice
commit (which carries a ``Slice-Id:`` trailer by construction, per
``des commit-slice``) was therefore unconditionally ruled "earned" without a
single test ever having been re-run -- a silent-wrong ALLOW on every commit,
never a genuine theater catch. GDP-6 forbids exactly this: a control that
cannot verify the property it claims to check must degrade LOUD or
INDETERMINATE, never fabricate a pass.

Why retire instead of arm: ruling a real commit honestly requires resolving
"which acceptance tests belong to the slice under commit" and "what seam does
each one declare" into real baseline/perturbed ``nwave.test_result.v1`` runs
via the shipped ``run_tests`` (slice-02) / ``inject_seam`` (slice-03) adapters.
That slice->AT->seam-manifest resolution does not exist anywhere in this repo
today (verified: ``nwave.seam_manifest.v1`` is declared only by this feature's
OWN test fixtures, never by DISTILL's generated-AT scaffolding) -- the
feature-delta's "generated ATs carry a seam by construction via scaffold
ADR-028" claim does not hold; ADR-028 is the unrelated atdd-pure roadmap-free
spine ADR. Building that resolver is a real, multi-slice feature (a proper
DESIGN->DISTILL->DELIVER cycle), not a hook bugfix. Until that slice ships,
the only honest behaviour on real traffic is ABSTAIN.

The CORE (:mod:`des.domain.earned_verdict`), the commit-gate composition
(:mod:`des.domain.earned_verdict_commit_gate`), the self-test
(:mod:`des.cli.earned_verdict_self_test`), and the real per-language ports
(:mod:`des.cli.run_tests`, :mod:`des.cli.inject_seam`) are unaffected -- they
are genuine, real infrastructure a future slice can wire honestly. Only the
commit-message-text discriminator in THIS module is retired.
"""

from __future__ import annotations

import re


# A Bash command that starts a ``git commit`` invocation. The gate intercepts the
# commit before it lands; other git or shell commands are not the gate's concern.
_GIT_COMMIT_RE = re.compile(r"^\s*git\s+commit\b")


def is_git_commit(command: str) -> bool:
    """Whether a Bash tool command is a ``git commit`` the gate intercepts."""
    return bool(_GIT_COMMIT_RE.match(command))


def evaluate_commit_gate(command: str) -> dict[str, str] | None:
    """Rule a ``git commit``. Always ABSTAINs (returns ``None``) today.

    ``command`` is intentionally unused: no fact reachable from the raw commit
    text can honestly stand in for a real per-AT perturb-loop result (see the
    module docstring). Returning ``None`` here means "out of scope for this
    gate" -- the caller (``pre_tool_use_handler.handle_pre_tool_use``) falls
    through to the commit-attribution path unchanged, exactly as it does for
    any other commit the gate does not have a trustworthy verdict for.
    """
    del command  # no reachable fact to decide on; see module docstring
    return None
