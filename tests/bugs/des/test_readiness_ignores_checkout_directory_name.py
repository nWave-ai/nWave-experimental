"""Regression: `des verify-readiness-pre-dispatch` refuses on
`scenario_slice_tags` when the CHECKOUT DIRECTORY happens to be named like the
feature id -- every `.feature` file in the repo is then mistaken for one of the
feature's own.

Root cause (single locus, diagnosed + reproduced): `_check_scenario_slice_tags`
(`src/des/cli/verify_readiness_pre_dispatch.py`, legacy leg (a)) selects the
feature's legacy `.feature` files with

    [p for p in tests_dir.rglob("*.feature") if feature_id in p.parts]

`p` is an ABSOLUTE path, so `p.parts` includes every ancestor directory of the
checkout -- including the checkout directory's own name. A worktree checked out
at `.../wt/<feature-id>/` therefore matches EVERY `.feature` file in the tree,
and any untagged scenario belonging to ANOTHER feature refuses the dispatch.
Measured on the real defect: 484 `.feature` files matched (expected 0) and 536
untagged scenarios owned by other features, refusing a feature that owns no
`.feature` file at all.

THE PROPERTY under test (not the shape of the fix): **the name of the directory
the repo happens to be checked out into is not a selector.** The same repo
content must produce the same `scenario_slice_tags` verdict whether the checkout
directory is named after the feature or not. The test asserts that invariance on
two axes -- the absolute verdict for the feature-named checkout, and its equality
with a neutrally-named checkout holding byte-identical content -- so it survives
any implementation that makes the selection repo-root-relative.

Driving port (Mandate 16, no-direct-domain-testing; mirrors the established
idiom of `test_readiness_not_vacuously_cleared_on_zero_scenario_slice.py`):
drives `des.cli.verify_readiness_pre_dispatch.main(argv)` -- the SAME
composition root `des verify-readiness-pre-dispatch` dispatches -- and reads the
emitted stdout JSON verdict line. In-process, hermetic, box-light: no
subprocess, no git, no network.

RED-for-right-reason before the fix: a genuine semantic `AssertionError` --
`scenario_slice_tags` reports `satisfied: false` for the feature-named checkout
while reporting `satisfied: true` for the byte-identical neutrally-named one --
never an import/collection error.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest

from des.cli import verify_readiness_pre_dispatch as readiness_gate


_FEATURE_ID = "synthetic-checkout-dir-name-feature"
_OTHER_FEATURE_ID = "synthetic-unrelated-neighbour-feature"
_SLICE_ID = "slice-01"
_NEUTRAL_CHECKOUT_DIR = "neutrally-named-checkout"
_INV_SCENARIO_TAGS = "scenario_slice_tags"


def _author_repo(checkout_dir: Path) -> Path:
    """Author a hermetic repo at `checkout_dir` whose CONTENT is identical
    regardless of the directory's name.

    Content:
      * a bare `.git` marker (no real `git init` -- the gate is git-free,
        target-machine agnosticism);
      * a feature-delta for `_FEATURE_ID` with ONE Slice-Plan row so the other
        readiness invariants are satisfiable;
      * ZERO `.feature` files for `_FEATURE_ID` -- it has not been distilled;
      * ONE `.feature` file belonging to a DIFFERENT feature
        (`@feature-{_OTHER_FEATURE_ID}`) carrying an UNTAGGED scenario. It is
        not this feature's file by either resolver: it neither self-identifies
        with `@feature-{_FEATURE_ID}` (leg (b), tag-based) nor sits under a
        `{_FEATURE_ID}` path segment RELATIVE TO THE REPO ROOT (leg (a),
        path-based). Only an absolute-path comparison can mistake it for one.
    """
    checkout_dir.mkdir(parents=True)
    (checkout_dir / ".git").mkdir()

    workspace = checkout_dir / "docs" / "feature" / _FEATURE_ID
    workspace.mkdir(parents=True)
    (workspace / "feature-delta.md").write_text(
        f"# Feature Delta: {_FEATURE_ID}\n\n"
        "## Wave: DISCUSS / [REF] Slice Plan\n\n"
        "| Slice | Value statement |\n"
        "|---|---|\n"
        f"| {_SLICE_ID} | not yet distilled -- owns no .feature file |\n\n"
        "## Reuse Analysis\n\n"
        "Reuse-Analysis: no-overlap\n\n"
        "## Test Reuse & Consolidation Analysis\n\n"
        "Test-Reuse-Analysis: methodology-exempt\n"
    )

    neighbour_dir = checkout_dir / "tests" / "acceptance" / _OTHER_FEATURE_ID
    neighbour_dir.mkdir(parents=True)
    (neighbour_dir / "untagged_neighbour.feature").write_text(
        f"@feature-{_OTHER_FEATURE_ID}\n"
        "Feature: A scenario owned by an entirely unrelated feature\n\n"
        "  Scenario: An untagged scenario belonging to another feature\n"
        "    Given a precondition the neighbour feature sets up\n"
        "    When the neighbour behavior runs\n"
        "    Then the neighbour outcome is observed\n"
    )
    return checkout_dir


def _run_readiness(repo_root: Path) -> tuple[int, dict]:
    """Invoke `des verify-readiness-pre-dispatch`'s `main(argv)` in-process and
    capture the emitted stdout JSON verdict line."""
    argv = [
        "--feature-id",
        _FEATURE_ID,
        "--slice-id",
        _SLICE_ID,
        "--repo-root",
        str(repo_root),
    ]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = readiness_gate.main(argv)
    line = next(
        (
            ln
            for ln in reversed(out.getvalue().splitlines())
            if ln.strip().startswith("{")
        ),
        "{}",
    )
    return code, json.loads(line)


def _invariant(report: dict, invariant_id: str) -> dict:
    for inv in report.get("invariants", []):
        if inv["id"] == invariant_id:
            return inv
    raise AssertionError(
        f"invariant {invariant_id!r} missing from report entirely -- the gate "
        f"must always emit every invariant it evaluates. observed "
        f"report={report}"
    )


@pytest.mark.negative_at
def test_scenario_slice_tags_ignores_checkout_directory_name(
    tmp_path: Path,
) -> None:
    """The checkout directory's NAME must not select which `.feature` files
    belong to the feature.

    Two byte-identical repos are authored; only the name of the directory each
    is checked out into differs -- one is named exactly `_FEATURE_ID`, the
    other is neutrally named. Neither repo contains a single `.feature` file
    owned by `_FEATURE_ID`; both contain one untagged scenario owned by an
    unrelated neighbour feature. The `scenario_slice_tags` invariant must be
    satisfied in BOTH, and must be the SAME in both.

    RED before the fix: leg (a) tests `feature_id in p.parts` on an ABSOLUTE
    path, so in the feature-named checkout the neighbour's untagged scenario is
    attributed to `_FEATURE_ID` and the invariant reports `satisfied: false`,
    while the neutrally-named checkout with identical content reports
    `satisfied: true`.

    CONTRACT_SHAPE: pure-function
    """
    feature_named_repo = _author_repo(tmp_path / "checkouts" / _FEATURE_ID)
    neutral_repo = _author_repo(tmp_path / "checkouts" / _NEUTRAL_CHECKOUT_DIR)

    neutral_code, neutral_report = _run_readiness(neutral_repo)
    neutral_inv = _invariant(neutral_report, _INV_SCENARIO_TAGS)
    # Control assertion: with a neutrally-named checkout the invariant already
    # behaves correctly today. If THIS ever fails the fixture is malformed
    # (or another invariant broke), not the defect under test.
    assert neutral_inv["satisfied"] is True, (
        "fixture control check failed: with a neutrally-named checkout "
        "directory, scenario_slice_tags must be satisfied -- the feature owns "
        "no .feature file and the only scenario present belongs to an "
        f"unrelated feature. observed={neutral_inv}, "
        f"code={neutral_code}, report={neutral_report}"
    )

    named_code, named_report = _run_readiness(feature_named_repo)
    named_inv = _invariant(named_report, _INV_SCENARIO_TAGS)

    assert named_inv["satisfied"] is True, (
        "scenario_slice_tags must be satisfied when the feature owns no "
        ".feature file, regardless of what the checkout directory is named. "
        "THE BUG: _check_scenario_slice_tags's legacy leg (a) filters "
        "`tests_dir.rglob('*.feature')` with `feature_id in p.parts` on an "
        "ABSOLUTE path, so a checkout directory named "
        f"{_FEATURE_ID!r} makes EVERY .feature file in the repo match -- here "
        "the untagged scenario of an unrelated neighbour feature. observed "
        f"={named_inv}, code={named_code}, report={named_report}"
    )

    assert named_inv["satisfied"] == neutral_inv["satisfied"], (
        "the scenario_slice_tags verdict must be invariant under the name of "
        "the directory the repo is checked out into: two repos with "
        "byte-identical content disagreed. feature-named checkout "
        f"({feature_named_repo.name!r}) -> {named_inv}; neutrally-named "
        f"checkout ({neutral_repo.name!r}) -> {neutral_inv}"
    )
