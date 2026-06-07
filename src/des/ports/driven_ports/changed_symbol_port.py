"""ChangedSymbolPort -- driven port over a feature's net-new ADDED-files delta.

slice-01 of oss-dormant-seam-gate (DESIGN D-2, Reuse R4). The dormant-seam gate
evaluates ONLY the feature's net-new delta (DISCUSS D3 -- net-new-delta-only, no
retroactive blast on the static tree). This port supplies that delta: the set of
files ADDED since the merge-base with a base ref (``git diff --diff-filter=A
--name-only {base_ref}...HEAD``), exactly the ``FeatureDeltaPort`` shape this is
modeled on.

git enters ONLY behind this port's adapter
(``des.adapters.driven.git.git_changed_symbol_adapter.GitChangedSymbolAdapter``);
per ``feedback_target_machine_independence_2026_05_15`` (AD-21) the gate LOGIC
stays git-free and the port's degrade-LOUD ``Indeterminate`` (git absent / not a
work-tree / base ref unresolvable) NEVER fabricates an empty
``ChangedSymbols(())`` silent pass -- a git failure surfaces LOUD, never a silent
empty delta the detector would read as "nothing dormant".

``Indeterminate`` is REUSED from ``des.ports.driven_ports.committed_scope_port``
(the same degrade-LOUD VO -- not redefined here), as ``FeatureDeltaPort`` does.

slice-01 floor (DESIGN OQ-1): added-FILE granularity. The CLI cross-references
the added files against the public-effectful-symbol surface; added-LINE
resolution for modified files carrying a net-new symbol is a slice-04 concern.
The port is named ``ChangedSymbolPort`` (the design vocabulary) but slice-01
realizes the file-granular delta; the symbol derivation lives in the CLI.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class ChangedSymbols:
    """The repo-relative files a feature's git delta ADDED (net-new delta).

    Frozen observation: the files added (``--diff-filter=A``) since the merge-base
    with the base ref. An empty ``ChangedSymbols(())`` is the LEGITIMATE
    git-SUCCESS "the feature added nothing" signal; it is NEVER used to mask a git
    failure -- that degrades to ``Indeterminate`` instead.
    """

    paths: tuple[str, ...]


class ChangedSymbolPort(ABC):
    """Driven, read-only port over a feature's net-new ADDED-files delta.

    The gate defines WHAT the feature's delta is (the added-paths set); the
    adapter decides HOW to read it out of git. ``changed_symbols`` returns the
    repo-relative files ADDED since the merge-base with ``base_ref``, or an
    ``Indeterminate`` when git is absent / ``repo`` is not a work-tree /
    ``base_ref`` is unresolvable. Pure read -- no filesystem mutation (the gate is
    a pure observer of the delta; the port exposes NO write method).
    """

    @abstractmethod
    def changed_symbols(
        self, repo: Path, base_ref: str
    ) -> ChangedSymbols | Indeterminate:
        """Return the feature's net-new ADDED-files delta, or Indeterminate.

        The delta is ``git diff --diff-filter=A --name-only {base_ref}...HEAD``
        (three-dot: files added since the merge-base with ``base_ref``). git
        exiting non-zero -- ``repo`` is not a work-tree, the git binary is absent,
        or ``base_ref`` is unresolvable -- yields ``Indeterminate``: the gate
        degrades LOUD rather than fabricate an empty delta it could not compute.
        """
        ...


__all__ = ["ChangedSymbolPort", "ChangedSymbols", "Indeterminate"]
