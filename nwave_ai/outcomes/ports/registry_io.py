"""Driven ports — RegistryReader / RegistryWriter Protocols.

Adapters implement these. Application services depend on them, never on
concrete adapters (hexagonal Dependency Inversion).
"""

from __future__ import annotations

from typing import Protocol

from nwave_ai.outcomes.domain.outcome import Outcome  # noqa: TC001  # runtime Protocol


class RegistryReader(Protocol):
    """Driven port — read all outcomes from the registry."""

    def read_outcomes(self) -> tuple[Outcome, ...]:
        """Return an immutable snapshot of all registered outcomes."""
        ...


class RegistryWriter(Protocol):
    """Driven port — append a new outcome to the registry."""

    def append_outcome(self, outcome: Outcome) -> None:
        """Persist a new outcome. Caller guarantees id uniqueness."""
        ...
