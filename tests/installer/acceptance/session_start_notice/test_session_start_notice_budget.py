"""Public oracle: the injected notice declares its size and refuses to grow.

Authority: docs/product/architecture/brief.md#The Injected Notice Declares Its
Measured Size And Refuses To Grow Past It.

Every session start spends a fixed part of the agent's context on the route
notice. That cost must be a MEASURED, reported fact -- in bytes, and in tokens
stated honestly as a derived upper bound -- and the notice must refuse to grow
past a declared ceiling, naming both the measured and the permitted size when
it does.

The falsifier is the second half of that sentence made executable: the shipped
text is enlarged on disk and the check must fail. Today that enlargement passes
unnoticed, so this observation's future green genuinely discriminates.
"""

from __future__ import annotations

from tests.installer.acceptance.session_start_notice.notice_budget_oracle import (
    EXPECTED_SEMANTIC_OBSERVATION,
    observe_notice_budget,
)


def test_injected_notice_declares_its_size_and_refuses_to_grow_past_the_ceiling() -> (
    None
):
    observed = observe_notice_budget()
    assert observed["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, (
        "WHAT: the session-start notice did not report its measured size, or did "
        "not refuse an enlargement past its declared ceiling. Observed: "
        f"{observed!r}.\n"
        "WHY: the notice is a standing tax on every session's context, so its "
        "cost must be visible as a measured fact and bounded by a ceiling that "
        "the shipped text cannot quietly outgrow.\n"
        "HOW: report, on stderr, the exact UTF-8 byte length of the injected "
        "additionalContext together with its derived ceil(bytes/4) token upper "
        "bound and the permitted ceiling; when the measurement exceeds that "
        "ceiling, refuse the injection the way every other degradation refuses "
        "-- no stdout, one WHAT/WHY/HOW line naming both sizes, exit 0."
    )
