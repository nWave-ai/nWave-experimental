"""Step definitions: des commit-slice stamps the Slice-Id trailer (C9).

Binds the slice-01 ``.feature`` scenarios to the production-wired
``CommitSliceComposition`` driving the REAL ``commit_slice.main`` over a hermetic
tmp_path git repo. Layer 3 acceptance (CLI subprocess-class driving port +
real-IO git work-tree).

Paradigm (Mandate 9/11): example-only, no PBT machinery. The four ACs form a
finite, enumerable closed set of message/arg arrangements (arg-only / message-
carried / neither), so a small set of explicit examples is the correct paradigm;
the sad path (the refuse-if-absent RED path, AC-3) is enumerated explicitly,
never PBT-generated -- this is a Layer-3 surface.

Mandate-8 (state-delta): the observables here are single committed-artifact
outcomes -- a trailer's presence / count / the exit code / the emitted event --
each a direct port-exposed observation of the committed git state, not a multi-
field struct delta. So the Then steps assert the single observable directly
(layers 3+ may use traditional assertions; the Universe is the committed message
+ exit code).

Step bodies delegate to the composition (Mandate-12 criterion 3): each body is a
typed lookup plus a single composition call, no inline business logic / control
flow.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from .composition import CommitOutcome, CommitSliceComposition
from .domain_types import CommitMessageBody, SliceId


scenarios("../slice-01-commit-slice-slice-id-trailer.feature")


@pytest.fixture
def composition(tmp_path: Path) -> CommitSliceComposition:
    """Production-wired composition root over a hermetic tmp_path git repo."""
    return CommitSliceComposition(tmp_path / "repo")


# --- Given -------------------------------------------------------------------


@given("a hermetic git repo with a staged change ready to commit")
def given_staged_change(composition: CommitSliceComposition) -> None:
    composition.given_staged_change()


@given("the slice-commit message body carries no Slice-Id trailer")
def given_message_without_slice_id(composition: CommitSliceComposition) -> None:
    composition.given_message_body(
        CommitMessageBody("feat(slice): add the new slice behaviour")
    )


@given(
    parsers.parse(
        "the slice-commit message body already carries the trailer "
        '"Slice-Id: {slice_id}"'
    )
)
def given_message_with_slice_id(
    composition: CommitSliceComposition, slice_id: str
) -> None:
    composition.given_message_body(
        CommitMessageBody(
            f"feat(slice): add the new slice behaviour\n\nSlice-Id: {slice_id}"
        )
    )


# --- When --------------------------------------------------------------------


@when(
    parsers.parse('the slice is committed with slice id "{slice_id}"'),
    target_fixture="outcome",
)
def when_committed_with_slice_id(
    composition: CommitSliceComposition, slice_id: str
) -> CommitOutcome:
    return composition.commit_slice(SliceId(slice_id))


@when("the slice is committed with no slice id passed", target_fixture="outcome")
def when_committed_without_slice_id(
    composition: CommitSliceComposition,
) -> CommitOutcome:
    return composition.commit_slice(None)


# --- Then --------------------------------------------------------------------


@then(parsers.parse('the committed slice commit carries the trailer "{trailer}"'))
def then_carries_trailer(outcome: CommitOutcome, trailer: str) -> None:
    # trailer == "Slice-Id: slice-01"; observe through the committed HEAD message.
    expected_slice = trailer.split(":", 1)[1].strip()
    slice_ids = CommitSliceComposition.slice_ids_in(outcome.head_message)
    assert outcome.exit_code == 0, (
        f"expected commit_slice to succeed and stamp {trailer!r}, but it exited "
        f"{outcome.exit_code} (active-RED at HEAD: --slice-id is not a recognised "
        "argument -> argparse refuses it -> no commit, no stamp)"
    )
    assert expected_slice in slice_ids, (
        f"expected the committed HEAD message to carry a {trailer!r} trailer, but "
        f"its Slice-Id trailers are {slice_ids!r} (active-RED at HEAD: commit_slice "
        "has no --slice-id arg and never stamps the Slice-Id trailer)"
    )


@then(
    parsers.parse(
        "the committed slice commit carries exactly one Slice-Id trailer for "
        '"{slice_id}"'
    )
)
def then_carries_exactly_one(outcome: CommitOutcome, slice_id: str) -> None:
    # extract_slice_ids collapses duplicates; assert on the RAW trailer line count
    # so a literal duplicate is caught, and on the collapsed identity so the
    # single id is preserved (no loss).
    raw_count = sum(
        1
        for line in outcome.head_message.splitlines()
        if line.strip().startswith("Slice-Id:")
    )
    slice_ids = CommitSliceComposition.slice_ids_in(outcome.head_message)
    assert outcome.exit_code == 0, (
        f"expected the message-carried Slice-Id path to commit cleanly, exited "
        f"{outcome.exit_code}"
    )
    assert slice_ids == [slice_id], (
        f"expected the preserved Slice-Id identity to be exactly [{slice_id!r}], "
        f"got {slice_ids!r}"
    )
    assert raw_count == 1, (
        f"expected exactly ONE Slice-Id: trailer line (no mechanical duplicate of "
        f"the message-carried one), found {raw_count}"
    )


@then("the slice commit is refused with a non-zero exit")
def then_refused_non_zero(outcome: CommitOutcome) -> None:
    assert outcome.exit_code != 0, (
        "expected commit_slice to refuse up-front (non-zero exit) when neither "
        "--slice-id nor a message Slice-Id is present, but it exited 0 (active-RED "
        "at HEAD: there is no refuse-if-absent guard -- a Slice-Id-less commit is "
        "produced)"
    )


@then("no Slice-Id-less slice commit is produced")
def then_no_slice_less_commit(outcome: CommitOutcome) -> None:
    # The refusal observable: the slice-less message must NOT have become a NEW
    # HEAD commit. (If a commit was produced it necessarily lacks a Slice-Id, the
    # exact defect.)
    if outcome.produced_commit:
        slice_ids = CommitSliceComposition.slice_ids_in(outcome.head_message)
        assert slice_ids, (
            "a new slice commit was produced carrying NO Slice-Id trailer -- the "
            "exact C9 defect (active-RED at HEAD: no refuse-if-absent guard, so a "
            f"Slice-Id-less commit lands; its trailers are {slice_ids!r})"
        )


@then("the slice commit is a verified Gate-Scope commit")
def then_verified_gate_scope(outcome: CommitOutcome) -> None:
    # Preservation (Mandate-12): adding the Slice-Id stamp must not change the
    # Gate-Scope mechanics. The acceptance proof is the production event:
    # SliceCommitted with verified == True (the post-amend GateScopeVerified ran).
    assert outcome.exit_code == 0, (
        f"expected a verified Gate-Scope commit, exited {outcome.exit_code}"
    )
    assert outcome.event is not None, "commit_slice emitted no JSON event"
    assert outcome.event.get("event") == "SliceCommitted", (
        f"expected a SliceCommitted event (Gate-Scope mechanics unchanged), got "
        f"{outcome.event!r}"
    )
    assert outcome.event.get("verified") is True, (
        "expected the committed-scope Gate-Scope verify to pass (verified == True) "
        f"with the Slice-Id stamp present, got {outcome.event!r}"
    )
