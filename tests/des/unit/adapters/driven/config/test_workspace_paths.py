"""Configured workspace placement is refused before any consumer writes.

The resolver is the ONE derivation every real-work placement shares (reuse
workspace, cold candidates, lane worktrees), so its refusal algebra is a
safety property, not a convenience: absolute paths, traversal, reserved
components, symlinks, and generated-output overlaps can never place real
work outside the repository or inside evidence/generated territory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.config.workspace_paths import (
    CANDIDATE_DIRNAME,
    DEFAULT_WORKSPACE_ROOT,
    VERIFICATION_DIRNAME,
    WorkspaceConfigInvalid,
    resolve_workspace_paths,
)


def _configured(root: Path, workspace: dict, outputs: list | None = None) -> Path:
    (root / ".nwave").mkdir(parents=True, exist_ok=True)
    reuse: dict = {"workspace": workspace}
    if outputs is not None:
        reuse["outputs"] = outputs
    (root / ".nwave/config.json").write_text(
        json.dumps({"verification": {"reuse": reuse}})
    )
    return root


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def test_defaults_preserve_the_earlier_layout(tmp_path: Path) -> None:
    """The explicit project/lanes promise: unconfigured == legacy layout."""
    root = _repo(tmp_path)
    paths = resolve_workspace_paths(root)
    assert paths.root == root
    assert paths.lanes == root / DEFAULT_WORKSPACE_ROOT
    assert paths.verification == root / "lanes/.des-verification"
    assert paths.candidate == root / f"lanes/{CANDIDATE_DIRNAME}"
    # The user chose automatic eviction of OWNED inactive cache; unknown
    # materializations stay protected regardless of this flag.
    assert paths.automatic is True


def test_adopted_outputs_are_declared_and_shape_checked(tmp_path: Path) -> None:
    root = _configured(
        _repo(tmp_path),
        {
            "adopt_outputs": ["target", "vendor-cache"],
            "automatic": False,
        },
        outputs=["target", "vendor-cache"],
    )
    paths = resolve_workspace_paths(root)
    assert paths.adopted == ("target", "vendor-cache")
    assert paths.automatic is False
    for index, declared in enumerate(
        (
            ["/tmp/escape"],
            ["../escape"],
            [],
            ["target", "target"],
            "target",
            ["lanes"],
        )
    ):
        broken = _configured(
            _repo(tmp_path, f"repo{index}"), {"adopt_outputs": declared}
        )
        with pytest.raises(WorkspaceConfigInvalid):
            _ = resolve_workspace_paths(broken)
    for index, declared in enumerate((["work"], ["work/deep"])):
        broken = _configured(
            _repo(tmp_path, f"repo-work{index}"),
            {"root": "work", "adopt_outputs": declared},
        )
        with pytest.raises(WorkspaceConfigInvalid):
            _ = resolve_workspace_paths(broken)


def test_verification_name_is_the_configured_default(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    paths = resolve_workspace_paths(root)
    assert paths.verification.name == VERIFICATION_DIRNAME


def test_configured_root_moves_all_roots_together(tmp_path: Path) -> None:
    root = _configured(_repo(tmp_path), {"root": "work", "automatic": True})
    paths = resolve_workspace_paths(root)
    assert paths.lanes == root / "work"
    assert paths.candidate == root / f"work/{CANDIDATE_DIRNAME}"
    assert paths.verification == root / f"work/{VERIFICATION_DIRNAME}"
    assert paths.automatic is True


def test_linked_lane_resolves_to_the_principal_root(tmp_path: Path) -> None:
    principal = _repo(tmp_path)
    admin = principal / ".git" / "worktrees" / "feature"
    admin.mkdir(parents=True)
    lane = principal / "lanes" / "feature"
    lane.mkdir(parents=True)
    (lane / ".git").write_text(f"gitdir: {admin}\n")
    (admin / "commondir").write_text("../..\n")
    paths = resolve_workspace_paths(lane)
    assert paths.root == principal
    assert paths.lanes == principal / "lanes"


def _relative_declared(tmp_path: Path) -> Path:
    return _configured(_repo(tmp_path), {"root": "work"})


@pytest.mark.parametrize(
    "declared",
    [
        "/tmp/escape",
        "~/escape",
        "../escape",
        "work/../escape",
        "work/./deep",
        "work//double",
        "work/",
        "",
        ".",
        ".git/work",
        "work/.git",
        ".nwave/work",
        ".venv/work",
        "work\\windows",
    ],
)
def test_unsafe_workspace_roots_are_refused(tmp_path: Path, declared: str) -> None:
    root = _configured(_repo(tmp_path), {"root": declared})
    with pytest.raises(WorkspaceConfigInvalid):
        _ = resolve_workspace_paths(root)


def test_symlink_component_is_refused(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (root / "lanes").symlink_to(outside)
    _configured(root, {"root": "lanes"})
    with pytest.raises(WorkspaceConfigInvalid):
        _ = resolve_workspace_paths(root)


def test_workspace_root_overlapping_a_generated_output_is_refused(
    tmp_path: Path,
) -> None:
    root = _configured(_repo(tmp_path), {"root": "generated"})
    (root / ".nwave/config.json").write_text(
        json.dumps(
            {
                "verification": {
                    "reuse": {
                        "outputs": ["generated"],
                        "workspace": {"root": "generated"},
                    }
                }
            }
        )
    )
    with pytest.raises(WorkspaceConfigInvalid):
        _ = resolve_workspace_paths(root)


def test_workspace_root_containing_a_generated_output_is_refused(
    tmp_path: Path,
) -> None:
    root = _repo(tmp_path)
    (root / ".nwave").mkdir(parents=True, exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps(
            {
                "verification": {
                    "reuse": {
                        "outputs": ["work/build"],
                        "workspace": {"root": "work"},
                    }
                }
            }
        )
    )
    with pytest.raises(WorkspaceConfigInvalid):
        _ = resolve_workspace_paths(root)


def test_malformed_outputs_refusal_keeps_its_exact_error(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / ".nwave").mkdir(parents=True, exist_ok=True)
    (root / ".nwave/config.json").write_text(
        json.dumps({"verification": {"reuse": {"outputs": []}}})
    )
    with pytest.raises(WorkspaceConfigInvalid) as bound:
        _ = resolve_workspace_paths(root)
    assert "nonempty list of distinct" in str(bound.value)


def test_malformed_outputs_are_refused_by_the_resolver(tmp_path: Path) -> None:
    """Malformed output declarations refuse before any consumer acts.

    cli/lane and the maintenance budget consume the same declarations; an
    aliasing spelling like ``a/../lanes`` must never pass by being skipped
    or merely downgraded to an unobservable budget.
    """
    for outputs in (["a/../lanes"], ["/tmp/escape"], ["a//b"], ["~/x"], ["x/"]):
        root = _repo(tmp_path, f"repo{outputs}")
        (root / ".nwave").mkdir()
        (root / ".nwave/config.json").write_text(
            json.dumps({"verification": {"reuse": {"outputs": outputs}}})
        )
        with pytest.raises(WorkspaceConfigInvalid):
            _ = resolve_workspace_paths(root)


def test_config_transition_selects_whole_admitted_configuration(
    tmp_path: Path,
) -> None:
    """A→B at the read boundary: each observation is ONE admitted whole.

    The selected (outputs, workspace) pair always comes from a single
    configuration snapshot -- never outputs from one read mixed with a
    workspace from another.
    """
    root = _repo(tmp_path)
    (root / ".nwave").mkdir()
    (root / ".nwave/config.json").write_text(
        json.dumps(
            {
                "verification": {
                    "reuse": {
                        "outputs": ["generated"],
                        "workspace": {"root": "work"},
                    }
                }
            }
        )
    )
    first = resolve_workspace_paths(root)
    assert first.outputs == ("generated",)
    assert first.candidate == root / "work/.des-candidate"
    assert first.verification == root / "work/.des-verification"

    (root / ".nwave/config.json").write_text(
        json.dumps(
            {
                "verification": {
                    "reuse": {
                        "outputs": ["artifacts"],
                        "workspace": {"root": "lanes"},
                    }
                }
            }
        )
    )
    second = resolve_workspace_paths(root)
    assert second.outputs == ("artifacts",)
    assert second.candidate == root / "lanes/.des-candidate"
    assert second.verification == root / "lanes/.des-verification"
    assert second.evidence == first.evidence
