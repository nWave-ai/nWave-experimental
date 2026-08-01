"""Step definitions + scenario bindings for the ledger-targeting acceptance.

Mandate-13 driving port: the production CLI entry point invoked as a subprocess
(`python -m des.cli.verify_deliver_integrity --feature-id <f> .`). The subprocess
boundary is the SUT surface (Layer 3 subprocess per nw-test-design-mandates).
No direct import of `_verify_atdd_pure` / `_shipped_slices` / `main` for
behavioral assertions -- only the `AtCompletionLedger` writer is used to seed
PRECONDITION ledger state (the world before the verifier runs), never the SUT.

Layer 3 ⇒ example-only (Mandate 9 + Mandate 11): no `@given` /
`RuleBasedStateMachine`. The finite, enumerable set of foreign pollutant slice
ids is covered by a `Scenario Outline` (parametrize-equivalent) -- a closed-world
finite domain, never PBT.

Set-algebra contract under test (F-DELIVER-INTEGRITY-LEDGER-TARGETING):
    unreconciled = (shipped MINUS verified) MINUS foreign_owned
where foreign_owned = the union, over every OTHER feature's ledger, of
    review_verdict_slices() UNION verified_slices()
(the loud-safe `shipped - verified` with only OTHER features' positively-owned
slices subtracted -- never an intersection against THIS feature's own ledger).

Two properties asserted as distinct scenarios:
  AT-1 (Scenario Outline): a co-resident feature's slice is excluded because a
       DISTINCT co-resident feature's ledger positively OWNS it (foreign_owned).
  AT-2 (regression-pin): an own-feature slice with NO ledger record is still
       reported -- in a single-feature repo foreign_owned is empty, so the
       formula degenerates to the loud-safe `shipped - verified` done-gate that
       the prior intersection-fix regressed.

F-PUSH-GATE-SLICE-ATTRIBUTION extends the same formula with a THIRD layer,
covering the case AT-1 does NOT: a co-resident feature's slice whose ledger is
NOT visible on disk in this worktree at all (the real swarm defect --
`.nwave/telemetry/atdd-pure/*.jsonl` is per-worktree and gitignored, so it
never travels with a merge). `foreign_owned` cannot subtract a ledger it
cannot see, so `candidate_unreconciled` is narrowed a second way: only a
slice-id the feature's OWN declared Slice-Plan claims (`feature-delta.md`,
git-free, travels with THIS feature's own tree) can ever be genuine debt.
  AT-3: a shipped slice this feature never declared is NOT reported
       unreconciled -- it is the distinct `could-not-attribute` third state,
       named on stdout (`unattributable_shipped_slices`), never blocking the
       push by itself.
  AT-4 (regression-pin, plan-aware): the Slice-Plan filter never WEAKENS
       genuine detection -- a slice the feature's OWN plan declares, shipped
       with no ledger record, still fails exactly like AT-2.

Fixture discipline: the git history and the ledger records are PRECONDITION
input state, NOT the expected output. The observable output is the verifier's
exit code + the `FeatureUnreconciled` / `FeatureReconciled` JSON payload on
stdout.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.des.acceptance.fix_deliver_integrity_ledger_targeting.steps.domain_types import (
    SliceSet,
)


scenarios("../ledger_targeting.feature")


# feedback_examine_surface_staleness_pin_worktree_local_invocation: `sys.executable`
# is the SHARED venv, whose editable `des` install resolves to whichever checkout
# it was last `pip install -e`d from -- NOT necessarily this worktree. Pin `src`
# on PYTHONPATH so the subprocess imports THIS worktree's `des.cli`, mirroring
# the sibling suite `gate-trailer-read-git-port-extract/steps/composition.py`.
REPO_ROOT = Path(__file__).resolve().parents[5]


# The feature under verification. The CLI receives this exact id via
# `--feature-id`, so reconciliation is scoped to THIS feature's ledger.
_FEATURE_UNDER_TEST = "feature-under-verification"


@dataclass
class _Ctx:
    repo_dir: Path
    feature_id: str = _FEATURE_UNDER_TEST
    completed: subprocess.CompletedProcess | None = None


@pytest.fixture
def ctx(tmp_path: Path) -> _Ctx:
    """A real temp git repo configured under atdd_pure workflow mode.

    The verifier reads the git log (`_shipped_slices`) and the per-feature
    AT-completion ledger; both live under this real repo. The deliver project
    dir is the repo root itself (`.`) so the CLI receives `.` as project_dir.
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@nwave.ai")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    nwave = repo / ".nwave"
    nwave.mkdir(parents=True, exist_ok=True)
    (nwave / "config.yaml").write_text(
        "workflow:\n  mode: atdd_pure\n", encoding="utf-8"
    )
    return _Ctx(repo_dir=repo)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _commit_with_slice_id(repo: Path, slice_id: str, marker: str) -> None:
    """Create one commit whose message carries a `Slice-Id:` trailer.

    `marker` keeps each commit's working-tree change unique so git accepts the
    commit. The trailer is the only payload the verifier reads.
    """
    (repo / f"{marker}.txt").write_text(marker, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "commit",
        "-q",
        "-m",
        f"feat({marker}): seed slice commit\n\nSlice-Id: {slice_id}",
    )


def _ledger_for(ctx: _Ctx, feature_id: str):
    from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

    return AtCompletionLedger(feature_id, ctx.repo_dir)


def _payload(ctx: _Ctx) -> dict:
    """The structured JSON event the verifier emits on stdout (last JSON line)."""
    assert ctx.completed is not None
    for line in reversed(ctx.completed.stdout.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise AssertionError(
        "no JSON payload on stdout; "
        f"stdout={ctx.completed.stdout!r} stderr={ctx.completed.stderr!r}"
    )


# --- Given: this feature's git commits ---------------------------------------


@given(
    parsers.parse('a shared git history carrying this feature\'s slices "{literal}"')
)
def given_own_commits(ctx: _Ctx, literal: str) -> None:
    for slice_id in SliceSet.parse(literal):
        _commit_with_slice_id(ctx.repo_dir, slice_id, f"own-{slice_id}")


@given(
    parsers.parse(
        'the same history also carries another feature\'s slice "{foreign_slice}" '
        "with no visible ledger"
    )
)
def given_foreign_commit_no_ledger(ctx: _Ctx, foreign_slice: str) -> None:
    # F-PUSH-GATE-SLICE-ATTRIBUTION, the real swarm defect: the co-resident
    # commit lands in the SAME git history (so it is in `shipped`), but --
    # UNLIKE `given_foreign_commit` below -- NO ledger is seeded for it
    # anywhere. This is the per-worktree-gitignored-telemetry reality: a
    # worktree that only ever ran ITS OWN feature has no ledger for a
    # co-resident feature merged upstream of its fork point, so
    # `_foreign_owned_slices` cannot see it and cannot subtract it.
    _commit_with_slice_id(
        ctx.repo_dir, foreign_slice, f"foreign-noledger-{foreign_slice}"
    )


@given(parsers.parse('this feature declares a Slice-Plan naming "{literal}"'))
def given_slice_plan(ctx: _Ctx, literal: str) -> None:
    # F-PUSH-GATE-SLICE-ATTRIBUTION: the property that travels with THIS
    # feature's own tree at HEAD -- its declared Slice-Plan, read from
    # feature-delta.md, git-free. Mirrors the minimal table shape
    # `_declared_slice_plan_slice_ids` parses (the `Slice` column only).
    feature_dir = ctx.repo_dir / "docs" / "feature" / ctx.feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    rows = "\n".join(
        f"| {slice_id} | value statement | Planned | | |"
        for slice_id in SliceSet.parse(literal)
    )
    (feature_dir / "feature-delta.md").write_text(
        f"# Feature Delta: {ctx.feature_id}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement | Status | Annotation | Justification |\n"
        "|---|---|---|---|---|\n"
        f"{rows}\n",
        encoding="utf-8",
    )


@given(
    parsers.parse(
        'the same history also carries another feature\'s slice "{foreign_slice}"'
    )
)
def given_foreign_commit(ctx: _Ctx, foreign_slice: str) -> None:
    # The co-resident feature's commit lands in the SAME git history (so the
    # foreign slice is in `shipped`). Its Slice-Id trailer is the cross-feature
    # pollutant that must NOT leak into this feature's reconciliation.
    _commit_with_slice_id(ctx.repo_dir, foreign_slice, f"foreign-{foreign_slice}")
    # The co-resident FEATURE positively OWNS this slice in its OWN ledger (a
    # DISTINCT feature id, never `ctx.feature_id`). Under the corrected
    # foreign-owned-subtraction model, `_foreign_owned_slices` unions
    # `review_verdict_slices() | verified_slices()` over every OTHER feature's
    # ledger; the scenario narrative ("another FEATURE's slice") already implies
    # that feature owns it. Seeding the verified record here is the precondition
    # that makes `foreign_owned` non-empty so the pollutant is subtracted.
    _ledger_for(ctx, "co-resident-feature").append_gate_event(
        "SliceCommitVerified", foreign_slice
    )


# --- Given: this feature's ledger records ------------------------------------


@given(parsers.parse('this feature\'s ledger reviewed slices "{literal}"'))
def given_reviewed(ctx: _Ctx, literal: str) -> None:
    ledger = _ledger_for(ctx, ctx.feature_id)
    for slice_id in SliceSet.parse(literal):
        ledger.append_review_verdict(slice_id, {})


@given(parsers.parse('this feature\'s ledger verified slices "{literal}"'))
def given_verified(ctx: _Ctx, literal: str) -> None:
    ledger = _ledger_for(ctx, ctx.feature_id)
    for slice_id in SliceSet.parse(literal):
        ledger.append_gate_event("SliceCommitVerified", slice_id)


@given("this feature's ledger recorded a complete feature-end cycle")
def given_feature_end_complete(ctx: _Ctx) -> None:
    # Seeds the per-feature ledger FILE so the reconciliation sweep runs
    # (an absent ledger short-circuits to a different "ledger missing"
    # violation, never reaching the shipped-vs-verified reconciliation). The
    # feature-end cycle records carry NO slice record for any committed slice,
    # so a committed-but-unrecorded slice still surfaces as unreconciled.
    from des.adapters.driven.logging.at_completion_ledger import (
        EBATCH_REFACTOR_COMPLETED,
        FEATURE_END_REVIEW_VERDICT,
    )

    ledger = _ledger_for(ctx, ctx.feature_id)
    ledger.append_feature_end_event(EBATCH_REFACTOR_COMPLETED)
    ledger.append_feature_end_event(FEATURE_END_REVIEW_VERDICT, verdict_hash="deadbeef")
    ledger.append_walking_skeleton_gate_ran()
    ledger.append_walking_skeleton_tier_verified("tier-sml")
    ledger.append_environmental_e2e_gate_ran()
    ledger.append_full_suite_leg_ran()
    ledger.append_coverage_map_verified_at_distill_exit()
    ledger.append_coverage_map_verified_at_deliver_exit()


# --- When: the driving port (CLI subprocess) ---------------------------------


@when("the operator verifies deliver integrity for this feature")
def when_verify(ctx: _Ctx) -> None:
    cmd = [
        sys.executable,
        "-m",
        "des.cli.verify_deliver_integrity",
        "--feature-id",
        ctx.feature_id,
        ".",
    ]
    env = {**os.environ, "NWAVE_FRESHNESS": "skip"}
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    ctx.completed = subprocess.run(
        cmd,
        cwd=ctx.repo_dir,
        capture_output=True,
        text=True,
        env=env,
    )


# --- Then: observable outcomes (exit code + JSON payload on stdout) ----------


@then("the verifier reports the feature has unreconciled work")
def then_unreconciled(ctx: _Ctx) -> None:
    assert ctx.completed is not None
    assert ctx.completed.returncode == 1, (
        f"expected exit 1, got {ctx.completed.returncode}; "
        f"stdout={ctx.completed.stdout!r} stderr={ctx.completed.stderr!r}"
    )
    payload = _payload(ctx)
    assert payload.get("event") == "FeatureUnreconciled", (
        f"expected FeatureUnreconciled event, got {payload!r}"
    )


@then(parsers.parse('the only unreconciled slice reported is "{slice_id}"'))
def then_only_slice(ctx: _Ctx, slice_id: str) -> None:
    # Authoritative bug-catcher: the reported set must be EXACTLY the expected
    # one unshipped slice. Any cross-feature slice in the list reds here.
    payload = _payload(ctx)
    reported = payload.get("unreconciled_slices")
    assert reported == [slice_id], (
        f"expected unreconciled_slices == [{slice_id!r}], got {reported!r} "
        "(a foreign feature's slice leaked into reconciliation, or the "
        "own-feature no-record slice was wrongly dropped)"
    )


@then(parsers.parse('the reconciliation excludes the foreign slice "{foreign_slice}"'))
def then_foreign_absent(ctx: _Ctx, foreign_slice: str) -> None:
    # Explicit cross-feature-leak guard, parametrized over the pollutant value
    # so the spec proves the foreign slice is filtered regardless of its id.
    payload = _payload(ctx)
    reported = payload.get("unreconciled_slices", [])
    assert foreign_slice not in reported, (
        f"foreign slice {foreign_slice!r} leaked into unreconciled_slices="
        f"{reported!r} (cross-feature reconciliation defect)"
    )


@then("the verifier reports the feature is reconciled")
def then_reconciled(ctx: _Ctx) -> None:
    assert ctx.completed is not None
    assert ctx.completed.returncode == 0, (
        f"expected exit 0, got {ctx.completed.returncode}; "
        f"stdout={ctx.completed.stdout!r} stderr={ctx.completed.stderr!r}"
    )
    payload = _payload(ctx)
    assert payload.get("event") == "FeatureReconciled", (
        f"expected FeatureReconciled event, got {payload!r}"
    )


@then(parsers.parse('the verifier names "{slice_id}" as unattributable, not blocking'))
def then_unattributable_named(ctx: _Ctx, slice_id: str) -> None:
    # GDP-8 arity corollary: the could-not-attribute third state must reach the
    # AGGREGATE verdict -- named, not silently dropped -- while never blocking
    # the push by itself (the surrounding scenario already asserted exit 0 /
    # FeatureReconciled via `then_reconciled`).
    payload = _payload(ctx)
    reported = payload.get("unattributable_shipped_slices", [])
    assert slice_id in reported, (
        f"expected {slice_id!r} named in unattributable_shipped_slices, got "
        f"{reported!r} (the could-not-attribute state was silently dropped "
        "or the pollutant was wrongly promoted to a hard-block)"
    )
    reconciled = payload.get("reconciled_slices", [])
    assert slice_id not in reconciled, (
        f"{slice_id!r} was wrongly reported as THIS feature's own reconciled "
        f"slice: {reconciled!r} (cross-feature misattribution, inverted)"
    )
