# @feature-feature-context-bootstrap
"""Public contract for a maintainer opening a feature context.

The tests use the stable, dynamically resolved ``des`` command dispatcher as
their only production import.  They deliberately do not import the future
bootstrap implementation: an absent route becomes an AssertionError inside a
test body (active RED), never a collection-time import failure.

CONTRACT_SHAPE: bounded-change -- the opening command may create only the
declared feature document; the following next-step read preserves the rest of
the repository universe.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest


def _tree_hashes(root: Path) -> dict[str, str]:
    """Observe every regular file beneath the public repository boundary."""
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _assert_only_context_document_was_added(
    before: dict[str, str], after: dict[str, str], delta_path: Path, root: Path
) -> None:
    """Pin the entire allowed publication universe, not merely a no-ledger sample."""
    delta_key = delta_path.relative_to(root).as_posix()
    expected = {**before, delta_key: after[delta_key]}
    assert after == expected, (
        "WHAT: opening a context changed files outside its one declared document. "
        "WHY: bootstrap must not manufacture delivery, review, examine, ledger, scorecard, or scheduler state. "
        "HOW: publish only docs/feature/<id>/feature-delta.md and preserve every other repository byte."
    )


def _capture_des_audit_events() -> list[str]:
    """Observe custom DES audit traffic without treating Python runtime events as product state."""
    events: list[str] = []

    def remember(event: str, _args: tuple[object, ...]) -> None:
        if event.startswith("des."):
            events.append(event)

    sys.addaudithook(remember)
    return events


def _run_public_des(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> tuple[int, dict[str, object]]:
    """Drive the real lazy DES command registry and capture its one JSON reply."""
    from des.cli.__main__ import main

    try:
        exit_code = main(argv)
    except SystemExit as exc:
        raise AssertionError(
            "WHAT: the public `des feature-open` route is not available. "
            "WHY: a maintainer cannot lawfully bootstrap a missing feature context through "
            "the existing dynamic DES command surface. HOW: register the lazy feature-open "
            "route without replacing the existing importlib-based command resolution."
        ) from exc

    stdout = capsys.readouterr().out.strip().splitlines()
    assert len(stdout) == 1, (
        "WHAT: the public command must emit exactly one receipt line. "
        "WHY: callers need one unambiguous context result. HOW: emit one JSON receipt or refusal "
        "from the command boundary."
    )
    try:
        return exit_code, json.loads(stdout[0])
    except json.JSONDecodeError as exc:
        raise AssertionError(
            "WHAT: the public command did not emit a JSON receipt. "
            "WHY: an operator cannot safely identify the context that was observed. "
            "HOW: serialize the public receipt as one JSON object."
        ) from exc


def test_maintainer_opens_context_and_reaches_discuss_without_completion_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A maintainer receives the first lawful step with no manual document assembly.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch
    """
    # covers: R1 R2 R3 R6
    feature_id = "safe-feature-context"
    intent = "A maintainer can begin a lawful feature discussion."
    before = _tree_hashes(tmp_path)

    open_code, receipt = _run_public_des(
        [
            "feature-open",
            "--feature-id",
            feature_id,
            "--intent",
            intent,
            "--repo",
            str(tmp_path),
        ],
        capsys,
    )

    delta = tmp_path / "docs" / "feature" / feature_id / "feature-delta.md"
    after_open = _tree_hashes(tmp_path)
    _assert_only_context_document_was_added(before, after_open, delta, tmp_path)
    assert open_code == 0 and receipt == {
        "event": "FeatureContextReceipt",
        "schema_version": "1",
        "feature_id": feature_id,
        "state": "OPEN",
        "feature_delta": f"docs/feature/{feature_id}/feature-delta.md",
        "intent_normalized": intent,
        "next": f"/nw-discuss --feature-id {feature_id}",
        **{
            key: receipt[key]
            for key in (
                "feature_delta_sha256",
                "intent_sha256",
                "template_version",
                "template_sha256",
                "canonical_body_sha256",
            )
        },
        "inventory": [],
    }, (
        "WHAT: opening a new context must return its complete receipt. "
        "WHY: the operator needs a durable, non-completion description of the created context. "
        "HOW: publish the declared delta and return the specified receipt fields."
    )
    assert (
        receipt["feature_delta_sha256"]
        == hashlib.sha256(delta.read_bytes()).hexdigest()
    ), (
        "WHAT: the receipt's feature-delta SHA-256 must identify the exact published bytes. "
        "WHY: callers need to verify the document they received without trusting an unrelated digest. "
        "HOW: calculate feature_delta_sha256 from the final on-disk feature-delta.md bytes."
    )

    next_code, next_step = _run_public_des(
        ["next", "--feature-id", feature_id, "--repo", str(tmp_path)], capsys
    )
    assert (
        next_code == 0
        and next_step.get("how") == f"/nw-discuss --feature-id {feature_id}"
    ), (
        "WHAT: a verified open context must project the DISCUSS action. "
        "WHY: the maintainer needs one lawful next step instead of an indeterminate delivery path. "
        "HOW: classify the exact bootstrap before the normal feature-document doctor."
    )


@pytest.mark.negative_at
def test_existing_feature_context_refuses_without_changing_delivery_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A maintainer cannot replace an existing context while opening a new one.

    CONTRACT_SHAPE: unbounded-preservation
    Outcome anchor: DISCUSS Elevator Pitch
    """
    # covers: R3
    feature_id = "already-owned-context"
    delta = tmp_path / "docs" / "feature" / feature_id / "feature-delta.md"
    delta.parent.mkdir(parents=True)
    delta.write_bytes(
        b"# A judged feature document\n\nExisting delivery work remains authoritative.\n"
    )
    evidence = tmp_path / ".nwave" / "des" / "logs" / "at-completion.jsonl"
    evidence.parent.mkdir(parents=True)
    evidence.write_bytes(
        b'{"event":"SliceCommitVerified","feature_id":"already-owned-context"}\n'
    )
    examine = tmp_path / "docs" / "feature" / feature_id / "deliver" / "examine.json"
    examine.parent.mkdir(parents=True)
    examine.write_bytes(b'{"event":"ExamineVerdictRecorded","verdict":"PASS"}\n')
    before = _tree_hashes(tmp_path)
    audit_events = _capture_des_audit_events()

    exit_code, refusal = _run_public_des(
        [
            "feature-open",
            "--feature-id",
            feature_id,
            "--intent",
            "A maintainer starts a different discussion.",
            "--repo",
            str(tmp_path),
        ],
        capsys,
    )

    assert exit_code != 0 and refusal.get("error") == "feature-context-conflict", (
        "WHAT: an existing feature document must refuse a second bootstrap context. "
        "WHY: replacing a judged document would erase the existing delivery and completion authority. "
        "HOW: return feature-context-conflict and require the maintainer to use the existing feature flow."
    )
    assert _tree_hashes(tmp_path) == before and audit_events == [], (
        "WHAT: refusing an existing context changed repository bytes or emitted DES audit authority. "
        "WHY: refusal is read-only with respect to an already-owned feature and cannot mint new evidence. "
        "HOW: make the collision check before creating directories, writing files, or emitting des.* audit events."
    )


@pytest.mark.negative_at
def test_adopted_work_never_claims_evidence_that_is_absent(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Selected existing work stays explicitly unevaluated at bootstrap.

    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch
    """
    # covers: R3 R4 R5
    feature_id = "adopted-context"
    wip = tmp_path / "existing-work"
    wip.mkdir()
    (wip / "public_check.py").write_text("assert True\n", encoding="utf-8")
    before_open = _tree_hashes(tmp_path)
    audit_events = _capture_des_audit_events()

    exit_code, receipt = _run_public_des(
        [
            "feature-open",
            "--feature-id",
            feature_id,
            "--intent",
            "A maintainer can adopt existing work for discussion.",
            "--repo",
            str(tmp_path),
            "--adopt-wip",
            "--adopt-root",
            "existing-work",
        ],
        capsys,
    )

    inventory = receipt.get("inventory")
    assert (
        exit_code == 0
        and receipt.get("state") == "ADOPTED_WIP"
        and inventory
        == [
            {
                "path": "existing-work/public_check.py",
                "sha256": inventory[0]["sha256"],
                "test_status": "UNKNOWN",
            }
        ]
    ), (
        "WHAT: adopted work must remain an explicit UNKNOWN inventory. "
        "WHY: an inventory is provenance, not passing execution, review, examine, or completion evidence. "
        "HOW: record only deterministic file hashes and UNKNOWN test status."
    )
    delta = tmp_path / "docs" / "feature" / feature_id / "feature-delta.md"
    _assert_only_context_document_was_added(
        before_open, _tree_hashes(tmp_path), delta, tmp_path
    )
    assert not (tmp_path / ".nwave").exists() and "completion" not in receipt, (
        "WHAT: absent WIP execution evidence must not create a completion claim. "
        "WHY: UNKNOWN work cannot safely enter normal delivery or commit. "
        "HOW: fail closed until an existing immutable execution record proves the adopted bytes."
    )
    before_next = _tree_hashes(tmp_path)
    open_audit_event_count = len(audit_events)
    next_code, next_step = _run_public_des(
        ["next", "--feature-id", feature_id, "--repo", str(tmp_path)], capsys
    )
    assert next_code == 0 and next_step.get("loop_state") == "INDETERMINATE", (
        "WHAT: adopted UNKNOWN work did not produce the fail-closed INDETERMINATE result. "
        "WHY: inventory hashes cannot prove a passing execution, review, examine, or completion result. "
        "HOW: return an INDETERMINATE next-step result until immutable execution evidence exists."
    )
    assert (
        _tree_hashes(tmp_path) == before_next
        and audit_events[open_audit_event_count:] == []
    ), (
        "WHAT: reading the next step changed repository bytes or emitted DES audit authority. "
        "WHY: opening may lawfully audit its bounded publication, but evidence-aware routing is read-only and must not mint evidence while it is absent. "
        "HOW: return INDETERMINATE without writing files, ledger records, or new des.* audit events."
    )
    assert "adopted-wip-regression-evidence-unavailable" in next_step.get(
        "what", ""
    ) or "adopted-wip-regression-evidence-unavailable" in next_step.get("why", ""), (
        "WHAT: the INDETERMINATE result does not name the adopted-WIP evidence refusal. "
        "WHY: the maintainer must know that UNKNOWN inventory is not executable regression evidence. "
        "HOW: name adopted-wip-regression-evidence-unavailable in the public WHAT or WHY."
    )
