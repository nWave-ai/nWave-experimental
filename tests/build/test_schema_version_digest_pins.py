"""Mechanical floor: a versioned schema's bytes cannot change without a bump.

Digest-pin registry: tests/build/fixtures/schema_version_pins.json maps every
versioned schema under nWave/schemas/ to its declared version and the sha256
of its bytes. Two floors, both ordinary unit-tier tests (zero new gates):

1. Completeness -- every schema in nWave/schemas/ that declares a version is
   pinned, so a new versioned schema cannot land unpinned.
2. Digest -- if a pinned schema's bytes change while its declared version does
   not, RED: "schema changed without a version bump".

Counterpart of the artifact-versioning golden corpus
(tests/des/unit/domain/test_artifact_versioning_corpus.py); together they are
the executable face of the G2 chain totality/idempotence invariant
(docs/analysis/2026-08-20-auto-goals-g1-g4.md, section G2, Mechanical floor).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMAS_DIR = REPO_ROOT / "nWave" / "schemas"
PINS_PATH = Path(__file__).parent / "fixtures" / "schema_version_pins.json"
PINS_PATH_REL = "tests/build/fixtures/schema_version_pins.json"


def _load_pins() -> dict[str, dict[str, str]]:
    return json.loads(PINS_PATH.read_text(encoding="utf-8"))


def _declared_version(schema: dict[str, Any]) -> str | None:
    """The schema's own declared version, or None for an unversioned schema.

    Two declaration shapes exist in nWave/schemas/ today: a top-level
    ``"schema"`` string carrying the version suffix (nwave.test_result.v1,
    nwave.test_observation.v1), and a JSON-Schema ``schema-version`` property
    pinned by ``const`` (thin-delivery-contract). ``"$schema"`` (the JSON
    Schema dialect URI) is NOT a version declaration.
    """
    top = schema.get("schema")
    if isinstance(top, str):
        return top
    const = schema.get("properties", {}).get("schema-version", {}).get("const")
    if isinstance(const, str):
        return const
    return None


def test_every_versioned_schema_is_pinned() -> None:
    pins = _load_pins()
    unpinned = []
    for path in sorted(SCHEMAS_DIR.glob("*.json")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        declared = _declared_version(json.loads(path.read_text(encoding="utf-8")))
        if declared is not None and rel not in pins:
            unpinned.append((rel, declared))
    assert not unpinned, (
        f"WHAT: versioned schema(s) not in the digest-pin registry: {unpinned}.\n"
        "WHY: an unpinned schema can change shape silently -- no test reminds "
        "the author to bump the version and ship the migration.\n"
        f"HOW: add each schema to {PINS_PATH_REL} with its declared version "
        "and the sha256 of its bytes (sha256sum <file>)."
    )


@pytest.mark.parametrize("rel_path", sorted(_load_pins()))
def test_pinned_schema_bytes_match_declared_version(rel_path: str) -> None:
    pin = _load_pins()[rel_path]
    path = REPO_ROOT / rel_path
    assert path.exists(), (
        f"WHAT: pinned schema {rel_path} no longer exists.\n"
        "WHY: deleting a versioned schema is itself a shape change consumers "
        "must be migrated away from, not a silent removal.\n"
        f"HOW: restore the file, or remove its pin from {PINS_PATH_REL} in the "
        "same commit that migrates/retires every consumer of that schema."
    )
    actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    declared = _declared_version(json.loads(path.read_text(encoding="utf-8")))
    if actual_sha == pin["sha256"]:
        assert declared == pin["declared-version"], (
            f"WHAT: {rel_path} bytes are unchanged but the pin records version "
            f"{pin['declared-version']!r} while the file declares {declared!r}.\n"
            "WHY: the registry contradicts the file it pins; the floor's memory "
            "is corrupt and the next change is judged against a lie.\n"
            f"HOW: fix the declared-version entry for {rel_path} in "
            f"{PINS_PATH_REL} to match the file."
        )
        return
    if declared == pin["declared-version"]:
        pytest.fail(
            f"WHAT: {rel_path} bytes changed (sha256 now {actual_sha}) but its "
            f"declared version is still {declared!r}.\n"
            "WHY: consumers key migrations on the declared version; a shape "
            "change without a bump ships with no upcaster and breaks every "
            "artifact written under the old shape.\n"
            "HOW: bump the schema's declared version, add the matching "
            "upcaster/migration (see the golden corpus test), then update this "
            f"schema's pin in {PINS_PATH_REL} with the new version and "
            f"sha256 {actual_sha}."
        )
    pytest.fail(
        f"WHAT: {rel_path} was re-versioned to {declared!r} but the pin still "
        f"records {pin['declared-version']!r} (sha256 now {actual_sha}).\n"
        "WHY: a stale pin stops guarding the NEXT unversioned change to this "
        "schema.\n"
        f"HOW: update the {rel_path} entry in {PINS_PATH_REL} with "
        f"declared-version {declared!r} and sha256 {actual_sha}, and confirm "
        "the upcaster for the new version exists (golden corpus test)."
    )
