"""The four public outcomes of a DES step, and of a whole Request.

ADR-SSOT-002 Section 4b: «Each takes minimal typed input and returns one closed
outcome -- `Success | Refusal | Retry | Indeterminate`.»  They are «now the
outcome of each STEP as well as of the Request, with the same meanings and the
same prohibition on retrying an uncertain effect».

WHY IT LIVES IN THE DOMAIN AND NOT BESIDE THE RUNNER.  ADR-DES-003 §4 asks for
ONE carrier for this four-valued answer, after finding three spellings of it and
seven sites re-deriving it by string comparison. Making `StepRefusal` carry the
enum put every CLI step in the position of importing it, and the enum's only
home was the application module that also owns the composed run -- so a step
reaching for a value type had to bind the composer, and the guard that forbids a
second composer could not tell the two apart.

The enum is a value, not a boundary: nothing about it belongs to whoever
composes. Moving it here lets the guard stay exact and the carrier stay one.
"""

from __future__ import annotations

from enum import Enum


class Disposition(str, Enum):
    """The complete public result vocabulary."""

    Success = "Success"
    Refusal = "Refusal"
    Retry = "Retry"
    Indeterminate = "Indeterminate"
