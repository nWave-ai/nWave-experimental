"""pytest-bdd binding: CommitTrailerReadPort commit_messages port-contract
hardening (slice-02 -- D1 many-cardinality + D2/D3 non-existent/non-worktree
path degrades LOUD to Indeterminate).

Driving port: ``GitCommitTrailerReadAdapter.commit_messages(repo: Path)`` at
the adapter boundary -- the port-contract variant sanctioned by the DESIGN
Driving Surface table ("ATs drive the adapter directly or via a thin harness;
no CLI surface change"). Step bodies delegate to the composition root
(``composition_slice_02.py``); no business logic lives in any step body
(Mandate-12 criterion 3: each body is a single delegation).

The ``scenarios(...)`` call binds every scenario in the slice-02 ``.feature``
file via the RELATIVE path from this steps/ module -- the proven-collecting
form used by slice-01 of this feature. Step literal text is unique within this
feature directory (S1 step-text-uniqueness invariant: no overlap with the
slice-01 step literals in test_slice_01_git_absent_indeterminate_refusal.py).

GREEN-on-author (all three scenarios, empirically confirmed at authorship HEAD):
  - many-cardinality (D1): adapter already returns all N messages -> GREEN.
  - non-existent path (D2): FileNotFoundError caught -> Indeterminate -> GREEN.
  - not-a-work-tree (D3): CalledProcessError caught -> Indeterminate -> GREEN.
All three are COVERAGE-PIN ATs: existing correct behavior is pinned so future
refactors of the exception-translation path cannot silently regress these
partitions.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from pytest_bdd import given, scenarios, then, when

from .composition_slice_02 import CommitMessagesComposition


scenarios("../slice-02-commit-messages-port-contract-hardening.feature")


@pytest.fixture
def composition() -> Iterator[CommitMessagesComposition]:
    comp = CommitMessagesComposition()
    yield comp
    comp.cleanup()


# --- Given -------------------------------------------------------------------


@given("a git work-tree containing three commits with distinct message bodies")
def given_real_worktree_three_commits(composition: CommitMessagesComposition) -> None:
    composition.given_real_worktree_with_three_commits()


@given("a repo path that does not exist on the filesystem")
def given_absent_path(composition: CommitMessagesComposition) -> None:
    composition.given_absent_path()


@given("a directory that exists on the filesystem but contains no git repository")
def given_existing_non_worktree(composition: CommitMessagesComposition) -> None:
    composition.given_existing_non_worktree_dir()


# --- When --------------------------------------------------------------------


@when("the port reads the full commit-message stream from that work-tree")
def when_reads_from_worktree(composition: CommitMessagesComposition) -> None:
    composition.when_port_reads_commit_messages()


@when("the port attempts to read the commit-message stream from that absent path")
def when_reads_from_absent_path(composition: CommitMessagesComposition) -> None:
    composition.when_port_reads_commit_messages()


@when(
    "the port attempts to read the commit-message stream from that non-work-tree path"
)
def when_reads_from_non_worktree(composition: CommitMessagesComposition) -> None:
    composition.when_port_reads_commit_messages()


# --- Then --------------------------------------------------------------------


@then("the returned stream contains all three commit message bodies")
def then_contains_all_bodies(composition: CommitMessagesComposition) -> None:
    composition.then_stream_contains_all_known_bodies()


@then("the stream is not truncated to fewer messages than the repo holds")
def then_not_truncated(composition: CommitMessagesComposition) -> None:
    composition.then_stream_not_truncated()


@then("the port read does not modify the work-tree")
def then_does_not_modify_worktree(composition: CommitMessagesComposition) -> None:
    # Pure-read universe guard already asserted inside the When-step;
    # this Then-step affirms the run completed and re-states the contract.
    composition.then_result_is_not_none()


@then("the port signals a loud cannot-read refusal rather than an empty message stream")
def then_signals_loud_refusal(composition: CommitMessagesComposition) -> None:
    composition.then_result_is_indeterminate()


@then("the cannot-read refusal carries a non-empty reason")
def then_refusal_has_reason(composition: CommitMessagesComposition) -> None:
    composition.then_indeterminate_has_reason()


@then("the cannot-read refusal is structurally identical to the absent-path refusal")
def then_refusal_matches_absent_path(composition: CommitMessagesComposition) -> None:
    composition.then_indeterminate_shape_matches_absent_path()
