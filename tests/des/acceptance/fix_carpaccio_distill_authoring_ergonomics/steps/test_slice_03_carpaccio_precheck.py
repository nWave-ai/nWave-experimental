"""slice-03: a DISTILL author pre-checks a feature's format before recording.

ADR-001 (shared predicates) + Principle 12 (read/write driving-port split).
Layer 3 (subprocess / FS acceptance) -- the real `python -m des.cli.carpaccio_precheck`
CLI is the driving port (Mandate-13), invoked MODULE-DIRECT. The pre-check is a
non-gate designer tool; it is NOT a `des` dispatcher subcommand because the
dispatcher registry is parity-pinned to the 19-row gate catalog
(tests/build/d4_phase_1_catalog_files) -- a non-gate tool cannot be added without
a gate-vs-tool registry distinction, deferred to
F-DES-AT-REVIEW-VERDICT-SUBCOMMAND-SURFACE.

RED on master: the `des.cli.carpaccio_precheck` module does not exist, so the
module-direct subprocess fails (ModuleNotFoundError, no diagnostic output). Each
AT reds because the expected diagnostic content is absent from the CLI output --
a semantic AssertionError, not a collection/import error of this test module
(its own imports resolve cleanly on master).
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .steps_shared import *  # noqa: F403 -- shared step registry (S1 SSOT)


scenarios("../slice-03-carpaccio-precheck.feature")
