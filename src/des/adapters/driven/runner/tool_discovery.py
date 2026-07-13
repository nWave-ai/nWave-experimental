"""The SHARED ``resolve_tool`` 3-rung discovery scale (feature-delta §V.C).

The genericità primitive every language adapter (TestRunner now; Build / Coverage
/ AST / Mutation later) and every ``LanguageAdapterPlugin.probe()`` inherits: a
tool a language-adapter needs is DISCOVERED, never assumed at a fixed position.

The scale (in order):

* rung 1 -- PATH: ``shutil.which(name)`` -- the tool is on the search PATH.
* rung 2 -- known install location: absent from PATH but present in a
  caller-supplied ``known_locations`` dir (the WSL2 ``~/.cargo/bin`` GOTCHA #1
  rung -- a present toolchain off the hook PATH is USED, never a false
  INDETERMINATE).
* rung 3 -- not found: absent everywhere after the full scale -> a terminal,
  LOUD INDETERMINATE that NAMES the remediation (an operator can act, never a
  silent degrade).

Effect isolation (Principle 12): ``resolve_tool`` is a pure return-only function
-- it INSPECTS the filesystem/PATH and RETURNS a typed ``ToolResolution`` value;
it never spawns, mutates, or raises on the absent-tool path (absence is a
first-class returned result, not an exception).

stdlib only (``shutil``, ``os``, ``pathlib``, ``dataclasses``) -- the genericità
primitive depends on ``des.*`` + the standard library alone (F-D-09).
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class ToolResolution:
    """The outcome of running ``resolve_tool`` over the 3-rung discovery scale.

    Exactly one of the two facets is populated:

    * RESOLVED -- ``path`` is the tool's on-disk path and ``remediation`` is
      ``None``.
    * INDETERMINATE -- ``path`` is ``None`` and ``remediation`` is a non-empty,
      actionable install instruction.

    ``rung`` names which rung produced the outcome (the port-exposed observable).
    """

    rung: str
    path: str | None = None
    remediation: str | None = None


def resolve_tool(
    name: str,
    known_locations: Sequence[str],
    base_dir: Path | str | None = None,
) -> ToolResolution:
    """Discover ``name`` across the 3-rung scale; return a typed resolution.

    Rung 1 (PATH): ``shutil.which(name)`` -- if found, RESOLVED at that path.
    Rung 2 (known install location): for each dir in ``known_locations``, if
    ``<dir>/<name>`` exists and is executable, RESOLVED at that path (the WSL2
    GOTCHA #1 rung). Rung 3 (not found): a LOUD INDETERMINATE naming the
    remediation.

    ``base_dir`` -- when provided, each RELATIVE entry in ``known_locations``
    is resolved against ``base_dir`` instead of the process CWD (an ABSOLUTE
    entry is used as-is; the PATH rung is unaffected). Fixes #203: a
    repo-local tool (e.g. ``<repo>/node_modules/.bin/vitest``) must resolve
    against the TARGET repo, never the caller's CWD. ``base_dir=None`` (the
    default) preserves EXACTLY today's CWD-relative behaviour for every
    existing caller.
    """
    on_path = shutil.which(name)
    if on_path is not None:
        return ToolResolution(rung="on-path", path=on_path)

    for location in known_locations:
        location_path = Path(location)
        if base_dir is not None and not location_path.is_absolute():
            candidate = Path(base_dir) / location_path / name
        else:
            candidate = location_path / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return ToolResolution(rung="known-location", path=str(candidate))

    return ToolResolution(
        rung="not-found",
        remediation=(
            f"{name} not found on PATH or in {list(known_locations)}; "
            f"install it (e.g. via rustup or 'cargo install {name}') and retry"
        ),
    )


__all__ = ["ToolResolution", "resolve_tool"]
