"""Configured placement of DES real work inside the repository.

One resolver, one exception, zero writes. Every consumer that creates real
work -- lane worktrees, the managed reuse workspace, isolated cold candidate
checkouts -- derives its directory from :class:`WorkspacePaths` here instead
of hardcoding ``lanes/...``, so a project's ``.nwave/config.json`` governs
cold and reuse paths identically from any linked lane checkout.

Boundary: a DRIVEN ADAPTER like its sibling
``repository_config_root.resolve_repository_config_root`` (whose marker walk
it reuses for the principal root). It reads the repository config tier and
probes filesystem components for symlinks; it NEVER writes, never shells out
to ``git``, and never touches the global config tier -- workspace placement
is repository OWNERSHIP, and a global preference cannot grant ownership over
this repository's directories (the same stance as
``DESConfig.verification_reuse_outputs``).

Refusal algebra: a configuration that would place real work outside the
repository, inside ignored/evidence/generated territory, or across a symlink
raises :class:`WorkspaceConfigInvalid` BEFORE any consumer writes -- never a
half-materialized workspace. ``WorkspaceConfigInvalid`` subclasses
``ValueError`` so existing ``except (OSError, ValueError)`` consumers keep
their exact behaviour. Declared outputs are shape-refused here too, so
consumers as distant as ``cli/lane`` can never act on an aliasing
spelling like ``a/../lanes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.config.repository_config_root import (
    resolve_repository_config_root,
)


#: The boring default that preserves every pre-configured layout: lanes stay
#: at ``<repo>/lanes``, the managed reuse workspace at
#: ``<repo>/lanes/.des-verification`` exactly as before this module existed.
DEFAULT_WORKSPACE_ROOT = "lanes"

#: Isolated cold candidate checkouts. Real worktrees, registered to this
#: repository's common Git dir -- never a tmp/cache directory.
CANDIDATE_DIRNAME = ".des-candidate"

#: The managed reuse workspace (one warm repository cache).
VERIFICATION_DIRNAME = ".des-verification"

#: Runner-owned metadata and native evidence live here and are NEVER
#: disposable; declared as a root so consumers and maintenance report the
#: same boundary instead of repeating the literal.
EVIDENCE_RELPATH = PurePosixPath(".nwave") / "des"

#: Ownership marker written INSIDE a generated output root at the moment
#: DES first creates it (never found preexisting), and honoured by
#: maintenance as the creation-side half of the ownership proof; the
#: project config's ``adopt_outputs`` is the explicit-adoption half.
#: Unknown preexisting principal caches carry neither and are preserved.
OWNERSHIP_MARKER = ".nwave-des-owned.json"

#: Producer receipt written INSIDE every cold candidate checkout at
#: creation, binding it to this repository's common Git dir. The Git
#: worktree registry is location, not ownership: maintenance force-removes
#: a candidate only when this receipt proves DES produced it here.
CANDIDATE_RECEIPT = ".nwave-des-candidate.json"

#: Components a workspace root may never contain: Git ownership, evidence,
#: and virtualenv territory are not disposable workspace.
_FORBIDDEN_COMPONENTS = frozenset({".git", ".nwave", ".venv"})


class WorkspaceConfigInvalid(ValueError):
    """Workspace configuration cannot place real work inside the repository."""


@dataclass(frozen=True)
class WorkspacePaths:
    """Immutable configured workspace roots of one repository.

    ``root`` is the PRINCIPAL repository root -- the checkout that owns
    ``.nwave/config.json`` -- resolved through the worktree-aware marker
    walk, so every path below is principal-rooted even when resolution
    starts inside a linked lane.
    """

    root: Path
    #: Disposable lane-worktree root; the lane surface derives
    #: ``<lanes>/<name>`` from this.
    lanes: Path
    #: Cold candidate worktrees: real checkouts registered to this
    #: repository's common Git dir, never tmp/cache.
    candidate: Path
    #: The managed reuse workspace -- the one warm repository cache.
    verification: Path
    #: Runner-owned metadata/native-evidence root; never disposable.
    evidence: Path
    #: ``verification.reuse.outputs`` verbatim; ``None`` when undeclared.
    outputs: tuple[str, ...] | None
    #: Output roots the project EXPLICITLY declares rebuildable
    #: (``verification.reuse.workspace.adopt_outputs``); the adoption half
    #: of the cache-ownership proof for roots DES did not create.
    adopted: tuple[str, ...]
    #: ``verification.reuse.workspace.cache_limit_bytes``; None = unbounded.
    cache_limit_bytes: int | None
    #: ``verification.reuse.workspace.automatic``; default True -- the user
    #: chose automatic eviction of OWNED inactive cache; unknown and
    #: evidence are protected regardless.
    automatic: bool


def resolve_workspace_paths(
    start: Path, *, config: DESConfig | None = None
) -> WorkspacePaths:
    """Resolve the configured workspace roots governing ``start``.

    ``start`` may be the repository root, any subdirectory, or a linked lane
    checkout; resolution always lands on the principal root. Read-only;
    raises :class:`WorkspaceConfigInvalid` for a malformed workspace
    declaration (absolute or escaping paths, ``.git``/``.nwave``/``.venv``
    components, symlink components, overlap with declared generated
    outputs) before any consumer writes. ``OSError`` from filesystem probes
    may propagate, exactly like ``Path.is_symlink()`` anywhere else.
    """
    config = DESConfig(cwd=start) if config is None else config
    try:
        policy = config.verification_reuse_policy()
    except ValueError as error:
        raise WorkspaceConfigInvalid(str(error)) from error
    outputs = None if policy is None else policy.outputs
    workspace = None if policy is None else policy.workspace
    if outputs is not None:
        for output in outputs:
            # A malformed output spelling is refused HERE, before any
            # consumer writes or accounts: cli/lane and the maintenance
            # budget are consumers of the same declarations, and an
            # aliasing spelling like "a/../lanes" must never pass by
            # being merely skipped.
            _configured_relative_root(output, label="declared generated output")
    root = resolve_repository_config_root(start.resolve())
    declared = None if workspace is None else workspace.get("root")
    relative = _configured_relative_root(declared)
    lanes = root.joinpath(*relative.parts)
    candidate_rel = relative / CANDIDATE_DIRNAME
    verification_rel = relative / VERIFICATION_DIRNAME
    for workspace_relative in (relative, candidate_rel, verification_rel):
        _refuse_symlink_components(root, workspace_relative)
    adopted = _configured_adopted(workspace, outputs)
    _refuse_output_overlap(outputs, relative, candidate_rel, verification_rel)
    _refuse_workspace_overlap(adopted, relative, candidate_rel, verification_rel)
    return WorkspacePaths(
        root=root,
        lanes=lanes,
        candidate=root.joinpath(*candidate_rel.parts),
        verification=root.joinpath(*verification_rel.parts),
        evidence=root / EVIDENCE_RELPATH,
        outputs=outputs,
        adopted=adopted,
        cache_limit_bytes=(
            None if workspace is None else workspace.get("cache_limit_bytes")
        ),
        automatic=True if workspace is None else workspace.get("automatic", True),
    )


def _configured_adopted(
    workspace: dict | None, outputs: tuple[str, ...] | None
) -> tuple[str, ...]:
    """Explicitly adopted output roots, each a DECLARED generated output.

    Adoption narrows an already-declared output to rebuildable; it cannot
    invent a new deletion target, so an unlisted adoption is a typed
    config error with the recovery named.
    """
    if workspace is None:
        return ()
    declared = workspace.get("adopt_outputs")
    if declared is None:
        return ()
    if not isinstance(declared, list) or not declared:
        raise WorkspaceConfigInvalid(
            "verification.reuse.workspace.adopt_outputs must be a nonempty "
            "list of repository-relative generated directories"
        )
    for entry in declared:
        _configured_relative_root(entry, label="adopted output")
        # Adoption narrows an ALREADY-DECLARED output to rebuildable; it
        # cannot invent a new deletion target. An unlisted adoption would
        # otherwise be silently inert at eviction time with a misleading
        # recovery hint.
        if outputs is None or entry not in outputs:
            raise WorkspaceConfigInvalid(
                f"adopted output {entry!r} is not a declared "
                "verification.reuse.outputs path; declare it in "
                "verification.reuse.outputs first, then adopt it"
            )
    if len(set(declared)) != len(declared):
        raise WorkspaceConfigInvalid(
            "verification.reuse.workspace.adopt_outputs must be distinct"
        )
    return tuple(declared)


def _configured_relative_root(
    declared: str | None, *, label: str = "workspace root"
) -> PurePosixPath:
    """The repository-relative path, structurally refused if unsafe.

    An absolute path, a traversal, a ``.git``/``.nwave``/``.venv`` component,
    or any non-normalized spelling is refused here -- real work can only be
    placed at a repository-relative location, so tmp/cache/HOME placement is
    structurally impossible rather than special-cased per tool.
    """
    if declared is None:
        return PurePosixPath(DEFAULT_WORKSPACE_ROOT)
    path = PurePosixPath(declared)
    if "\\" in declared:
        raise WorkspaceConfigInvalid(
            f"{label} {declared!r} must be a repository-relative POSIX path"
        )
    if (
        not declared
        or not path.parts
        or path.is_absolute()
        or path.as_posix() != declared
    ):
        raise WorkspaceConfigInvalid(
            f"{label} {declared!r} must be a normalized "
            "repository-relative POSIX directory"
        )
    for part in path.parts:
        if part in {".", ".."}:
            raise WorkspaceConfigInvalid(
                f"{label} {declared!r} must not traverse outside the repository"
            )
        if part == "~" or part.startswith("~"):
            raise WorkspaceConfigInvalid(
                f"{label} {declared!r} must be repository-relative; "
                "home-expansion spelling is refused"
            )
        if part in _FORBIDDEN_COMPONENTS:
            raise WorkspaceConfigInvalid(
                f"{label} {declared!r} may not contain the reserved component {part!r}"
            )
    return path


def _refuse_workspace_overlap(
    adopted: tuple[str, ...],
    relative: PurePosixPath,
    candidate: PurePosixPath,
    verification: PurePosixPath,
) -> None:
    """Adopted output roots may alias declared outputs, never the workspace.

    Adoption declares a generated cache rebuildable; adopting the
    workspace root itself, anything inside it, or a live lane worktree
    under it would hand budget eviction uncommitted work, so such
    declarations are refused outright. Adopted entries are
    shape-validated by ``_configured_adopted``.
    """
    for entry in adopted:
        path = PurePosixPath(entry)
        for workspace_relative in (relative, candidate, verification):
            shared = min(len(path.parts), len(workspace_relative.parts))
            if path.parts[:shared] == workspace_relative.parts[:shared]:
                raise WorkspaceConfigInvalid(
                    f"adopted output {entry!r} overlaps the configured "
                    "workspace roots; adoption is for generated caches, "
                    "not the workspace itself"
                )


def _refuse_symlink_components(root: Path, relative: PurePosixPath) -> None:
    """A workspace reached through a symlink is someone else's directory."""
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise WorkspaceConfigInvalid(f"workspace component is a symlink: {current}")


def _refuse_output_overlap(
    outputs: tuple[str, ...] | None,
    relative: PurePosixPath,
    candidate: PurePosixPath,
    verification: PurePosixPath,
) -> None:
    """The workspace must not live inside, or contain, a generated output.

    The workspace ROOT itself participates: a generated output declared
    inside the configured workspace root (a sibling of the candidate and
    verification caches) is refused exactly like the reverse containment.
    Every declared output is already shape-validated by the resolver
    before this runs, so each entry is a comparable relative path.
    """
    if outputs is None:
        return
    for output in outputs:
        path = PurePosixPath(output)
        for workspace_relative in (relative, candidate, verification):
            shared = min(len(path.parts), len(workspace_relative.parts))
            if path.parts[:shared] == workspace_relative.parts[:shared]:
                raise WorkspaceConfigInvalid(
                    f"workspace root overlaps declared generated output {output!r}"
                )
