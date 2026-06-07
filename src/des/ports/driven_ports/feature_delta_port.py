"""FeatureDeltaPort -- driven port over a feature's git ADDED-paths delta.

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified option B-port,
2026-06-05). The walking-skeleton floor's installability cross-check becomes
DELTA-AWARE: instead of probing whether the AMBIENT tree is installable (the
slice-02 ``_detect_installable`` direct-children probe, which false-FAILs every
monorepo-internal feature), the gate asks "does THIS feature's git DELTA
introduce a NEW installable root?". The delta is the set of files ADDED since the
merge-base with a base ref (``git diff --diff-filter=A --name-only
{base_ref}...HEAD``).

git enters ONLY behind this port's adapter
(``des.adapters.driven.git.git_feature_delta_adapter.GitFeatureDeltaAdapter``);
per ``feedback_target_machine_independence_2026_05_15`` (AD-21) the gate LOGIC
stays git-free and the port's degrade-LOUD ``Indeterminate`` (git absent / not a
work-tree / base ref unresolvable) drives the gate's INDETERMINATE verdict -- a
git failure NEVER fabricates an empty ``AddedPaths(())`` silent pass.

``Indeterminate`` is REUSED from ``des.ports.driven_ports.committed_scope_port``
(the same degrade-LOUD VO -- not redefined here).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class AddedPaths:
    """The set of repo-relative paths a feature's git delta ADDED.

    Frozen observation: the files added (``--diff-filter=A``) since the merge-base
    with the base ref. An empty ``AddedPaths(())`` is the LEGITIMATE git-SUCCESS
    "the feature added nothing" signal (a monorepo-internal change); it is NEVER
    used to mask a git failure -- that degrades to ``Indeterminate`` instead.
    """

    paths: tuple[str, ...]


class FeatureDeltaPort(ABC):
    """Driven, read-only port over a feature's git ADDED-paths delta.

    The gate defines WHAT the feature's delta is (the added-paths set); the
    adapter decides HOW to read it out of git. ``added_paths`` returns the
    repo-relative files ADDED since the merge-base with ``base_ref``, or an
    ``Indeterminate`` when git is absent / ``repo`` is not a work-tree /
    ``base_ref`` is unresolvable. Pure read -- no filesystem mutation.
    """

    @abstractmethod
    def added_paths(self, repo: Path, base_ref: str) -> AddedPaths | Indeterminate:
        """Return the feature's ADDED-paths delta, or Indeterminate.

        The delta is ``git diff --diff-filter=A --name-only {base_ref}...HEAD``
        (three-dot: files added since the merge-base with ``base_ref``). git
        exiting non-zero -- ``repo`` is not a work-tree, the git binary is absent,
        or ``base_ref`` is unresolvable -- yields ``Indeterminate``: the gate
        degrades LOUD rather than fabricate an empty delta it could not compute.
        """
        ...


__all__ = ["AddedPaths", "FeatureDeltaPort", "Indeterminate"]
