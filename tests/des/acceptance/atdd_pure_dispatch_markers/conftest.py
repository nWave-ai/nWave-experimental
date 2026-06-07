"""Pytest config for the hg-slice-00 atdd_pure dispatch marker recognition slice.

hg-slice-00 of F-DES-ATDD-PURE-HOOK-GATES (U0 -- ADR-030 D8).

The U0 marker-recognition surfaces have landed (`DesMarkerParser` carries the
atdd_pure DES-MODE/DES-PHASE/DES-SLICE vocabulary and
`classify_atdd_pure_dispatch` is the real three-way classifier), so every
scenario runs as a normal GREEN test. The RED-scaffold `xfail` collection hook
has been removed at GREEN.
"""

from __future__ import annotations
