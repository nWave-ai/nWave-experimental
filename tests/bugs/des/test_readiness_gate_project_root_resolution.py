"""Regression: the readiness gate reads TRUNK, not the declared project root --
and reports the file it did not find there as one with a broken ENCODING.

OBSERVED (reproduced empirically, 2026-07-26): an orchestrator generates an
envelope with `des dispatch --repo-root <worktree>` and dispatches the crafter.
`verify-readiness-pre-dispatch` refuses with `ReadinessRefused -- 4
invariant(s) failed`, three of them saying `feature-delta could not be read as
UTF-8 text at <TRUNK path>`. On trunk that file does not exist; in the declared
worktree it exists, 29,517 bytes, and `iconv -f UTF-8 -t UTF-8` exits 0 -- it is
perfectly valid UTF-8. The gate read the wrong tree, then mis-named why.

THREE DEFECTS, each with its own AT below:

  1. PATH RESOLUTION. `des dispatch --repo-root X` never stamped a
     `DES-PROJECT-ROOT` marker, so the declaration never reached the hook:
     `DesMarkerParser` reads only the `<!-- DES-PROJECT-ROOT : ... -->` marker
     grammar, and the prose line an operator adds by hand is invisible to it.
     With nothing declared, `_evaluate_u1_intercept` fell back to the
     orchestrator's cwd -- trunk -- and every downstream gate read that tree.
     Cross-worktree dispatch is the NORMAL shape here and a feature-delta is
     born in a worktree before it reaches trunk, so the gate refused, by
     construction, every new feature it exists to serve.

     Corollary (the naive remedy's own trap): a marker that IS present but
     names an unreachable directory is a THIRD state -- declared-but-
     unreachable -- and must be SAID. Silently substituting the cwd is the
     same defect in its worse form: the operator then reads a refusal about
     files missing from a tree they never named.

  2. THE MESSAGE. Three causes lead to three different operator actions, and
     the first two collapsed into the second: absent -> create it (or fix the
     path), and the HOW invokes the PRODUCING TOOL; not-UTF-8 -> re-encode it;
     present-but-missing-a-section -> write the section. The shared read seam
     `des.domain.feature_delta_source.read_feature_delta` now distinguishes
     them once, for all four call sites.

  3. THE ESCAPE HATCH. The refusal's last line teaches re-marking the feature
     as `DES-LANE: bugfix` to skip the ceremony -- printed even when the gate
     had merely looked in the wrong tree, i.e. a gate that, being wrong,
     teaches how to get around itself. It is now withheld whenever the
     feature-delta demonstrably EXISTS.

DRIVING PORTS (Mandate 16, no direct domain testing): the envelope is produced
by the real `des.cli.dispatch.main`, resolved by the real
`pre_tool_use_handler._evaluate_u1_intercept`, and evaluated by the real
`verify_readiness_pre_dispatch.main` -- the same three composition roots the
production flow runs through. The refusal formatter is exercised through
`carpaccio_intercept._readiness_reason`, the function the hook prints from.

RED-for-right-reason (verified by reverting production and re-running):
test 1 fails with `AssertionError` -- the resolved root is the cwd, not the
declared worktree; test 2 fails because the block payload is `None` (the
dispatch is silently re-pointed at the cwd); tests 3-5 fail on the collapsed
message and the unconditional escape hint. None fail on import/collection.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from des.adapters.drivers.hooks import pre_tool_use_handler
from des.adapters.drivers.hooks.carpaccio_intercept import (
    InterceptDecision,
    _readiness_reason,
)
from des.adapters.drivers.hooks.pre_tool_use_handler import _evaluate_u1_intercept
from des.cli import dispatch
from des.cli import verify_readiness_pre_dispatch as gate
from des.domain.feature_delta_source import (
    FEATURE_DELTA_ABSENT,
    FEATURE_DELTA_SECTION_MISSING,
)


_FEATURE_ID = "synthetic-declared-project-root-feature"
_SLICE_ID = "slice-01"

_DELTA_INVARIANTS = (
    "reuse_first_or_design_skip",
    "prefactoring_assessment",
    "sustainability",
)


def _complete_feature_delta() -> str:
    """A feature-delta satisfying every content invariant of the gate.

    Same shape as `_author_feature_delta_with_one_real_slice` in the sibling
    `test_readiness_gate_refuses_nonexistent_slice.py` -- one Slice Plan row,
    a no-overlap Reuse Analysis, a methodology-exempt sustainability marker.
    """
    return (
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_SLICE_ID} | the only planned slice |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )


def _author_delta(repo_root: Path, body: str | None = None) -> Path:
    workspace = repo_root / "docs" / "feature" / _FEATURE_ID
    workspace.mkdir(parents=True, exist_ok=True)
    delta = workspace / "feature-delta.md"
    delta.write_text(body if body is not None else _complete_feature_delta())
    return delta


def _run_gate(repo_root: Path) -> tuple[int, dict]:
    """Invoke `des verify-readiness-pre-dispatch` in-process, capturing its
    JSON verdict line -- the idiom the sibling readiness regressions use."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = gate.main(
            [
                "--feature-id",
                _FEATURE_ID,
                "--slice-id",
                _SLICE_ID,
                "--repo-root",
                str(repo_root),
            ]
        )
    line = next(ln for ln in out.getvalue().splitlines() if ln.startswith("{"))
    return code, json.loads(line)


def _invariant(payload: dict, invariant_id: str) -> dict:
    for inv in payload["invariants"]:
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(f"invariant {invariant_id!r} absent from {payload!r}")


# ---------------------------------------------------------------------------
# 1 -- PATH RESOLUTION: the declared project root is the tree the gate reads
# ---------------------------------------------------------------------------


@pytest.fixture
def declared_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """A real git repo (the orchestrator's cwd) plus a declared project root
    INSIDE it that carries the feature-delta the cwd does not.

    A real `git init` is required here and only here: `validate_project_root`
    verifies repository membership through `git rev-parse --git-common-dir`,
    so a bare `.git` marker directory (enough for the readiness gate itself,
    which has no git dependency) would not exercise the real rule.
    """
    if shutil.which("git") is None:
        pytest.skip("git is unavailable; the marker's repo-membership rule needs it")
    cwd_root = tmp_path / "orchestrator_cwd"
    declared_root = cwd_root / "declared_worktree"
    declared_root.mkdir(parents=True)
    subprocess.run(["git", "-C", str(cwd_root), "init", "-q"], check=True, timeout=30)
    # The dispatch SSOT lives on the RUNTIME axis: `des dispatch` reads it from
    # cwd. Copying the two YAMLs keeps this test hermetic.
    shutil.copytree(
        Path(__file__).resolve().parents[3] / "nWave" / "dispatch",
        cwd_root / "nWave" / "dispatch",
    )
    # `gate_output_produceable` accepts a `.nwave/` skeleton for a non-git root.
    (declared_root / ".nwave").mkdir()
    _author_delta(declared_root)
    return cwd_root, declared_root


def _envelope_for(declared_root: Path) -> str:
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = dispatch.main(
            [
                "--mode",
                "atdd_pure",
                "--project-id",
                _FEATURE_ID,
                "--slice",
                _SLICE_ID,
                "--phase",
                "A_GREEN",
                "--repo-root",
                str(declared_root),
                "--intent",
                "green the slice",
            ]
        )
    assert code == 0, f"des dispatch failed with exit {code}"
    return out.getvalue()


@pytest.mark.negative_at
def test_readiness_reads_the_feature_delta_from_the_declared_project_root(
    declared_worktree: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """THE named oracle: an envelope declaring a project root that carries a
    valid, complete feature-delta ABSENT from the cwd must be READ and
    EVALUATED there -- never refused naming the cwd's path."""
    cwd_root, declared_root = declared_worktree
    monkeypatch.chdir(cwd_root)

    captured: dict[str, Path] = {}

    def _capture(
        *, prompt: str, feature_id: str, project_root: Path, subagent_type: str
    ) -> InterceptDecision:
        captured["project_root"] = project_root
        return InterceptDecision.allow()

    monkeypatch.setattr(pre_tool_use_handler, "intercept_atdd_pure_dispatch", _capture)

    envelope = _envelope_for(declared_root)
    block = _evaluate_u1_intercept(envelope, "nw-software-crafter")

    assert block is None, f"unexpected block: {block!r}"
    resolved = captured.get("project_root")
    assert resolved == declared_root, (
        "the envelope DECLARED its project root via `des dispatch --repo-root "
        f"{declared_root}`; the dispatch gates must resolve against that tree. "
        f"Observed project_root={resolved!r} -- the declaration did not survive "
        "the envelope (no DES-PROJECT-ROOT marker is stamped), so the hook fell "
        "back to its default root and every gate read the wrong tree."
    )

    code, payload = _run_gate(resolved)
    for invariant_id in _DELTA_INVARIANTS:
        inv = _invariant(payload, invariant_id)
        assert inv["satisfied"] is True, (
            f"{invariant_id} must be EVALUATED against the feature-delta at "
            f"{declared_root}, which is valid and complete; observed "
            f"remediation={inv['remediation']!r}"
        )
    assert code == 0, f"expected the gate to clear, got exit {code}: {payload!r}"

    # The discriminating half: the SAME gate pointed at the cwd refuses -- so
    # the assertion above cannot pass vacuously.
    cwd_code, cwd_payload = _run_gate(cwd_root)
    assert cwd_code == 1, "the cwd carries no feature-delta; the gate must refuse"
    assert _invariant(cwd_payload, "sustainability")["satisfied"] is False


@pytest.mark.negative_at
def test_declared_project_root_that_is_unreachable_is_refused_not_swapped_for_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A DECLARED root that does not exist is a third state, and it is SAID.

    Degrading it to the cwd fallback substitutes one tree for another without
    telling anyone -- the same defect as reading the wrong tree, only harder to
    diagnose.
    """
    cwd_root = tmp_path / "orchestrator_cwd"
    cwd_root.mkdir()
    monkeypatch.chdir(cwd_root)

    ran_against: list[Path] = []

    def _record(
        *, prompt: str, feature_id: str, project_root: Path, subagent_type: str
    ) -> InterceptDecision:
        ran_against.append(project_root)
        return InterceptDecision.allow()

    monkeypatch.setattr(pre_tool_use_handler, "intercept_atdd_pure_dispatch", _record)

    missing = tmp_path / "worktree_that_was_removed"
    envelope = (
        "<!-- DES-MODE: atdd_pure -->\n"
        f"<!-- DES-PROJECT-ID: {_FEATURE_ID} -->\n"
        f"<!-- DES-PROJECT-ROOT : {missing} -->\n"
        "green the slice"
    )

    block = _evaluate_u1_intercept(envelope, "nw-software-crafter")

    assert ran_against == [], (
        "the dispatch was silently re-pointed and RAN against "
        f"{ran_against!r} -- a tree the envelope never named"
    )
    assert block is not None, (
        "a DECLARED project root that does not exist must be refused LOUD; "
        "observed an allow"
    )
    reason = block["reason"]
    assert str(missing) in reason, (
        f"the refusal must NAME the declared path; got {reason!r}"
    )
    assert "does-not-exist" in reason, (
        f"the refusal must name WHICH rule refused; got {reason!r}"
    )
    assert "des dispatch --repo-root" in reason, (
        f"the HOW must invoke the producing tool; got {reason!r}"
    )


# ---------------------------------------------------------------------------
# 2 -- THE MESSAGE: absent, undecodable and section-missing are three causes
# ---------------------------------------------------------------------------


@pytest.fixture
def hermetic_repo(tmp_path: Path) -> Path:
    """A repo_root with the `.git` marker the gate accepts (no real git -- the
    readiness gate has zero git dependency) and no feature-delta yet."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / ".git").mkdir()
    return repo_root


@pytest.mark.negative_at
def test_absent_feature_delta_is_reported_as_absent_not_as_an_encoding_fault(
    hermetic_repo: Path,
) -> None:
    _code, payload = _run_gate(hermetic_repo)

    for invariant_id in _DELTA_INVARIANTS:
        inv = _invariant(payload, invariant_id)
        remediation = inv["remediation"] or ""
        assert inv["cause"] == FEATURE_DELTA_ABSENT, (
            f"{invariant_id} must name the ABSENT cause; got {inv['cause']!r}"
        )
        assert "UTF-8" not in remediation, (
            f"{invariant_id} reports a file that does not exist as one that "
            f"could not be decoded -- two causes, two different fixes, and the "
            f"operator is sent to the wrong one: {remediation!r}"
        )
        assert "does not exist" in remediation or "no feature-delta.md" in (
            remediation
        ), f"{invariant_id} must say the file is absent; got {remediation!r}"
        assert "des feature-delta-schema inject" in remediation, (
            f"the HOW for an absent document must invoke the PRODUCING TOOL, "
            f"never hand-authoring advice; got {remediation!r}"
        )


@pytest.mark.negative_at
def test_present_but_undecodable_feature_delta_is_reported_as_an_encoding_fault(
    hermetic_repo: Path,
) -> None:
    delta = _author_delta(hermetic_repo)
    delta.write_bytes(b"# Feature Delta\n\xff\xfe not utf-8 at all\n")

    _code, payload = _run_gate(hermetic_repo)

    for invariant_id in _DELTA_INVARIANTS:
        inv = _invariant(payload, invariant_id)
        remediation = inv["remediation"] or ""
        assert "UTF-8" in remediation, (
            f"{invariant_id} must name the encoding fault; got {remediation!r}"
        )
        assert "EXISTS" in remediation, (
            f"{invariant_id} must say the file is THERE -- the operator must "
            f"not be sent to regenerate it; got {remediation!r}"
        )


def test_present_delta_missing_a_section_names_the_section_not_the_encoding(
    hermetic_repo: Path,
) -> None:
    _author_delta(
        hermetic_repo,
        body=(
            f"# Feature Delta: {_FEATURE_ID}\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| Slice | Value statement |\n"
            "|---|---|\n"
            f"| {_SLICE_ID} | the only planned slice |\n"
        ),
    )

    _code, payload = _run_gate(hermetic_repo)

    inv = _invariant(payload, "reuse_first_or_design_skip")
    assert inv["satisfied"] is False
    assert inv["cause"] == FEATURE_DELTA_SECTION_MISSING, (
        "a readable delta missing a section is neither absent nor undecodable; "
        f"got cause={inv['cause']!r}"
    )
    assert "UTF-8" not in (inv["remediation"] or "")


# ---------------------------------------------------------------------------
# 3 -- THE ESCAPE HATCH: withheld whenever the feature-delta EXISTS
# ---------------------------------------------------------------------------


def _refusal_payload(cause: str) -> str:
    return json.dumps(
        {
            "event": "ReadinessRefused",
            "verdict": "refused",
            "invariants": [
                {
                    "id": "reuse_first_or_design_skip",
                    "status": "failed",
                    "satisfied": False,
                    "remediation": "author the section",
                    "cause": cause,
                }
            ],
        }
    )


@pytest.mark.negative_at
def test_bugfix_lane_escape_is_withheld_when_the_feature_delta_exists() -> None:
    reason = _readiness_reason(_refusal_payload(FEATURE_DELTA_SECTION_MISSING))

    assert "DES-LANE: bugfix" not in reason, (
        "the feature-delta EXISTS and merely lacks a section -- advising the "
        "operator to re-mark the feature as a bugfix is the gate teaching how "
        f"to get around itself: {reason!r}"
    )
    assert "author the section" in reason, (
        f"the real remediation must still be surfaced: {reason!r}"
    )


def test_bugfix_lane_escape_is_still_offered_when_the_feature_delta_is_absent() -> None:
    reason = _readiness_reason(_refusal_payload(FEATURE_DELTA_ABSENT))

    assert "DES-LANE: bugfix" in reason, (
        "a dispatch with NO feature-delta at all is exactly the shape the "
        f"bugfix lane serves -- the escape must stay discoverable: {reason!r}"
    )


def test_bugfix_lane_escape_survives_a_payload_carrying_no_cause() -> None:
    """Absence of the fact is not the opposite fact: a producer that emits no
    `cause` must not have the hint suppressed on its behalf."""
    legacy = json.dumps(
        {
            "event": "ReadinessRefused",
            "invariants": [
                {
                    "id": "slice_plan_section",
                    "status": "failed",
                    "satisfied": False,
                    "remediation": "add the heading",
                }
            ],
        }
    )

    assert "DES-LANE: bugfix" in _readiness_reason(legacy)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
