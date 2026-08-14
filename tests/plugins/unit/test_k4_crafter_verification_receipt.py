"""K4 crafter verification receipt — terminal gate before Examiner/commit (2026-08-13).

Confirmed defect: nw-software-crafter ran `python3 manage.py test hc.api
hc.front`, observed 4 failures plus 2 errors, then its async Agent result
completed/truncated mid-sentence. Root noticed the truncation but treated a
focused AT green plus Examiner PASS as sufficient and committed anyway.
Hidden acceptance was 6/6 but the subject regression had failed — the
terminating full relevant suite's outcome was never captured as a checkable
fact, so a truncated/failing run was indistinguishable from a clean one.

Tests verify, anchored on nw-software-crafter.md's own dispatch-authority
paragraph in agreement with nw-auto/SKILL.md's "## M/L route" Join step:
(a) the crafter's own spec obligates a terminal verification receipt
    (outcome/argv/scope/exit_code) after the terminating suite run, with
    PASS requiring exit_code == 0 and an incomplete/missing run stated as
    incomplete
(b) nw-auto's Join step requires that same receipt, present and well-formed,
    before dispatching the examiner or committing
(c) a missing/malformed/truncated/nonzero/FAIL receipt is terminal FAIL
    under the single-pass rule: preserve WIP, no retry/resume/root
    repair/source-inspection substitution
(d) a focused-AT-green result or an Examiner PASS is explicitly barred from
    substituting for the receipt
(e) the receipt's field vocabulary (outcome/argv/scope/exit_code) agrees,
    verbatim, across both files
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

CRAFTER_ANCHOR = "For a validated thin delivery, `DeliveryContract.targets`"
SIBLING_ANCHOR = "1. `nw-acceptance-designer` (every run):"
JOIN_ANCHOR = "3. **Join**:"
EXAMINER_ANCHOR = "4. `nw-user-examiner` (only if `examine=true`):"

RECEIPT_FIELDS = ("outcome", "argv", "scope", "exit_code")


def _crafter_body() -> str:
    return (AGENTS_DIR / "nw-software-crafter.md").read_text(encoding="utf-8")


def _skill_body() -> str:
    return (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _crafter_dispatch_paragraph() -> str:
    body = _crafter_body()
    start = body.index(CRAFTER_ANCHOR)
    end = body.index("## Workflow Mode Dispatch")
    return _normalized(body[start:end])


def _join_step() -> str:
    body = _skill_body()
    start = body.index(JOIN_ANCHOR)
    end = body.index(EXAMINER_ANCHOR)
    return _normalized(body[start:end])


def _sibling_dispatch_step() -> str:
    body = _skill_body()
    start = body.index(SIBLING_ANCHOR)
    end = body.index(JOIN_ANCHOR)
    return _normalized(body[start:end])


class TestCrafterVerificationReceipt:
    """Terminal receipt contract: crafter emits it, root gates on it."""

    def test_crafter_spec_obligates_terminal_receipt_with_pass_semantics(self):
        """(a) Crafter's own spec: receipt fields, PASS == exit 0, incomplete-if-missing."""
        paragraph = _crafter_dispatch_paragraph()
        for token in (
            "concise terminal verification receipt",
            "never a paraphrase",
            "outcome: PASS|FAIL",
            "exit_code == 0",
            "incomplete, not done",
        ):
            assert token in paragraph, f"Missing: {token}"
        for field in RECEIPT_FIELDS:
            assert f"`{field}" in paragraph or f" {field}:" in paragraph, (
                f"Receipt field missing from crafter spec: {field}"
            )

    def test_join_step_requires_receipt_before_examiner_or_commit(self):
        """(b) Root gates the conditional examiner on a terminal receipt."""
        join = _join_step()
        for token in (
            "returns the ephemeral receipt",
            "outcome: PASS|FAIL",
            "argv",
            "scope",
            "exit_code",
            "verification-scope.commands",
            "scope` to cover them",
            "every exit code to be zero",
            "terminal FAIL",
            "focused-AT green or Examiner PASS never substitutes",
            "No receipt ledger/artifact",
        ):
            assert token in join, f"Missing: {token}"
        body = _skill_body()
        assert body.index(JOIN_ANCHOR) < body.index(EXAMINER_ANCHOR)

    def test_bad_receipt_is_terminal_fail_preserving_wip_no_repair_paths(self):
        """(c) Missing/malformed/truncated/nonzero/FAIL receipt is terminal FAIL."""
        join = _join_step()
        for token in (
            "Missing/malformed/truncated/mismatched/nonzero/FAIL",
            "terminal FAIL",
            "preserve WIP",
        ):
            assert token in join
        assert "single-pass rule" in join

    def test_receipt_field_vocabulary_agrees_across_crafter_and_root(self):
        """The crafter owns receipt production; root verifies its full interface."""
        paragraph = _crafter_dispatch_paragraph()
        join = _join_step()
        for field in RECEIPT_FIELDS:
            assert field in paragraph, f"Crafter spec missing field: {field}"
            assert field in join, f"nw-auto Join step missing field: {field}"

    def test_join_anchor_is_the_sole_stable_owner(self):
        """The Join step must exist exactly once; removal must fail this suite."""
        body = _skill_body()
        assert body.count(JOIN_ANCHOR) == 1
        assert body.index(JOIN_ANCHOR) < body.index(EXAMINER_ANCHOR)
