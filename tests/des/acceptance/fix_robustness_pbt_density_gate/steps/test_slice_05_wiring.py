"""pytest-bdd binding for slice-05-wiring.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): this
module only registers the slice's scenarios and re-exports the shared step
vocabulary from ``common_steps``. No step definitions or business logic
live here.

WIRING SLICE (last by design -- feature-delta § 6 line 410). The conftest's
``_RED_SCAFFOLD_SLICES`` set lists ``slice-05`` so every scenario in this
binding is collected as ``xfail(strict=False)`` until DELIVER ships the
production wiring substrate (the ``at_review_verdict`` consumer path, the
``SubagentStop`` hook intercept, and the catalog ``quality_gates:`` entry).

B4 INVARIANT (feature-delta § 6 lines 443-449): slice-05 AT2 MUST exercise
the real ``SubagentStop`` hook chain end-to-end against a real sub-agent
dispatch -- NEVER a mocked dispatch. This is the symmetric inverse of
slice-04 M2 (slice-04 ATs MUST NOT touch live mutmut; slice-05 AT2 MUST NOT
mock the hook chain). DELIVER's GREEN implementation MUST keep AT2 driven
by the real Claude Code ``SubagentStop`` JSON delivery path -- the unit-test
shortcut of feeding a hand-crafted hook payload into the handler function
violates Mandate-13 (driving-port-only boundary).

B1 INVARIANT (feature-delta § 6 lines 451-462): slice-05 AT3 MUST stage a
throwaway feature whose ``component-manifest.yaml`` is emitted by the REAL
M slice-04 ``nw-design`` manifest producer -- NEVER a hand-authored fixture.
The throwaway feature substrate proves the producer-to-gate seam against
genuine producer output, converting the M slice-04 cross-feature edge from
a calendar dependency into a demonstrated seam.

CRAFT-BLOCKING EDGE (feature-delta § 9 N1): slice-05's AT3 cannot reach
GREEN until M slice-04 (the manifest producer) ships. A crafter who reaches
slice-05 before M slice-04 ships WILL stall on AT3 -- this is the canonical
slice-05 craft-blocking edge per the feature-delta build-order map.

MANDATE-13 INVARIANT (driving-port-only boundary): every AT in this slice
MUST drive the SUT through a composition-root driving port at Layer 3
subprocess (AT1, AT3 -- ``python -m scripts.cli.at_review_verdict`` /
``python -m scripts.cli.check_robustness_density``) OR Layer 4 wiring_e2e
hook chain (AT2 -- real Claude Code ``SubagentStop`` JSON delivery). NO
direct production imports of ``des.application.*`` services in step
composition; NO function-boundary invocation of pure helpers in the
production CLI modules. The DELIVER crafter MUST keep all three ATs driven
through the production composition root.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *  # noqa: F403 -- shared step vocabulary


scenarios("../slice-05-wiring.feature")
