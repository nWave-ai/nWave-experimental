"""Regression: `run_contract_gate._node_belongs_to_slice` must recognize a
pytest-only-authored AT, not only a sibling `.feature` file.

DEFECT (agnostic-at-discovery-ssot-repair, gap 2, second site): the run-scope
membership check `_node_belongs_to_slice` -- used by `run_slice_ats` /
`_slice_run_scope` to classify a collected node-id as in-slice vs
out-of-slice -- resolved membership EXCLUSIVELY by globbing `*.feature` files
in the node's own directory and reading their `@<entering_slice>` tag. A node
whose OWN pytest file is head-comment-tagged `@<entering_slice>` (the SAME
convention ADR-AAD-001 and gap 1 of this repair already trust as first-class)
was always reported out-of-slice, however the node was reached -- one more
Gherkin-only authority for a fact the module already resolves agnostically
elsewhere (`_authored_slice_tags`, `_mode_feature_scoped`).

The fix adds a pytest arm: when no sibling `.feature` carries the tag, the
node's OWN file is checked via `resolve_test_file_attribution` (filtered
through `is_pytest_collectible`), the SAME resolver pair the Gherkin-file-free
fixes in this repair already compose -- no new discovery mechanism.

Driving surface: `_node_belongs_to_slice(repo, node_id, entering_slice)`
called directly, in-process -- a pure filesystem read, no pytest collection,
no subprocess.
"""

from __future__ import annotations

from pathlib import Path

from des.cli.run_contract_gate import _node_belongs_to_slice


def _write_pytest_only_at(
    project_dir: Path, entering_slice: str, *, rel_dir: str, filename: str
) -> Path:
    """A pytest-collectible AT head-tagged `@<entering_slice>`, with no sibling
    `.feature` file anywhere in its directory."""
    scope_dir = project_dir / rel_dir
    scope_dir.mkdir(parents=True, exist_ok=True)
    at_file = scope_dir / filename
    at_file.write_text(
        f"# @feature-gap2-node-membership-probe\n# @{entering_slice}\n"
        "def test_behaviour():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )
    return at_file


def test_pytest_only_node_in_own_slice_is_in_slice(tmp_path: Path) -> None:
    """POSITIVE (active-RED before the fix): a node-id whose OWN pytest file
    is head-tagged for the entering slice, with NO sibling `.feature`, must be
    classified in-slice."""
    project_dir = tmp_path / "repo"
    at_file = _write_pytest_only_at(
        project_dir,
        "slice-01",
        rel_dir="tests/acceptance/gap2_node_membership",
        filename="test_login_flow.py",
    )
    rel = at_file.relative_to(project_dir)
    node_id = f"{rel}::test_behaviour"

    assert _node_belongs_to_slice(project_dir, node_id, "slice-01") is True


def test_pytest_only_node_tagged_for_a_different_slice_is_out_of_slice(
    tmp_path: Path,
) -> None:
    """NEGATIVE (invariance pin): a pytest-only node tagged for a DIFFERENT
    slice must still be reported out-of-slice -- the fix widens WHAT counts as
    an authority, never WHICH slice a node is attributed to."""
    project_dir = tmp_path / "repo"
    at_file = _write_pytest_only_at(
        project_dir,
        "slice-02",
        rel_dir="tests/acceptance/gap2_node_membership_wrong_slice",
        filename="test_login_flow.py",
    )
    rel = at_file.relative_to(project_dir)
    node_id = f"{rel}::test_behaviour"

    assert _node_belongs_to_slice(project_dir, node_id, "slice-01") is False


def test_non_test_file_with_matching_head_comment_is_not_misread(
    tmp_path: Path,
) -> None:
    """NEGATIVE (invariance pin): a NON-pytest-collectible file (e.g. a plain
    module) whose head merely mentions the tag convention must never be
    misread as an authored AT -- `is_pytest_collectible` stays the guard."""
    project_dir = tmp_path / "repo"
    scope_dir = project_dir / "tests" / "acceptance" / "gap2_non_test_file"
    scope_dir.mkdir(parents=True, exist_ok=True)
    plain_file = scope_dir / "notes.py"
    plain_file.write_text(
        "# @feature-gap2-node-membership-probe\n# @slice-01\n"
        "# just a note mentioning the tag convention, not an authored AT\n",
        encoding="utf-8",
    )
    node_id = f"{plain_file.relative_to(project_dir)}::test_behaviour"

    assert _node_belongs_to_slice(project_dir, node_id, "slice-01") is False


def test_gherkin_arm_still_wins_when_present(tmp_path: Path) -> None:
    """NEGATIVE (invariance pin): when a sibling `.feature` file carries the
    tag, the existing Gherkin arm still governs -- unchanged behavior."""
    project_dir = tmp_path / "repo"
    scope_dir = project_dir / "tests" / "acceptance" / "gap2_gherkin_still_wins"
    scope_dir.mkdir(parents=True, exist_ok=True)
    (scope_dir / "the.feature").write_text(
        "@feature-gap2-node-membership-probe @slice-01\n"
        "Feature: probe\n  Scenario: probe\n    Given x\n",
        encoding="utf-8",
    )
    step_file = scope_dir / "test_steps.py"
    step_file.write_text("def test_behaviour():\n    assert True\n", encoding="utf-8")
    node_id = f"{step_file.relative_to(project_dir)}::test_behaviour"

    assert _node_belongs_to_slice(project_dir, node_id, "slice-01") is True
