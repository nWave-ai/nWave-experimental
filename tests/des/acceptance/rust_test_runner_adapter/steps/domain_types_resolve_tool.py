"""Typed domain vocabulary for f-rust-test-runner-adapter slice-01 ATs.

Mandate-12 (SSOT + Zero Duplication via Types): every domain noun the Gherkin
names is expressed once here as a typed enum / frozen value, so the composition
methods consume typed parameters (no raw ``str`` where an enum exists). These
types are TEST-LOCAL -- they never import production code; the ATs drive the SUT
(``resolve_tool``) only through the composition-root driving port (Mandate-13,
Layer 3 subprocess: a child interpreter imports ``resolve_tool`` and runs it over
a REAL controlled filesystem + PATH/HOME env).

slice-01 surface (feature-delta §V.C / Acceptance AT-1..3): the SHARED
``resolve_tool(name, known_locations)`` 3-rung discovery scale -- the genericità
primitive every language adapter + ``probe()`` inherits. The observables are the
RUNG that resolved a tool (PATH / known-install-location / not-found) and, on the
terminal rung, the ACTIONABLE remediation string the INDETERMINATE result names.
"""

from __future__ import annotations

from enum import Enum


class DiscoveryRung(Enum):
    """Which rung of the 3-rung ``resolve_tool`` scale produced the outcome.

    The port-exposed observable the AT asserts ON (the discovery OUTCOME), never
    a line number or an internal field. The three rungs are the §V.C contract:

    - ``ON_PATH``        -- rung 1: ``shutil.which(name)`` found the tool on PATH.
    - ``KNOWN_LOCATION`` -- rung 2: absent from PATH, found in a caller-supplied
                            known install location (the WSL2 ``~/.cargo/bin``
                            GOTCHA #1 rung -- a present tool resolved HERE is USED,
                            never a false INDETERMINATE).
    - ``NOT_FOUND``      -- rung 3: absent everywhere after the full scale -> a
                            terminal INDETERMINATE that NAMES the remediation.
    """

    ON_PATH = "on-path"
    KNOWN_LOCATION = "known-location"
    NOT_FOUND = "not-found"
