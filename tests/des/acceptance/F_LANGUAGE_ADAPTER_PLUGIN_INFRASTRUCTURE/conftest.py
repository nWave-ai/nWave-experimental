"""pytest-bdd configuration for F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE.

DISTILL-authored RED scaffold (ADR-025): every slice-01 AT is authored
ahead of the production wiring. At DISTILL time the empirical state is:

- ``nWave/data/language-adapter-ports.yaml`` -- ABSENT
- ``nWave/schemas/language-adapter-ports.schema.json`` -- ABSENT
- ``scripts/cli/validate_language_adapter_catalog.py`` -- ABSENT
- ``src/des/cli/doctor.py`` -- ABSENT
- ``des doctor`` -- NOT REGISTERED in
  ``src/des/cli/__main__.py:_REGISTRY``

Every scenario reds for the RIGHT reason -- MISSING_FUNCTIONALITY (the
production artifacts are absent), NOT ImportError / FixtureBroken /
SetupFailure. The composition exercises real production code paths via
subprocess; the assertions fail because the subprocess can't find the
target (module-not-found / unknown subcommand / file-not-found).

The collection hook below marks every slice-01 scenario ``xfail`` (strict=False)
until DELIVER greens it. DELIVER narrows ``_RED_SCAFFOLD_SLICES`` slice-by-
slice at the GREEN phase, one slice at a time, per the one-at-a-time TDD
cadence.

The ``strict=False`` choice mirrors the
``fix_oss_environmental_e2e_gate``/``walking_skeleton_feature_end_wiring``
sibling pattern: some Outline rows (e.g., languages whose adapter happens
to never have existed) may pass organically pre-implementation if the
subprocess returns the right shape by accident -- strict xfail would treat
them as XPASS-regressions, which they aren't.
"""

from __future__ import annotations

from pathlib import Path

import pytest


# This conftest's directory -- the xfail hook is scoped to items collected
# from under here so a session-wide ``@slice-NN`` keyword match never poisons
# unrelated suites.
_SUITE_DIR = Path(__file__).parent

# Every slice is author-ahead RED until DELIVER greens it. DELIVER removes a
# tag from this set as its slice greens.
#   - Slice-01 GREENed by DELIVER 2026-05-25.
#   - Slice-02 GREENed by DELIVER M49 2026-05-25 (substrate per M44 Option (a):
#     pure ABC at src/des/ports/language_adapter_plugin.py decoupled from
#     scripts.install.plugins.base; dual-base concrete fixture at
#     scripts/install/plugins/_conformance_fixture_language_adapter.py).
#     M52 ATD amendment (2026-05-25) closed friction #43 by dropping the
#     obsolete AT-1 And-step "ABC is InstallationPlugin subclass" -- the
#     dimension's correct architectural locus is AT-3's dual-issubclass at
#     the concrete fixture entry-point. All 11 ATs now pass organically.
_RED_SCAFFOLD_SLICES: frozenset[str] = frozenset()


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Mark every author-ahead RED-scaffold scenario xfail until GREEN."""
    xfail = pytest.mark.xfail(
        reason="RED scaffold -- DISTILL-authored, awaiting DELIVER implementation",
        strict=False,
        raises=(AssertionError, ModuleNotFoundError, ImportError, FileNotFoundError),
    )
    for item in items:
        if not _belongs_to_this_suite(item):
            continue
        if set(item.keywords) & _RED_SCAFFOLD_SLICES:
            item.add_marker(xfail)


def _belongs_to_this_suite(item: pytest.Item) -> bool:
    """Whether a collected item lives under this conftest's suite directory."""
    item_path = getattr(item, "path", None)
    if item_path is None:
        return False
    return _SUITE_DIR in Path(item_path).parents or Path(item_path) == _SUITE_DIR
