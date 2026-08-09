"""Dense non-dry-run coverage for the P1-D skills-ownership review blockers.

All tests drive the REAL `NWaveUninstaller` methods (`remove_skills`,
`validate_removal`, `_skills_removal_state`) against a real filesystem with
`dry_run=False` -- none returns early on dry-run and none mocks
`scan_claude_ownership` / `remove_family_record`. `test_standalone_import_...`
statically verifies the one property a runtime test cannot reach: the
`except ImportError` branch's `skill_distribution` import list is a strict
superset check against the `try` branch's, so a name added to one and
forgotten in the other (the actual `FamilyRemovalEvidence` regression) fails
loudly instead of silently NameError-ing only when `scripts` is unimportable.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest


try:
    from scripts.install.install_utils import PathUtils
    from scripts.install.uninstall_nwave import NWaveUninstaller
except ImportError:  # pragma: no cover - direct-script import fallback
    from install_utils import PathUtils
    from uninstall_nwave import NWaveUninstaller

from scripts.shared.skill_distribution import SKILLS_FAMILY_KEY, write_family_record


pytestmark = pytest.mark.unit


def _fs_snapshot(path: Path) -> dict:
    return {
        str(p.relative_to(path)): p.read_bytes() if p.is_file() else None
        for p in sorted(path.glob("**/*"))
    }


@pytest.fixture
def claude_dir(tmp_path, monkeypatch):
    """Point PathUtils.get_claude_config_dir() at a tmp ~/.claude."""
    cfg = tmp_path / ".claude"
    cfg.mkdir()
    monkeypatch.setattr(PathUtils, "get_claude_config_dir", staticmethod(lambda: cfg))
    return cfg


def _seed_tracked_and_custom_skill(
    skills_dir: Path, *, dangling_symlink: bool = False
) -> None:
    skills_dir.mkdir()
    (skills_dir / "nw-one").mkdir()
    (skills_dir / "nw-one" / "SKILL.md").write_text("# One")
    tracked = ["nw-one"]
    if dangling_symlink:
        (skills_dir / "nw-dangling").symlink_to(skills_dir / "nw-missing-target")
        tracked.append("nw-dangling")
    write_family_record(skills_dir, tracked, key=SKILLS_FAMILY_KEY)
    (skills_dir / "nw-custom").mkdir()
    (skills_dir / "nw-custom" / "custom.txt").write_text("user data")


def test_standalone_import_branch_names_match_the_try_branch():
    """The except-ImportError branch must import every name the try imports
    from skill_distribution -- this is the exact shape of the reviewed bug
    (FamilyRemovalEvidence present in try, absent in except)."""
    source = Path(sys.modules[NWaveUninstaller.__module__].__file__)
    tree = ast.parse(source.read_text(encoding="utf-8"))
    # The module-top-level try/except (the standalone-vs-package import
    # switch) -- NOT one of the nested try/except blocks inside methods.
    try_node = next(n for n in tree.body if isinstance(n, ast.Try))

    def _names(stmts):
        found = set()
        for stmt in stmts:
            if (
                isinstance(stmt, ast.ImportFrom)
                and stmt.module
                and stmt.module.endswith("skill_distribution")
            ):
                found.update(alias.name for alias in stmt.names)
        return found

    try_names = _names(try_node.body)
    except_names = _names(try_node.handlers[0].body)

    assert "FamilyRemovalEvidence" in try_names
    assert try_names == except_names


def test_second_uninstall_run_on_absent_skills_does_not_crash(claude_dir):
    """Two fresh, independent uninstaller instances (two standalone
    invocations) against a skills-less tree must both construct
    FamilyRemovalEvidence via remove_skills() without raising."""
    for _ in range(2):
        uninstaller = NWaveUninstaller(force=True)
        uninstaller.remove_skills()
        assert uninstaller._skills_removal_state() == "already-clean"
    assert not (claude_dir / "skills").exists()


def test_absent_skills_dir_reports_already_clean_and_validates_green(claude_dir):
    uninstaller = NWaveUninstaller(force=True)
    uninstaller.remove_skills()

    assert uninstaller._skills_removal_state() == "already-clean"
    assert uninstaller.validate_removal() is True


def test_tracked_skill_removed_while_untracked_custom_survives(claude_dir):
    skills_dir = claude_dir / "skills"
    _seed_tracked_and_custom_skill(skills_dir, dangling_symlink=True)
    assert (skills_dir / "nw-dangling").is_symlink()

    uninstaller = NWaveUninstaller(force=True)
    uninstaller.remove_skills()

    assert not (skills_dir / "nw-one").exists()
    assert not (skills_dir / "nw-dangling").is_symlink()
    assert (skills_dir / "nw-custom" / "custom.txt").read_text() == "user data"
    assert uninstaller._skills_removal_state() == "removed-completely-this-run"
    assert uninstaller.validate_removal() is True


@pytest.mark.parametrize(
    ("manifest_bytes", "unsafe_member", "expected_state", "expected_how_fragment"),
    [
        (None, None, "absent-before-run", "re-run the nWave installer"),
        (b"not valid json", None, "corrupt", "restore skills/.nwave-manifest.json"),
        # A tracked member whose name fails `_is_safe_member_name` (contains
        # "/") blocks the whole family before any filesystem mutation --
        # this drives `remove_family_record`'s real unsafe-name branch, not
        # a mocked ownership scan.
        (None, "nested/escape", "blocked", "check filesystem permissions"),
    ],
    ids=["missing_manifest", "corrupt_manifest", "blocked_unsafe_member"],
)
def test_missing_or_corrupt_manifest_cannot_green(
    claude_dir,
    capsys,
    manifest_bytes,
    unsafe_member,
    expected_state,
    expected_how_fragment,
):
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "nw-candidate").mkdir()
    (skills_dir / "nw-candidate" / "file.txt").write_text("data")
    if manifest_bytes is not None:
        (skills_dir / ".nwave-manifest.json").write_bytes(manifest_bytes)
    elif unsafe_member is not None:
        write_family_record(skills_dir, [unsafe_member], key=SKILLS_FAMILY_KEY)

    uninstaller = NWaveUninstaller(force=True)
    uninstaller.remove_skills()
    # remove_skills() itself must already emit an actionable WHAT/WHY/HOW --
    # the scan's skills_manifest_status classification (not a second read of
    # result.status) is what selects this message, so seeing it here proves
    # the inventory is a real decision input, not just a logged count.
    removal_output = capsys.readouterr().out
    assert "WHAT:" in removal_output
    assert "WHY:" in removal_output
    assert expected_how_fragment in removal_output

    assert (skills_dir / "nw-candidate").exists()
    assert uninstaller._skills_removal_state() == expected_state
    assert uninstaller.validate_removal() is False
    validation_output = capsys.readouterr().out
    assert "WHAT:" in validation_output
    assert expected_how_fragment in validation_output


def test_two_run_idempotence_after_real_removal(claude_dir):
    # No untracked sibling here (unlike the previous test): once the sole
    # tracked member is gone, skills_dir itself empties and is rmdir'd, so
    # the second run takes the "skills_dir absent" branch -- the case that
    # actually exercises the mirrored FamilyRemovalEvidence construction.
    skills_dir = claude_dir / "skills"
    skills_dir.mkdir()
    (skills_dir / "nw-one").mkdir()
    (skills_dir / "nw-one" / "SKILL.md").write_text("# One")
    write_family_record(skills_dir, ["nw-one"], key=SKILLS_FAMILY_KEY)

    first = NWaveUninstaller(force=True)
    first.remove_skills()
    assert first.validate_removal() is True
    state_after_first = _fs_snapshot(claude_dir)

    second = NWaveUninstaller(force=True)
    second.remove_skills()
    assert second._skills_removal_state() == "already-clean"
    assert second.validate_removal() is True
    assert _fs_snapshot(claude_dir) == state_after_first
