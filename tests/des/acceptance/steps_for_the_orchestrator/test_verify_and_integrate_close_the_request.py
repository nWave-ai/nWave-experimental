"""Public oracle: `des verify` and `des integrate`, the last two steps.

ADR-SSOT-002 Section 4b names four properties across these two commands:
constructing the whole-Request candidate from an identified base, verifying
natively on it, judging the promised observation source-blind, and integrating
by compare-and-swap with the owned index reconciled and the workspace released.

WHY THE JUDGEMENT LIVES IN `des verify` AND NOT IN A THIRD COMMAND.  Section 4b
keeps two invariants that decide it together: native evidence is «captured
exactly once and never re-executed», and for the source-blind pass «the software
still CONSTRUCTS those three inputs».  A separate command could only satisfy
both by carrying captured stdout and stderr across two processes, and the only
places to carry it are new owned state -- which Section 4b's own falsifiers
forbid -- or the orchestrator's hands, which would make the software stop
constructing the input it must construct.  So the capture and the judgement
share one process, and the orchestrator's real choice is preserved where it
actually exists: after the terminal, where `des integrate` remains a step of its
own that it may invoke with evidence of its own.

NO CORRECTION PASS.  The composed run answers a failed verification or a vetoed
diff with one crafter correction turn.  Invoked alone this step returns the
finding instead: Section 4b makes the fixed correction edges moves an
orchestrator may make, never moves the runner takes on its own.
"""

from __future__ import annotations

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
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def verdict(diagnostic: str, outcome: str = "accepted") -> dict:
    return {"structured_output": {"outcome": outcome, "diagnostic": diagnostic}}


def crafted(root: Path, step) -> None:
    """Everything `des verify` consumes: bound, admitted oracle, crafted batch."""
    assert (
        step(
            "po",
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


def test_verify_builds_one_candidate_runs_it_natively_and_judges_it(
    root: Path, step, turns: Path
) -> None:
    crafted(root, step)
    head_before = git(root, "rev-parse", "HEAD")
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is present in the captured evidence"),
        ],
    )
    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert len(lines["CANDIDATE"]) == 40
    assert "NATIVE" in lines
    assert asked(turns)[-2:] == ["nw-software-crafter-reviewer", "nw-user-examiner"]
    # The candidate is a real commit parented on the base, and HEAD has NOT moved.
    assert git(root, "rev-parse", f"{lines['CANDIDATE']}^") == head_before
    assert git(root, "rev-parse", "HEAD") == head_before
    assert nexts(out)[0].startswith(
        f"des integrate --repo-root {root} --candidate {lines['CANDIDATE']}"
    )


def test_a_vetoed_diff_returns_the_finding_and_buys_no_correction_turn(
    root: Path, step, turns: Path
) -> None:
    crafted(root, step)
    spent = len(asked(turns))
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the diff changes a path no value in this Request owns", "rejected")
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"].startswith("ImplementationReviewRejected")
    assert "no value in this Request owns" in lines["DIAGNOSTIC"]
    # ONE reviewer turn: no correction crafter, no examiner behind a veto.
    assert len(asked(turns)) == spent + 1
    assert git(root, "status", "--porcelain") != ""


def test_a_rejecting_examiner_names_the_candidate_and_moves_no_ref(
    root: Path, step
) -> None:
    crafted(root, step)
    head_before = git(root, "rev-parse", "HEAD")
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is absent from the evidence", "rejected"),
        ],
    )
    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"].startswith("ExamineRejected on candidate ")
    assert git(root, "rev-parse", "HEAD") == head_before
    assert f"des integrate --repo-root {root} --candidate " in " ".join(nexts(out))


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


def test_verify_and_integrate_need_current_bytes_not_each_roles_history(
    root: Path, step, turns: Path
) -> None:
    """One shared green oracle admits all designed values without old role refs."""
    assert (
        step(
            "po",
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
    assert asked(turns)[spent:] == ["nw-software-crafter-reviewer", "nw-user-examiner"]
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


def refused_examination(root: Path, step) -> str:
    """A candidate the examiner did NOT admit, returned by its SHA."""
    crafted(root, step)
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is absent from the evidence", "rejected"),
        ],
    )
    assert code == 1, out + err
    return block(out, err)["WHAT"].rpartition(" on candidate ")[2].strip()


def decisions(root: Path) -> list[str]:
    """Every durable decision record in this repository, newest message first."""
    named = git(root, "for-each-ref", "--format=%(objectname)", "refs/nwave/decisions")
    return [
        git(root, "log", "-1", "--format=%B", sha) for sha in named.splitlines() if sha
    ]


def test_a_refused_examination_still_records_the_candidate_with_its_verdict(
    root: Path, step
) -> None:
    candidate = refused_examination(root, step)

    recorded = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")

    assert any(name.endswith("/verify") for name in recorded.splitlines())
    subject = git(
        root,
        "log",
        "-1",
        "--format=%s",
        next(
            name for name in recorded.splitlines() if name.endswith("/verify-outcome")
        ),
    )
    assert subject == "nwave verify: not-admitted"
    assert candidate in git(
        root, "for-each-ref", "--format=%(objectname)", "refs/nwave/turns"
    )


def test_integrating_a_candidate_the_judge_refused_names_the_flag_it_needs(
    root: Path, step
) -> None:
    candidate = refused_examination(root, step)
    head_before = git(root, "rev-parse", "HEAD")

    code, out, err = step(
        "integrate", "--repo-root", str(root), "--candidate", candidate
    )

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "CandidateNotAdmitted"
    assert "not-admitted" in lines["WHY"]
    assert f"--candidate {candidate} --on-my-evidence -" in lines["HOW"]
    assert git(root, "rev-parse", "HEAD") == head_before
    assert decisions(root) == []


def test_the_orchestrator_may_integrate_on_its_own_evidence_and_it_is_recorded(
    root: Path, step
) -> None:
    candidate = refused_examination(root, step)

    code, out, err = step(
        "integrate",
        "--repo-root",
        str(root),
        "--candidate",
        candidate,
        "--on-my-evidence",
        "-",
        stdin="I ran the oracle myself against the installed runtime and saw it pass",
    )

    assert code == 0, out + err
    lines = block(out, err)
    assert lines["DELIVERY-OUTCOME"] == "Success"
    assert lines["INTEGRATED"] == candidate
    assert git(root, "rev-parse", "HEAD") == candidate
    recorded = decisions(root)
    assert len(recorded) == 1
    assert "over verdict: not-admitted" in recorded[0]
    assert "I ran the oracle myself" in recorded[0]


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
        "--on-my-evidence",
        "-",
        stdin="a candidate this Request never built",
    )

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "CandidateUnverified"
    assert decisions(root) == []


def test_a_refused_examination_offers_the_form_the_next_step_accepts(
    root: Path, step
) -> None:
    crafted(root, step)
    code, out, _err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation and nothing else"),
            verdict("the promised observation is absent from the evidence", "rejected"),
        ],
    )
    assert code == 1
    offered = next(line for line in nexts(out) if line.startswith("des integrate"))

    assert "--on-my-evidence -" in offered
