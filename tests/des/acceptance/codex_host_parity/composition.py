"""Protocol driver for the slice-00 public parity journey.

This is deliberately the only production import allowed to the slice-00 AT
set: the public re-export of the production composition root. Scenarios pass
public-shaped values and external doubles at that boundary, then invoke
``CodexParityJourneyPort.run``. They do not import domain values, application
helpers, driven ports, or build a second runner in test code.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class CodexParityJourneyComposition:
    """Drive the sole production composition root through its public surface."""

    def run(
        self,
        request: Mapping[str, object],
        *,
        external_ports: Mapping[str, object],
    ) -> Any:
        try:
            # `des.CodexParityComposition` is the public re-export of the one
            # declared production root. Every other dependency is supplied by
            # that root, never imported by an AT.
            from des import CodexParityComposition
        except ImportError:
            raise AssertionError(
                "__SCAFFOLD__: CodexParityComposition and its "
                "CodexParityJourneyPort are not implemented"
            ) from None

        try:
            composition = CodexParityComposition.compose(**external_ports)
        except TypeError as error:
            if "unexpected keyword argument" not in str(error):
                raise
            raise AssertionError(
                "__SCAFFOLD__: CodexParityComposition.compose does not yet "
                "implement the frozen five-port keyword contract"
            ) from None
        journey = composition.journey_port()
        return journey.run(request)

    def compose_only(self, *, external_ports: Mapping[str, object]) -> Any:
        """Expose the public factory so production owns five-port closure."""
        from des import CodexParityComposition

        return CodexParityComposition.compose(**external_ports)


def field(value: Any, name: str) -> Any:
    """Read a public result field without coupling scenarios to its class."""
    if isinstance(value, Mapping):
        return value[name]
    return getattr(value, name)


def diagnostic_field(result: Any, name: str) -> str:
    """Assert against the public WHAT/WHY/HOW diagnostic, never an exception."""
    diagnostic = field(result, "diagnostic")
    return str(field(diagnostic, name))
