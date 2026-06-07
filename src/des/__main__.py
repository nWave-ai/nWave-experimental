"""Package-level `python -m des` entry point.

Delegates to `des.cli.__main__:main` so `python -m des <subcommand>` is an
alternative invocation surface to the `des` console-script (defined in
pyproject.toml `[project.scripts]`). Required by slice-03 D1 readiness gate
ATs which spawn subprocesses via `python -m des verify-readiness-pre-dispatch`
(per Mandate-13 driving-port subprocess invocation; conftest authored by
DISTILL M83 for the slice).
"""

from __future__ import annotations

import sys

from des.cli.__main__ import main


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
