"""pytest-bdd configuration for the discuss-epic-mode slice-07 acceptance set.

atdd_pure (the path): this AT set is authored JIT for slice-07 ahead of its
implementation. Per ADR-GV-001 D6 there is NO ``@skip`` / ``@xfail`` markering and
NO ``pytest_bdd_apply_tag`` translation hook -- the scenarios are active-RED. They
RUN and FAIL with a business-logic reason (the caveman reasoning mandate does not
exist in any discuss surface on the current tip, so the audit reads ABSENT),
surfacing as a semantic ``AssertionError`` -- a deliberate missing-functionality
RED, never a collection error.

Honest RED/WITNESS split: AT-1 (mandate presence) is the genuine active-RED.
AT-2 (caveman-native style) and AT-3 (zero-retroactive-compression) are WITNESSES --
the slice-02/04/05/06 epic-mode text was authored caveman-native by instruction and
the pre-existing content already exists, so they pass on the current tip. DELIVER
makes AT-1 GREEN by authoring the caveman reasoning mandate into the discuss skill +
the nw-product-owner agent surface; it does NOT unskip anything.
"""

from __future__ import annotations
