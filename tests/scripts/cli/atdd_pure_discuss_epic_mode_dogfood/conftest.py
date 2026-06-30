"""pytest-bdd configuration for the discuss-epic-mode slice-06 dogfood AT set.

atdd_pure (the path): this AT set is authored JIT for slice-06 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering and
NO ``pytest_bdd_apply_tag`` translation hook -- the scenarios are active-RED.

Slice-06 is the DOGFOOD: the first real epic-mode run. Unlike slices 02/04/05 --
which witnessed the epic-delta contract against a suite-local reference oracle
producing into ``tmp_path`` -- the slice-06 deliverable IS the REAL artifact at the
production repository path ``docs/epic/flow-v2-wave-migrations/epic-delta.md``. The
reference oracle CANNOT stand in here: the real artifact is the deliverable,
authored at DELIVER by the Luna PO agent following the epic-mode procedure (the
slice-02 authoring prose + slice-04 escalation + slice-05 maintenance, all
exercised against this single real run).

These ATs therefore OBSERVE the real repository path, read-only -- they never
write it. Active-RED = artifact-absence at the REAL path: on the current tip
``docs/epic/flow-v2-wave-migrations/epic-delta.md`` does not exist, so every
observation reads an absent artifact -> ``EPIC_DELTA_ABSENT`` / missing structural
pins -> semantic ``AssertionError``. A deliberate missing-functionality RED, never
a collection error.

DELIVER (slice-06) makes these active-RED scenarios GREEN by running the epic-mode
authoring procedure to produce the conformant epic-delta at its production path --
it does NOT unskip anything.
"""

from __future__ import annotations
