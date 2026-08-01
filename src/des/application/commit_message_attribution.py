"""Application seam: resolve the attribution decision, apply the trailer.

The SINGLE call site both `des commit` (`commit.py`) and `des commit-slice`
(`commit_slice.py`) invoke -- GDP-4, the PRODUCING TOOL attributes itself,
never a command-line rewrite or a git hook (fix-attribution-trailer-never-
applied). One implementation, two call sites.

"Due" = the repo is nWave-active (ADR-AG-002 `resolve_activation` over the
per-project marker + the global activation mode) AND the attribution
preference is enabled (ADR-CA-007: attribution is a property of an ACTIVE
nWave repo, not of the developer's machine). Any failure anywhere in that
resolution -- unreadable/corrupt config, permission error, anything --
degrades to "not enabled": a missed trailer is recoverable, a refused commit
is not (property 3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.config.des_config import DESConfig
from des.domain.activation_policy import resolve_activation
from des.domain.commit_attribution.attribution_trailer import (
    apply_attribution_trailer,
)


if TYPE_CHECKING:
    from pathlib import Path


def attribute_commit_message(
    repo: Path, message: str, *, global_config_path: Path | None = None
) -> str:
    """Return *message*, with the nWave attribution trailer appended when due.

    Never raises: the whole activation/config resolution is wrapped so no
    exception can escape and block the commit it is meant to merely credit.

    Args:
        repo: the repository whose ``.nwave/local-config.json`` marker (walk-up
            resolved) is read for the activation decision.
        message: the fully-assembled commit message BEFORE this call.
        global_config_path: optional override for ``~/.nwave/global-config.json``
            (test hermeticity only -- production callers omit it and get the
            real per-machine global config via ``DESConfig``'s own default).
    """
    try:
        config = (
            DESConfig(cwd=repo, global_config_path=global_config_path)
            if global_config_path is not None
            else DESConfig(cwd=repo)
        )
        active = resolve_activation(config.enabled_for_repo, config.activation_mode)
        enabled = bool(active and config.attribution_enabled)
    except Exception:
        enabled = False
    return apply_attribution_trailer(message, enabled=enabled)
