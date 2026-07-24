"""Typed domain vocabulary for the data-tree-completeness acceptance test.

SSOT-via-Types-Services-DSL mandate (criterion 1, canonical:
``nw-test-design-mandates``): the one domain noun the Gherkin of
``data-tree-completeness.feature`` names explicitly is expressed here once.
"""

from __future__ import annotations

from typing import NewType


DataEntryName = NewType("DataEntryName", str)

#: The declared data entry the "dropped in transit" scenario simulates losing.
#: It is a directory (not a single file) — the entry the orchestrator-
#: affordance standing-loop hook reads, and the one the RCA named explicitly.
ORCHESTRATOR_AFFORDANCE_ENTRY = DataEntryName("orchestrator-affordance")
