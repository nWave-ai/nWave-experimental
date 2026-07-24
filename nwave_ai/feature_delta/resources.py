"""Locate the feature-delta runtime resources that ship INSIDE the package.

Every resource `validate-feature-delta` needs at startup — the JSON Schema, the
protocol/substantive verb lists, the Gherkin keywords, the rule-maturity
manifest — is a PACKAGE RESOURCE under ``nwave_ai/feature_delta/``. They travel
with ``nwave_ai`` into every install via the existing ``packages = [...]`` entry
(pyproject.toml), with no force-include line for anyone to remember.

They must NEVER be resolved by walking out of the package
(``Path(__file__).parent.parent.parent.parent / "schemas" / ...``): from a
source checkout those hops land on the repo root, where the assets happen to
sit, so everything resolves and the defect is invisible; from an install they
land in site-packages, where none of it exists and the command dies over its own
missing files instead of reporting on the maintainer's document.

Sibling of nWave-ai/nWave#63 (`cfaaaf192`), which established this pattern for
``nwave_ai/outcomes/schema.json``.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path


_PACKAGE = "nwave_ai.feature_delta"


def packaged_resource(*parts: str) -> Path:
    """Return the filesystem path of a packaged resource under this package.

    `parts` are joined beneath ``nwave_ai/feature_delta/`` — e.g.
    ``packaged_resource("data", "protocol-verbs")``.

    The path is resolved through ``importlib.resources``, so it is correct
    wherever the package is installed and carries no assumption about what lives
    ABOVE it. The result is returned as a ``Path`` because every consumer here
    reads real files (and the tests inject real ``Path`` overrides through the
    same seams); a zip-imported install is out of contract for this package,
    which ships unzipped into site-packages on every channel.
    """
    return Path(str(files(_PACKAGE).joinpath(*parts)))
