"""V4-24 regression: ``_reconcile`` must compare attribution semantically.

``ConfigWriter._reconcile`` previously compared the existing (public
on/off-string) and legacy (``{"enabled": bool}`` dict) attribution values
by raw ``!=``, so a semantically-identical pair (e.g. public ``"on"`` vs
legacy ``{"enabled": True}``) raised a false ``ConfigMigrationError``. This
suite drives real files through ``ConfigWriter.bootstrap`` to prove:

  1. Semantically-equal public/legacy pairs no longer conflict.
  2. A genuine on/off disagreement still refuses BEFORE any write.
  3. A legacy custom field (``trailer``) is preserved, never discarded.
  4. dry-run and a second (idempotent) real run behave consistently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.adapters.driven.config.config_writer import ConfigMigrationError, ConfigWriter


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_public_on_and_legacy_enabled_true_do_not_conflict(tmp_path: Path) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "on"})
    _write(home / ".nwave" / "global-config.json", {"attribution": {"enabled": True}})

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert json.loads(result.global_path.read_text())["attribution"] == "on"


def test_public_off_and_legacy_enabled_false_do_not_conflict(tmp_path: Path) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "off"})
    _write(home / ".nwave" / "global-config.json", {"attribution": {"enabled": False}})

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert json.loads(result.global_path.read_text())["attribution"] == "off"


def test_genuine_on_off_conflict_still_refuses_before_any_write(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "on"})
    global_legacy = home / ".nwave" / "global-config.json"
    _write(global_legacy, {"attribution": {"enabled": False}})
    original_canonical_bytes = global_path.read_bytes()
    original_legacy_bytes = global_legacy.read_bytes()

    with pytest.raises(ConfigMigrationError):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    # Refusal happens before any write: both files remain untouched.
    assert global_path.read_bytes() == original_canonical_bytes
    assert global_legacy.read_bytes() == original_legacy_bytes
    assert not (repo / ".nwave" / "config.json").exists()


def test_legacy_custom_trailer_is_preserved_not_discarded(tmp_path: Path) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "on"})
    _write(
        home / ".nwave" / "global-config.json",
        {"attribution": {"enabled": True, "trailer": "Co-Authored-By: Custom <c@c>"}},
    )

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    written = json.loads(result.global_path.read_text())
    assert written["attribution"] == {
        "enabled": True,
        "trailer": "Co-Authored-By: Custom <c@c>",
    }


def test_different_trailers_both_enabled_true_is_a_genuine_conflict(
    tmp_path: Path,
) -> None:
    """Same ``enabled`` but disagreeing ``trailer`` must still refuse (V4-24
    correction): silently keeping the canonical trailer would discard the
    legacy operator's own attribution text without telling them.
    """
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(
        global_path,
        {"schema-version": 1, "attribution": {"enabled": True, "trailer": "Canonical"}},
    )
    global_legacy = home / ".nwave" / "global-config.json"
    _write(global_legacy, {"attribution": {"enabled": True, "trailer": "Legacy"}})
    original_canonical_bytes = global_path.read_bytes()
    original_legacy_bytes = global_legacy.read_bytes()

    with pytest.raises(ConfigMigrationError):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert global_path.read_bytes() == original_canonical_bytes
    assert global_legacy.read_bytes() == original_legacy_bytes


def test_unknown_public_string_versus_legacy_enabled_is_a_conflict(
    tmp_path: Path,
) -> None:
    """An unrecognised public ``attribution`` string is never treated as
    ``None``-shaped and silently accepted against a legacy ``enabled``
    fact (V4-24 correction): an unknown shape must refuse, not win.
    """
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "invalid-choice"})
    global_legacy = home / ".nwave" / "global-config.json"
    _write(global_legacy, {"attribution": {"enabled": True}})
    original_canonical_bytes = global_path.read_bytes()
    original_legacy_bytes = global_legacy.read_bytes()

    with pytest.raises(ConfigMigrationError):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    assert global_path.read_bytes() == original_canonical_bytes
    assert global_legacy.read_bytes() == original_legacy_bytes


def test_compatible_custom_trailer_extra_field_is_still_preserved(
    tmp_path: Path,
) -> None:
    """Disjoint extra legacy fields (no shared-field disagreement) still
    merge and survive, distinguishing a real conflict from compatible extra
    information (V4-24 correction target, kept green by the semantic fix).
    """
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "on"})
    _write(
        home / ".nwave" / "global-config.json",
        {"attribution": {"enabled": True, "trailer": "Co-Authored-By: Custom <c@c>"}},
    )

    result = ConfigWriter(home_dir=home, repo_root=repo).bootstrap()

    written = json.loads(result.global_path.read_text())
    assert written["attribution"] == {
        "enabled": True,
        "trailer": "Co-Authored-By: Custom <c@c>",
    }


def test_dry_run_makes_no_writes_on_semantic_conflict(tmp_path: Path) -> None:
    """dry-run of a genuine semantic conflict raises and writes nothing."""
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(
        global_path,
        {"schema-version": 1, "attribution": {"enabled": True, "trailer": "Canonical"}},
    )
    global_legacy = home / ".nwave" / "global-config.json"
    _write(global_legacy, {"attribution": {"enabled": True, "trailer": "Legacy"}})
    original_canonical_bytes = global_path.read_bytes()
    original_legacy_bytes = global_legacy.read_bytes()

    with pytest.raises(ConfigMigrationError):
        ConfigWriter(home_dir=home, repo_root=repo).bootstrap(dry_run=True)

    assert global_path.read_bytes() == original_canonical_bytes
    assert global_legacy.read_bytes() == original_legacy_bytes
    assert not (repo / ".nwave" / "config.json").exists()


def test_dry_run_makes_no_mutation_then_real_run_is_idempotent(
    tmp_path: Path,
) -> None:
    home, repo = tmp_path / "home", tmp_path / "repo"
    global_path = home / ".nwave" / "config.json"
    _write(global_path, {"schema-version": 1, "attribution": "on"})
    global_legacy = home / ".nwave" / "global-config.json"
    _write(global_legacy, {"attribution": {"enabled": True}})

    writer = ConfigWriter(home_dir=home, repo_root=repo)
    dry_result = writer.bootstrap(dry_run=True)
    assert dry_result.dry_run is True
    assert global_legacy.exists()  # untouched by dry-run

    first = writer.bootstrap()
    assert not global_legacy.exists()
    second = writer.bootstrap()
    assert json.loads(first.global_path.read_text()) == json.loads(
        second.global_path.read_text()
    )
