"""Typed domain vocabulary for the SubagentStop fenced-marker acceptance suite.

Mandate-12 (SSOT-via-types): the domain nouns the Gherlin speaks — *where a DES
marker sits in an agent's read-only return* (inside a fence, inside an inline-code
span, outside any fence, or absent) — are expressed ONCE here as a typed enum, and
the observable outcome (was a DES dispatch context resolved?) as a small frozen
value. The composition consumes these typed values; no raw ``str`` flows where a
domain enum exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class MarkerPlacement(Enum):
    """Where a DES marker text sits inside an agent's read-only return content.

    The fix strips fenced / inline-code spans before marker resolution, so the
    placement is the discriminant between "documentation" (FENCED_BLOCK /
    INLINE_CODE — must be IGNORED) and "directive" (UNFENCED — must still
    resolve).
    """

    #: A complete DES marker set wrapped in a triple-backtick ``` fenced block —
    #: a read-only return DOCUMENTING the marker syntax. Must be ignored.
    FENCED_BLOCK = "fenced_block"
    #: A DES marker wrapped in an inline `backtick` span — documentation. Ignored.
    INLINE_CODE = "inline_code"
    #: A real DES marker OUTSIDE any fence — a genuine dispatch directive. Resolved.
    UNFENCED = "unfenced"
    #: No DES marker anywhere in the return content. No context.
    ABSENT = "absent"


@dataclass(frozen=True)
class ResolvedContext:
    """The observable outcome of SubagentStop DES-context resolution.

    Universe = the port-exposed observable: whether the resolver treated the
    return as carrying a DES dispatch directive (``has_des_context``) and, when
    it did, the resolved ``project_id``. These are exactly the keys the real
    resolver's returned ``dict | None`` exposes — no internal struct fields.
    """

    has_des_context: bool
    project_id: str | None
