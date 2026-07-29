"""The commit-time examine gate must arm on the charter PROPERTY, never on the
charter DESIGNATION (GDP-8).

Defect (measured 2026-07-28): ``des commit-slice``'s examine gate arms when a
*file* exists under ``docs/product/expectations/{feature_id}/*.md`` -- the
DESIGNATION -- with no check that the charter can actually serve as an oracle.
A scaffold carrying only ``## Intent`` (Preconditions / Charter / Expected
observations still the literal template placeholders) therefore armed the gate,
whose refusal then instructed the operator to *dispatch nw-user-examiner with
the slice's charter*. An examiner was dispatched against exactly such a hollow
scaffold; the verdict it would have produced described the charter, not the
code. A lane's vigilance stopped it -- not the gate built for it.

The property is already computed by ``des verify-charter-filled``
(``src/des/cli/verify_charter_filled.py``), whose own docstring says it exists
so *"a hollow scaffold can never masquerade as a real one"*, and which the
DISTILL skill declares mandatory before a charter may arm a DELIVER EXAMINE.
It had ZERO callers in the flow: catalogued but never armed.

THIRD STATE (the arity that must survive): "no charter at all" (gate unarmed --
the feature never adopted the convention, backward-compatible no-op) is a
DIFFERENT outcome from "charter present but hollow" (a LOUD refusal naming the
charter and the sections still unfilled). Collapsing the second into the first
would let an empty scaffold pass for a feature that opted out.

Driving surface: ``des.cli.commit_slice.check_examine_verdict(repo,
feature_id, slice_id)`` -- the real decision point the commit path calls, and
the one that renders the "dispatch the examiner" instruction. Pure filesystem,
no git (the target-machine-agnosticism constraint the gate itself is under).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.cli.commit_slice import check_examine_verdict


FEATURE_ID = "fix-charter-filled-unwired"
SLICE_ID = "slice-01"

#: A scaffold that was created and never filled -- the exact shape observed on
#: 2026-07-28: an authored Intent, every judgment section still the verbatim
#: template placeholder from `nWave/templates/expectation-charter.md`.
HOLLOW_CHARTER = """# The operator sees the thing
ID: EXP-fix-1 - Spec rows: R1 - Persona: operator

## Intent
The operator accomplishes the thing that matters.

## Preconditions
<start recipe: how to run the system from a clean state, seed state>

## Charter
Explore <area> via <surface: browser/CLI/API> to verify <intent>.

## Expected observations (oracle)
- <observable outcome, user language>
- <negative: what must NOT happen>

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""

#: The same charter, genuinely FILLED -- a real start recipe, real observations,
#: and the >=1 negative observation the oracle contract requires.
FILLED_CHARTER = """# The operator sees the thing
ID: EXP-fix-1 - Spec rows: R1 - Persona: operator

## Intent
The operator accomplishes the thing that matters.

## Preconditions
cd into the tree under test and run `uv run des commit-slice --help` from a
clean checkout with no staged changes.

## Charter
Explore the commit path via the CLI to verify the examine gate arms honestly.

## Expected observations (oracle)
- The refusal names the charter file by path.
- Negative: the operator is NOT told to dispatch an examiner against it.

## Session log (append-only)
| date | examiner | verdict | observations |
|------|----------|---------|--------------|
"""


def _write_charter(repo: Path, body: str, name: str = "intent.md") -> Path:
    charter_dir = repo / "docs" / "product" / "expectations" / FEATURE_ID
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / name
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return tmp_path


def test_hollow_charter_is_not_given_the_same_outcome_as_a_filled_charter(
    tmp_path: Path,
) -> None:
    """NEGATIVE AT -- the wrong outcome must NOT be produced.

    The gate currently decides on the DESIGNATION: a file exists, therefore
    arm. So a hollow scaffold and a genuinely filled charter yield the SAME
    verdict -- ``ExamineVerdictMissing``, whose remediation instructs
    dispatching nw-user-examiner. The gate is blind to the only difference
    that matters, and that blindness is what put an examiner in front of an
    empty scaffold. Two inputs that differ in the decisive property must not
    collapse to one outcome.
    """
    hollow_repo = tmp_path / "hollow"
    hollow_repo.mkdir()
    _write_charter(hollow_repo, HOLLOW_CHARTER)

    filled_repo = tmp_path / "filled"
    filled_repo.mkdir()
    _write_charter(filled_repo, FILLED_CHARTER)

    hollow_outcome = check_examine_verdict(hollow_repo, FEATURE_ID, SLICE_ID)
    filled_outcome = check_examine_verdict(filled_repo, FEATURE_ID, SLICE_ID)

    assert filled_outcome is not None, (
        "precondition: a filled charter arms the gate on an unexamined slice"
    )
    assert hollow_outcome is not None, (
        "a hollow charter must not clear the gate silently either"
    )
    assert hollow_outcome.get("event") != filled_outcome.get("event"), (
        "the gate gave a hollow scaffold and a real charter the SAME verdict "
        f"({filled_outcome.get('event')!r}) -- it decided on the file's "
        "EXISTENCE, not on whether the charter can serve as an oracle, so an "
        "examiner gets dispatched against an empty scaffold"
    )


def test_absent_charter_leaves_the_gate_unarmed(repo: Path) -> None:
    """BACKWARD-COMPAT / third state: a feature that never adopted the charter
    convention has NO charter, and the gate stays a no-op (``None``). This is
    the outcome a present-but-hollow charter must NOT be collapsed into.
    """
    assert check_examine_verdict(repo, FEATURE_ID, SLICE_ID) is None, (
        "with no charter at all the gate must remain unarmed (no-op)"
    )


def test_hollow_charter_refusal_names_the_charter_and_never_dispatches_an_examiner(
    repo: Path,
) -> None:
    """The refusal is LOUD and self-explaining (WHAT / WHY / HOW), it names the
    hollow charter and the sections still unfilled, and -- the damage that was
    actually done -- its HOW routes to the producing tool
    (``des verify-charter-filled``) instead of instructing a dispatch of
    nw-user-examiner against an oracle that cannot judge anything.
    """
    charter_path = _write_charter(repo, HOLLOW_CHARTER)

    outcome = check_examine_verdict(repo, FEATURE_ID, SLICE_ID)

    assert outcome is not None, "a hollow charter must refuse, not clear"
    assert "exit_code" in outcome, (
        "the payload must be a REFUSAL (carrying exit_code), not the "
        "exit_code-less DEFER shape"
    )
    for key in ("what", "why", "how"):
        assert str(outcome.get(key, "")).strip(), f"refusal is missing a {key!r}"

    rendered = " ".join(str(outcome.get(k, "")) for k in ("what", "why", "how"))
    assert charter_path.name in rendered, (
        f"the refusal must NAME the hollow charter; got: {rendered!r}"
    )
    assert "verify-charter-filled" in rendered, (
        "the HOW must invoke the producing/verifying tool "
        f"`des verify-charter-filled`; got: {rendered!r}"
    )
    assert "nw-user-examiner" not in rendered, (
        "the refusal must NOT instruct dispatching an examiner against a "
        f"charter that cannot serve as an oracle; got: {rendered!r}"
    )


def test_filled_charter_still_arms_the_examine_gate_unchanged(repo: Path) -> None:
    """No regression on the honest path: a genuinely FILLED charter arms the
    gate exactly as before -- an unexamined slice still gets
    ``ExamineVerdictMissing`` and IS told to dispatch the examiner.
    """
    _write_charter(repo, FILLED_CHARTER)

    outcome = check_examine_verdict(repo, FEATURE_ID, SLICE_ID)

    assert outcome is not None, "a filled charter must still ARM the gate"
    assert outcome.get("event") == "ExamineVerdictMissing", (
        f"expected the pre-existing missing-verdict refusal; got {outcome!r}"
    )
    assert "nw-user-examiner" in str(outcome.get("how", "")), (
        "on a filled charter the examiner dispatch instruction is correct and "
        "must survive"
    )


def test_one_filled_charter_among_several_still_arms(repo: Path) -> None:
    """A feature mid-authoring -- one charter filled, a later one still a
    scaffold -- must not be blocked: the property "this feature has a usable
    oracle" holds, so the gate arms normally rather than refusing.
    """
    _write_charter(repo, FILLED_CHARTER, name="slice-01.md")
    _write_charter(repo, HOLLOW_CHARTER, name="slice-99-not-yet-authored.md")

    outcome = check_examine_verdict(repo, FEATURE_ID, SLICE_ID)

    assert outcome is not None
    assert outcome.get("event") == "ExamineVerdictMissing", (
        "a feature with at least one filled charter has a usable oracle -- "
        f"the gate must arm normally, not refuse; got {outcome!r}"
    )
