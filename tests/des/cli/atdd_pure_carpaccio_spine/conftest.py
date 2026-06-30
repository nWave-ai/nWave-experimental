"""pytest-bdd configuration for the simplify-atdd-pure-carpaccio-spine AT set.

DISTILL-authored RED scaffold (ADR-025): every scenario in the four carpaccio
slice `.feature` files is authored ahead of the implementation. The composition
root (`steps/composition.py`) drives the production simplified-spine surfaces;
the slice SUTs (`run_contract_gate`, `verify_slice_commit`, the M-2 hook,
`verify_deliver_integrity`) are EXTEND targets that exist on master, so imports
succeed (no BROKEN classification); every scenario reds for the RIGHT reason --
missing slice-NN functionality (Mandate 7).

The four carpaccio slices decompose the simplification's DISCUSS slice plan to
the `atdd_pure.carpaccio_slice_max: 3` ceiling (each slice <= 3 `@slice-NN`
scenario blocks). slice-01 is the `@walking_skeleton @wiring_e2e` vertical.

The collection hook below marks every author-ahead RED-scaffold scenario
`xfail(strict=True)` until DELIVER greens it. xfail keeps the suite green so the
full-suite pre-commit gate can accept the DISTILL commit; `strict=True` means an
UNEXPECTED pass (the scaffold quietly working) fails the suite -- the xfail is a
contract, not a mute. DELIVER removes a slice's tag from `_RED_SCAFFOLD_SLICES`
at the RED phase of that slice, one slice at a time, runs it (genuine RED,
fails-for-the-right-reason), then GREENs it.

To enable a single slice for DELIVER, narrow `_RED_SCAFFOLD_SLICES` to exclude
that slice's tag, or delete the hook once all slices are green. Mechanism
mirrored verbatim from
`tests/des/acceptance/walking_skeleton_production_like_gate/conftest.py`.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here. `pytest_collection_modifyitems` runs session-wide on EVERY
# collected item; without this scope the `slice-NN` keyword match would also
# xfail unrelated suites that tag their own scenarios `@slice-NN`.
_SUITE_DIR = Path(__file__).parent


# Slices still RED (author-ahead). DELIVER removes a tag as its slice greens.
# All four slices are author-ahead RED scaffolds -- there is no pre-existing
# GREEN production code for any slice of this feature.
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


# A single author-ahead RED-scaffold scenario BLOCK inside an otherwise-green
# slice. `_RED_SCAFFOLD_SLICES` is whole-slice; a block tagged
# `@red_scaffold_distill` is the granular escape hatch.
#
# DELIVER re-A_GREEN (slice-01): the slice-01 `@red_scaffold_distill` blocks are
# un-xfailed here -- `_mode_feature_scoped` now routes through real node-id
# collection, so both the walking-skeleton happy path and the malformed rows go
# live. The block keyword is emptied so no block is held xfail; slices 03-04
# stay whole-slice xfail via `_RED_SCAFFOLD_SLICES`.
_RED_SCAFFOLD_BLOCK_KEYWORD = ""


# slice-04 -> no scaffold-coupling escape hatch. slice-04's error scenario was
# re-scoped (C_REVIEWER_AUDIT) to drive the M-2 backstop FROM WITHIN the
# new-spine four-phase flow (`deliver_slice_on_new_spine`) -- not as a
# standalone `run_commit_backstop_hook` poke. The new-spine flow does not exist
# until the slice-03 skill rewrite + new-spine orchestration land, so BOTH
# slice-04 scenarios are genuinely RED and stay whole-slice `xfail(strict=True)`
# via `_RED_SCAFFOLD_SLICES`. No early-pass coupling to slice-03's hook remains,
# so the former `_SLICE04_M2_COUPLED_SCENARIO` non-strict escape hatch is gone.


# slice-02 RED-scaffold BLOCKS (C_REVIEWER_AUDIT BLOCKER closure). The
# strengthened slice-02 ATs assert the ledger seam the carpaccio chain reads
# (`AtCompletionLedger.verified_slices()` at the telemetry substrate, with the
# M7 `seq` / `record_hash` integrity fields) plus C4a re-run idempotency. The
# two POSITIVE-seam scenarios are genuinely RED -- production still writes the
# wrong substrate -- and carry `@slice02_seam_scaffold`; they are held
# xfail(strict=True) so an accidental pass (the seam quietly working) fails the
# suite -- the xfail is a contract, not a mute. The two NEGATIVE outline rows
# (E1/E2 fails -> no record) are substrate-agnostic ("no record anywhere") and
# stay GREEN -- they carry no block tag. DELIVER empties this keyword when the
# crafter lands the production seam fix (write via `append_gate_event`).
#
# DELIVER Phase D (slice-02 BLOCKER closure): the production seam fix has
# landed -- `_append_slice_commit_verified` now writes through
# `AtCompletionLedger.append_gate_event`, so the two POSITIVE-seam scenarios
# are GREEN. The keyword is emptied; no slice-02 block is held xfail.
_SLICE02_SEAM_SCAFFOLD_KEYWORD = ""


# slice-03 RED-scaffold BLOCK (C_REVIEWER_AUDIT MEDIUM-gap closure). The M-2
# backstop decision-table Outline (allow / refuse / abstain) is GREEN -- the
# hook ships and all three rows pass, including the `NotASliceCommit` abstain
# row (the audit BLOCKER, now witnessed). The feature-end reconciliation
# Outline drives the DDD-10 `Slice-Id:`<->`SliceCommitVerified` reconciliation
# EXTEND of `verify_deliver_integrity` -- that EXTEND has NOT landed, so the CLI
# emits no `FeatureReconciled` / `FeatureUnreconciled` structured verdict and
# both Outline rows are genuinely RED (fails-for-the-right-reason: the DDD-10
# reconciliation behaviour is missing, not an argparse/setup error).
#
# The reconciliation Outline carries `@red_scaffold_reconciliation`.
#
# DELIVER slice-03 re-A_GREEN (history): the DDD-10 reconciliation EXTEND of
# `verify_deliver_integrity._verify_atdd_pure` landed -- the atdd_pure path now
# computes the `Slice-Id:`<->`SliceCommitVerified` set-difference and emits the
# `FeatureReconciled` / `FeatureUnreconciled` structured verdict. The reconciled
# and unreconciled Outline rows went live and pass.
#
# Re-C_REVIEWER_AUDIT BLOCKER (this revision): the reconciliation Outline gained
# a third row -- `feature-end-cycle-incomplete`. A feature whose every Slice-Id
# commit IS recorded (the sweep clears) but whose ledger carries no
# `EBatchRefactorCompleted` / `FeatureEndReviewVerdict` record must FAIL: the
# feature-end cycle never ran. The production short-circuits to
# `FeatureReconciled` exit 0 the moment the sweep clears (it `return 0`s before
# reaching the feature-end-cycle check), so that third row is genuinely RED --
# the verdict does not yet COMPOSE the two checks.
#
# DELIVER slice-03 re-A_GREEN (this revision): the compose-order fix landed --
# the reconciliation-success path now FALLS THROUGH to the feature-end-cycle
# check instead of `return 0`. A feature whose sweep clears but whose ledger
# carries no `EBatchRefactorCompleted` / `FeatureEndReviewVerdict` record now
# fails with a structured `FeatureEndCycleIncomplete` verdict; a feature with
# both checks clearing emits `FeatureReconciled` exit 0. All three
# reconciliation Outline rows go live. The keyword is emptied.
_SLICE03_RECONCILIATION_SCAFFOLD_KEYWORD = ""


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN."""
    xfail_slice = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=True,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    xfail_block = pytest.mark.xfail(
        reason=(
            "RED scaffold block -- DISTILL-authored happy path, awaiting "
            "DELIVER real node-id collection"
        ),
        strict=False,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    xfail_slice02_seam = pytest.mark.xfail(
        reason=(
            "slice-02 seam RED scaffold -- DISTILL-authored, asserts the "
            "carpaccio-chain ledger seam; awaiting DELIVER's production seam fix"
        ),
        strict=True,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    xfail_slice03_reconciliation = pytest.mark.xfail(
        reason=(
            "slice-03 reconciliation RED scaffold -- the feature-end-cycle-"
            "incomplete Outline row is genuinely RED (the verdict short-circuits "
            "to FeatureReconciled before the feature-end-cycle check); the "
            "reconciled / unreconciled rows pass live, so the marker is "
            "non-strict to tolerate their XPASS. Awaiting DELIVER's "
            "compose-the-two-checks fix"
        ),
        strict=False,
        raises=(AssertionError, ModuleNotFoundError, ImportError),
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        # Serialize these cwd=_REPO_ROOT dogfood tests into the shared real-repo
        # xdist group so (under `--dist=loadgroup`) they never run on a worker
        # concurrent with another test mutating the repo's `.nwave/telemetry`
        # substrate. Fixes the order-dependent slice-04 "refuses unverified slice"
        # failure exposed when test-suite deletions redistributed the xdist load.
        item.add_marker(pytest.mark.xdist_group("real_repo_scan"))
        keywords = set(item.keywords)
        if keywords & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail_slice)
        elif _SLICE02_SEAM_SCAFFOLD_KEYWORD and (
            _SLICE02_SEAM_SCAFFOLD_KEYWORD in keywords
        ):
            item.add_marker(xfail_slice02_seam)
        elif _SLICE03_RECONCILIATION_SCAFFOLD_KEYWORD and (
            _SLICE03_RECONCILIATION_SCAFFOLD_KEYWORD in keywords
        ):
            item.add_marker(xfail_slice03_reconciliation)
        elif _RED_SCAFFOLD_BLOCK_KEYWORD and _RED_SCAFFOLD_BLOCK_KEYWORD in keywords:
            item.add_marker(xfail_block)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
