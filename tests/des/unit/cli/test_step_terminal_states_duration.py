"""HOW-TO-INVOKE must tell its reader a step can outlast a short timeout.

Measured on this lane: the interval between consecutive role-turn-buying steps
in a real lane ran 427s, 400s and 373s, with several near 115s -- well past a
shell tool's default ~120s timeout. A caller that backgrounds the call and
waits for a notification never gets one for a single step invocation, so it
waits forever on a turn that already finished. `HOW_TO_INVOKE` used to say a
step is invoked alone and returns its `NEXT` as data, but said nothing about
how long that invocation can run or how to invoke it so the result is not
lost -- this is the gap this test closes.
"""

from __future__ import annotations

from des.cli.step_terminal import HOW_TO_INVOKE, StepRefusal, refuse, succeed


def test_how_to_invoke_warns_the_call_can_outlast_a_short_timeout() -> None:
    assert "minute" in HOW_TO_INVOKE
    assert "background" in HOW_TO_INVOKE
    assert "timeout" in HOW_TO_INVOKE


def test_the_warning_is_printed_on_success(capsys) -> None:
    succeed(["REQUEST: (none)"], "des po --repo-root R -- one Request on stdin")
    out = capsys.readouterr().out
    assert HOW_TO_INVOKE in out


def test_the_warning_is_printed_on_refusal(capsys) -> None:
    refuse(
        StepRefusal(what="w", why="y", how="h"),
        "des state --repo-root R",
    )
    out = capsys.readouterr().out
    assert HOW_TO_INVOKE in out
