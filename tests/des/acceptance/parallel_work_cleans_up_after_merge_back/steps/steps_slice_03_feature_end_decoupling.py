"""Step bodies for parallel-work-cleans-up-after-merge-back slice-03 (a
bugfix's cleanup never waits on a feature-end it doesn't owe).

Only 2 Given steps are authored fresh here -- every When/Then this slice
needs is REUSED VERBATIM from slice-01's own step module
(`steps_slice_01_worktree_cleanup`), imported into the pytest-bdd binding
module (`test_slice_03_feature_end_decoupling.py`), not redefined here.
Those reused Then bodies already assert `new_feature_end_pending_count == 0`
as part of their combined `assert_state_delta` call -- exactly the
read/wait-side proof D-D6's decoupling guarantee needs, whether the
pre-sweep ledger count is 0 (untouched, scenario 2) or 1 (an unrelated
pre-existing record, scenarios 1+3): the DELTA stays 0 either way.

Mandate-12 criterion 2: `PERSONA_WORKTREE_NAME` is the typed-parameter
lookup this file performs -- never a raw string dispatch on `persona`.

Mandate 9 v2: layer 3 (real git repo + real ledger JSONL, @real-io) =>
example-only. PBT machinery intentionally NOT imported (Mandate 11).
"""

from __future__ import annotations

from pytest_bdd import given, parsers


PERSONA_WORKTREE_NAME: dict[str, str] = {
    "a bugfix": "fix-race-window",
    "a feature slice": "feature-slice-09",
}


@given("a feature-end-pending record already exists for an unrelated unit of work")
def given_feature_end_pending_already_exists(cleanup_fixture, state_01) -> None:
    cleanup_fixture.seed_existing_feature_end_pending()


@given(
    parsers.parse(
        "a worktree named for {persona}, whose branch is confirmed merged "
        "into the target branch and still registered"
    )
)
def given_persona_worktree_confirmed_merged(cleanup_fixture, state_01, persona) -> None:
    name = PERSONA_WORKTREE_NAME[persona]  # typed-parameter validation
    cleanup_fixture.ensure_trunk_repo()
    cleanup_fixture.create_linked_worktree(name)
    cleanup_fixture.confirm_merge_back(name)
