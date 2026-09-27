"""Public oracle: `des verify` and `des integrate`, the last two steps.

ADR-SSOT-002 Section 4b names four properties across these two commands:
constructing the whole-Request candidate from an identified base, verifying it
natively once, constructing separately selected role inputs, and integrating by
compare-and-swap with the owned index reconciled and the workspace released.

`verify` persists native evidence only. The host separately prepares and records
reviewer/examiner observations, then decides whether to call `integrate`; role
results are observations and cannot become an admission gate or correction flow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
    nexts,
)


REQUEST = "one Request carried from decomposition to an integrated commit"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
#: The target sits at the repository root, and the oracle puts that root on
#: `sys.path` itself. Every byte either scenario writes is a DECLARED path of
#: this value: the runner refuses an undeclared one as unattributed drift, which
#: is the guard working, not a fixture inconvenience.
TARGET = "product_value.py"
RED_ORACLE = (
    "import pathlib\n"
    "import sys\n"
    "\n"
    "\n"
    "def test_value():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n"
    "\n"
    "    assert VALUE == 1\n"
)


def design_facts() -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the value to its typed design facts",
            "design_facts": {
                "targets": [{"path": TARGET, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                "oracle_verification_index": 0,
            },
        }
    }


def verdict(diagnostic: str, outcome: str = "accepted") -> dict:
    return {"structured_output": {"outcome": outcome, "diagnostic": diagnostic}}


def _role_result(role: str, outcome: str, diagnostic: str) -> str:
    payload: dict[str, object] = {"outcome": outcome, "diagnostic": diagnostic}
    if role == "reviewer":
        payload |= {
            "defect_owner": None if outcome == "accepted" else "oracle",
            "defect_value": None,
        }
    return json.dumps({"structured_output": payload})


def _prepare_and_record(root: Path, step, role: str, candidate: str, outcome: str):
    prepared = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
    )
    assert prepared[0] == 0, prepared[1] + prepared[2]
    prepared_lines = block(prepared[1], prepared[2])
    code, out, err = step(
        "record-role-result",
        "--repo-root",
        str(root),
        "--role",
        role,
        "--candidate",
        candidate,
        "--provider",
        "claude",
        "--model",
        "host-observation-model",
        "--session-id",
        f"legacy-{role}-{outcome}",
        "--input",
        "-",
        *(("--prepared-input", prepared_lines["INPUT"]) if role == "examiner" else ()),
        stdin=_role_result(role, outcome, f"host {role} {outcome}"),
    )
    assert code == 0, out + err
    return block(out, err)


def crafted(root: Path, step) -> None:
    """Everything `des verify` consumes: bound, admitted oracle, crafted batch."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    assert (
        step(
            "design", "--repo-root", str(root), "--value", "1", answers=[design_facts()]
        )[0]
        == 0
    )
    code, out, err = step(
        "oracle",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "authored the oracle",
                },
                "writes": {ORACLE: RED_ORACLE, SUPPORT: "MARKER = 1\n"},
            },
            verdict("the oracle set is admissible"),
        ],
    )
    assert code == 0, out + err
    code, out, err = step(
        "craft",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[
            {
                "structured_output": {
                    "outcome": "accepted",
                    "diagnostic": "implemented the value behind its oracle",
                },
                "writes": {TARGET: "VALUE = 1\n"},
            }
        ],
    )
    assert code == 0, out + err


def test_verify_builds_one_candidate_runs_it_natively_without_buying_a_judge(
    root: Path, step, turns: Path
) -> None:
    crafted(root, step)
    head_before = git(root, "rev-parse", "HEAD")
    spent = len(asked(turns))
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[],
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert len(lines["CANDIDATE"]) == 40
    assert "NATIVE" in lines
    assert asked(turns)[spent:] == []
    # The candidate is a real commit parented on the base, and HEAD has NOT moved.
    assert git(root, "rev-parse", f"{lines['CANDIDATE']}^") == head_before
    assert git(root, "rev-parse", "HEAD") == head_before
    assert nexts(out) == [
        f"des prepare-role --repo-root {root} --role reviewer --candidate {lines['CANDIDATE']}"
    ]


def test_verify_does_not_govern_direct_integration(root: Path, step) -> None:
    """The host may integrate a native-success candidate without any role result."""
    crafted(root, step)
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    integrated = step("integrate", "--repo-root", str(root), "--candidate", candidate)
    assert integrated[0] == 0, integrated[1] + integrated[2]


def test_a_host_recorded_reviewer_rejection_is_observation_not_admission(
    root: Path, step, turns: Path
) -> None:
    crafted(root, step)
    spent = len(asked(turns))
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    recorded = _prepare_and_record(root, step, "reviewer", candidate, "rejected")
    assert recorded["OUTCOME"] == "rejected"
    # Recording a host observation is provider-free and selects no correction.
    assert len(asked(turns)) == spent
    assert git(root, "status", "--porcelain") != ""


def test_a_host_recorded_examiner_rejection_leaves_integration_to_the_host(
    root: Path, step
) -> None:
    crafted(root, step)
    head_before = git(root, "rev-parse", "HEAD")
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    recorded = _prepare_and_record(root, step, "examiner", candidate, "rejected")
    assert recorded["CANDIDATE"] == candidate
    assert recorded["OUTCOME"] == "rejected"
    assert git(root, "rev-parse", "HEAD") == head_before
    integrated = step("integrate", "--repo-root", str(root), "--candidate", candidate)
    assert integrated[0] == 0, integrated[1] + integrated[2]


def test_integrate_swaps_the_head_reconciles_and_closes_the_handover(
    root: Path, step, turns: Path
) -> None:
    crafted(root, step)
    verified = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is present in the captured evidence"),
        ],
    )
    assert verified[0] == 0, verified[1] + verified[2]
    candidate = block(verified[1], verified[2])["CANDIDATE"]
    spent = len(asked(turns))

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["INTEGRATED"] == candidate
    assert git(root, "rev-parse", "HEAD") == candidate
    # The owned index is reconciled: nothing the Request wrote is left staged or
    # untracked. `.nwave/` is the runner's own state directory and is excluded by
    # construction -- it holds the shared delivery lock, never a delivered byte.
    assert [
        line
        for line in git(root, "status", "--porcelain").splitlines()
        if not line.endswith(".nwave/")
    ] == []
    assert not (root / ".nwave" / "des" / "handover.json").exists()
    assert len(asked(turns)) == spent  # integration buys no turn at all
    assert "NEXT" in lines


def test_prepare_role_can_read_the_verified_candidate_after_integration(
    root: Path, step
) -> None:
    """Cleanup closes current work without erasing candidate-bound review evidence."""
    crafted(root, step)
    verified = step("verify", "--repo-root", str(root), answers=[])
    assert verified[0] == 0, verified[1] + verified[2]
    candidate = block(verified[1], verified[2])["CANDIDATE"]

    integrated = step("integrate", "--repo-root", str(root), "--candidate", candidate)
    assert integrated[0] == 0, integrated[1] + integrated[2]
    assert not (root / ".nwave" / "des" / "handover.json").exists()

    prepared = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    )
    assert prepared[0] == 0, prepared[1] + prepared[2]
    assert block(prepared[1], prepared[2])["CANDIDATE"] == candidate


def test_verify_and_integrate_need_current_bytes_not_each_roles_history(
    root: Path, step, turns: Path
) -> None:
    """One shared green oracle admits all designed values without old role refs."""
    assert (
        step(
            "po",
            "--project",
            "--repo-root",
            str(root),
            answers=[accepted_values("A", "B", "C")],
            stdin=REQUEST,
        )[0]
        == 0
    )
    for value in (1, 2, 3):
        assert (
            step(
                "design",
                "--repo-root",
                str(root),
                "--value",
                str(value),
                answers=[design_facts()],
            )[0]
            == 0
        )
    for value, marker in ((1, "MARKER = 1\n"), (3, "MARKER = 2\n")):
        recorded = step(
            "oracle",
            "--repo-root",
            str(root),
            "--value",
            str(value),
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "authored shared oracle",
                    },
                    "writes": {ORACLE: RED_ORACLE, SUPPORT: marker},
                },
                verdict("the shared oracle is admissible"),
            ],
        )
        assert recorded[0] == 0, recorded[1] + recorded[2]
    state = step("state", "--repo-root", str(root))
    assert "VALUE-1" in state[1] + state[2]
    assert "oracle=bytes moved" in state[1] + state[2]
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "3",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented shared target",
                    },
                    "writes": {TARGET: "VALUE = 1\n"},
                }
            ],
        )[0]
        == 0
    )
    spent = len(asked(turns))
    verified = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observations"),
            verdict("the captured evidence proves them"),
        ],
    )
    assert verified[0] == 0, verified[1] + verified[2]
    assert asked(turns)[spent:] == []
    candidate = block(verified[1], verified[2])["CANDIDATE"]
    integrated = step("integrate", "--repo-root", str(root), "--candidate", candidate)
    assert integrated[0] == 0, integrated[1] + integrated[2]
    assert git(root, "rev-parse", "HEAD") == candidate
    assert not (root / ".nwave" / "des" / "handover.json").exists()


def test_integrating_a_candidate_whose_base_moved_refuses_the_swap(
    root: Path, step
) -> None:
    """Compare-and-swap: a destination that moved refuses, never overwrites."""
    crafted(root, step)
    verified = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is present in the captured evidence"),
        ],
    )
    candidate = block(verified[1], verified[2])["CANDIDATE"]
    (root / "OTHER.md").write_text("someone else\n")
    git(root, "add", "OTHER.md")
    git(root, "commit", "-qm", "a concurrent commit moved the destination")
    moved = git(root, "rev-parse", "HEAD")

    code, _out, _err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    assert code == 1
    assert git(root, "rev-parse", "HEAD") == moved
    assert (root / ".nwave" / "des" / "handover.json").exists()


def recorded_examiner_rejection(root: Path, step) -> tuple[str, Path]:
    """One host-recorded examiner observation, returned with its receipt."""
    crafted(root, step)
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    recorded = _prepare_and_record(root, step, "examiner", candidate, "rejected")
    return candidate, root / recorded["RESULT"]


def decisions(root: Path) -> list[str]:
    """Every durable decision record in this repository, newest message first."""
    named = git(root, "for-each-ref", "--format=%(objectname)", "refs/nwave/decisions")
    return [
        git(root, "log", "-1", "--format=%B", sha) for sha in named.splitlines() if sha
    ]


def test_a_recorded_examination_keeps_its_candidate_bound_observation(
    root: Path, step
) -> None:
    candidate, result = recorded_examiner_rejection(root, step)
    observation = json.loads(result.read_bytes())
    assert observation["role"] == "examiner"
    assert observation["candidate_sha"] == candidate
    assert observation["result"]["outcome"] == "rejected"


def test_integrating_a_candidate_with_a_rejected_observation_is_mechanical(
    root: Path, step
) -> None:
    candidate, _ = recorded_examiner_rejection(root, step)
    head_before = git(root, "rev-parse", "HEAD")

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["INTEGRATED"] == candidate
    assert git(root, "rev-parse", "HEAD") != head_before
    assert decisions(root) == []


def test_a_candidate_no_record_covers_is_still_refused_as_unverified(
    root: Path, step
) -> None:
    crafted(root, step)
    stranger = git(root, "rev-parse", "HEAD")

    code, out, err = step(
        "integrate",
        "--repo-root",
        str(root),
        "--candidate",
        stranger,
    )

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "CandidateUnverified"
    assert decisions(root) == []


def test_native_verify_does_not_offer_an_admission_override_form(
    root: Path, step
) -> None:
    crafted(root, step)
    code, out, err = step("verify", "--repo-root", str(root), answers=[])
    assert code == 0, out + err
    assert "--on-my-evidence" not in out
