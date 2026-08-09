"""Uninstall: shared-manifest family record removal (P1-A).

``remove_family_record`` is the one primitive every asset-family uninstaller
uses to retire its own key from ``.nwave-manifest.json`` and delete the
members it recorded — without ever touching sibling families, untracked
children, or user-owned files with the same directory.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from hypothesis import given
from hypothesis import settings as h_settings
from hypothesis import strategies as st

from scripts.shared.skill_distribution import (
    MANIFEST_FILENAME,
    remove_family_record,
)


_OWNED_KEY = "installed_utilities"
_SIBLING_KEY = "installed_scripts"

_SAFE_NAMES = st.from_regex(r"\A[a-zA-Z0-9_.-]{1,12}\Z", fullmatch=True).filter(
    lambda name: name not in (".", "..")
)


def _write_doc(target_dir: Path, doc: dict) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / MANIFEST_FILENAME).write_text(json.dumps(doc, indent=2) + "\n")


def _read_doc(target_dir: Path) -> dict | None:
    path = target_dir / MANIFEST_FILENAME
    if not path.exists():
        return None
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------
# Semantic property: arbitrary safe owned + sibling trees, idempotent.
# ---------------------------------------------------------------------------


@given(
    owned=st.sets(_SAFE_NAMES, max_size=4),
    sibling=st.sets(_SAFE_NAMES, max_size=4),
    user_owned=st.sets(_SAFE_NAMES, max_size=4),
    missing=st.sets(_SAFE_NAMES, max_size=2),
)
@h_settings(max_examples=40, deadline=None)
def test_remove_family_record_deletes_only_its_own_members_and_is_idempotent(
    owned, sibling, user_owned, missing
) -> None:
    owned -= missing
    sibling -= owned | missing
    user_owned -= owned | sibling | missing
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        for name in owned | sibling | user_owned:
            (target / name).write_text("content\n")
        _write_doc(target, {_OWNED_KEY: sorted(owned), _SIBLING_KEY: sorted(sibling)})

        evidence = remove_family_record(target, key=_OWNED_KEY)

        assert evidence.status == "complete"
        assert evidence.removed | evidence.already_absent == owned
        assert evidence.blocked == frozenset()
        for name in owned:
            assert not (target / name).exists()
        for name in sibling | user_owned:
            assert (target / name).exists()
        doc = _read_doc(target)
        assert doc is not None
        assert doc.get(_OWNED_KEY) is None
        assert doc[_SIBLING_KEY] == sorted(sibling)

        second = remove_family_record(target, key=_OWNED_KEY)
        assert second.status == "complete"
        assert second.removed == frozenset()
        for name in sibling | user_owned:
            assert (target / name).exists()


# ---------------------------------------------------------------------------
# Path-adversary property: any unsafe recorded name blocks the whole family.
# ---------------------------------------------------------------------------

_UNSAFE_NAMES = st.sampled_from(
    [
        "",
        ".",
        "..",
        "/etc/passwd",
        "../escape",
        "nested/child",
        "nested\\child",
        "C:\\Windows",
        "a/../../b",
    ]
)


@given(
    unsafe=_UNSAFE_NAMES,
    safe_siblings=st.sets(_SAFE_NAMES, max_size=3),
)
@h_settings(max_examples=30, deadline=None)
def test_unsafe_member_name_blocks_family_without_mutating_disk(
    unsafe, safe_siblings
) -> None:
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / "target"
        target.mkdir()
        for name in safe_siblings:
            (target / name).write_text("content\n")
        members = [unsafe, *sorted(safe_siblings)]
        _write_doc(target, {_OWNED_KEY: members})
        before = _read_doc(target)

        evidence = remove_family_record(target, key=_OWNED_KEY)

        assert evidence.status == "blocked"
        assert evidence.removed == frozenset()
        assert evidence.blocked == frozenset(members)
        for name in safe_siblings:
            assert (target / name).exists()
        assert _read_doc(target) == before


# ---------------------------------------------------------------------------
# Compact parametrized malformed / edge cases.
# ---------------------------------------------------------------------------


def test_missing_manifest_reports_missing_manifest(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()

    evidence = remove_family_record(target, key=_OWNED_KEY)

    assert evidence.status == "missing_manifest"
    assert evidence.removed == frozenset()


@pytest.mark.parametrize(
    "raw",
    [
        "not json{{{",
        json.dumps(["a", "list", "not", "a", "dict"]),
        json.dumps({_OWNED_KEY: "not-a-list"}),
        json.dumps({_OWNED_KEY: ["ok", 42]}),
    ],
)
def test_corrupt_or_malformed_manifest_reports_invalid_manifest(
    tmp_path: Path, raw: str
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / MANIFEST_FILENAME).write_text(raw)
    before = (target / MANIFEST_FILENAME).read_text()

    evidence = remove_family_record(target, key=_OWNED_KEY)

    assert evidence.status == "invalid_manifest"
    assert evidence.removed == frozenset()
    assert (target / MANIFEST_FILENAME).read_text() == before


def test_dangling_symlink_member_unlinks_only_the_link_not_target(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("keep me\n")
    link = target / "owned-link"
    link.symlink_to(outside)
    _write_doc(target, {_OWNED_KEY: [link.name]})

    evidence = remove_family_record(target, key=_OWNED_KEY)

    assert evidence.status == "complete"
    assert evidence.removed == frozenset({link.name})
    assert not link.is_symlink()
    assert outside.exists()
    assert outside.read_text() == "keep me\n"


def test_listed_missing_member_is_already_absent_and_leaves_family(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "present.txt").write_text("x\n")
    _write_doc(target, {_OWNED_KEY: ["present.txt", "gone.txt"]})

    evidence = remove_family_record(target, key=_OWNED_KEY)

    assert evidence.status == "complete"
    assert evidence.removed == frozenset({"present.txt"})
    assert evidence.already_absent == frozenset({"gone.txt"})
    assert _read_doc(target) is None
