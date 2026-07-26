"""Acceptance evidence for the advisory delivery ready-set.

The public value is not a slice number: a maintainer can see all independently
ready work before serially dispatching only one of them.  The command is
read-only and cannot itself launch an agent.
"""

from __future__ import annotations

import json
from pathlib import Path


def _feature_delta(path: Path) -> None:
    path.write_text(
        """# Feature Delta

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|----------------|
| establish-contract | A user can establish the contract. | pending | @walking_skeleton | First value. |
| publish-cli | A user can use the public CLI. | pending |  | Independent value. |
| prove-journey | A user can trust the assembled journey. | pending | depends-on establish-contract | It consumes the established contract. |
""",
        encoding="utf-8",
    )


def _payload(capsys) -> dict[str, object]:
    captured = capsys.readouterr()
    return json.loads(captured.out.splitlines()[-1])


def test_delivery_plan_exposes_all_independently_ready_customer_outcomes(
    tmp_path: Path, capsys
) -> None:
    from des.cli.delivery_plan import main

    feature_delta = tmp_path / "feature-delta.md"
    _feature_delta(feature_delta)

    assert main(["--feature-delta", str(feature_delta)]) == 0

    assert _payload(capsys) == {
        "event": "DeliveryPlan",
        "completed": [],
        "ready": ["establish-contract", "publish-cli"],
        "unused_parallelism": True,
    }


def test_delivery_plan_unblocks_a_dependent_customer_outcome_after_its_prerequisite(
    tmp_path: Path, capsys
) -> None:
    from des.cli.delivery_plan import main

    feature_delta = tmp_path / "feature-delta.md"
    _feature_delta(feature_delta)

    assert (
        main(
            ["--feature-delta", str(feature_delta), "--completed", "establish-contract"]
        )
        == 0
    )

    assert _payload(capsys)["ready"] == ["publish-cli", "prove-journey"]


def test_delivery_plan_refuses_a_completion_claim_outside_the_declared_work(
    tmp_path: Path, capsys
) -> None:
    from des.cli.delivery_plan import main

    feature_delta = tmp_path / "feature-delta.md"
    _feature_delta(feature_delta)

    assert (
        main(["--feature-delta", str(feature_delta), "--completed", "invented-work"])
        == 2
    )
    payload = _payload(capsys)
    assert payload["event"] == "DeliveryPlanRejected"
    assert "absent from the Slice Plan" in str(payload["reason"])
