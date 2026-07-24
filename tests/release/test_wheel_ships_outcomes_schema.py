"""Regression ATs: the built wheel SHIPS the JSON Schemas the CLI needs.

Two sibling bugs of the same class live here — a resource resolved by walking
OUT of the package is a resource that ships nowhere. They share this module so
they share the ONE module-scoped `built_wheel` build; splitting them into two
files would build the wheel twice for the same question.

    nWave-ai/nWave#63          `outcomes register`         (fixed, cfaaaf192)
    fix-feature-delta-schema-path  `validate-feature-delta` (slice-01)

Issue: nWave-ai/nWave#63 — `nwave-ai outcomes register` dies with a raw
`FileNotFoundError` on `<site-packages>/docs/product/outcomes/schema.json` from
any normal install, because the schema lives OUTSIDE the package (under `docs/`,
which is stripped from every distribution channel) and is resolved by walking
out of it (`Path(__file__).resolve().parents[3] / "docs" / ...`).

The fix moves the schema INSIDE the package (`nwave_ai/outcomes/schema.json`,
one canonical copy) and loads it via `importlib.resources`. `nwave_ai` is a
`[tool.hatch.build.targets.wheel] packages` entry, so data files under it ship
with zero force-include configuration (`des/config/des_defaults.yaml` is the
existing proof). This AT pins that: whatever the loading mechanism, the resource
must actually BE in the artifact users install.

Companion (the behavioural half):
    tests/bugs/outcomes/test_outcomes_register_schema_install_shape.py

RED today: the wheel carries no `nwave_ai/outcomes/schema.json`.

Reuses the real `built_wheel` build harness from `tests/build/unit/
test_wheel_contract.py` (a genuine `python -m build --wheel`) rather than
introducing a second one — a fake wheel layout could not prove what hatchling
actually packages, which is the entire question here.
"""

from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile

import pytest

# Reused build harness (module-scoped `python -m build --wheel`). Imported for
# its fixture; F401 is intentional — pytest resolves it by name.
from tests.build.unit.test_wheel_contract import built_wheel  # noqa: F401


REPO_ROOT = Path(__file__).resolve().parents[2]
NWAVE_DATA = REPO_ROOT / "nWave" / "data"

SCHEMA_IN_WHEEL = "nwave_ai/outcomes/schema.json"

# The sibling site (fix-feature-delta-schema-path, D-5a/D-6). FIVE runtime
# resources are resolved by walking four `.parent` hops out of the package —
# which lands on the repo root from a checkout, and on site-packages from an
# install, where neither `schemas/` nor `nWave/data/` exists. Post-fix home: all
# five inside the package, shipped by the same `packages = [...]` entry with no
# force-include line for anyone to remember (that forgetting is the systemic
# root, F-PACKAGED-RESOURCE-PATH-GATE).
FEATURE_DELTA_SCHEMA_IN_WHEEL = "nwave_ai/feature_delta/schema.json"
FEATURE_DELTA_DATA_IN_WHEEL = "nwave_ai/feature_delta/data"
_ASSET_DIRS = ("protocol-verbs", "substantive-verbs", "gherkin-keywords")


def _feature_delta_resources_expected_in_wheel() -> tuple[str, ...]:
    """The five feature-delta runtime resources, derived from the repo.

    Derived rather than hard-coded so the pin cannot drift from the assets it
    protects — and so a fix that ships only `en.txt`, silently degrading the
    documented `--lang es|fr|it` to empty verb lists, is caught here.
    """
    names = [
        FEATURE_DELTA_SCHEMA_IN_WHEEL,
        f"{FEATURE_DELTA_DATA_IN_WHEEL}/feature-delta-rule-maturity.json",
    ]
    for asset_dir in _ASSET_DIRS:
        for txt in sorted((NWAVE_DATA / asset_dir).glob("*.txt")):
            names.append(f"{FEATURE_DELTA_DATA_IN_WHEEL}/{asset_dir}/{txt.name}")
    return tuple(names)


# The proof that a data file under a `packages` entry ships with no
# force-include: this one already does. Asserted alongside, so a RED on the
# schema can never be misread as "hatchling drops data files".
KNOWN_SHIPPED_DATA_FILE = "des/config/des_defaults.yaml"

# D-2: the force-include that dropped a top-level `schemas/` into site-packages
# root on the public wheel. Once the schema is a package resource, this line only
# lays down a stale SECOND copy that can drift from, and shadow, the canonical
# one — so the fix deletes it (scripts/release/patch_pyproject.py:191).
STALE_FORCE_INCLUDE = '"schemas" = "schemas"'


@pytest.mark.slow
def test_wheel_ships_outcomes_schema_inside_the_package(built_wheel: Path) -> None:
    """The outcomes JSON Schema is a packaged resource in the built wheel.

    Without this the schema is unreachable from every install (PyPI wheel, and
    the public GitHub tree too, where `docs/` is rsync-stripped), so
    `outcomes register` cannot validate and therefore cannot register — issue
    #63 exactly.
    """
    names = ZipFile(built_wheel).namelist()

    assert KNOWN_SHIPPED_DATA_FILE in names, (
        f"{KNOWN_SHIPPED_DATA_FILE} is missing from the wheel — the packaging "
        "premise of this test (data files under a `packages` entry ship "
        "automatically) no longer holds; investigate the build config before "
        "reading the assertion below."
    )
    assert SCHEMA_IN_WHEEL in names, (
        f"{SCHEMA_IN_WHEEL} is absent from the built wheel. The outcomes schema "
        "still lives outside the package (docs/product/outcomes/schema.json), so "
        "it ships in NO distribution channel and `outcomes register` cannot "
        "validate from an install (nWave-ai/nWave#63)."
    )


# ---------------------------------------------------------------------------
# AT6 (fix-feature-delta-schema-path, slice-01) — ALL FIVE sibling resources.
# @real-io @slow  @contract-shape:pure-function
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_wheel_ships_every_feature_delta_runtime_resource(
    built_wheel: Path,
) -> None:
    """All five feature-delta runtime resources are packaged in the built wheel.

    Companion (the behavioural half):
        tests/bugs/feature_delta/test_validate_feature_delta_schema_install_shape.py

    Today NONE of them is inside the package. The schema sits at the repo's
    top-level `schemas/`; the four data assets sit under `nWave/data/`. The DEV
    wheel carries neither, so `validate-feature-delta` refuses at startup (exit
    70) from any install built here. The PUBLIC wheel survives the schema hop
    only because `patch_pyproject.py:191` force-includes `schemas/` into
    site-packages root — and it does NOT survive the data hop at all: the
    published 3.21.0 payload has no `nWave/data` directory, so the shipped
    product dies on the `verbs.py:81` assert (a raw traceback).

    The fix moves all five inside the package, where the existing
    `packages = [... "nwave_ai"]` entry ships them on every channel with no
    force-include to remember. This is the pin that keeps that true.

    RED today: the wheel carries none of them.
    """
    names = set(ZipFile(built_wheel).namelist())

    assert KNOWN_SHIPPED_DATA_FILE in names, (
        f"{KNOWN_SHIPPED_DATA_FILE} is missing from the wheel — the packaging "
        "premise of this test (data files under a `packages` entry ship "
        "automatically) no longer holds; investigate the build config before "
        "reading the assertion below."
    )

    expected = _feature_delta_resources_expected_in_wheel()
    missing = [name for name in expected if name not in names]
    assert not missing, (
        "these feature-delta runtime resources are absent from the built wheel. "
        "They still live outside the package (top-level `schemas/` and "
        "`nWave/data/`), so they reach an install on no channel and the command "
        "cannot read its own validation rules:\n  " + "\n  ".join(missing)
    )


# ---------------------------------------------------------------------------
# AT7 (fix-feature-delta-schema-path, D-2) — the stale force-include is GONE.
# @contract-shape:pure-function
# ---------------------------------------------------------------------------


def test_public_wheel_config_no_longer_force_includes_the_schemas_directory() -> None:
    """D-2: `patch_pyproject.py` stops dropping `schemas/` into site-packages root.

    Once the schema is a package resource, this force-include lays down a stale
    SECOND copy at `<site-packages>/schemas/feature-delta-schema.json` — one that
    can drift from, and shadow, the canonical one inside the package. Two copies
    of a schema is exactly the drift the parent fix's D-2 forbids.

    Asserted against the map the function actually GENERATES, not against a
    string in the source file, so the pin cannot be satisfied by a comment. The
    control assertion below keeps a RED here from being misread as "the function
    stopped emitting a force-include map at all".

    GREEN today for the wrong reason is impossible: the line is currently there.
    """
    from scripts.release.patch_pyproject import _patch_wheel_packages

    original = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    patched, message = _patch_wheel_packages(original, "nwave_ai")

    assert message is not None, (
        "the public-wheel section was not rewritten at all — the premise of this "
        "test (that `_patch_wheel_packages` generates the force-include map) no "
        "longer holds; investigate before reading the assertion below."
    )
    assert '"scripts/install" = "scripts/install"' in patched, (
        "the generated force-include map is missing a known-good entry, so a "
        "failure below would not distinguish 'schemas removed' from 'map broken'."
    )
    assert STALE_FORCE_INCLUDE not in patched, (
        f"the public-wheel config still force-includes {STALE_FORCE_INCLUDE} into "
        "site-packages root. With the schema now a package resource, that drops a "
        "stale second copy beside the package which can drift from, and shadow, "
        "the canonical one (D-2)."
    )
