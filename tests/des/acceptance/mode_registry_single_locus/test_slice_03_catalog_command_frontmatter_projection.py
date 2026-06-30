"""pytest-bdd binding for mode-registry-single-locus slice-03.

Thin binding: registers the slice-03 scenarios and imports the step
vocabulary. No step definitions or business logic live here — the SSOT for
step bodies is `steps/steps_slice_03_catalog_command_frontmatter_projection.py`
+ `steps/composition_slice_03.py`; the SSOT for the scenarios is the
`.feature` file (per the DISTILL mandate).

Slice-03 = command frontmatter `description:` / `argument-hint:` projected
from `framework-catalog.yaml` via the real docgen entry (DESIGN decision
D-project): the catalog becomes the sole author, the staleness check refuses
the 2026-06-10 hotfix desync class (execute description / distill argument
hint) instead of serving it stale, and AT-03 pins acceptance-implies-full-
catalog-agreement + idempotency so the retired hand-sync contract
(`tests/plugins/test_command_frontmatter.py`) is safely deletable at GREEN.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps.steps_slice_03_catalog_command_frontmatter_projection import *


scenarios("slice-03-catalog-command-frontmatter-projection.feature")
