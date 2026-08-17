"""Shared single-line JSON stdout EMIT primitive for the DES CLI surface.

One shape -- "print exactly one single-line JSON object to stdout" -- was
independently defined as ``def _emit(payload): print(json.dumps(payload))``
in 14 separate ``des.cli`` modules (D03, mikado 2026-07-28). All 14 bodies
were byte-identical; none carried ``sort_keys`` or a second stream. This
module is the ONE place that shape now lives.

This module is the shared primitive for current CLI consumers; retired
per-slice review, attest and gate implementations are not part of its
contract. Bespoke emitters with a different observable output contract remain
separate rather than changing JSON ordering or stream behavior implicitly.
"""

from __future__ import annotations

import json


def emit_json_line(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object to stdout."""
    print(json.dumps(payload))
