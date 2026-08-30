"""No workflow may start itself on a push to the OSS trunk.

WHY THIS EXISTS (named incident, GDP-10): until 2026-08-23 every push to
`feature/atdd-pure-staging` started BOTH `ci.yml` and `publish-experimental.yml`.
Measured that day with `gh run list --limit 200` over the window opening
2026-08-21T11:19Z: 65 `CI Pipeline` runs + ~68 `Experimental preview` runs, all
`failure`, all `push`, each 3-9 seconds long -- the GitHub Actions budget (~$100)
was already exhausted, so the runs could not even start. Automatic spend, zero
verification, zero publications.

Ale's decision that day: the push is DELIBERATE, not continuous. Verification
runs locally on demand (`uv run poe validate-changed` / `validate-tiers`), and
the pipelines are dispatched once, by hand, when a feature is implemented.

This test is the falsifier for that decision: re-adding the trunk under any
`push:` block turns the automatic spend back on silently, and a silent
regression here is measured in dollars, not in red tests.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

import pytest
import yaml


WORKFLOWS = Path(__file__).resolve().parents[2] / ".github" / "workflows"
TRUNK = "feature/atdd-pure-staging"

# The two workflows the decision names explicitly. Both must keep a manual
# trigger, otherwise "dispatch it deliberately" is an instruction nobody can obey.
DISPATCH_REQUIRED = ("ci.yml", "publish-experimental.yml")


def _triggers(document: dict) -> dict:
    """The `on:` mapping. PyYAML reads the bare key `on` as the boolean True."""
    for key in (True, "on", "On", "ON"):
        value = document.get(key)
        if isinstance(value, dict):
            return value
    return {}


def push_branches(text: str) -> list[str]:
    document = yaml.safe_load(text) or {}
    push = _triggers(document).get("push")
    if not isinstance(push, dict):
        return []
    return list(push.get("branches") or [])


def fires_on_trunk_push(text: str) -> bool:
    """GitHub matches `push.branches` patterns against the branch name."""
    return any(fnmatch.fnmatch(TRUNK, pattern) for pattern in push_branches(text))


@pytest.mark.parametrize(
    "workflow", sorted(WORKFLOWS.glob("*.yml")), ids=lambda p: p.name
)
def test_no_workflow_starts_on_a_push_to_the_trunk(workflow: Path) -> None:
    assert not fires_on_trunk_push(workflow.read_text()), (
        f"{workflow.name} would start on every push to {TRUNK}. That is the "
        "automatic Actions spend retired on 2026-08-23 (see this module's "
        "docstring). Dispatch the workflow by hand instead, or record a new "
        "decision in docs/product/backlog.md before re-adding the branch."
    )


@pytest.mark.parametrize("name", DISPATCH_REQUIRED)
def test_the_deliberate_workflows_keep_a_manual_trigger(name: str) -> None:
    document = yaml.safe_load((WORKFLOWS / name).read_text()) or {}
    assert "workflow_dispatch" in _triggers(document), (
        f"{name} has no workflow_dispatch, so after the trunk push trigger was "
        "removed there is no way left to run it at all."
    )
