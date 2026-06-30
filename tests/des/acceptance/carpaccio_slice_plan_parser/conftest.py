"""pytest-bdd configuration for the C10 carpaccio slice-plan parser slice.

slice-01 of fix-carpaccio-slice-plan-parser-unify (atdd_pure). The scenarios are
ACTIVE-RED at HEAD (AC-1/2/3 run and raise AssertionError because the two real
parsers diverge / miscount / report section-missing); AC-4 is a live-green
preservation guard. No xfail / skip markers -- per ADR-GV-001 D6 the current
slice's scenarios run and fail for the right reason until C10 lands.
"""

from __future__ import annotations
