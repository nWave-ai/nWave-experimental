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
import sys
from pathlib import Path

from tests.des._helpers.host_facts import design_manifest
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    git,
    observation,
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
            "manifest": design_manifest(
                {
                    "targets": [{"path": target, "decision": "CREATE_NEW"}],
                    "paradigm": "object_oriented",
                    "decisions": ["one opaque semantic decision"],
                    "oracle": ORACLE,
                    "acceptance_supports": [SUPPORT],
                    "verification": [[sys.executable, "-m", "pytest", ORACLE]],
                    "oracle_verification_index": 0,
                    "architectural_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no structural boundary change.",
                    },
                    "contract_tests": {
                        "applicability": "not_applicable",
                        "reason": "The fixture changes no shared contract.",
                    },
                    "prefactoring": {
                        "applicability": "not_applicable",
                        "reason": "The fixture requires no preservation move.",
                    },
                    "agreement_analysis": {
                        "applicability": "not_applicable",
                        "reason": "The fixture has no affected agreement.",
                    },
                    "reuse_analysis": {"candidates": []},
                    "impact_closure": {
                        "applicability": "not_applicable",
                        "reason": "The fixture reaches no public surface, consumer or build metadata.",
                    },
                },
                observation("A"),
                1,
            ),
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


def test_l1_verify_twice_buys_no_judgement_and_rebuilds_nothing(
    root: Path, step, turns: Path
) -> None:
    candidate = verified(root, step)

    code, out, err = step("verify", "--repo-root", str(root))

    assert code == 0, out + err
    assert block(out, err)["CANDIDATE"] == candidate


def test_changed_handover_gets_a_new_candidate_even_with_identical_source_and_clock(
    root: Path, step, monkeypatch
) -> None:
    from des.application.handover import (
        StoredHandover,
        _canonical_bytes,
        _CanonicalProjection,
        read_handover,
    )

    monkeypatch.setenv("GIT_AUTHOR_DATE", "2000-01-01T00:00:00+0000")
    monkeypatch.setenv("GIT_COMMITTER_DATE", "2000-01-01T00:00:00+0000")
    candidate = verified(root, step)
    handover = root / HANDOVER
    original = handover.read_bytes()
    stored = read_handover(original)
    assert isinstance(stored, StoredHandover)
    revised_raw = _canonical_bytes(
        stored.request,
        stored.values,
        feature_id=stored.feature_id,
        shared=stored.shared_design,
        product_authority=stored.product_authority,
        projection=_CanonicalProjection(include_scope=False),
    )
    assert revised_raw != original
    assert isinstance(read_handover(revised_raw), StoredHandover)
    handover.write_bytes(revised_raw)

    code, out, err = step("verify", "--repo-root", str(root))

    assert code == 0, out + err
    revised = block(out, err)["CANDIDATE"]
    assert revised != candidate
    assert git(root, "rev-parse", f"{candidate}^{{tree}}") == git(
        root, "rev-parse", f"{revised}^{{tree}}"
    )
    snapshots = root / ".nwave/des/candidates"
    assert (snapshots / candidate / "handover.json").read_bytes() == original
    assert (snapshots / revised / "handover.json").read_bytes() == revised_raw


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

    code, out, err = step("integrate", "--repo-root", str(root), "--candidate", other)

    assert code == 1
    lines = block(out, err)
    assert lines["WHAT"] == "CandidateUnverified"

    assert (root / HANDOVER).exists()
