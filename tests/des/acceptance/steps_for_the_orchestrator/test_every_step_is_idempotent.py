"""L1: a step re-invoked over the state it left succeeds, changes nothing, costs 0.

ADR-DES-003 §2, L1: «if the step succeeds and leaves a state, running the same
step again on that state succeeds, leaves it unchanged, and costs 0.» The design
measured two steps that break it at `steps@6d817bc91`:

- `design` re-buys the architect over a bound value and SILENTLY REPLACES the
  bound facts. Re-binding is spelled `--finding -` and nothing else; anything
  less makes a retry after a lost terminal a paid overwrite.
- `verify` re-builds the candidate and re-buys the whole-diff reviewer AND the
  examiner over unchanged bytes. `CandidateUnchanged` never fires in a lone
  step, because the variable it compares is set only by a correction pass the
  step disables.

The repair for `verify` is a carrier one, not a special case: §5's criterion says
that wherever the orchestrator holds a decision, the carrier must hold the fact
the decision is about. Between `verify` and `integrate` it decides on a VERIFIED
candidate, and nothing recorded it. The record is `refs/nwave/turns/<req>/<req>/
verify`, the same substrate and the same tree-equality predicate as `oracle` and
`craft`, so `integrate` can refuse `CandidateUnverified` on any other SHA and
`des state` can name `integrate` as the canonical next.
"""

from __future__ import annotations

import json
from pathlib import Path

from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    asked,
    block,
    git,
)


REQUEST = "one Request whose every step is invoked twice over the state it left"
ORACLE = "tests/acceptance/test_value.py"
SUPPORT = "tests/acceptance/support.py"
TARGET = "product_value.py"
HANDOVER = Path(".nwave") / "des" / "handover.json"
RED_ORACLE = (
    "import pathlib\nimport sys\n\n\ndef test_value():\n"
    "    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))\n"
    "    from product_value import VALUE\n\n    assert VALUE == 1\n"
)


def design_facts(target: str = TARGET) -> dict:
    return {
        "structured_output": {
            "outcome": "accepted",
            "diagnostic": "bound the typed facts",
            "design_facts": {
                "targets": [{"path": target, "decision": "CREATE_NEW"}],
                "paradigm": "object_oriented",
                "decisions": ["one opaque semantic decision"],
                "oracle": ORACLE,
                "acceptance_supports": [SUPPORT],
                "verification": [["python", "-m", "pytest", ORACLE]],
            },
        }
    }


def verdict(diagnostic: str) -> dict:
    return {"structured_output": {"outcome": "accepted", "diagnostic": diagnostic}}


def authority(root: Path) -> object:
    return json.loads((root / HANDOVER).read_text())["values"][0]["authority"]


def bound(root: Path, step) -> None:
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


def verified(root: Path, step) -> str:
    """Carry one value to an approved, examined candidate."""
    bound(root, step)
    assert (
        step(
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
        )[0]
        == 0
    )
    assert (
        step(
            "craft",
            "--repo-root",
            str(root),
            "--value",
            "1",
            answers=[
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "implemented the value",
                    },
                    "writes": {TARGET: "VALUE = 1\n"},
                }
            ],
        )[0]
        == 0
    )
    code, out, err = step(
        "verify",
        "--repo-root",
        str(root),
        answers=[
            verdict("the whole diff implements the observation"),
            verdict("the promised observation is in the evidence"),
        ],
    )
    assert code == 0, out + err
    return block(out, err)["CANDIDATE"]


def test_l1_design_twice_is_free_and_replaces_nothing(
    root: Path, step, turns: Path
) -> None:
    bound(root, step)
    facts = authority(root)
    spent = len(asked(turns))

    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        answers=[design_facts(target="src/somewhere/else.py")],
    )

    assert code == 0, out + err
    assert block(out, err)["TURNS-BOUGHT"] == "0"
    assert "RECORDED" in block(out, err)
    assert authority(root) == facts
    assert len(asked(turns)) == spent


def test_re_binding_is_spelled_with_a_finding_and_nothing_else(
    root: Path, step, turns: Path
) -> None:
    """L1 does not close the door: it names the one form that opens it."""
    bound(root, step)
    spent = len(asked(turns))
    code, out, err = step(
        "design",
        "--repo-root",
        str(root),
        "--value",
        "1",
        "--finding",
        "-",
        answers=[design_facts(target="src/somewhere/else.py")],
        stdin="the declared target does not exist",
    )
    assert code == 0, out + err
    assert authority(root)["targets"][0]["path"] == "src/somewhere/else.py"
    assert len(asked(turns)) == spent + 1


def test_l1_verify_twice_buys_no_judgement_and_rebuilds_nothing(
    root: Path, step, turns: Path
) -> None:
    candidate = verified(root, step)
    spent = len(asked(turns))

    code, out, err = step("verify", "--repo-root", str(root))

    assert code == 0, out + err
    assert block(out, err)["CANDIDATE"] == candidate
    assert block(out, err)["TURNS-BOUGHT"] == "0"
    assert "RECORDED" in block(out, err)
    assert len(asked(turns)) == spent


def test_the_verified_candidate_is_recorded_and_named_as_the_next_step(
    root: Path, step
) -> None:
    """§5: the carrier holds the fact the orchestrator's decision is about."""
    candidate = verified(root, step)
    refs = git(root, "for-each-ref", "--format=%(refname)", "refs/nwave/turns")
    assert any(line.endswith("/verify") for line in refs.splitlines()), refs

    _code, out, err = step("state", "--repo-root", str(root))
    assert block(out, err)["NEXT"].startswith(
        f"des integrate --repo-root {root} --candidate {candidate}"
    )


def test_integrate_refuses_a_candidate_no_verify_record_covers(
    root: Path, step, turns: Path
) -> None:
    verified(root, step)
    other = git(root, "rev-parse", "HEAD")
    spent = len(asked(turns))

    code, out, err = step("integrate", "--repo-root", str(root), "--candidate", other)

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "CandidateUnverified"
    assert len(asked(turns)) == spent
    assert (root / HANDOVER).exists()
