"""PUBLIC ORACLE -- the injected notice is guarded as descriptive.

Authority: docs/product/architecture/brief.md#The Injected Notice Is Guarded As
Descriptive.

An agent beginning a session in an enabled nWave project receives the delivery
route notice in its OWN starting context. The install-time guard questions only
the managed section spliced into the project's guidance file; it provably cannot
see the bytes injected at runtime, which are resolved from an installed tree
that can legitimately drift. This observation therefore questions the RUNTIME
path, through the published SessionStart command, as a real process:

* wording that COMMANDS the agent to route fails the check, and the refusal
  quotes the offending phrase back;
* working directly must remain STATED as a legitimate answer, or the notice is
  likewise refused;
* both refusals are members of the handler's existing fail-open family -- no
  stdout, one WHAT/WHY/HOW line on stderr, exit 0 -- because a SessionStart hook
  that blocks or crashes bricks a session;
* on a passing invocation the hook REPORTS that the guard ran and over how many
  declared phrases it decided, so a green observation cannot be produced by a
  guard that was never invoked.

The journey, the stimuli and the projection live in the sibling support module.
This file holds the observation and the single expected result.
"""

from __future__ import annotations

import json

from tests.installer.acceptance.session_start_notice.descriptive_notice_oracle import (
    EXPECTED_SEMANTIC_OBSERVATION,
    observe_descriptive_notice,
)


def test_the_injected_notice_is_guarded_as_descriptive() -> None:
    """The whole observation is compared as ONE value.

    Asserting the projection whole, rather than field by field, keeps a silently
    dropped question from passing unnoticed: a missing key is a difference.
    """
    observation = observe_descriptive_notice()
    assert observation["semantic"] == EXPECTED_SEMANTIC_OBSERVATION, json.dumps(
        observation, indent=2, sort_keys=True, default=str
    )


if __name__ == "__main__":
    # The declared invocation is `python <this file>`. Running the module must
    # EXECUTE the observation, not merely define it: the printed projection and
    # the exit status together carry the verdict to an examiner who sees no
    # source.
    observation = observe_descriptive_notice()
    print(json.dumps(observation, indent=2, sort_keys=True, default=str))
    if observation["semantic"] != EXPECTED_SEMANTIC_OBSERVATION:
        raise SystemExit(
            "the injected session-start notice is not guarded as descriptive"
        )
