"""Driven adapters for the FreshnessProbe port.

Two concrete probes:

* :class:`RepoSourceProbe` — reads ``_install_manifest.json`` colocated with
  the installed ``des/`` package and returns the four-state verdict (§1.3).
* :class:`NullProbe` — returns state ``A`` unconditionally; used by tests and
  by the ``NWAVE_FRESHNESS=skip`` opt-out path inside
  :mod:`des.runtime.freshness`.

Reference: docs/feature/fix-des-self-hosted-gate-sync/feature-delta.md §1.5.
"""

from __future__ import annotations

from des.adapters.driven.freshness.null_probe import NullProbe
from des.adapters.driven.freshness.repo_source_probe import RepoSourceProbe


__all__ = ["NullProbe", "RepoSourceProbe"]
