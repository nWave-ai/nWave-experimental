"""Explicit test-host role execution followed by deterministic DES operations.

The scripted host is test infrastructure, never a production DES callback.
Each helper performs only the action its caller selected; no continuation loop
or fallback chooses the next role.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from des.application.delivery_continuation import (
    DeliveryContinuationRunner,
    DeliveryOutcome,
    SelectedValue,
)
from des.application.delivery_steps import DeliverySteps, ReplacementModes
from des.application.handover import StoredHandover, load_handover
from tests.des._helpers.host_facts import product_manifest


def immutable_source(root: Path, paths: tuple[str, ...]) -> tuple[str, str]:
    """Name current product bytes in an unreferenced commit without moving the host."""

    def git(*argv: str, environment: dict[str, str] | None = None) -> str:
        return subprocess.run(
            ["git", "-C", str(root), *argv],
            env={
                **(os.environ if environment is None else environment),
                "GIT_OPTIONAL_LOCKS": "0",
            },
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def workspace() -> dict:
        population = {
            path
            for path in git(
                "ls-files", "--cached", "--others", "--exclude-standard", "-z"
            ).split("\0")
            if path
        }
        index = root / git("rev-parse", "--git-path", "index")
        return {
            "head": git("rev-parse", "HEAD"),
            "index": index.read_bytes(),
            "refs": git("for-each-ref", "--format=%(refname) %(objectname)"),
            "status": git("status", "--porcelain=v1", "-z", "--untracked-files=all"),
            "files": {
                path: (
                    str((root / path).readlink())
                    if (root / path).is_symlink()
                    else (root / path).read_bytes()
                    if (root / path).is_file()
                    else None
                )
                for path in sorted(population)
            },
        }

    before = workspace()
    with tempfile.TemporaryDirectory(
        prefix="nwave-test-immutable-source-"
    ) as temporary:
        environment = {
            **os.environ,
            "GIT_INDEX_FILE": str(Path(temporary) / "index"),
        }
        git("read-tree", before["head"], environment=environment)
        git("add", "--", *paths, environment=environment)
        tree = git("write-tree", environment=environment)
        commit = git(
            "commit-tree",
            tree,
            "-p",
            before["head"],
            "-m",
            "explicit immutable test-host product source",
            environment=environment,
        )
    assert workspace() == before, (
        "WHAT: immutable fixture-source construction changed HEAD, index, refs or workspace bytes. "
        "WHY: selecting GREEN source must not move or rewrite the host. "
        "HOW: build the unreferenced commit with a temporary index and no ref update."
    )
    return commit, tree


class StepRefused(Exception):
    def __init__(self, step, outcome):
        what = outcome.failure.what if outcome.failure is not None else "(no failure)"
        super().__init__(
            f"the {step} step answered {outcome.disposition.value}: {what}"
        )
        self.step = step
        self.outcome = outcome


def _reread(root: Path, request: str) -> StoredHandover:
    stored = load_handover(root, request)
    assert isinstance(stored, StoredHandover), stored
    return stored


def _prompt(**facts):
    return "\n".join(f"{name}: {json.dumps(value)}" for name, value in facts.items())


def decomposed(runner, port, root, request):
    supplied = port.invoke(
        role_id="nw-product-owner", prompt=_prompt(request=request), cwd=root
    )
    manifest = product_manifest(
        request, [value.observation for value in supplied.product_values]
    )
    outcome = DeliverySteps().discuss_document(
        root, json.dumps(manifest), project=False, feature="fixture"
    )
    if not outcome.succeeded:
        raise StepRefused("po", outcome)
    return _reread(root, request)


def designed(runner, port, root, stored, manifest, *, position=0):  # noqa: PLR0913 - explicit host, repository and selected evidence context
    observation = stored.values[position].observation
    port.invoke(
        role_id="nw-solution-architect",
        prompt=_prompt(observation=observation),
        cwd=root,
    )
    outcome = DeliverySteps().design_document(
        root,
        position + 1,
        json.dumps(manifest),
        modes=ReplacementModes(
            replace_current=stored.values[position].authority is not None
        ),
    )
    if not outcome.succeeded:
        raise StepRefused("design", outcome)
    stored = _reread(root, stored.request)
    authority = runner.selected_authority(root, stored, position + 1)
    if isinstance(authority, DeliveryOutcome):
        raise StepRefused("design", authority)
    return stored, authority


def oracled(  # noqa: PLR0913 - explicit host, repository and selected evidence context
    runner, port, root, stored, design, *, baseline: str, position=0, finding=None
):
    port.invoke(
        role_id="nw-acceptance-designer",
        cwd=root,
        prompt=_prompt(
            observation=stored.values[position].observation,
            oracle=design.acceptance_paths[0],
            finding=finding,
        ),
    )
    return runner.measure_oracle(
        root, SelectedValue(stored, stored.values[position], design), explicit=baseline
    )


def crafted(runner, port, root, stored, design, *, position=0):  # noqa: PLR0913 - explicit host, repository and selected evidence context
    supplied = port.invoke(
        role_id="nw-software-crafter",
        cwd=root,
        prompt=_prompt(
            observation=stored.values[position].observation,
            mutable_targets=[
                path
                for path, decision in design.target_decisions
                if decision != "REUSE" and path not in design.acceptance_paths
            ],
        ),
    )
    result = {
        "structured_output": {
            "outcome": supplied.outcome.value,
            "diagnostic": supplied.diagnostic,
            "blocked_by": supplied.craft_blocker.value
            if supplied.craft_blocker
            else None,
        }
    }
    outcome = DeliverySteps().craft(root, position + 1, json.dumps(result))
    return (
        ()
        if outcome.succeeded
        else DeliveryOutcome(outcome.disposition, outcome.failure)
    )


def through_oracle(port, root, request, manifest, *, baseline: str, position=0):  # noqa: PLR0913 - explicit host, repository and retained baseline context
    runner = DeliveryContinuationRunner()
    stored = decomposed(runner, port, root, request)
    stored, design = designed(runner, port, root, stored, manifest, position=position)
    measured = oracled(
        runner, port, root, stored, design, baseline=baseline, position=position
    )
    if measured.refusal is not None:
        raise StepRefused("oracle", measured.refusal)
    return runner, _reread(root, stored.request), design
