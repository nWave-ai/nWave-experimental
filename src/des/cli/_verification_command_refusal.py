"""Shared verification-scope.commands refusal (K4 Run 9).

Mirrors `_declared_import_refusal.py`'s shape exactly: `des dispatch` and
`des validate-delivery-contract` both call this, one WHAT/WHY/HOW message,
no drifting second copy across the two point-of-use verification call
sites (ADR-SSOT-002 Section 4a item 9).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.domain.verification_command_resolver import missing_verification_paths


if TYPE_CHECKING:
    from pathlib import Path


def all_missing_verification_paths(repo_root: Path, contract: dict) -> list[str]:
    """Every `verification-scope.commands` argument naming an absent test
    module/file, across every command -- not only the first."""
    return missing_verification_paths(repo_root, contract)


def first_missing_verification_path(repo_root: Path, contract: dict) -> str | None:
    return next(iter(all_missing_verification_paths(repo_root, contract)), None)


def missing_verification_path_finding(path: str) -> tuple[str, str, str]:
    """One `(what, why, how)` defect naming `path`."""
    return (
        f"verification-scope.commands cites {path!r}, which does not "
        "resolve to a base-tree test module or file",
        "a DeliveryContract citing a wrong test path (K4 matrix Run 9, "
        "e.g. a wrong Django app-label prefix) costs a full crafter "
        "dispatch discovering the command itself is wrong before it can "
        "correctly refuse to guess a fix",
        f"correct {path!r} to the exact test module/file this project's "
        "own test runner already resolves -- for a Django `manage.py "
        "test` label, the dotted path a real `<app>/tests/<module>.py` "
        "file already matches; for pytest, the exact repository-relative "
        "file path -- or, if this contract's own oracle IS that file, "
        "point it at `acceptance-tests.locator`'s exact spelling",
    )
