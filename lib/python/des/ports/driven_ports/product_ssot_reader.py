"""Product-SSOT presence driven port (slice-07, nwave-flow-v2-enforcement).

A read-only capability port (principle 12: a bounded read behind a port, never a
god-object reaching ``os`` / ``Path.home()``). The DISCUSS gate-IN precondition
per flow-design §8 is the presence of the product migration-gate (docs/product/)
plus the four required SSOT docs.

Asymmetric authority (§22.0): the gate VETOES; it never writes product SSOT, so
this port exposes ONLY a read.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class SsotPresence:
    """The gate-IN read result VO (driven-port output).

    ``indeterminate`` is the degrade-LOUD floor: the read MECHANISM could not run
    (e.g. the project root is itself unreadable). It is NEVER fabricated to mask a
    read failure as "all present".
    """

    product_dir_present: bool  # docs/product/ exists (the migration-gate)
    vision: bool
    backlog: bool
    glossary: bool
    jobs: bool
    indeterminate: bool = False

    def missing_docs(self) -> tuple[str, ...]:
        """The required SSOT docs that are absent (empty tuple iff all present)."""
        absent: list[str] = []
        if not self.vision:
            absent.append("vision.md")
        if not self.backlog:
            absent.append("backlog.md")
        if not self.glossary:
            absent.append("glossary.md")
        if not self.jobs:
            absent.append("jobs.yaml")
        return tuple(absent)


class ProductSsotReader(ABC):
    """Driven, read-only port over the product-SSOT precondition state."""

    @abstractmethod
    def ssot_present(self, project_root: Path) -> SsotPresence:
        """Return the product-SSOT presence under ``project_root``.

        Absent docs -> the corresponding ``SsotPresence`` flags are ``False``
        (NOT raise -- absence is a normal unmet-precondition state). A root whose
        read MECHANISM fails -> ``SsotPresence(indeterminate=True, ...)``,
        degrade-LOUD, NEVER a fabricated all-present masking the failure.
        """
        ...
