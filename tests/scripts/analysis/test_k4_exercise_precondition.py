"""The precondition must REJECT the campaign that motivated it.

Every check here is a transcript the detector has to judge. The first one is
the shape the 2026-09-12 campaign actually had -- Bash, Edit and Write, nothing
else -- and the second is the loophole the first wording of the precondition
left open: one read-only step, and the rule would have called it exercised.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


_K4 = Path(__file__).resolve().parents[3] / "scripts" / "analysis" / "k4"
sys.path.insert(0, str(_K4))

import delivery_attribution as attribution
import exercise_precondition as ep


def _transcript(workspace: Path, *tool_uses: dict) -> Path:
    """Write one arm workspace holding a transcript of the given tool uses."""
    path = workspace / ".claude-k4" / "projects" / "p" / "session.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for use in tool_uses:
            record = {"message": {"role": "assistant", "content": [use]}}
            handle.write(json.dumps(record) + "\n")
    return path


def _bash(command: str) -> dict:
    return {"type": "tool_use", "name": "Bash", "input": {"command": command}}


def _native_turn(path: Path, *, result: str = '{"outcome":"accepted"}') -> Path:
    """The fields that the current native TurnRecorder emits for a craft turn."""
    path.write_text(
        json.dumps(
            {
                "run_id": "native-run-1",
                "sequence": 5,
                "role_id": "nw-software-crafter",
                "exit_status": 0,
                "raised": None,
                "provider_stdout": json.dumps(
                    {
                        "session_id": "provider-session-1",
                        "terminal_reason": "completed",
                        "is_error": False,
                        "result": result,
                    }
                ),
            }
        ),
        encoding="utf-8",
    )
    return path


def _patch(change: str) -> str:
    return (
        "diff --git a/module.py b/module.py\n"
        "index 1111111..2222222 100644\n"
        "--- a/module.py\n"
        "+++ b/module.py\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        f"+{change}\n"
    )


def _write_legacy_attribution(
    workspace: Path, *, final_patch: str | None = None
) -> None:
    """Write the formerly accepted caller-created attribution evidence."""
    native = _native_turn(workspace / "native-turn.json")
    root_delivery = workspace / "delivery.json"
    root_delivery.write_text('{"session_id":"root-delivery-1"}', encoding="utf-8")
    producer_patch = workspace / "producer.patch"
    producer_patch.write_text(_patch("crafted"), encoding="utf-8")
    captured = workspace / "DELIVERY.patch"
    captured.write_text(final_patch or _patch("crafted"), encoding="utf-8")
    producer = attribution.ProducerReceiptV1(
        schema=attribution.PRODUCER_RECEIPT_SCHEMA,
        root_delivery_session="root-delivery-1",
        des_step="craft",
        role_id="nw-software-crafter",
        run_id="native-run-1",
        turn=5,
        producer_session_id="provider-session-1",
        input_base_tree="base-tree-1",
        native_turn_receipt_path="native-turn.json",
        result_patch_path="producer.patch",
        result_patch_sha256=hashlib.sha256(producer_patch.read_bytes()).hexdigest(),
        result_tree_sha256=None,
        native_turn_receipt_sha256=hashlib.sha256(native.read_bytes()).hexdigest(),
        native_result_sha256=hashlib.sha256(b'{"outcome":"accepted"}').hexdigest(),
        native_handover_path=None,
        native_handover_sha256=None,
        completion="completed",
    )
    receipt = attribution.construct_delivery_attribution(
        producer,
        root_delivery_session_path="delivery.json",
        root_delivery_session_receipt=root_delivery,
        final_delivery_patch_path="DELIVERY.patch",
        final_delivery_patch=captured,
    )
    attribution.write_attribution(
        workspace / attribution.ATTRIBUTION_FILE_NAME, receipt
    )


def _whole_route(workspace: Path, *, integrate: bool = False) -> None:
    commands = [
        _bash("des discuss --repo-root ."),
        _bash("des design --value 1"),
        _bash("des oracle --value 1"),
        _bash("des craft --value 1"),
        _bash("des verify --repo-root ."),
        _bash("des evolution --candidate abc123"),
    ]
    if integrate:
        commands.append(_bash("des integrate --candidate abc123"))
    _transcript(workspace, *commands)


def test_a_hand_typed_delivery_is_not_exercised(tmp_path: Path) -> None:
    """The 2026-09-12 shape: Bash, Edit and Write, no step and no delegation."""
    _transcript(
        tmp_path,
        _bash("python manage.py test hc.api"),
        {
            "type": "tool_use",
            "name": "Edit",
            "input": {"file_path": "hc/api/models.py"},
        },
        {"type": "tool_use", "name": "Write", "input": {"file_path": "hc/lib/x.py"}},
    )
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.NOT_EXERCISED
    assert "no DES step" in result.why


def test_a_read_only_step_alone_is_not_exercised(tmp_path: Path) -> None:
    """The loophole: `des state` buys no role turn, so it cannot admit a run."""
    _transcript(
        tmp_path,
        _bash("des state --repo-root ."),
        {
            "type": "tool_use",
            "name": "Edit",
            "input": {"file_path": "hc/api/models.py"},
        },
    )
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.NOT_EXERCISED
    assert "buy no role turn" in result.why
    assert "des state" in result.why


def test_one_role_buying_step_is_not_the_route(tmp_path: Path) -> None:
    """The complaint is about the whole route, so one step cannot answer it."""
    _transcript(tmp_path, _bash("des craft --value 1"))
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.NOT_EXERCISED
    assert "deliver" in result.why
    assert "clarify" in result.why and "finalize" in result.why


def test_craft_command_text_alone_does_not_prove_authorship(tmp_path: Path) -> None:
    _transcript(tmp_path, _bash("des craft --value 1"))
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.NOT_EXERCISED
    assert "missing" in result.why


def test_the_whole_route_with_no_producer_receipt_is_indeterminate(
    tmp_path: Path,
) -> None:
    _whole_route(tmp_path)
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.INDETERMINATE
    assert "DeliveryAttributionV2" in result.why


def test_completed_receipt_plus_matching_caller_patch_is_indeterminate(
    tmp_path: Path,
) -> None:
    _whole_route(tmp_path)
    _write_legacy_attribution(tmp_path)
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.INDETERMINATE
    assert "system-record" in result.why
    assert result.attributions[0].status == attribution.INDETERMINATE


def test_completed_legacy_receipt_never_names_a_producer(
    tmp_path: Path,
) -> None:
    _whole_route(tmp_path, integrate=True)
    _write_legacy_attribution(tmp_path)
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.INDETERMINATE
    assert "des integrate" not in result.role_buying
    assert "des integrate" in result.reporting_only
    assert result.attributions[0].producer_role is None


def test_completed_native_receipt_and_matching_patch_cannot_construct_receipt(
    tmp_path: Path,
) -> None:
    native = _native_turn(tmp_path / "native-turn.json")
    patch = tmp_path / "producer.patch"
    patch.write_text(_patch("crafted"), encoding="utf-8")
    try:
        attribution.construct_producer_receipt(
            native,
            root_delivery_session="root-delivery-1",
            des_step="craft",
            input_base_tree="base-tree-1",
            native_turn_receipt_path="native-turn.json",
            result_patch_path="producer.patch",
            result_patch=patch,
        )
    except attribution.AttributionError as exc:
        assert "system-record" in str(exc)
    else:
        raise AssertionError("a caller-supplied matching patch constructed a receipt")


def test_absent_or_empty_producer_projection_cannot_construct_receipt(
    tmp_path: Path,
) -> None:
    native = _native_turn(tmp_path / "native-turn.json")
    absent = tmp_path / "absent.patch"
    for projection in (absent, tmp_path / "empty.patch", tmp_path / "zero.patch"):
        if projection.name == "empty.patch":
            projection.write_text("", encoding="utf-8")
        if projection.name == "zero.patch":
            projection.write_text(
                "diff --git a/module.py b/module.py\nindex 1111111..1111111 100644\n",
                encoding="utf-8",
            )
        try:
            attribution.construct_producer_receipt(
                native,
                root_delivery_session="root-delivery-1",
                des_step="craft",
                input_base_tree="base-tree-1",
                native_turn_receipt_path="native-turn.json",
                result_patch_path=projection.name,
                result_patch=projection,
            )
        except attribution.AttributionError:
            continue
        raise AssertionError(
            "an absent, empty, or zero producer projection constructed a receipt"
        )


def test_a_delegated_turn_alone_is_not_the_route(tmp_path: Path) -> None:
    """A dispatched agent is work, but it is not evidence the route ran."""
    _transcript(
        tmp_path,
        {
            "type": "tool_use",
            "name": "Task",
            "input": {"subagent_type": "nw-software-crafter"},
        },
    )
    result = ep.examine_arm(tmp_path, "nwave")
    assert result.verdict == ep.NOT_EXERCISED
    assert "delegated" in result.why


def test_a_campaign_reports_one_verdict_per_pair(tmp_path: Path) -> None:
    campaign = tmp_path / "campaign"
    _whole_route(campaign / "pair-1" / "nwave")
    _write_legacy_attribution(campaign / "pair-1" / "nwave")
    _transcript(campaign / "pair-2" / "nwave", _bash("des state --repo-root ."))
    results = ep.examine_campaign(campaign)
    assert [r.verdict for r in results] == [ep.INDETERMINATE, ep.NOT_EXERCISED]


def test_every_step_of_the_surface_is_classified() -> None:
    """A step added later must be classified deliberately, never pass silently."""
    surface = {
        "state",
        "po",
        "design",
        "oracle",
        "craft",
        "verify",
        "integrate",
        "lane",
        "commit",
        "devops",
        "discuss",
        "distill",
        "evolution",
        "project",
        "code-fact",
        "verify-agreement",
    }
    classified = ep.ROLE_BUYING_STEPS | ep.REPORTING_STEPS
    assert surface - classified == set()
    assert ep.ROLE_BUYING_STEPS.isdisjoint(ep.REPORTING_STEPS)
    assert "integrate" in ep.REPORTING_STEPS


def test_a_campaign_with_no_arm_workspace_refuses_loudly(
    tmp_path: Path, capsys
) -> None:
    """Absence of transcripts is not a pass: it is a refusal that says how."""
    (tmp_path / "pair-1").mkdir(parents=True)
    assert ep.main(["--campaign", str(tmp_path)]) == 2
    printed = capsys.readouterr().out
    assert "WHAT:" in printed and "WHY:" in printed and "HOW:" in printed
