"""Pytest config for the slice-03 M7 AT-completion ledger acceptance slice.

slice-03 of F-DES-ATDD-PURE-HOOK-GATES (U3 -- ADR-030 D3 / M7).

The U3 ledger substrate has landed (`AtCompletionLedger` carries the
flock-serialised append, per-record `seq` + `record_hash`, and the fail-closed
integrity read contract), so every scenario runs as a normal GREEN test. The
RED-scaffold `xfail` collection hook has been removed at GREEN.
"""

from __future__ import annotations
