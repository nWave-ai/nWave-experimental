"""pytest-bdd configuration for the f-coherence-and-attestation slice-01 suite.

DISTILL-authored active-RED scaffold (ADR-025 + ADR-028, atdd_pure per-slice JIT):
every scenario in this slice-01 ``.feature`` file is authored ahead of the
implementation and RUNS (it is NOT @skip'd -- ADR-GV-001 D6). Each scenario fails
RED for the RIGHT reason because the net-new production seams the slice-01
Code-Design pins are ABSENT at HEAD:

  * ``src/des/ports/code_fact_port.py``            (CodeFactPort / CodeFactResult /
                                                    CapabilityDescriptor / the 5
                                                    locked capability-id constants)
  * ``src/des/adapters/driven/codefact/text_search_code_fact_adapter.py``
                                                   (TextSearchAdapter, the
                                                    universal ``noisy`` floor)
  * the ONE slice-01 code-fact gate that re-derives ``query.never-wired`` through
    the port (composition-root driving surface -- see ASSUMPTION below)
  * ``tests/build/fixtures/locked-vocabulary.json`` + the byte-lock guard module
    (the Published-Language conformance guard, ADR-CA-001 D2)

DRIVING SURFACES (Mandate-13 driving-port-only):
  * AT-1 / AT-2 / AT-3 -> Layer 3 composition: the REAL ``CodeFactPort`` /
    ``TextSearchAdapter`` / slice-01 gate via the production composition root; the
    observable is the ``CodeFactResult`` envelope (``{provider, confidence,
    payload}``, ADR-LA-001 D9 slice (c): ``reason_code`` moved into the
    capability-owned payload schema) / the gate verdict + its provenance tag.
  * AT-4 -> the REAL byte-lock guard mechanism: it asserts the OSS-serialized
    locked-vocabulary token set is byte-identical to the committed
    ``locked-vocabulary.json`` fixture, AND is SELF-PROBED (a planted-drift variant
    makes the guard RED).

The step modules import only test-local types at module top; every production
seam is reached through a LAZY import inside the composition's driving-port
invocation, so an absent seam degrades to a captured "seam absent" sentinel that
the ``Then`` turns into a NAMED semantic ``AssertionError`` (never a collection /
import / setup error). The suite therefore COLLECTS cleanly at HEAD and each
scenario RED-fails for the right reason (pre-DELIVER fail-for-right-reason gate).

ASSUMPTION flagged to DELIVER (DESIGN-contract ambiguity, slice-01 gate_id): the
slice-01 Code-Design does NOT pin a concrete ``des <gate-id>`` subcommand for the
ONE code-fact gate (AT-3); ``gate_g.py`` is the slice-03 gate. Per Mandate-13 the
slice-01 gate is therefore driven at the **composition root** (a real gate
callable over the real ``CodeFactPort`` substrate), NOT a subprocess ``des``
dispatch (the dispatcher ``_REGISTRY`` has no slice-01 gate row at HEAD, which
would be a collection-stage failure, not a semantic RED). The composition reads
the gate's expected import path from the DESIGN Reuse table
(``src/des/adapters/driven/codefact/``) but degrades-LOUD if DELIVER lands the
gate elsewhere -- DELIVER MUST wire AT-3 to whatever real slice-01 code-fact gate
callable it ships.
"""

from __future__ import annotations
