"""Typed domain vocabulary for the slice-02 contract-SSOT + drift-guard ATs.

Mandate-12 (SSOT + Zero Duplication via Types): the slice-02 Gherkin nouns
(the canonical-contract artefact + the four command templates that must agree
with it) expressed once here. Test-local (Mandate-13).
"""

from __future__ import annotations

from enum import Enum


class CommandTemplate(Enum):
    """The four command templates that ship a DES-WAVE-only entering dispatch.

    Each must (a) emit the literal ``<!-- DES-WAVE: <wave> -->`` for its wave and
    (b) carry NO instruction requiring classic `_DES_MARKER_KEY` markers on the
    ENTERING dispatch -- agreement with the entry-marker Contract SSOT. The enum
    value is the template's wave name (= the basename under nWave/tasks/nw/ and
    the DES-WAVE marker's wave literal).
    """

    DISCUSS = "discuss"
    DESIGN = "design"
    DEVOPS = "devops"
    DISTILL = "distill"
