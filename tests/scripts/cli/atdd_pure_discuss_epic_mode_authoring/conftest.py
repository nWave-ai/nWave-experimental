"""pytest-bdd configuration for the discuss-epic-mode slice-02 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-02 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering and
NO ``pytest_bdd_apply_tag`` translation hook -- the scenarios are active-RED. They
RUN and FAIL with a business-logic reason (the ``--epic`` authoring procedure does
not exist on the current tip, so the production-path epic-delta is never produced
and every EDC observation reads an absent artifact), surfacing as
``EPIC_DELTA_ABSENT`` / missing structural pins -- a deliberate
missing-functionality RED, never a collection error.

DELIVER makes these active-RED scenarios GREEN by authoring the ``--epic``
procedure (skill / command text) AND producing a conformant epic-delta at the
production path -- it does NOT unskip anything.
"""

from __future__ import annotations
