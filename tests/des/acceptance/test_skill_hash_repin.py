"""Acceptance tests -- scripts/hooks/validate_skill_hashes.py --repin.

Charter: docs/product/expectations/skill-hash-repin/
         repin-accepts-intentional-skill-edits.md
Feature-delta: docs/feature/skill-hash-repin/feature-delta.md

Drives the production module through its real driving surface: the module
itself, with `SKILLS_DIR` / `HASH_TEST_FILE` monkeypatched onto a throwaway
tmp_path tree (Mandate: Driving-Port-Only Boundary -- the module IS the
composition root here, there is no narrower internal component to bypass).

RED today (slice-01, active-RED, atdd_pure): `compute_drift` and `repin`
do not exist yet on `scripts.hooks.validate_skill_hashes`. The module import
itself succeeds (hidden-import, no collection ImportError); each scenario
that needs the new functions asserts their presence first, via a semantic
`AssertionError` (MISSING_FUNCTIONALITY), never an `AttributeError` and
never a bare `ImportError` at collection time.
"""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path

import pytest


FOO_ORIGINAL = "# nw-foo\n\nOriginal skill content for the repin walking skeleton.\n"
FOO_EDITED = "# nw-foo\n\nIntentionally edited skill content -- triggers hash drift.\n"
BAR_CONTENT = "# nw-bar\n\nStable skill content that never drifts in these scenarios.\n"


def _load_module():
    """Hidden-import the production module (RED: compute_drift/repin absent)."""
    return importlib.import_module("scripts.hooks.validate_skill_hashes")


def _require_repin_functionality(module) -> None:
    """Semantic RED gate: fails with AssertionError while the names are absent."""
    assert hasattr(module, "compute_drift"), (
        "MISSING_FUNCTIONALITY: validate_skill_hashes.compute_drift is not "
        "implemented yet (slice-01 RED)"
    )
    assert hasattr(module, "repin"), (
        "MISSING_FUNCTIONALITY: validate_skill_hashes.repin is not "
        "implemented yet (slice-01 RED)"
    )


def _seed_throwaway_tree(tmp_path: Path) -> tuple[Path, Path, str, str]:
    """Build a throwaway skills/ + baseline pair, both monitored skills clean.

    Returns (skills_dir, baseline_file, foo_hash, bar_hash).
    """
    skills_dir = tmp_path / "skills"
    (skills_dir / "nw-foo").mkdir(parents=True)
    (skills_dir / "nw-bar").mkdir(parents=True)
    (skills_dir / "nw-foo" / "SKILL.md").write_text(FOO_ORIGINAL, encoding="utf-8")
    (skills_dir / "nw-bar" / "SKILL.md").write_text(BAR_CONTENT, encoding="utf-8")

    foo_hash = hashlib.md5(FOO_ORIGINAL.encode("utf-8")).hexdigest()
    bar_hash = hashlib.md5(BAR_CONTENT.encode("utf-8")).hexdigest()

    baseline_file = tmp_path / "hash_baseline.py"
    baseline_file.write_text(
        '"""Throwaway baseline fixture for skill-hash-repin AT."""\n\n'
        "BULK_HASHES = {\n"
        f'    "nw-foo": "{foo_hash}",\n'
        f'    "nw-bar": "{bar_hash}",\n'
        "}\n",
        encoding="utf-8",
    )
    return skills_dir, baseline_file, foo_hash, bar_hash


def _edit_skill(skill_md: Path, new_content: str) -> str:
    """Overwrite a skill's SKILL.md, returning its new md5 hash."""
    skill_md.write_text(new_content, encoding="utf-8")
    return hashlib.md5(new_content.encode("utf-8")).hexdigest()


def test_no_op_on_clean_tree_leaves_baseline_byte_unchanged(tmp_path, monkeypatch):
    """
    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch

    A developer runs --repin on a tree where every monitored skill already
    matches its baseline. compute_drift() reports nothing to re-pin, and
    repin() is a true no-op: exit 0, baseline file byte-unchanged.
    """
    module = _load_module()
    _require_repin_functionality(module)

    skills_dir, baseline_file, _foo_hash, _bar_hash = _seed_throwaway_tree(tmp_path)
    monkeypatch.setattr(module, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(module, "HASH_TEST_FILE", baseline_file)
    before = baseline_file.read_text(encoding="utf-8")

    drift = module.compute_drift()
    assert drift == []

    exit_code = module.repin(drift)
    assert exit_code == 0
    assert baseline_file.read_text(encoding="utf-8") == before


def test_repin_accepts_an_intentional_skill_edit(tmp_path, monkeypatch):
    """
    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch

    A developer intentionally edits nw-foo's SKILL.md. compute_drift()
    reports exactly the one drifted monitored skill (old hash, new hash);
    repin() rewrites that skill's baseline entry to the new hash and a
    fresh compute_drift() afterwards reports no more drift.
    """
    module = _load_module()
    _require_repin_functionality(module)

    skills_dir, baseline_file, foo_hash, _bar_hash = _seed_throwaway_tree(tmp_path)
    monkeypatch.setattr(module, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(module, "HASH_TEST_FILE", baseline_file)

    new_hash = _edit_skill(skills_dir / "nw-foo" / "SKILL.md", FOO_EDITED)

    drift = module.compute_drift()
    assert drift == [("nw-foo", foo_hash, new_hash)]

    exit_code = module.repin(drift)
    assert exit_code == 0

    rewritten = baseline_file.read_text(encoding="utf-8")
    assert f'"nw-foo": "{new_hash}"' in rewritten
    assert foo_hash not in rewritten
    assert module.compute_drift() == []


def test_repin_is_surgical_leaving_non_drifted_entries_byte_unchanged(
    tmp_path, monkeypatch
):
    """
    CONTRACT_SHAPE: bounded-change
    Outcome anchor: DISCUSS Elevator Pitch

    After repinning the drifted nw-foo entry, the non-drifted nw-bar
    baseline entry stays byte-unchanged -- repin() touches only the
    genuinely drifted monitored entries, never a matching one.
    """
    module = _load_module()
    _require_repin_functionality(module)

    skills_dir, baseline_file, _foo_hash, bar_hash = _seed_throwaway_tree(tmp_path)
    monkeypatch.setattr(module, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(module, "HASH_TEST_FILE", baseline_file)
    bar_line = f'    "nw-bar": "{bar_hash}",\n'
    assert bar_line in baseline_file.read_text(encoding="utf-8")

    _edit_skill(skills_dir / "nw-foo" / "SKILL.md", FOO_EDITED)

    exit_code = module.repin(module.compute_drift())
    assert exit_code == 0
    assert bar_line in baseline_file.read_text(encoding="utf-8")


@pytest.mark.negative_at
def test_default_check_never_rewrites_the_baseline(tmp_path, monkeypatch):
    """
    CONTRACT_SHAPE: pure-function
    Outcome anchor: DISCUSS Elevator Pitch

    Negative AT (GS-8): asserts the WRONG outcome -- a silent baseline
    auto-rewrite without --repin -- is NOT produced. The module's existing
    default check path (extract_bulk_hashes + per-skill hash comparison)
    only ever READS SKILLS_DIR/HASH_TEST_FILE; an intentional nw-foo edit
    must be detectable as a mismatch without the baseline file ever being
    touched. GREEN today (uses only pre-existing, already-implemented
    module functionality) and stays green after --repin lands.
    """
    module = _load_module()

    skills_dir, baseline_file, foo_hash, _bar_hash = _seed_throwaway_tree(tmp_path)
    monkeypatch.setattr(module, "SKILLS_DIR", skills_dir)
    monkeypatch.setattr(module, "HASH_TEST_FILE", baseline_file)

    edited_hash = _edit_skill(skills_dir / "nw-foo" / "SKILL.md", FOO_EDITED)
    before = baseline_file.read_text(encoding="utf-8")

    baseline = module.extract_bulk_hashes()
    actual = hashlib.md5((skills_dir / "nw-foo" / "SKILL.md").read_bytes()).hexdigest()

    assert baseline["nw-foo"] == foo_hash
    assert actual == edited_hash
    assert actual != baseline["nw-foo"], "expected the default path to detect drift"

    after = baseline_file.read_text(encoding="utf-8")
    assert after == before, (
        "the default (non --repin) check path must never rewrite the baseline"
    )
