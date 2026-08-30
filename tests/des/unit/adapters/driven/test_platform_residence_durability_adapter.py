from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from des.adapters.driven.platform_residence_durability_adapter import (
    PlatformResidenceDurabilityAdapter,
)
from des.domain.worktree_residence import ResidenceDurability


def test_platform_temp_root_is_ephemeral_even_for_repo_local_candidate(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    adapter = PlatformResidenceDurabilityAdapter(repo)

    assert adapter.classify(repo / ".nwave" / "worktrees" / "lane") is (
        ResidenceDurability.EPHEMERAL
    )
    assert (
        adapter.classify(Path(tempfile.gettempdir())) is ResidenceDurability.EPHEMERAL
    )
    default = adapter.durable_default(repo)
    assert default is not None
    assert adapter.classify(default) is ResidenceDurability.EPHEMERAL


def test_repository_local_default_is_durable_outside_ephemeral_roots() -> None:
    repo = Path(__file__).resolve().parents[5]
    adapter = PlatformResidenceDurabilityAdapter(repo)
    default = adapter.durable_default(repo)

    assert default is not None
    assert adapter.classify(default / "lane") is ResidenceDurability.DURABLE


def test_unrelated_root_is_unknown() -> None:
    repo = Path(__file__).resolve().parents[5]
    adapter = PlatformResidenceDurabilityAdapter(repo)

    assert adapter.classify(Path("/opt/nwave-unrelated")) is ResidenceDurability.UNKNOWN
