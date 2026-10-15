"""The advisory NEXT walks an applicable structural move through its phases.

Driven through the real `des craft` entry point over a real Git repository whose
native argv is a language-neutral shell command: the preservation phase the
state owes is projected from the retained receipts, NEXT names it before the
feature oracle, and a phase refusal retries as that phase.
"""

from __future__ import annotations

import json
import shlex
import subprocess
from pathlib import Path

import pytest

from des.application.delivery_state import canonical_next, read_state
from des.application.delivery_steps import DeliverySteps, ReplacementModes
from des.cli import craft
from des.domain.delivery_disposition import Disposition
from tests.des._helpers.host_facts import design_manifest, product_manifest


OBSERVATION = "the public command reports the agreed answer of forty-two"
ORACLE_ACCEPTED = json.dumps(
    {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "The assertion falsifies the missing public answer.",
        }
    }
)
NOT_APPLICABLE = {"applicability": "not_applicable", "reason": "Nothing affected."}


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


@pytest.fixture
def root(tmp_path: Path) -> Path:
    root = tmp_path / "subject"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "native@example.test")
    _git(root, "config", "user.name", "Native Fixture")
    (root / ".gitignore").write_text("_build/\n.nwave/\n")
    (root / "product.txt").write_text("before\n")
    (root / "support.txt").write_text("same support\n")
    (root / "preserve.sh").write_text(
        'case "$(cat product.txt)" in before|after) exit 0;; *) exit 1;; esac\n'
    )
    (root / "oracle.sh").write_text(
        'test "$(cat product.txt)" = feature\n'
        "status=$?\n"
        "printf 'DES-ORACLE-OBSERVATION: "
        '{"version":1,"observed":1,"assertions_failed":%s,"setup_failed":0}\\n'
        '\' "$status"\n'
        'exit "$status"\n'
    )
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "Existing native implementation and witness")
    return root


def _design_manifest(facts: dict) -> dict:
    manifest = design_manifest(facts, OBSERVATION, 1)
    # The closed DESIGN grammar requires the impact closure decision; the shared
    # helper owns it when it carries one, otherwise nothing is affected here.
    manifest.setdefault("impact_closure", NOT_APPLICABLE)
    return manifest


APPLICABLE_PREFACTORING = {
    "applicability": "applicable",
    "existing_oracle": "preserve.sh",
    "move": "Rewrite the stored representation without changing its result.",
    "preserved_observation": "The stored representation stays accepted.",
    "verification": [["sh", "preserve.sh"]],
    "acceptance_supports": ["support.txt"],
}


def _design(root: Path, prefactoring: dict, *, replace: bool = False) -> None:
    facts = {
        "targets": [{"path": "product.txt", "decision": "EXTEND"}],
        "paradigm": "functional",
        "decisions": ["Keep the existing public seam."],
        "oracle": "oracle.sh",
        "acceptance_supports": [],
        "verification": [["sh", "oracle.sh"]],
        "oracle_verification_index": 0,
        "architectural_tests": NOT_APPLICABLE,
        "contract_tests": NOT_APPLICABLE,
        "agreement_analysis": NOT_APPLICABLE,
        "prefactoring": prefactoring,
    }
    outcome = DeliverySteps().design_document(
        root,
        1,
        json.dumps(_design_manifest(facts)),
        modes=ReplacementModes(replace_current=replace),
    )
    assert outcome.disposition is Disposition.Success, outcome


def _distill(root: Path, *, replace: bool = False) -> None:
    outcome = DeliverySteps().distill_document(
        root,
        json.dumps(
            {
                "schema_version": 2,
                "values": [
                    {
                        "observation": OBSERVATION,
                        "acceptance_obligations": [
                            {
                                "id": "public-answer",
                                "stimulus": "Run the public command.",
                                "expected": "The public answer is forty-two.",
                            }
                        ],
                        "oracle": "oracle.sh",
                        "acceptance_supports": [],
                        "verification": [["sh", "oracle.sh"]],
                        "oracle_verification_index": 0,
                    }
                ],
            }
        ),
        replace_current=replace,
    )
    assert outcome.disposition is Disposition.Success, outcome


def _delivery_with_applicable_prefactoring(root: Path) -> None:
    outcome = DeliverySteps().discuss_document(
        root,
        json.dumps(product_manifest("Deliver the answer.", [OBSERVATION])),
        project=False,
        feature="native",
    )
    assert outcome.disposition is Disposition.Success, outcome
    _design(root, APPLICABLE_PREFACTORING)
    _distill(root)


def _craft_phase(root: Path, capsys: pytest.CaptureFixture[str], phase: str):
    code = craft.main(
        ["--repo-root", str(root), "--value", "1", "--prefactoring-phase", phase]
    )
    out = capsys.readouterr().out
    rows = {}
    for line in out.splitlines():
        label, _, text = line.partition(": ")
        rows.setdefault(label, []).append(text)
    return code, rows


def _form(root: Path, phase: str) -> str:
    return f"des craft --repo-root {root} --value 1 --prefactoring-phase {phase}"


def test_next_walks_before_move_then_after_move_then_oracle_and_refusal_retries_the_phase(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _delivery_with_applicable_prefactoring(root)
    baseline = _git(root, "rev-parse", "HEAD")
    state = read_state(root)
    assert state.values[0].prefactoring_phase == "before-move"
    assert canonical_next(state, root) == _form(root, "before-move")

    code, rows = _craft_phase(root, capsys, "before-move")
    assert code == 0, rows
    after_move_next = rows["NEXT"][0]
    assert rows["NEXT"] == [_form(root, "after-move-before-behavior")]
    assert read_state(root).values[0].prefactoring_phase == "after-move-before-behavior"

    # The phase command is advisory: DES did not run it, so no move was observed
    # and the refusal retries as the selected phase, never as the --input template.
    code, rows = _craft_phase(root, capsys, "after-move-before-behavior")
    assert code != 0, rows
    assert rows["WHAT"] == ["PrefactoringProductionUnchanged"]
    assert rows["NEXT"] == [
        f"{_form(root, 'after-move-before-behavior')} -- after the HOW above",
        f"des state --repo-root {root}",
    ]
    assert not any("--input" in row for row in rows["NEXT"])

    # Perform only the declared move, then follow the NEXT printed after before-move.
    (root / "product.txt").write_text("after\n")
    generated = shlex.split(after_move_next)
    assert generated[0] == "des"
    code, rows = _craft_phase(root, capsys, generated[-1])
    assert code == 0, rows
    assert rows["NEXT"] == [f"des oracle --repo-root {root} --value 1 --input -"]
    assert read_state(root).values[0].prefactoring_phase is None

    # Following that NEXT no longer reaches the unrecorded-preservation refusal.
    oracle = DeliverySteps().oracle(root, 1, ORACLE_ACCEPTED, baseline=baseline)
    assert (
        oracle.failure is None
        or oracle.failure.what != "PrefactoringPreservationUnrecorded"
    ), oracle


def test_a_superseded_oracle_record_does_not_make_a_newly_owed_preservation_too_late(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = _git(root, "rev-parse", "HEAD")
    outcome = DeliverySteps().discuss_document(
        root,
        json.dumps(product_manifest("Deliver the answer.", [OBSERVATION])),
        project=False,
        feature="native",
    )
    assert outcome.disposition is Disposition.Success, outcome
    _design(root, NOT_APPLICABLE)
    _distill(root)
    recorded = DeliverySteps().oracle(root, 1, ORACLE_ACCEPTED, baseline=baseline)
    assert recorded.disposition is Disposition.Success, recorded
    assert read_state(root).values[0].oracle == "recorded"

    # `--replace-current` rewrites only a tracked authority.
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "Bound DESIGN authority")
    # The architect corrects the DESIGN to add a structural move, then the
    # requested DISTILL realignment follows; the earlier oracle ref is now history.
    _design(root, APPLICABLE_PREFACTORING, replace=True)
    _distill(root, replace=True)
    stale = read_state(root).values[0]
    assert stale.oracle == "bytes moved"
    assert stale.prefactoring_phase == "before-move"
    assert canonical_next(read_state(root), root) == _form(root, "before-move")

    code, rows = _craft_phase(root, capsys, "before-move")
    assert code == 0, rows
    assert rows["NEXT"] == [_form(root, "after-move-before-behavior")]
    (root / "product.txt").write_text("after\n")
    code, rows = _craft_phase(root, capsys, "after-move-before-behavior")
    assert code == 0, rows
    assert rows["NEXT"] == [f"des oracle --repo-root {root} --value 1 --input -"]
    reoracle = DeliverySteps().oracle(root, 1, ORACLE_ACCEPTED, baseline=baseline)
    assert reoracle.disposition is Disposition.Success, reoracle
    assert read_state(root).values[0].oracle == "recorded"
