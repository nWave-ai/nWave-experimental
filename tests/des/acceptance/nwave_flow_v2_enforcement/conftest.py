"""pytest-bdd configuration for the nwave-flow-v2-enforcement slice-04 suite.

DISTILL-authored active-RED scaffold (ADR-025 + ADR-028): every scenario in the
slice-04 ``.feature`` files is authored ahead of the implementation and RUNS
(it is NOT @skip'd -- atdd_pure per-slice JIT, ADR-GV-001 D6). Each scenario
fails RED for the RIGHT reason because the net-new production seams are RED
scaffolds (``src/des/domain/wave_active.py``,
``src/des/ports/driven_ports/wave_active_store.py``,
``src/des/ports/driver_ports/wave_active_anchor_port.py``,
``src/des/adapters/drivers/hooks/user_prompt_submit_handler.py``).

DRIVING PORTS (Mandate-13 driving-port-only):
  * walking skeleton -> Layer 4 wiring_e2e: the REAL prompt-submission hook
    invoked as a subprocess; the wave-active floor file is the observable effect.
  * read + scope -> Layer 3 composition: the REAL PreToolUseService.validate via
    the production composition root, with a real WaveActiveReader over a tmp_path
    floor.

No production module is imported-and-called at the step boundary; the step
modules import only test-local types. The suite therefore COLLECTS cleanly and
each scenario RED-fails with a semantic ``AssertionError`` (pre-DELIVER
fail-for-right-reason gate), never a collection / import / setup error.
"""

from __future__ import annotations
