"""Workflow contracts for final public-artifact privacy gates.

Privacy must be checked on the immutable release assets and final mirror
tree—not merely on the source checkout before later packaging/transforms.
These tests inspect the concrete, ordered GitHub Actions steps that perform
the irreversible publication operations.
"""

from __future__ import annotations

import shlex
import zipfile
from itertools import pairwise
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
DECISION_SCRIPT = "scripts/release/release_migration_decision.py"


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


def _logical_shell_segments(script: str) -> tuple[tuple[str, ...], ...]:
    """Extract simple release-command segments; this is not a general shell parser."""
    logical = _without_shell_comments(script).replace("\\\n", " ")
    segments: list[tuple[str, ...]] = []
    lexer = shlex.shlex(logical, posix=True, punctuation_chars=";&|\n")
    lexer.whitespace = " \t\r"
    lexer.whitespace_split = True
    lexer.commenters = ""
    current: list[str] = []
    for token in lexer:
        if token and all(character in ";&|\n" for character in token):
            if current:
                segments.append(tuple(current))
                current = []
        else:
            current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def _without_shell_comments(script: str) -> str:
    """Remove unquoted shell comments while retaining newline command boundaries."""
    kept: list[str] = []
    quote: str | None = None
    escaped = False
    index = 0
    while index < len(script):
        character = script[index]
        if escaped:
            kept.append(character)
            escaped = False
        elif character == "\\" and quote != "'":
            kept.append(character)
            escaped = True
        elif quote is not None:
            kept.append(character)
            if character == quote:
                quote = None
        elif character in "'\"":
            kept.append(character)
            quote = character
        elif character == "#" and (
            index == 0 or script[index - 1].isspace() or script[index - 1] in ";|&"
        ):
            while index < len(script) and script[index] != "\n":
                index += 1
            continue
        else:
            kept.append(character)
        index += 1
    return "".join(kept)


def _is_publish_unit_invocation(argv: tuple[str, ...], unit: str) -> bool:
    if (
        len(argv) < 5
        or Path(argv[0]).name not in {"python", "python3"}
        or argv[1] != DECISION_SCRIPT
        or argv[2] != "publish-unit"
    ):
        return False
    return any(flag == "--unit" and value == unit for flag, value in pairwise(argv[3:]))


def _publish_unit_step(job: dict, unit: str) -> int:
    """Locate the reviewed writer boundary for one declared publication unit."""
    for index, step in enumerate(job["steps"]):
        for argv in _logical_shell_segments(str(step.get("run", ""))):
            if _is_publish_unit_invocation(argv, unit):
                return index
    pytest.fail(
        f"job must publish declared {unit!r} through the release decision writer"
    )


def test_publish_unit_step_ignores_comment_and_unrelated_unit_text() -> None:
    """Only the command's own exact unit argument can satisfy the contract."""
    job = {
        "steps": [
            {
                "run": """
                    python3 -c "
                    print('multiline quoted helper')
                    "
                    echo "
                    python scripts/release/release_migration_decision.py publish-unit --unit wanted
                    "
                    echo 'scripts/release/release_migration_decision.py publish-unit --unit wanted'
                    echo python scripts/release/release_migration_decision.py publish-unit --unit wanted
                    python scripts/release/release_migration_decision.py publish-unit --unit other.unit
                    # comment's unrelated --unit wanted must not poison the lexer
                    # python scripts/release/release_migration_decision.py publish-unit --unit wanted
                """
            }
        ]
    }

    with pytest.raises(pytest.fail.Exception):
        _publish_unit_step(job, "wanted")

    job["steps"][0]["run"] += """
        python scripts/release/release_migration_decision.py \\
          publish-unit --unit wanted
    """
    assert _publish_unit_step(job, "wanted") == 0


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
    ("workflow_name", "release_metadata_unit"),
    [
        ("release-dev.yml", "dev.release.metadata"),
        ("release-rc.yml", "rc.release.metadata"),
        ("release-prod.yml", "prod.release.metadata"),
    ],
)
def test_github_release_assets_are_privacy_verified_before_release_operation(
    workflow_name: str, release_metadata_unit: str
) -> None:
    """Every GitHub Release path verifies assets before its release writer unit."""
    job = _job(workflow_name, "tag-release")
    needs = job.get("needs", [])
    assert "build" in needs and "build-plugin" in needs, (
        f"{workflow_name}:tag-release must depend on both artifact-producing jobs "
        "before verifying and releasing their downloaded final assets."
    )

    wheel_index = _verifier_step(job, WHEEL_VERIFIER, "dist/*.whl")
    plugin_index = _verifier_step(job, PLUGIN_VERIFIER, "dist/nwave-plugin-v*.zip")
    release_index = _publish_unit_step(job, release_metadata_unit)
    assert wheel_index < release_index and plugin_index < release_index, (
        f"{workflow_name}:tag-release must verify the exact downloaded wheel and "
        f"plugin ZIP before its GitHub Release metadata writer."
    )


@pytest.mark.parametrize(
    ("workflow_name", "package_index_unit"),
    [
        ("release-rc.yml", "rc.testpypi.wheel"),
        ("release-prod.yml", "prod.pypi.wheel"),
    ],
)
def test_pypi_rebuild_is_privacy_verified_after_build_and_before_publish(
    workflow_name: str, package_index_unit: str
) -> None:
    """RC and stable PyPI publish only a freshly rebuilt, verified wheel."""
    job = _job(workflow_name, "pypi-publish")

    build_index = _step_index(job, "python -m build --wheel")
    verifier_index = _verifier_step(job, WHEEL_VERIFIER, "dist/*.whl")
    publish_index = _publish_unit_step(job, package_index_unit)

    assert build_index != -1, (
        f"{workflow_name}:pypi-publish must retain its independent final-wheel "
        "rebuild; this contract is not discharged by an earlier artifact."
    )
    assert build_index < verifier_index < publish_index, (
        f"{workflow_name}:pypi-publish must order rebuild -> final-wheel privacy "
        "verification -> reviewed package-index writer."
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
    branch_unit = (
        "rc.beta.branch" if workflow_name == "release-rc.yml" else "prod.public.branch"
    )
    publish_index = _publish_unit_step(job, branch_unit)

    assert strip_index != -1, (
        f"{workflow_name}:{job_name} must retain its private-artifact strip before "
        "the final public-tree verification."
    )
    assert strip_index < verifier_index < publish_index, (
        f"{workflow_name}:{job_name} must order private-artifact stripping -> final "
        "target verification -> declared public branch writer."
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
    metadata_unit = (
        "rc.beta.release.metadata"
        if workflow_name == "release-rc.yml"
        else "prod.public.release.metadata"
    )
    release_index = _publish_unit_step(job, metadata_unit)

    assert tree_gate_index != -1, (
        f"{workflow_name}:{job_name} must retain the final target-tree gate."
    )
    assert download_index != -1, (
        f"{workflow_name}:{job_name} must download the plugin ZIP that its public "
        "GitHub Release attaches."
    )
    assert tree_gate_index < download_index < plugin_gate_index < release_index, (
        f"{workflow_name}:{job_name} must verify the exact ZIP downloaded after "
        "the tree gate and before the declared release metadata writer."
    )


def test_stable_github_release_has_an_adjacent_final_asset_gate() -> None:
    """Stable tags or other mutations cannot occur after its last asset check."""
    job = _job("release-prod.yml", "tag-release")
    release_index = _publish_unit_step(job, "prod.release.metadata")
    final_gate = job["steps"][release_index - 1]
    final_gate_text = "\n".join(
        str(final_gate.get(key, "")) for key in ("name", "run", "uses")
    )
    assert WHEEL_VERIFIER in final_gate_text and "dist/*.whl" in final_gate_text, (
        "the step immediately before the stable metadata writer must verify the "
        "final wheel; no tag or mutation step may intervene."
    )
    assert (
        PLUGIN_VERIFIER in final_gate_text
        and "dist/nwave-plugin-v*.zip" in final_gate_text
    ), (
        "the step immediately before the stable metadata writer must verify the "
        "final plugin ZIP; no tag or mutation step may intervene."
    )


def test_standalone_github_release_verifies_the_wheel_before_the_dependent_writer() -> (
    None
):
    """The standalone GitHub channel preserves its cross-job wheel gate."""
    build = _job("release-github.yml", "build")
    release = _job("release-github.yml", "publish-release")

    wheel_index = _verifier_step(build, WHEEL_VERIFIER, "dist/*.whl")
    upload_index = _step_index(build, "actions/upload-artifact")
    _publish_unit_step(release, "github-prerelease.release.metadata")

    assert "build" in release.get("needs", []), (
        "release-github.yml:publish-release must depend on the wheel-producing job"
    )
    assert wheel_index < upload_index, (
        "release-github.yml:build must verify its final wheel before uploading the "
        "artifact consumed by the dependent metadata writer."
    )
