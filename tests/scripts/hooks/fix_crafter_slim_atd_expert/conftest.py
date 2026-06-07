"""pytest-bdd configuration for the fix-crafter-slim-atd-expert AT set.

ATDD-pure carpaccio: 4 slices, 12 ATs total. Only slice-01 (the walking
skeleton — agent-prose layer + classic-template loophole closure) lives in
this collected ``tests/`` tree. Slices 02-04 are PARKED under
``docs/feature/fix-crafter-slim-atd-expert/distill/pending-slices/`` per the
F-CARPACCIO-FUTURE-SLICE-SCAFFOLD-BLOCKS-COMMIT workaround and moved back per
slice when the DELIVER loop reaches them.

SUT (slice-01 walking skeleton): the prose layer of three asset files —
``nWave/agents/nw-software-crafter.md`` (loophole at L48/L106 to be
removed), ``nWave/agents/nw-functional-software-crafter.md`` (already
clean — regression guard), and ``nWave/skills/nw-execute/SKILL.md`` (the
classic-template loophole at L119 to be replaced by the escalation
contract). Slice-01 ATs are *grep contracts*: they assert the absence of
the loophole text and the presence of the escalation-contract text on the
files-as-shipped. No subprocess, no hook execution — those land at
slice-03.

Layer 3 (filesystem / grep over project assets). Example-only per Mandate
9/11 — sad paths enumerated explicitly (the loophole text is the sad
input; the escalation contract is the happy output). No PBT machinery.
"""

from __future__ import annotations
