"""TestRunnerPort -- the per-language test-runner resolution registry (slice-05).

The per-language test-runner port resolved from the INSTALLED target by
FILESYSTEM lockfile inspection (never a hardcoded ``pytest``). ``resolve`` walks
the recognized ``(lockfile -> runner)`` registry against the files actually
present in the target root and returns the matching ``RunnerAdapter``; an
unrecognized target (no recognized lockfile) degrades LOUD to the
``Indeterminate`` driven-port signal (N=0), NEVER a silent ``pytest`` fallback
(C3 / §17 / Invariant 2 -- no silent pass).

``pytest`` is the nWave-dev DOGFOOD runner: it is one row among equals in the
registry, resolved ONLY when a ``pyproject.toml`` / ``pytest.ini`` is the
target's own manifest -- it is never the universal executor for a non-Python
target (the genericità / language-agnostic mandate). The resolution is a GENUINE
filesystem inspection of the target, not a lookup keyed on a caller-supplied
runner name: a target carrying a ``package.json`` with a ``vitest`` devDependency
resolves ``vitest``; a ``go.mod`` resolves ``go-test``; a ``Cargo.toml`` resolves
``cargo-test``.

The ``Indeterminate`` value object is REUSED from the committed-scope driven port
(``des.ports.driven_ports.committed_scope_port``) -- the SAME degrade-LOUD signal
the contract gate already converts into a LOUD health event, never a silent
fall-back. (The DESIGN [REF] Code-Design cell mis-cited
``des.cli.committed_scope_port``; the correct, verified path is
``des.ports.driven_ports.committed_scope_port``.)

Stdlib-only at this layer (``pathlib`` + ``dataclasses``) per the DES-bundle
contract: it reads the filesystem and mutates nothing. The per-runner adapters
(which SHELL the target's own runner) live behind this port in
``des.adapters.driven.runner``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from des.ports.driven_ports.committed_scope_port import Indeterminate


if TYPE_CHECKING:
    from pathlib import Path


@dataclass(frozen=True)
class RunVerdict:
    """The observable outcome of RUNNING a scoped node-id set (the run facet).

    Port-exposed observable of ``RunnerAdapter.run`` (CRITICAL-2): the abstract
    pass/fail the gate earns its verdict from, plus the runner that produced it.
    ``passed`` is the only behavioral observable; ``runner`` names which runner
    executed (so the gate can prove it ran in the RESOLVED runner, never a
    hardcoded pytest -- CT-3). HOW the verdict was earned (the binary argv, the
    exit-code mapping) is the per-runner adapter's concern, never the port's.
    """

    passed: bool
    runner: str


@dataclass(frozen=True)
class ListScope:
    """The observable outcome of ENUMERATING a resolved runner's test scope.

    Port-exposed observable of ``RunnerAdapter.list_scope`` (the enumerate
    counterpart of ``RunVerdict``): the node-id set the whole-tree digest
    fingerprints, plus the runner that enumerated it. ``node_ids`` is the only
    behavioral observable; ``runner`` names WHICH runner's enumerate facet produced
    it -- so the gate can prove the digest is runner-aware (``cargo nextest list``
    on a crate, ``_collect_scope`` on a pytest tree), never a hardcoded pytest
    enumerate over a non-Python tree. HOW the set was enumerated (the binary argv,
    the list-output parse) is the per-runner adapter's concern, never the port's.
    """

    node_ids: tuple[str, ...]
    runner: str


@dataclass(frozen=True)
class RunnerAdapter:
    """The runner the target's lockfile resolves to (its abstract identity).

    ``name`` is the abstract runner identity the gate earns its verdict from
    (``pytest`` / ``vitest`` / ``go-test`` / ``cargo-test``), NOT the concrete
    binary argv -- HOW the adapter shells the runner is the per-runner adapter's
    concern (``des.adapters.driven.runner``). The port's observable is WHICH
    runner resolved.
    """

    name: str

    def run(self, target_root: Path, scoped_node_ids: tuple[str, ...]) -> RunVerdict:
        """RUN the scoped node-ids in this resolved runner; return PASS/FAIL.

        The run facet (CRITICAL-2): the abstract contract is "execute exactly the
        scoped node-ids in the runner this adapter resolved to, and report
        whether they passed". The concrete shelling (binary argv, exit->verdict
        mapping) lives in the per-runner adapter under
        ``des.adapters.driven.runner`` -- the port stays stdlib-only at import
        time and dispatches to the concrete adapter by ``name`` only on the
        effect path (the import is local so the port's import-time surface is
        unchanged). Dispatch is REGISTRY-based (ADR-RTR-001 D2): the run-facet is
        looked up in ``GLOBAL_REGISTRY`` by this adapter's ``name`` -- the SAME
        registry a plugin's ``register_adapters`` populates (the ``pytest``
        built-in, cargo via the Rust entry-point plugin) -- NOT a hardcoded
        ``if name == "pytest"`` branch. A miss self-heals by seeding once (the
        registry may be unseeded when ``run`` is reached outside the gate
        preamble); a runner still absent after seeding raises
        ``RunnerAdapterUnavailable`` (degrade-LOUD, never a silent pass and never
        a pytest fallback on a non-Python target).
        """
        from des.adapters.driven.runner.runner_registry import (
            GLOBAL_REGISTRY,
            seed_runner_registry,
        )

        run_facet = GLOBAL_REGISTRY.lookup(self.name)
        if run_facet is None:
            seed_runner_registry()
            run_facet = GLOBAL_REGISTRY.lookup(self.name)
        if run_facet is None:
            raise RunnerAdapterUnavailable(self.name)
        return run_facet(self, target_root, scoped_node_ids)

    def list_scope(self, target_root: Path) -> ListScope:
        """ENUMERATE this resolved runner's whole-tree test scope (the list facet).

        The read/enumerate counterpart of ``run`` (ADR-FLOW-011 D5): the abstract
        contract is "enumerate the target's whole test scope in the runner this
        adapter resolved to, and report the node-id set the digest fingerprints".
        Dispatch is REGISTRY-based exactly like ``run`` -- the list-facet is looked
        up in the SAME ``GLOBAL_REGISTRY`` by this adapter's ``name`` (the list
        facet a plugin registered via ``register_list``: ``list_pytest_scope`` /
        ``list_cargo_scope``), NOT a hardcoded ``if name == "pytest"`` branch, so
        the digest is runner-aware by construction. A miss self-heals by seeding
        once; a runner still absent after seeding raises ``RunnerAdapterUnavailable``
        (degrade-LOUD, never a fabricated digest and never a pytest enumerate on a
        non-Python target).
        """
        from des.adapters.driven.runner.runner_registry import (
            GLOBAL_REGISTRY,
            seed_runner_registry,
        )

        list_facet = GLOBAL_REGISTRY.lookup_list(self.name)
        if list_facet is None:
            seed_runner_registry()
            list_facet = GLOBAL_REGISTRY.lookup_list(self.name)
        if list_facet is None:
            raise RunnerAdapterUnavailable(self.name)
        return list_facet(self, target_root)


class RunnerAdapterUnavailable(RuntimeError):
    """The resolved runner has no production-ready concrete adapter (DDD-7).

    Raised by ``RunnerAdapter.run`` when the target resolves a recognized runner
    whose concrete run-adapter is not built in this feature. The gate maps it to
    INDETERMINATE (degrade-LOUD, named reason) -- NEVER a silent pass and NEVER a
    pytest fallback on a non-Python target.
    """

    def __init__(self, runner: str, reason: str | None = None) -> None:
        self.runner = runner
        self.reason = reason
        super().__init__(
            reason
            if reason is not None
            else (
                f"no production-ready run-adapter for the resolved runner "
                f"{runner!r} (only the pytest dogfood run-facet is built in this "
                "feature -- degrading LOUD to INDETERMINATE rather than falling "
                "back to pytest on a non-Python target)"
            )
        )


@dataclass(frozen=True)
class UnrecognizedRunner(Indeterminate):
    """The 0-lockfile resolution outcome -- UNRECOGNIZED, not AMBIGUOUS (D9).

    A typed subtype of ``Indeterminate`` returned ONLY when no recognized
    lockfile matches the target root (``resolve``'s ``not matched`` branch).
    ``Indeterminate`` conflates two cases needing OPPOSITE whole-tree treatment:

    * UNRECOGNIZED (0 lockfiles) -> pre-#73 ran pytest-collect / pytest directly;
      a lockfile-less Python tree MUST fall back to pytest (the nWave-dev home
      runner), NEVER degrade-LOUD exit-3.
    * AMBIGUOUS (2+ lockfiles, polyglot) -> genuinely ambiguous; degrade-LOUD
      (the bare ``Indeterminate``, with ``.nwave/runner.json`` as the escape hatch).

    The subtype is purely ADDITIVE: it IS-A ``Indeterminate`` (inherits ``reason``),
    so every existing ``isinstance(resolution, Indeterminate)`` check and
    ``resolution.reason`` access continues to hold UNCHANGED. The whole-tree routers
    add ONE narrow ``isinstance(resolution, UnrecognizedRunner)`` pre-check BEFORE
    the generic ``Indeterminate`` degrade to take the pytest-fallback path; the
    polyglot / override-error paths keep returning the bare ``Indeterminate``.
    """


@dataclass(frozen=True)
class _RegistryRow:
    """One ``(lockfile, predicate) -> runner`` row of the resolution registry."""

    filename: str
    runner: str
    requires_substring: str | None = None


# The recognized ``(lockfile -> runner)`` registry, inspected by FILESYSTEM
# presence in the target root (§V.A). ``pytest`` is the nWave-dev DOGFOOD runner,
# one row among equals -- NEVER the universal executor (C3). ``package.json``
# carries an extra ``requires_substring`` so a Node project is resolved to its
# declared test runner (``vitest``) rather than guessed.
_REGISTRY: tuple[_RegistryRow, ...] = (
    _RegistryRow(filename="pyproject.toml", runner="pytest"),
    _RegistryRow(filename="pytest.ini", runner="pytest"),
    _RegistryRow(filename="package.json", runner="vitest", requires_substring="vitest"),
    _RegistryRow(filename="go.mod", runner="go-test"),
    _RegistryRow(filename="Cargo.toml", runner="cargo-test"),
)


@dataclass(frozen=True)
class RunnerResolutionContext:
    """The FEATURE context that disambiguates a POLYGLOT target (ADR-FLOW-008).

    ``resolve`` is otherwise root-lockfile-blind; on a multi-lockfile (polyglot)
    repo it needs to know WHICH project the feature belongs to. Carries the
    feature-id (the cargo-target-presence + runner.json signals) and the repo
    root (to read an optional per-feature ``runner.json`` override). Optional: a
    single-lockfile target needs no context (the fast-path ignores it).
    """

    feature_id: str
    repo: Path


def resolve(
    target_root: Path,
    feature: RunnerResolutionContext | None = None,
) -> RunnerAdapter | Indeterminate:
    """Resolve the target's test runner by filesystem lockfile inspection.

    Three-state, feature/target-aware (ADR-FLOW-008, BUG B):

    * 0 matched lockfiles -> ``Indeterminate`` (degrade-LOUD, N=0), NEVER pytest.
    * 1 matched lockfile  -> that runner (the single-lockfile FAST-PATH, identical
      to the pre-ADR-FLOW-008 behavior; ``feature`` is ignored).
    * 2+ matched (POLYGLOT) -> ``_disambiguate`` via the signal cascade
      (runner.json override -> cargo-target-presence); un-disambiguable ->
      ``Indeterminate`` naming the competing lockfiles. NEVER a silent first-row
      pick (the BUG B defect: ``package.json`` shadowing ``Cargo.toml``).

    A ``package.json`` matches only when it declares the expected runner
    (``vitest``) so a Node project is resolved to its OWN runner.

    WHOLE-TREE override (D8): when there is no feature context (``feature is
    None``) a repo-level ``.nwave/runner.json`` is consulted BEFORE the
    lockfile-scan -- so a POLYGLOT root the scan cannot disambiguate escapes the
    ``Indeterminate`` by DECLARING its runner. An absent declaration falls through
    to the unchanged scan (no regression); the feature-scoped path is untouched.
    """
    if feature is None:
        override = _repo_runner_override(target_root)
        if override is not None:
            return override
    matched = [
        row
        for row in _REGISTRY
        if (target_root / row.filename).is_file()
        and _manifest_satisfies(target_root / row.filename, row.requires_substring)
    ]
    if not matched:
        return UnrecognizedRunner(reason=_unrecognized_reason(target_root))
    if len(matched) == 1:
        return RunnerAdapter(name=matched[0].runner)
    return _disambiguate(matched, feature)


def _disambiguate(
    matched: list[_RegistryRow],
    feature: RunnerResolutionContext | None,
) -> RunnerAdapter | Indeterminate:
    """Pick one runner among 2+ matched lockfiles, or degrade-LOUD INDETERMINATE.

    Signal cascade (ADR-FLOW-008): (c) an explicit ``runner.json`` ``runner`` key
    overrides; (b) cargo-target-presence -- a ``Cargo.toml`` among the matched
    rows wins (the convention-derived ``binary(/<snake_feature_id>/)`` IS the
    presence signal, and a wrong cargo guess fails LOUD via cargo exit-4, never a
    false pass). With no feature context or no winning signal -> ``Indeterminate``
    naming the competing lockfiles (NEVER a silent first-row pick).
    """
    by_runner = {row.runner: row for row in matched}
    if feature is not None:
        # (c) runner.json explicit override -- tier-1 authority above cargo.
        from des.adapters.driven.runner.runner_json import read_runner_json

        override = read_runner_json(feature.feature_id, feature.repo)
        if override is not None:
            declared = override.get("runner")
            if isinstance(declared, str) and declared in by_runner:
                return RunnerAdapter(name=declared)
        # (b) cargo-target-presence -- a matched Cargo.toml wins (convention).
        if "cargo-test" in by_runner:
            return RunnerAdapter(name="cargo-test")
    return Indeterminate(reason=_ambiguous_reason(matched))


# The repo-level whole-tree runner declaration path (D8) -- the override the
# ``feature is None`` pre-check consults BEFORE the lockfile-scan. Named verbatim
# in every override degrade-LOUD reason so the operator knows WHICH file to fix.
_REPO_RUNNER_OVERRIDE = ".nwave/runner.json"


def _repo_runner_override(
    target_root: Path,
) -> RunnerAdapter | Indeterminate | None:
    """Consult the repo-level ``.nwave/runner.json`` whole-tree declaration (D8).

    The whole-tree (``feature is None``) pre-check that lets a POLYGLOT root escape
    the polyglot ``Indeterminate`` by DECLARING its runner. Mirrors the local-import
    discipline of ``_disambiguate`` (the adapter is imported INSIDE the function so
    the port's import-time surface stays stdlib-only):

    * absent             -> ``None``: the lockfile-scan runs UNCHANGED (no regression).
    * valid registry key -> the ``RunnerAdapter`` (BYPASS the scan).
    * unknown key        -> ``Indeterminate`` naming the unregistered key + the file.
    * malformed JSON     -> ``Indeterminate`` naming the file (caught, never a crash).
    """
    from des.adapters.driven.runner.runner_json import (
        RepoRunnerDeclarationMalformed,
        read_repo_runner_json,
    )

    try:
        override = read_repo_runner_json(target_root)
    except RepoRunnerDeclarationMalformed as exc:
        return Indeterminate(reason=_malformed_override_reason(str(exc)))
    if override is None:
        return None
    declared = override.get("runner")
    if isinstance(declared, str) and declared in _registered_runner_names():
        return RunnerAdapter(name=declared)
    return Indeterminate(reason=_unregistered_override_reason(declared))


def _registered_runner_names() -> set[str]:
    """The set of runner names the registry knows -- the ONE home for the concept."""
    return {row.runner for row in _REGISTRY}


def _unregistered_override_reason(declared: object) -> str:
    """A degrade-LOUD reason naming the unregistered declared runner + the file."""
    known = sorted(_registered_runner_names())
    return (
        f"the repo-level {_REPO_RUNNER_OVERRIDE} declares runner {declared!r} which "
        f"is not a registered runner (recognized: {known!r}). Refusing to guess a "
        "runner the registry does not know (degrade-LOUD, never a silent pick)."
    )


def _malformed_override_reason(detail: str) -> str:
    """A degrade-LOUD reason naming the malformed declaration (no crash)."""
    return (
        f"the repo-level {_REPO_RUNNER_OVERRIDE} whole-tree runner declaration is "
        f"malformed and could not be parsed ({detail}). Degrade-LOUD INDETERMINATE "
        "(the JSONDecodeError is caught, never a crash); fix or remove the file."
    )


def _ambiguous_reason(matched: list[_RegistryRow]) -> str:
    """A degrade-LOUD reason naming the competing lockfiles + the remediations."""
    lockfiles = ", ".join(row.filename for row in matched)
    return (
        f"polyglot target -- {len(matched)} recognized lockfiles match "
        f"({lockfiles}) and no signal disambiguates the feature's runner. "
        "Declare it explicitly via docs/feature/<id>/runner.json "
        '({"runner": "<name>"}), or -- for a Rust feature -- follow the cargo '
        "binary(/<snake_feature_id>/) convention. Refusing to guess "
        "(degrade-LOUD, never a silent first-lockfile pick)."
    )


def _manifest_satisfies(manifest: Path, requires_substring: str | None) -> bool:
    """Whether ``manifest`` satisfies a row's content predicate (if any)."""
    if requires_substring is None:
        return True
    return requires_substring in manifest.read_text(encoding="utf-8")


def _unrecognized_reason(target_root: Path) -> str:
    """The LOUD reason naming why no runner resolved (Invariant 2 -- no silence)."""
    present = sorted(child.name for child in target_root.iterdir() if child.is_file())
    return (
        "no recognized test-runner lockfile found in the target "
        f"{target_root.name!r} (recognized: "
        f"{sorted(row.filename for row in _REGISTRY)!r}); present manifests: "
        f"{present!r} -- degrading LOUD to INDETERMINATE rather than falling "
        "back to pytest on a non-Python target (the pytest runner is the "
        "nWave-dev dogfood, never the universal executor)"
    )


__all__ = [
    "Indeterminate",
    "ListScope",
    "RunVerdict",
    "RunnerAdapter",
    "RunnerAdapterUnavailable",
    "UnrecognizedRunner",
    "resolve",
]
