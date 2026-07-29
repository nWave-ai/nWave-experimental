"""Regression: the DISCUSS reviewer spec must invoke the review PRODUCER.

DEFECT (GDP-2 authoring-surface affordance, third instance of the class fixed
in ``764a9fe21`` for DESIGN/DEVOPS): ``verify-discuss-review`` is armed on the
DISCUSS gate-out stack (``nWave/waves/discuss.yaml``). The consumer reads back
a ledger record written by a PRODUCER -- ``des record-discuss-review``
(``src/des/cli/discuss_review_verdict.py``, real and unit-tested). Nothing in
``nw-product-owner-reviewer.md`` -- the reviewer whose own verdict this gate
reads back -- ever named the producer. A reviewer could produce a perfect YAML
verdict and the gate-out would still read back nothing, refusing forever,
because the only guidance lived in the gate's own rejection message (GDP-3),
reachable only by REACTING to a failure, never by knowing in advance.

Unlike the DESIGN/DEVOPS instance, the DISCUSS gate-out HAS returned PASS in
this repo's own telemetry (e.g. ``f-runner-capability-probe``,
``codex-host-parity``) -- but only because a human, on hitting the gate's
reactive remediation, ran the producer command by hand. The spec gap (no
proactive authoring-surface step) is the same defect regardless.

The fix belongs at the authoring surface: the reviewer's own workflow must
name the producer command as the last step of finishing a review.

This test pins the fix: the reviewer spec must contain the exact producer
invocation, keyed to a `--verdict` flag naming both terminal tokens the gate
consumer understands (`approved` / `needs-revision`).
"""

from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]

PRODUCT_OWNER_REVIEWER = REPO_ROOT / "nWave" / "agents" / "nw-product-owner-reviewer.md"


def test_product_owner_reviewer_invokes_discuss_review_producer() -> None:
    """The DISCUSS reviewer spec names `des record-discuss-review` with both
    verdict tokens the `verify-discuss-review` gate consumer reads back."""
    text = PRODUCT_OWNER_REVIEWER.read_text(encoding="utf-8")

    assert "des record-discuss-review" in text
    assert "--verdict approved" in text
    assert "needs-revision" in text
