import pytest

from scripts.install.uninstall_nwave import NWaveUninstaller
from scripts.shared.skill_distribution import (
    SKILLS_FAMILY_KEY,
    remove_family_record,
    write_family_record,
)


def _fs_snapshot(path):
    return {
        str(p.relative_to(path)): p.read_bytes() if p.is_file() else None
        for p in sorted(path.glob("**/*"))
    }


def _make_uninstaller(tmp_path, monkeypatch):
    config_dir = tmp_path / "claude_config"
    config_dir.mkdir()
    monkeypatch.setattr(
        "scripts.install.uninstall_nwave.PathUtils.get_claude_config_dir",
        lambda: config_dir,
    )
    return config_dir, NWaveUninstaller(dry_run=True)


class TestRemoveSkillsManifestOwnership:
    def test_owned_removed_sibling_preserved(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "nw-one").mkdir()
        (skills_dir / "nw-one" / "SKILL.md").write_text("# One")
        (skills_dir / "nw-two").mkdir()
        (skills_dir / "nw-two" / "SKILL.md").write_text("# Two")
        write_family_record(skills_dir, ["nw-one", "nw-two"], key=SKILLS_FAMILY_KEY)
        (skills_dir / "nw-custom").mkdir()
        (skills_dir / "nw-custom" / "custom.txt").write_text("user data")

        result = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert result.status == "complete"
        assert result.removed == frozenset({"nw-one", "nw-two"})
        assert not (skills_dir / "nw-one").exists()
        assert not (skills_dir / "nw-two").exists()
        assert (skills_dir / "nw-custom" / "custom.txt").read_text() == "user data"

    @pytest.mark.parametrize(
        "has_manifest,write_content,expect_status",
        [
            (False, None, "missing_manifest"),
            (True, "not valid json", "invalid_manifest"),
        ],
    )
    def test_manifest_edge_cases_preserve_candidates(
        self, tmp_path, has_manifest, write_content, expect_status
    ):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        (skills_dir / "nw-candidate").mkdir()
        (skills_dir / "nw-candidate" / "file.txt").write_text("data")

        if has_manifest:
            (skills_dir / ".nwave-manifest.json").write_text(write_content)

        result = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert result.status == expect_status
        assert result.removed == frozenset()
        assert (skills_dir / "nw-candidate").exists()

    def test_idempotent_retry(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()
        write_family_record(skills_dir, [], key=SKILLS_FAMILY_KEY)

        result1 = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert result1.status == "complete"
        assert not (skills_dir / ".nwave-manifest.json").exists()

        state1 = _fs_snapshot(skills_dir)
        result2 = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert result2.status == "missing_manifest"
        assert result2.removed == frozenset()
        assert state1 == _fs_snapshot(skills_dir)

    def test_dangling_symlink_ownership(self, tmp_path):
        skills_dir = tmp_path / "skills"
        skills_dir.mkdir()

        target = tmp_path / "external"
        target.mkdir()
        (skills_dir / "nw-linked").symlink_to(target)
        target.rmdir()

        write_family_record(skills_dir, ["nw-linked"], key=SKILLS_FAMILY_KEY)
        result = remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert result.status == "complete"
        assert result.removed == frozenset({"nw-linked"})
        assert not (skills_dir / "nw-linked").exists()

        untracked_target = tmp_path / "external2"
        untracked_target.mkdir()
        (skills_dir / "nw-untracked-link").symlink_to(untracked_target)
        untracked_target.rmdir()
        write_family_record(skills_dir, [], key=SKILLS_FAMILY_KEY)

        remove_family_record(skills_dir, key=SKILLS_FAMILY_KEY)
        assert (skills_dir / "nw-untracked-link").is_symlink()

    def test_dry_run_immutable(self, tmp_path, monkeypatch):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        (skills_dir / "nw-owned").mkdir()
        (skills_dir / "nw-owned" / "SKILL.md").write_text("# Owned")
        write_family_record(skills_dir, ["nw-owned"], key=SKILLS_FAMILY_KEY)
        (skills_dir / "nw-custom").mkdir()
        (skills_dir / "nw-custom" / "data.txt").write_text("user data")

        manifest_before = (skills_dir / ".nwave-manifest.json").read_bytes()
        tree_before = _fs_snapshot(skills_dir)

        uninstaller.remove_skills()

        assert (skills_dir / ".nwave-manifest.json").read_bytes() == manifest_before
        assert _fs_snapshot(skills_dir) == tree_before
        assert (skills_dir / "nw-owned").exists()
        assert (skills_dir / "nw-custom").exists()

    @pytest.mark.parametrize(
        "manifest_bytes",
        [
            b"[]",
            b'{"installed_skills": {}}',
            b'{"installed_skills": ["nw-one", 42]}',
        ],
    )
    def test_dry_run_malformed_manifest_idempotent(
        self, tmp_path, monkeypatch, manifest_bytes
    ):
        config_dir, uninstaller = _make_uninstaller(tmp_path, monkeypatch)
        skills_dir = config_dir / "skills"
        skills_dir.mkdir()

        manifest_path = skills_dir / ".nwave-manifest.json"
        manifest_path.write_bytes(manifest_bytes)
        (skills_dir / "nw-candidate").mkdir()
        (skills_dir / "nw-candidate" / "data.txt").write_text("content")

        manifest_before = manifest_path.read_bytes()
        tree_before = _fs_snapshot(skills_dir)

        uninstaller.remove_skills()

        assert manifest_path.read_bytes() == manifest_before
        assert _fs_snapshot(skills_dir) == tree_before
        assert (skills_dir / "nw-candidate").exists()
