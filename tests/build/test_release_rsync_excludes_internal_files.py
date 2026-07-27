"""Architecture test: prod/RC release rsync MUST exclude internal-only files.

`CLAUDE.md`, `ARCH_TECH_DEBT.md`, `.mailmap`, `.claude/`, and
`.tla-swarm-model/` are git-tracked at repo root and were never excluded from
the real `release-prod.yml` / `release-rc.yml` rsync filters, so a real
release would rsync them straight into the public/beta mirror -- none of the
downstream privacy gates (`verify_public_tree_privacy.py`,
`verify_wheel_privacy.py`) inspect repo-root files, only `nWave/agents/` and
`nWave/skills/`. `scripts/release/publish_experimental.py`'s RSYNC_FILTER
already excludes all five (it claims to mirror release-prod.yml verbatim),
proving the gap was previously identified but never back-ported.
"""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REQUIRED_EXCLUDES = (
    "CLAUDE.md",
    "ARCH_TECH_DEBT.md",
    ".mailmap",
    ".claude/",
    ".tla-swarm-model/",
)


def test_release_prod_excludes_internal_only_files() -> None:
    release_prod = (
        REPO_ROOT / ".github" / "workflows" / "release-prod.yml"
    ).read_text()
    for rule in REQUIRED_EXCLUDES:
        assert f"--exclude '{rule}'" in release_prod, (
            f"Missing rsync exclusion in release-prod.yml: '{rule}'. "
            "This internal-only file would leak to the public nWave-ai/nWave mirror."
        )


def test_release_rc_excludes_internal_only_files() -> None:
    release_rc = (REPO_ROOT / ".github" / "workflows" / "release-rc.yml").read_text()
    for rule in REQUIRED_EXCLUDES:
        assert f"--exclude '{rule}'" in release_rc, (
            f"Missing rsync exclusion in release-rc.yml: '{rule}'. "
            "This internal-only file would leak to the beta nWave-ai/nWave-beta mirror."
        )
