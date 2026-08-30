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


def attribution_is_due(repo: Path, *, global_config_path: Path | None = None) -> bool:
    """Is the nWave attribution trailer due for *repo*? The ONE decision.

    "Due" = the repo is nWave-ACTIVE (ADR-AG-002 ``resolve_activation`` over the
    tri-state per-repo declaration + the global activation mode) AND the
    attribution preference is enabled (ADR-CA-007). The trailer is an action on
    the USER's commit, so ADR-AG-005 (opt-in ratified) applies: nWave does not
    act in a repository the user has not activated.

    Extracted so the PreToolUse mutation branch
    (``pre_tool_use_handler.emit_commit_attribution_mutation``) and the
    producing-tool path (:func:`attribute_commit_message`) share ONE condition
    instead of writing it twice -- the asymmetry
    ``F-ATTRIBUTION-GATING-ASYMMETRY-PRETOOLUSE`` closed here was precisely two
    call sites deciding the same thing under different conditions.

    Never raises: any failure in the whole resolution (unreadable/corrupt
    config, permission error, anything) degrades to "not due". A missed trailer
    is recoverable; a refused or blocked commit is not.

    Args:
        repo: the repository whose activation declaration (walk-up resolved) and
            attribution preference are read.
        global_config_path: optional override for ``~/.nwave/global-config.json``.
            Production callers either omit it (``DESConfig``'s own default) or,
            where ``$HOME`` must be resolved at CALL time rather than at class-
            definition time, pass the computed path explicitly.
    """
    try:
        config = (
            DESConfig(cwd=repo, global_config_path=global_config_path)
            if global_config_path is not None
            else DESConfig(cwd=repo)
        )
        active = resolve_activation(config.enabled_for_repo, config.activation_mode)
        return bool(active and config.attribution_enabled)
    except Exception:
        return False


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
    enabled = attribution_is_due(repo, global_config_path=global_config_path)
    return apply_attribution_trailer(message, enabled=enabled)
