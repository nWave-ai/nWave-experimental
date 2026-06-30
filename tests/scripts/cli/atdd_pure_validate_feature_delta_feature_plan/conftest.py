"""pytest-bdd configuration for the discuss-epic-mode slice-01 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-01 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering
and NO ``pytest_bdd_apply_tag`` translation hook here -- the scenarios are
active-RED. They RUN and FAIL with a business-logic reason (the
``--require-feature-plan`` flag is unknown on the current tip, so the production
CLI prints usage + returns exit 1 and emits no ``verdict`` token), surfacing as
``UNRECOGNISED_INVOCATION`` -- a deliberate missing-functionality RED, never a
collection error.

DELIVER makes these active-RED scenarios GREEN by extending the production
``validate_feature_delta.py`` CLI with ``--require-feature-plan`` -- it does NOT
unskip anything.
"""

from __future__ import annotations
