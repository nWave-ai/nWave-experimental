"""Regression AT: the built wheel SHIPS the outcomes JSON Schema the CLI needs.

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

SCHEMA_IN_WHEEL = "nwave_ai/outcomes/schema.json"

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
