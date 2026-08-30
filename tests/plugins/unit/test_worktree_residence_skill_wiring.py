from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
AUTO = ROOT / "nWave" / "skills" / "nw-auto" / "SKILL.md"
THROUGHPUT = ROOT / "nWave" / "skills" / "nw-throughput" / "SKILL.md"
DELIVER = ROOT / "nWave" / "skills" / "nw-deliver" / "SKILL.md"


def test_auto_uses_one_admission_constructor_for_both_attachment_modes() -> None:
    text = AUTO.read_text(encoding="utf-8")

    assert text.count("des worktree-admit --repo <root> --lane auto") == 2
    assert "sibling = root + `.nwave-auto`" not in text
    assert "git worktree add --detach" not in text
    assert "sole stdout path" in text
    assert "byte-verifies WIP" in text


def test_throughput_never_delegates_residence_selection_to_harness() -> None:
    text = THROUGHPUT.read_text(encoding="utf-8")

    assert "des worktree-admit --repo <root> --lane <name>" in text
    assert '`isolation: "worktree"`' in text
    assert "des worktree-release" in text
    assert "absence or deletion" in text


def test_deliver_releases_after_finalize_then_runs_scoped_act() -> None:
    text = DELIVER.read_text(encoding="utf-8")
    handoff = text.index("8. **HAND OFF**")
    finalize = text.index("final F result", handoff)
    release = text.index("des worktree-release", finalize)
    check = text.index("des verify-worktree-cleanup", release)
    close_contract = text[check : check + 800]

    assert handoff < finalize < release < check
    assert "--target-branch <target-ref>" in close_contract
    assert "--worktree <execution-root>" in close_contract
    assert "without `--check-only`" in close_contract
    assert "`CLEANUP_DUE`" in close_contract and "`removed=true`" in close_contract
    assert "primary root may yield an empty scoped" in close_contract
