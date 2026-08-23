"""Golden corpus for the artifact-versioning kernel's production chains.

For every artifact type registered with an ``ArtifactVersioningKernel`` in
production code (src/des), the corpus freezes ONE fixture PER HISTORICAL
VERSION under tests/des/unit/domain/fixtures/artifact_corpus/<type>/v<N>.json.
The corpus is a LINEAGE by convention: fixture v(k+1) is the upcast of fixture
v(k), so upcast_to_current over ANY corpus fixture must reproduce the
current-version fixture exactly.

Floors, all ordinary unit-tier tests (zero new gates):

1. Discovery -- every type registered in src/des (AST scan of kernel call
   sites) appears in PRODUCTION_KERNELS below; a new versioned artifact type
   cannot ship without a corpus.
2. Totality -- every version 0..current of every type has a frozen fixture.
   The kernel makes "a version without an upcaster" unrepresentable (a type's
   current version IS its chain length), so this floor fires exactly when a
   chain grows without freezing the new shape.
3. Round-trip -- every fixture upcasts to the current fixture's exact content.
4. Idempotence -- upcasting an already-upcast doc changes nothing.

Baseline v0 for global-config is the real public v3.21.0 on-disk shape,
verbatim from that release's docs/reference/global-config.md (provenance:
tests/des/unit/adapters/driven/config/test_des_config_global_config_versioning.py).
Counterpart of the schema digest-pin floor
(tests/build/test_schema_version_digest_pins.py); together they are the
executable face of the G2 chain totality/idempotence invariant
(docs/analysis/2026-08-20-auto-goals-g1-g4.md, section G2, Mechanical floor).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from des.adapters.driven.config.des_config import (
    _GLOBAL_CONFIG_ARTIFACT_TYPE,
    _GLOBAL_CONFIG_VERSIONING,
)
from des.domain.artifact_versioning import (
    SCHEMA_VERSION_KEY,
    ArtifactVersioningKernel,
    read_version,
)


REPO_ROOT = Path(__file__).resolve().parents[4]
SRC_DES = REPO_ROOT / "src" / "des"
CORPUS_ROOT = Path(__file__).parent / "fixtures" / "artifact_corpus"
CORPUS_ROOT_REL = "tests/des/unit/domain/fixtures/artifact_corpus"

#: Every production-registered artifact type -> its production kernel. The
#: discovery test below fails when src/des registers a type missing here.
PRODUCTION_KERNELS: dict[str, ArtifactVersioningKernel] = {
    _GLOBAL_CONFIG_ARTIFACT_TYPE: _GLOBAL_CONFIG_VERSIONING,
}


def _fixture_path(artifact_type: str, version: int) -> Path:
    return CORPUS_ROOT / artifact_type / f"v{version}.json"


def _load_fixture(artifact_type: str, version: int) -> dict[str, Any]:
    return json.loads(_fixture_path(artifact_type, version).read_text(encoding="utf-8"))


def _is_kernel_ctor(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "ArtifactVersioningKernel"
    return isinstance(func, ast.Attribute) and (func.attr == "ArtifactVersioningKernel")


def _upcaster_dicts(node: ast.Call) -> list[ast.Dict]:
    """The dict literal(s) passed as the ctor's ``upcasters`` mapping."""
    dicts = [
        kw.value
        for kw in node.keywords
        if kw.arg == "upcasters" and isinstance(kw.value, ast.Dict)
    ]
    if node.args and isinstance(node.args[0], ast.Dict):
        dicts.append(node.args[0])
    return dicts


def _registered_types_in_production() -> dict[str, str]:
    """Artifact-type name -> registering file, via AST over src/des.

    Dict keys written as module-level string constants are resolved through
    that module's own top-level assignments; a key this scan cannot resolve
    statically fails LOUD rather than silently shrinking the census.
    """
    found: dict[str, str] = {}
    for py in sorted(SRC_DES.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        module_consts = {
            target.id: stmt.value.value
            for stmt in tree.body
            if isinstance(stmt, ast.Assign)
            and isinstance(stmt.value, ast.Constant)
            and isinstance(stmt.value.value, str)
            for target in stmt.targets
            if isinstance(target, ast.Name)
        }
        rel = py.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and _is_kernel_ctor(node)):
                continue
            for dict_node in _upcaster_dicts(node):
                for key in dict_node.keys:
                    name: str | None = None
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        name = key.value
                    elif isinstance(key, ast.Name):
                        name = module_consts.get(key.id)
                    if name is None:
                        pytest.fail(
                            f"WHAT: {rel} registers an ArtifactVersioningKernel "
                            "type whose key this census cannot resolve "
                            "statically.\n"
                            "WHY: an unresolvable key silently shrinks the "
                            "corpus census -- the floor would stop seeing new "
                            "versioned types.\n"
                            "HOW: name the artifact type as a string literal or "
                            "a module-level string constant at the registration "
                            "site."
                        )
                    found[name] = rel
    return found


def test_every_production_registered_type_has_a_corpus() -> None:
    discovered = _registered_types_in_production()
    missing = sorted(set(discovered) - set(PRODUCTION_KERNELS))
    assert not missing, (
        f"WHAT: artifact type(s) registered in production without a golden "
        f"corpus: { {t: discovered[t] for t in missing} }.\n"
        "WHY: a versioned type with no frozen corpus has no executable memory "
        "of its historical shapes -- the next shape change ships unmigrated.\n"
        f"HOW: for each type add {CORPUS_ROOT_REL}/<type>/v0.json (frozen from "
        "a real artifact) up to v<current>.json, and register its kernel in "
        "PRODUCTION_KERNELS in this module."
    )
    stale = sorted(set(PRODUCTION_KERNELS) - set(discovered))
    assert not stale, (
        f"WHAT: corpus covers type(s) no production kernel registers: {stale}.\n"
        "WHY: either the registration moved beyond this census's static reach "
        "(the discovery floor is now blind) or the type was retired without "
        "cleaning its corpus.\n"
        "HOW: keep registrations as literal dicts at the kernel call site, or "
        "remove the retired type's corpus directory and its PRODUCTION_KERNELS "
        "entry."
    )


@pytest.mark.parametrize("artifact_type", sorted(PRODUCTION_KERNELS))
def test_every_version_has_a_frozen_fixture(artifact_type: str) -> None:
    kernel = PRODUCTION_KERNELS[artifact_type]
    current = kernel.current_version(artifact_type)
    missing = [
        version
        for version in range(current + 1)
        if not _fixture_path(artifact_type, version).exists()
    ]
    assert not missing, (
        f"WHAT: '{artifact_type}' is at version {current} but corpus "
        f"fixture(s) v{missing} are missing under "
        f"{CORPUS_ROOT_REL}/{artifact_type}/.\n"
        "WHY: the upcaster chain grew without freezing the new shape -- the "
        "corpus is the binary future versions hook onto, and a hole means the "
        "new upcaster is never exercised against a real historical artifact.\n"
        f"HOW: freeze v<N>.json for each missing N (v<k+1> is the upcast of "
        "v<k>) in the same commit that adds the upcaster."
    )


@pytest.mark.parametrize("artifact_type", sorted(PRODUCTION_KERNELS))
def test_current_fixture_declares_current_version(artifact_type: str) -> None:
    kernel = PRODUCTION_KERNELS[artifact_type]
    current = kernel.current_version(artifact_type)
    declared = read_version(_load_fixture(artifact_type, current))
    assert declared == current, (
        f"WHAT: {CORPUS_ROOT_REL}/{artifact_type}/v{current}.json declares "
        f"{SCHEMA_VERSION_KEY}={declared}, not {current}.\n"
        "WHY: the current fixture IS the current shape's specimen; a wrong "
        "declared version makes every round-trip assertion vacuous.\n"
        f"HOW: set {SCHEMA_VERSION_KEY} to {current} in that fixture (it must "
        "equal the upcast of the previous fixture)."
    )


@pytest.mark.parametrize("artifact_type", sorted(PRODUCTION_KERNELS))
def test_all_fixtures_upcast_to_the_current_fixture(artifact_type: str) -> None:
    kernel = PRODUCTION_KERNELS[artifact_type]
    current = kernel.current_version(artifact_type)
    expected = _load_fixture(artifact_type, current)
    for version in range(current + 1):
        result = kernel.upcast_to_current(
            _load_fixture(artifact_type, version), artifact_type
        )
        assert result == expected, (
            f"WHAT: upcasting {CORPUS_ROOT_REL}/{artifact_type}/v{version}.json "
            f"to current does not reproduce v{current}.json.\n"
            "WHY: the corpus is a lineage (each fixture is the upcast of the "
            "previous); a divergence means an upcaster changed behaviour on a "
            "real historical shape, or a fixture was edited out of lineage.\n"
            "HOW: fix the upcaster if the divergence is a bug; if the new "
            "behaviour is intended, that IS a shape change -- add a new "
            "version + upcaster + fixture instead of editing history.\n"
            f"got: {result}\nexpected: {expected}"
        )
        again = kernel.upcast_to_current(result, artifact_type)
        assert again == result, (
            f"WHAT: upcast_to_current is not idempotent on '{artifact_type}' "
            f"corpus fixture v{version}.\n"
            "WHY: a non-idempotent chain rewrites artifacts on every reread -- "
            "the exact silent corruption the kernel exists to prevent.\n"
            "HOW: make every upcaster a pure v(n)->v(n+1) transform that "
            "leaves an already-current doc unchanged."
        )
