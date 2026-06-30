"""pytest-bdd configuration for the discuss-epic-mode slice-04 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-04 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering and
NO ``pytest_bdd_apply_tag`` translation hook -- the scenarios are active-RED. They
RUN and FAIL with a business-logic reason (the Phase 1.5 escalation contract does
not exist on the current tip, so the oversized-detection produces no escalation
outcome and every ESC observation reads its absent default), surfacing as
``ESCALATION_ABSENT`` / missing ESC pins -- a deliberate missing-functionality RED,
never a collection error.

DELIVER makes these active-RED scenarios GREEN by authoring the Phase 1.5
escalation contract (skill / command text) -- it does NOT unskip anything.
"""

from __future__ import annotations
