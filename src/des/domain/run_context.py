"""Run context -- the DECLARED provenance of an audit event.

The audit log mixes events born in different contexts: a test run, a real
gate firing, an interactive session, CI. Without a provenance field every
downstream count sums real events together with events manufactured by the
tests that verify the very thing being counted, and the result looks like a
number. Measured anchor: `HEALTH_GATE_INSTALL_FRESHNESS_STALE` fired 14,378
times over 8 days in this repo -- per-subprocess emissions, not real events
(see `des/runtime/freshness.py`). That distinction is not recoverable after
the fact, so the field must be written at birth.

Two rules make the field trustworthy:

1. **Declared, never inferred.** The context comes from the
   `NWAVE_RUN_CONTEXT` environment variable and from nothing else. Sniffing
   `PYTEST_CURRENT_TEST` or `CI` would re-introduce exactly the ambiguity the
   field exists to remove -- a gate exercised by a test that itself runs in
   CI has no single inferable answer.
2. **Undeclared is a value, not a silence.** An absent declaration resolves
   to the explicit ``unknown`` state, which the writer always serializes.
   Omitting the field instead would reproduce the same hole one level down:
   a reader could not tell "no context declared" from "written before this
   field existed".
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Mapping


__all__ = ["RUN_CONTEXT_ENV", "UNKNOWN_RUN_CONTEXT", "resolve_run_context"]


RUN_CONTEXT_ENV = "NWAVE_RUN_CONTEXT"
"""The single environment key a caller declares its run context through."""

UNKNOWN_RUN_CONTEXT = "unknown"
"""Explicit third state for an undeclared context. Never an absent field."""


def resolve_run_context(env: Mapping[str, str]) -> str:
    """Resolve the declared run context, or the explicit unknown state.

    Args:
        env: The environment mapping to read the declaration from. Injected
            rather than read from `os.environ` so the resolution is a pure
            function of its input and testable without process-global state.

    Returns:
        The declared context stripped of surrounding whitespace, or
        `UNKNOWN_RUN_CONTEXT` when the declaration is absent or blank.
    """
    declared = env.get(RUN_CONTEXT_ENV, "").strip()
    return declared or UNKNOWN_RUN_CONTEXT
