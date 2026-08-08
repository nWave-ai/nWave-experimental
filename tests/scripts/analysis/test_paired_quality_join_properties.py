"""Laws for the quality join. The one that matters is conservation.

A cost-per-accepted-outcome figure is a ratio, so its denominator is the whole
claim. If a run can vanish between the two sides of the join, the arm whose runs
went unscored looks cheaper — and nothing in the output would say so. These
properties pin that nothing vanishes, and that this tool never invents a verdict
it was not given.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.analysis.paired_quality_join import Joined, Unjoined, join


_SETTINGS = settings(max_examples=300, deadline=None)

_SESSIONS = st.lists(st.uuids().map(str), min_size=0, max_size=8, unique=True)


@st.composite
def _campaign(draw):
    """Sessions split three ways: run-only, verdict-only, and both."""
    sessions = draw(_SESSIONS)
    both = (
        draw(st.lists(st.sampled_from(sessions or ["x"]), max_size=8, unique=True))
        if sessions
        else []
    )
    run_only = [s for s in sessions if s not in both]
    verdict_only = draw(_SESSIONS)
    runs = {s: (f"pair-1/{s[:4]}", "control") for s in [*both, *run_only]}
    verdicts = {
        s: {"accepted": draw(st.booleans()), "evidence": "e"}
        for s in [*both, *(v for v in verdict_only if v not in runs)]
    }
    return runs, verdicts


@_SETTINGS
@given(campaign=_campaign())
def test_nothing_vanishes_between_the_two_sides(campaign) -> None:
    """Conservation: every run and every verdict is accounted for, exactly once.

    The refuted alternative is the one that biases a ratio: a run that is neither
    joined nor named as unjoined simply leaves the denominator.
    """
    runs, verdicts = campaign

    joined, unjoined = join(runs, verdicts)

    joined_sessions = {j.session_id for j in joined}
    unjoined_runs = {u for u in unjoined if u.what == "run"}
    unjoined_verdicts = {u for u in unjoined if u.what == "verdict"}

    assert len(joined) + len(unjoined_runs) == len(runs)
    assert len(unjoined_verdicts) == len(set(verdicts) - set(runs))
    assert joined_sessions <= set(runs) & set(verdicts)


@_SETTINGS
@given(campaign=_campaign())
def test_every_result_is_one_of_the_two_shapes(campaign) -> None:
    """Totality: the operation has two outcomes and both are in the return."""
    joined, unjoined = join(*campaign)

    assert all(isinstance(j, Joined) for j in joined)
    assert all(isinstance(u, Unjoined) for u in unjoined)


@_SETTINGS
@given(accepted=st.booleans(), session=st.uuids().map(str))
def test_the_tool_never_invents_acceptance(accepted: bool, session: str) -> None:
    """`accepted` is carried, never decided. The scorer owns quality."""
    joined, unjoined = join(
        {session: ("pair-1/A", "control")},
        {session: {"accepted": accepted, "evidence": "e"}},
    )

    assert not unjoined
    assert joined[0].accepted is accepted


@_SETTINGS
@given(session=st.uuids().map(str))
def test_a_verdict_without_an_accepted_field_does_not_join(session: str) -> None:
    """A malformed verdict is unjoined, not defaulted to False.

    Defaulting would turn a scorer's omission into a recorded rejection — a
    verdict this tool is explicitly forbidden to hold.
    """
    joined, unjoined = join(
        {session: ("pair-1/A", "control")}, {session: {"evidence": "e"}}
    )

    assert not joined
    assert unjoined and "no `accepted`" in unjoined[0].reason
