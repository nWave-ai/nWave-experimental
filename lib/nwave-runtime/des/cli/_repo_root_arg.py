"""Shared repo-root ARGUMENT primitive for the DES CLI surface.

One concept -- "the target repository root" -- was spelled FIVE different ways
across 46 registered ``des`` subcommands, each declaring its own
``add_argument(...)``:

===================  ==============================================
``--repo``           23 subcommands
``--repo-root``      14
``--project-root``    4
``--root``            3
``--repo-dir``        1 (``des commit``)
===================  ==============================================

The cost fell on the operator, who had to re-learn per command which of the
five names that command happens to want; a wrong guess is a rejected
invocation and a wasted round trip.

``add_repo_root_argument`` declares ALL FIVE names on ONE ``add_argument``
call, so every subcommand accepts the root under every spelling.

WHY THIS IS COMPATIBLE, not a rename. ``argparse`` derives ``dest`` from the
FIRST long option string, so passing a subcommand's CURRENT canonical name as
``canonical`` leaves ``args.repo`` / ``args.repo_root`` / ``args.project_root``
/ ``args.root`` exactly as it was: no reader changes, no caller breaks, purely
additive. Existing scripts, hooks, and dispatch prompts keep working verbatim.

WHAT THIS DOES **NOT** FIX. Unifying the NAME is not unifying the RESOLUTION.
Four resolution behaviours remain live behind these flags -- the
``resolve_repo_root`` SSOT (flag -> ``NWAVE_REPO_ROOT`` -> cwd), a bare
``default="."`` that ignores the env var, ``required=True`` with no default,
and ``default=Path.cwd()`` evaluated at parser-build time -- plus three
hand-rolled reimplementations of the SSOT. That divergence is a separate
defect; do not read this module as having closed it.

``--project-dir`` is DELIBERATELY NOT an alias. The same spelling formerly
named a feature directory for retired execution-log commands, but it names the
repo root on ``des resolve-workflow-mode``. One name, two concepts -- aliasing
it would conflate them.

Two ``scripts/release/`` modules are likewise out of scope: there ``--repo``
is a GitHub ``owner/repo`` SLUG, not a filesystem path
(``cleanup_tags.py`` proves the distinction is deliberate by carrying
``--repo`` and ``--repo-path`` in the same parser). Never alias those.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    import argparse


#: Every spelling of "the target repository root" on the ``des`` CLI surface.
#: Order is irrelevant here -- the ORDER PASSED to ``add_argument`` decides
#: ``dest``, and that is driven by each call site's ``canonical``.
REPO_ROOT_FLAG_ALIASES: tuple[str, ...] = (
    "--repo",
    "--repo-root",
    "--repo-dir",
    "--project-root",
    "--root",
)


def add_repo_root_argument(
    parser: argparse.ArgumentParser | argparse._ArgumentGroup,
    canonical: str,
    **kwargs: Any,
) -> argparse.Action:
    """Declare the repo-root argument under ALL its names on ``parser``.

    ``canonical`` MUST be the flag this parser already used, so that the
    ``dest`` argparse derives from it -- and therefore every ``args.<name>``
    read downstream -- is unchanged. Every other spelling is added as an
    alias on the same action.

    Raises ``ValueError`` on a ``canonical`` outside
    ``REPO_ROOT_FLAG_ALIASES``: a caller reaching for a sixth spelling is
    re-introducing the very divergence this module exists to end, and is
    refused LOUDLY rather than silently accommodated.
    """
    if canonical not in REPO_ROOT_FLAG_ALIASES:
        raise ValueError(
            f"WHAT: {canonical!r} is not a known repo-root flag spelling. "
            f"WHY: this helper aliases ONE concept across its known names "
            f"({', '.join(REPO_ROOT_FLAG_ALIASES)}); a name outside that set "
            f"either belongs to a different concept or is a sixth spelling "
            f"of this one. HOW: pass the spelling this parser already used, "
            f"or -- if the concept genuinely is the repo root under a new "
            f"name -- add it to REPO_ROOT_FLAG_ALIASES so EVERY subcommand "
            f"gains it at once, never just this one."
        )
    aliases = [flag for flag in REPO_ROOT_FLAG_ALIASES if flag != canonical]
    return parser.add_argument(canonical, *aliases, **kwargs)
