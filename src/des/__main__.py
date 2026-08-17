"""Package-level `python -m des` entry point.

Delegates to `des.cli.__main__:main` so `python -m des <subcommand>` and the
`des` console script expose the same public CLI.
"""

from __future__ import annotations

import sys

from des.cli.__main__ import main


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
