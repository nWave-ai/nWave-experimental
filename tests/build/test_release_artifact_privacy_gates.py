"""Workflow contracts for final public-artifact privacy gates.

Privacy must be checked on the immutable release assets and final mirror
tree—not merely on the source checkout before later packaging/transforms.
These tests inspect the concrete, ordered GitHub Actions steps that perform
the irreversible publication operations.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
import yaml

from scripts.release.verify_plugin_privacy import verify as verify_plugin
from scripts.release.verify_public_tree_privacy import verify as verify_public_tree
from scripts.release.verify_wheel_privacy import verify as verify_wheel


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
WHEEL_VERIFIER = "scripts/release/verify_wheel_privacy.py"
PLUGIN_VERIFIER = "scripts/release/verify_plugin_privacy.py"
TREE_VERIFIER = "scripts/release/verify_public_tree_privacy.py"


def _job(workflow_name: str, job_name: str) -> dict:
    workflow = yaml.safe_load((WORKFLOWS / workflow_name).read_text(encoding="utf-8"))
    return workflow["jobs"][job_name]


def _step_index(job: dict, needle: str) -> int:
    for index, step in enumerate(job["steps"]):
        text = "\n".join(str(step.get(key, "")) for key in ("name", "run", "uses"))
        if needle in text:
            return index
    return -1


def _verifier_step(job: dict, verifier: str, artifact: str) -> int:
    index = _step_index(job, verifier)
    assert index != -1, f"job must explicitly invoke {verifier}"
    assert artifact in job["steps"][index].get("run", ""), (
        f"{verifier} must inspect the exact final {artifact} artifact, rather than "
        "a source tree or a different build output."
    )
    return index


def _write_public_catalog(tree: Path, *, public_agents: str) -> None:
    nwave = tree / "nWave"
    nwave.mkdir(parents=True)
    (nwave / "framework-catalog.yaml").write_text(
        f"agents:\n{public_agents}", encoding="utf-8"
    )


def _write_plugin_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("agents/nw-public-agent.md", "---\n---\npublic")
        archive.writestr("skills/nw-public-agent/SKILL.md", "# public")


def test_wheel_verifier_rejects_an_empty_public_allow_list(tmp_path: Path) -> None:
    """An empty catalog is unverifiable, never proof that a wheel is clean."""
    tree = tmp_path / "artifact"
    _write_public_catalog(tree, public_agents="  {}\n")

    assert verify_wheel(tree), "wheel verifier must fail closed on an empty catalog"


def test_plugin_verifier_rejects_an_empty_public_allow_list(tmp_path: Path) -> None:
    """An empty catalog is unverifiable, never proof that a plugin is clean."""
    tree = tmp_path / "artifact"
    _write_public_catalog(tree, public_agents="  {}\n")
    plugin_zip = tmp_path / "plugin.zip"
    _write_plugin_zip(plugin_zip)

    assert verify_plugin(plugin_zip, catalog_root=tree), (
        "plugin verifier must fail closed on an empty catalog"
    )


def test_public_tree_verifier_checks_marketplace_plugin_content(tmp_path: Path) -> None:
    """A private marketplace plugin makes the final public mirror unsafe."""
    tree = tmp_path / "public-target"
    _write_public_catalog(
        tree,
        public_agents="  public-agent:\n    public: true\n",
    )
    (tree / "nWave" / "agents").mkdir()
    (tree / "nWave" / "agents" / "nw-public-agent.md").write_text(
        "---\n---\npublic", encoding="utf-8"
    )
    plugin_agent = tree / "plugins" / "nw" / "agents"
    plugin_agent.mkdir(parents=True)
    (plugin_agent / "nw-private-agent.md").write_text(
        "---\n---\nprivate", encoding="utf-8"
    )

    violations = verify_public_tree(tree)

    assert any("plugins/nw" in violation for violation in violations), (
        "public-tree verifier must inspect plugins/nw marketplace content, not only "
        "the nWave source tree."
    )


@pytest.mark.parametrize(
    ("workflow_name", "release_operations"),
    [
        ("release-dev.yml", ("gh release create",)),
        ("release-rc.yml", ("gh release create",)),
        ("release-prod.yml", ("gh release create", "gh release upload")),
    ],
)
def test_github_release_assets_are_privacy_verified_before_release_operation(
    workflow_name: str, release_operations: tuple[str, ...]
) -> None:
    """Every GitHub Release path verifies its downloaded wheel and plugin ZIP."""
    job = _job(workflow_name, "tag-release")
    needs = job.get("needs", [])
    assert "build" in needs and "build-plugin" in needs, (
        f"{workflow_name}:tag-release must depend on both artifact-producing jobs "
        "before verifying and releasing their downloaded final assets."
    )

    wheel_index = _verifier_step(job, WHEEL_VERIFIER, "dist/*.whl")
    plugin_index = _verifier_step(job, PLUGIN_VERIFIER, "dist/nwave-plugin-v*.zip")
    for release_operation in release_operations:
        release_index = _step_index(job, release_operation)
        assert release_index != -1, (
            f"{workflow_name}:tag-release no longer contains {release_operation!r}; "
            "update this publication contract."
        )
        assert wheel_index < release_index and plugin_index < release_index, (
            f"{workflow_name}:tag-release must verify the exact downloaded wheel and "
            f"plugin ZIP before {release_operation}."
        )


@pytest.mark.parametrize("workflow_name", ["release-rc.yml", "release-prod.yml"])
def test_pypi_rebuild_is_privacy_verified_after_build_and_before_publish(
    workflow_name: str,
) -> None:
    """RC and stable PyPI publish only a freshly rebuilt, verified wheel."""
    job = _job(workflow_name, "pypi-publish")

    build_index = _step_index(job, "python -m build --wheel")
    verifier_index = _verifier_step(job, WHEEL_VERIFIER, "dist/*.whl")
    publish_index = _step_index(job, "pypa/gh-action-pypi-publish")

    assert build_index != -1, (
        f"{workflow_name}:pypi-publish must retain its independent final-wheel "
        "rebuild; this contract is not discharged by an earlier artifact."
    )
    assert publish_index != -1, (
        f"{workflow_name}:pypi-publish no longer contains the PyPI publish action; "
        "update this publication contract."
    )
    assert build_index < verifier_index < publish_index, (
        f"{workflow_name}:pypi-publish must order rebuild -> final-wheel privacy "
        "verification -> publish."
    )


@pytest.mark.parametrize(
    ("workflow_name", "job_name", "target_dir"),
    [
        ("release-rc.yml", "sync-beta", "beta-target"),
        ("release-prod.yml", "sync-public", "nwave-target"),
    ],
)
def test_public_repo_sync_verifies_final_target_immediately_before_push(
    workflow_name: str, job_name: str, target_dir: str
) -> None:
    """All transforms finish before the pushed tree receives its final check."""
    job = _job(workflow_name, job_name)

    strip_index = _step_index(job, "strip_private_agents.py")
    verifier_index = _verifier_step(job, TREE_VERIFIER, target_dir)
    push_index = _step_index(job, "git push")

    assert strip_index != -1, (
        f"{workflow_name}:{job_name} must retain its private-artifact strip before "
        "the final public-tree verification."
    )
    assert push_index != -1, (
        f"{workflow_name}:{job_name} no longer contains its public git push; update "
        "this final-target contract."
    )
    assert strip_index < verifier_index, (
        f"{workflow_name}:{job_name} must verify the target after stripping it."
    )
    assert verifier_index + 1 == push_index, (
        f"{workflow_name}:{job_name} must run {TREE_VERIFIER} after every target "
        "transform and as the step immediately before git push."
    )


@pytest.mark.parametrize(
    ("workflow_name", "job_name", "download_path"),
    [
        ("release-rc.yml", "sync-beta", "../release-assets/nwave-plugin-v*.zip"),
        ("release-prod.yml", "sync-public", "../plugin-dist/nwave-plugin-v*.zip"),
    ],
)
def test_public_release_reverifies_plugin_zip_downloaded_after_tree_gate(
    workflow_name: str, job_name: str, download_path: str
) -> None:
    """The ZIP attached to the public/beta GitHub Release is verified late."""
    job = _job(workflow_name, job_name)
    tree_gate_index = _step_index(job, TREE_VERIFIER)
    download_index = _step_index(job, "Download plugin artifact")
    plugin_gate_index = _verifier_step(job, PLUGIN_VERIFIER, download_path)
    release_index = _step_index(job, "gh release create")

    assert tree_gate_index != -1, (
        f"{workflow_name}:{job_name} must retain the final target-tree gate."
    )
    assert download_index != -1, (
        f"{workflow_name}:{job_name} must download the plugin ZIP that its public "
        "GitHub Release attaches."
    )
    assert release_index != -1, (
        f"{workflow_name}:{job_name} no longer creates its public GitHub Release; "
        "update this contract."
    )
    assert tree_gate_index < download_index < plugin_gate_index < release_index, (
        f"{workflow_name}:{job_name} must verify the exact ZIP downloaded after "
        "the tree gate and before gh release create."
    )


def test_stable_github_release_has_an_adjacent_final_asset_gate() -> None:
    """Stable tags or other mutations cannot occur after its last asset check."""
    job = _job("release-prod.yml", "tag-release")
    release_index = _step_index(job, "gh release create")

    assert release_index != -1, (
        "release-prod.yml:tag-release must create a GitHub Release"
    )
    final_gate = job["steps"][release_index - 1]
    final_gate_text = "\n".join(
        str(final_gate.get(key, "")) for key in ("name", "run", "uses")
    )
    assert WHEEL_VERIFIER in final_gate_text and "dist/*.whl" in final_gate_text, (
        "the step immediately before stable gh release create/upload must verify the "
        "final wheel; no tag or mutation step may intervene."
    )
    assert (
        PLUGIN_VERIFIER in final_gate_text
        and "dist/nwave-plugin-v*.zip" in final_gate_text
    ), (
        "the step immediately before stable gh release create/upload must verify the "
        "final plugin ZIP; no tag or mutation step may intervene."
    )
