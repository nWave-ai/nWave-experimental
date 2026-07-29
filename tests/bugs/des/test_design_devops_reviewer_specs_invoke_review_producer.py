"""Regression: DESIGN/DEVOPS reviewer specs must invoke the review PRODUCER.

DEFECT (GDP-2 authoring-surface affordance): ``verify-design-review`` and
``verify-devops-review`` are armed on the DESIGN and DEVOPS gate-out stacks
(``nWave/waves/design.yaml``, ``nWave/waves/devops.yaml``). Both consumers
read back a ledger record written by a PRODUCER -- ``des record-design-review``
/ ``des record-devops-review`` (``src/des/cli/design_review_verdict.py`` /
``devops_review_verdict.py``, both real and unit-tested). Neither producer was
invoked anywhere: not by ``nw-solution-architect-reviewer.md``, not by
``nw-platform-architect-reviewer.md``, not by any skill or task prose. A
reviewer could produce a perfect YAML verdict and the gate-out would still
read back nothing and refuse forever -- INDETERMINATE, never PASS, because the
only guidance lived in the gate's own remediation message (GDP-3), reachable
only by REACTING to a rejection, never by knowing in advance.

The fix belongs at the authoring surface: the reviewer's own workflow must
name the producer command as the last step of finishing a review, not as a
wall the wave hits later.

This test pins the fix: both reviewer specs must contain the exact producer
invocation, keyed to a `--verdict` flag naming both terminal tokens the gate
consumer understands (`approved` / `needs-revision`).
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

SOLUTION_ARCHITECT_REVIEWER = (
    REPO_ROOT / "nWave" / "agents" / "nw-solution-architect-reviewer.md"
)
PLATFORM_ARCHITECT_REVIEWER = (
    REPO_ROOT / "nWave" / "agents" / "nw-platform-architect-reviewer.md"
)


def test_solution_architect_reviewer_invokes_design_review_producer() -> None:
    """The DESIGN reviewer spec names `des record-design-review` with both
    verdict tokens the `verify-design-review` gate consumer reads back."""
    text = SOLUTION_ARCHITECT_REVIEWER.read_text(encoding="utf-8")

    assert "des record-design-review" in text
    assert "--verdict approved" in text
    assert "needs-revision" in text


def test_platform_architect_reviewer_invokes_devops_review_producer() -> None:
    """The DEVOPS reviewer spec names `des record-devops-review` with both
    verdict tokens the `verify-devops-review` gate consumer reads back."""
    text = PLATFORM_ARCHITECT_REVIEWER.read_text(encoding="utf-8")

    assert "des record-devops-review" in text
    assert "--verdict approved" in text
    assert "needs-revision" in text
