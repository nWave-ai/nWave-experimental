"""pytest-bdd configuration for the discuss-epic-mode slice-05 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-05 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering and
NO ``pytest_bdd_apply_tag`` translation hook -- the scenarios are active-RED. They
RUN and FAIL with a business-logic reason (the linkage/status-flip maintenance
procedure does not exist on the current tip, so ``run_maintenance`` is a documented
NO-OP and every LSC observation reads its absent default), surfacing as
``MAINTENANCE_ABSENT`` / missing LSC pins -- a deliberate missing-functionality RED,
never a collection error.

DELIVER makes these active-RED scenarios GREEN by authoring the maintenance
procedure (linkage + status flips + JIT rule + backlog-cites-epic-by-name, skill /
command text) -- it does NOT unskip anything.
"""

from __future__ import annotations
