"""One loud refusal, shared by every feature-delta startup probe (D-6a).

When an adapter cannot read a runtime resource it owns, the tool has not found a
problem with the maintainer's document — it has found a problem with ITSELF, and
it must say so unmistakably:

  WHAT  the structured, machine-readable ``health.startup.refused`` event, naming
        the adapter that refused and the resource it could not read;
  WHY   the underlying error, in plain words;
  HOW   the cure the maintainer can actually act on — reinstall the tool.

Then exit 70 ("could not check"). Never a bare ``assert`` — an ``AssertionError``
escaping as a raw traceback is output the maintainer cannot act on, and is what
the shipped product does today. Above all, never a silent pass: "validated, no
violations" and "never validated anything" must be impossible to confuse from
the outside (GDP-3 self-explaining, GDP-6 degrade-loud-never-silent-wrong).
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, NoReturn


if TYPE_CHECKING:
    from pathlib import Path


EXIT_STARTUP_REFUSED = 70

_CURE = (
    "cure=the installation is damaged or incomplete — reinstall the tool "
    "(e.g. `pip install --force-reinstall nwave-ai`)"
)


def refuse_startup(adapter: str, path: Path | str, error: object) -> NoReturn:
    """Emit ``health.startup.refused`` naming adapter, resource, error, cure; exit 70."""
    print(
        f"health.startup.refused adapter={adapter} path={path} error={error} {_CURE}",
        file=sys.stderr,
    )
    sys.exit(EXIT_STARTUP_REFUSED)
