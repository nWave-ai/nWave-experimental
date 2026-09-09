"""``GraphifyAdapter`` — the optional precise CodeFact tier (ADR-LA-001 D4/LA1-L7).

LA1-L7 named this exactly: "a future precise provider registers through
``CodeFactProvider`` carrying its witness — a wiring change, not a port
change." This is that provider. It reads an ALREADY-MATERIALIZED
``graphify-out/{graph.json,manifest.json}`` pair under the queried root —
never invokes the ``graphify`` tool itself (pure Python, zero runtime
dependency on graphify, ADR-LA-001 D4/D10 portability). Absent data means
this adapter is excluded from :class:`CodeFactChain`'s provider tuple
entirely (ADR-LA-001 residual-stress table: "Optional precise provider
absent ... absent ⇒ not in tuple; absence is the OSS normal case" — never a
phantom tier, never a fabricated ``binding-resolved`` answer).

**The witness (LA1-L7)**: ``manifest.json`` records each file's ``mtime`` at
the moment the graph was materialized. Before answering ``binding-resolved``
for a query touching file F, this adapter re-``stat``s F and compares its
CURRENT mtime against the manifest's recorded mtime for F — an exact match
is the completed-handshake evidence that the graph's claim about F is still
true. Any mismatch (F touched since the graph was built) fails the query
with ``provider-error`` (the closest existing closed D3 cause — "this
provider's own data source failed a trust check for this file", never
inflated to a partial or stale ``binding-resolved``) rather than staying
silent about it or serving a stale structural claim. graphify's OWN
``ast_hash``/``semantic_hash`` manifest fields exist but are never
independently recomputed here — reproducing graphify's internal hash
algorithm would require importing graphify itself as a runtime dependency,
contradicting the zero-dependency design (D10); ``mtime`` is the cheap,
independently-verifiable proxy this adapter's own ADR amendment documents
as the realized witness mechanism.

**Capability coverage** is deliberately conservative — only what the data
directly and unambiguously backs, never inflated (LA1-L6):

* ``query.atoms-in-file`` — every node whose ``source_file`` names a given
  file IS an atom defined there, a directly-``EXTRACTED`` fact.
* ``query.callers-of`` / ``query.never-wired`` (slice 2) — a ``calls`` edge
  at ``confidence == "EXTRACTED"`` whose resolved target node's label names
  the callable IS a real call site; ``never-wired`` is the same data read
  as absence. ``calls`` edges also exist at ``confidence == "INFERRED"``
  (observed in real graphs) and ``indirect_call`` edges (100% ``INFERRED``
  in every sampled graph) — both excluded here, same LA1-L6 no-inflation
  reasoning as ``reads-of`` below.
* **``query.reads-of`` stays EXCLUDED.** The graph's closest relations are
  ``uses`` (100% ``INFERRED`` confidence across every sampled real graph)
  and ``references`` (``EXTRACTED``, but its own ``context`` field spans
  decorator application, type annotation and other non-bare-reference
  shapes in sampled data) — neither cleanly matches ``AstAdapter``'s own
  precise "bare identifier in ``Load`` context, structurally disjoint from
  a call" definition. Declaring coverage here would be exactly the
  inflation LA1-L6 forbids; this stays a later slice's job, not this one's.
* **``query.adr-section`` stays EXCLUDED.** It is a prose/text-presence
  capability (``AstAdapter`` itself only degrades to a textual scan for
  it); the graph schema carries no prose-anchor data at all — there is
  nothing here to back an answer with.

**Whole-tree completeness (``callers-of``/``never-wired`` only).** Unlike
``atoms-in-file`` (which only claims what one file/directory contains — an
incomplete graph merely narrows that answer's own scope), a ``never-wired``
claim asserts an ABSENCE across the whole tree: a caller sitting in a file
graphify never scanned would make a false "never wired" claim, not merely
an incomplete one. Before answering either capability this adapter walks
the LIVE tree (:class:`TreeScope`, the same shared pure-Python floor
``AstAdapter``/``TextSearchAdapter`` use — no new dependency) and requires
every currently-existing Python file to have a fresh manifest entry;
one missing or stale file fails the whole query with ``provider-error``
and the fold falls through, rather than serving a claim the graph cannot
honestly back over its own unobserved gaps.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.codefact.tree_scope import TreeScope
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_CALLERS_OF,
    CAPABILITY_NEVER_WIRED,
    REFERENCE_SHAPE_BARE_NAME,
    REFERENCE_SHAPE_DOTTED_ATTRIBUTE,
    Answered,
    CodeFactResult,
    Confidence,
    Failed,
    ManifestEntry,
    TraceEntry,
)
from des.runtime.spawn import SpawnTimeout, spawn


try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover - Windows has no fcntl
    _HAS_FCNTL = False


if TYPE_CHECKING:
    from collections.abc import Mapping

    from des.ports.code_fact_port import CapabilityDescriptor, Manifest


#: PUBLIC, and public for one measured reason: the ephemeral candidate
#: worktree the delivery runner verifies in must carry this directory, and
#: a second hand-typed copy of the name there would drift the day this one
#: changes.  One name, one owner -- the tier that reads it.
GRAPH_INDEX_DIR_NAME = "graphify-out"
_GRAPH_FILE_NAME = "graph.json"
_MANIFEST_FILE_NAME = "manifest.json"
_PYTHON_SOURCE_GLOB = "*.py"
_EXTRACTED = "EXTRACTED"
_CALLS_RELATION = "calls"

# F-GRAPHIFY-STALE-DEGRADES-SILENTLY (Ale 2026-08-24: regeneration is
# SYNCHRONOUS). One per-graphify-out lock file, same fcntl.flock(LOCK_EX)
# idiom as des.cli.commit's commit.lock -- serializes concurrent
# regeneration attempts against the SAME graph across separate OS
# processes (des is a fresh process per invocation; a Python-level lock
# would prove nothing).
_REGEN_LOCK_FILE_NAME = ".regen.lock"
_GRAPHIFY_EXECUTABLE_NAME = "graphify"
_GRAPHIFY_UPDATE_SUBCOMMAND = "update"

# Every capability this optional tier can attempt (deliberately the minimal,
# unambiguously-supported set — see module docstring). Shared by
# ``manifest()`` so a future widening never needs a second hand-typed copy.
_HANDLED_CAPABILITY_IDS = frozenset(
    {CAPABILITY_ATOMS_IN_FILE, CAPABILITY_CALLERS_OF, CAPABILITY_NEVER_WIRED}
)

# The reference SHAPES this tier represents, per capability (reference-shape
# coverage axis, 2026-08-23). A ``calls`` edge is resolved by TARGET NODE, not
# by call syntax, so a dotted call site (``owner.method()``) is observed exactly
# like a bare one -- BOTH shapes, no lexical anchor to be blind at.
#
# DECLARED RESIDUAL: this tier's ``never-wired`` is call-edge-only (it excludes
# ``reads-of`` on purpose, see the module docstring), while the structural tier
# now counts read-sites as wiring too. Both shapes are represented, so the
# blind-empty rule does not fire here -- the gap is a RELATION gap, not a shape
# gap, and closing it needs a ``uses``/``references`` edge slice this lane did
# not open. Absent graphify data (the OSS normal case) this tier is not in the
# provider tuple at all.
_REPRESENTED_SHAPES: dict[str, tuple[str, ...]] = {
    CAPABILITY_CALLERS_OF: (
        REFERENCE_SHAPE_BARE_NAME,
        REFERENCE_SHAPE_DOTTED_ATTRIBUTE,
    ),
    CAPABILITY_NEVER_WIRED: (
        REFERENCE_SHAPE_BARE_NAME,
        REFERENCE_SHAPE_DOTTED_ATTRIBUTE,
    ),
}


def _locate_graphify_out(start: Path) -> Path | None:
    """Walk from ``start`` (its parent, if ``start`` names a FILE — the
    established ``atoms-in-file`` convention where ``--root`` is a single
    file, not a directory) up the filesystem, returning the first
    ``graphify-out`` directory that contains BOTH ``graph.json`` and
    ``manifest.json``, or ``None`` (ABSENT — ADR-LA-001: absent ⇒ not in
    tuple). Bounded by the filesystem root; never loops."""
    current = start if start.is_dir() else start.parent
    seen: set[Path] = set()
    while True:
        resolved = current.resolve()
        if resolved in seen:
            return None
        seen.add(resolved)
        candidate = current / GRAPH_INDEX_DIR_NAME
        if (candidate / _GRAPH_FILE_NAME).is_file() and (
            candidate / _MANIFEST_FILE_NAME
        ).is_file():
            return candidate
        parent = current.parent
        if parent == current:
            return None
        current = parent


def _load_json_object(path: Path) -> dict | None:
    """``path``'s parsed JSON object, or ``None`` on any read/parse fault
    or a non-object top level — never a raised exception, matching the
    "absence is the OSS normal case" degrade."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


class GraphifyAdapter:
    """The optional precise :class:`CodeFactPort` tier — see module docstring."""

    confidence = Confidence.BINDING_RESOLVED.value
    provider = "graphify"
    provider_id = "graphify"

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)
        self._out_dir = _locate_graphify_out(self._root)
        self._graph: dict | None = None
        self._manifest: dict | None = None
        # A failed synchronous refresh is expensive (the provider's default
        # timeout is intentionally generous). Keep its honest failure only
        # while the graph/manifest pair and the stale live inputs are the same;
        # either side changing re-opens exactly one new refresh attempt.
        self._operation_state: dict[str, object] = {"failed_refresh": None, "views": []}
        self._operation_owner = self
        # Which of the two ABSENT sub-causes applies, recorded ONCE here so
        # a caller can name the exact closed detail without re-walking or
        # re-parsing anything a second time. ``None`` once real data is
        # found (``has_data`` is ``True``).
        self._absence_cause: str | None = None
        if self._out_dir is not None:
            graph = _load_json_object(self._out_dir / _GRAPH_FILE_NAME)
            manifest = _load_json_object(self._out_dir / _MANIFEST_FILE_NAME)
            if graph is not None and manifest is not None:
                self._graph = graph
                self._manifest = manifest
            else:
                # Malformed/unreadable data under an otherwise-present
                # graphify-out directory is treated identically to
                # ABSENT — never a partially-trusted graph.
                self._out_dir = None
                self._absence_cause = "index present-but-unreadable"
        else:
            self._absence_cause = "index directory absent"

    def scoped(self, root: Path | str) -> GraphifyAdapter:
        """A per-query view sharing this operation's graph and refresh state."""
        view = GraphifyAdapter(root)
        # Each view keeps its own query root, but refreshes one graph index.
        # Construct it normally so future adapter fields cannot be silently
        # omitted by a brittle shallow ``__dict__`` clone, then join the
        # operation state whose reload path updates every registered view.
        view._operation_owner = self._operation_owner
        view._operation_state = self._operation_state
        self._operation_state["views"].append(view)
        return view

    @property
    def has_data(self) -> bool:
        """``True`` iff a real, parseable ``graphify-out`` pair was found.

        The composition-time fact :class:`CodeFactChain` reads to decide
        whether this adapter enters the provider tuple at all (absent ⇒
        not in tuple, never a phantom tier that always fails)."""
        return self._graph is not None and self._manifest is not None

    # -- the uniform CodeFactProvider protocol (ADR-LA-001 D2/D9) -----------

    def manifest(self) -> Manifest:
        """Static coverage claim (LA1-L2) — empty when no data was found
        (never claims a capability it cannot back), otherwise the
        deliberately conservative set above, all at ``binding-resolved``
        (LA1-L6: declared honestly, the fold never inflates it further)."""
        if not self.has_data:
            return ()
        return tuple(
            ManifestEntry(
                capability_id=capability_id,
                confidence=self.confidence,
                represents=_REPRESENTED_SHAPES.get(capability_id, ()),
            )
            for capability_id in sorted(_HANDLED_CAPABILITY_IDS)
        )

    def resolve(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> Answered | Failed:
        """Total (LA1-L4): a stale or unlocatable file for this query
        fails with ``provider-error`` rather than serving a claim the
        witness cannot back. ``resolve_through_fold`` never calls this
        without a manifest-claimed capability (LA1-L5), so the defensive
        branches below are a safety net for direct callers, not the
        normal path."""
        if not self.has_data or descriptor.id not in _HANDLED_CAPABILITY_IDS:
            return self._provider_error("no graphify-out data for this capability")
        if descriptor.id == CAPABILITY_ATOMS_IN_FILE:
            return self._atoms_in_file()
        if descriptor.id in (CAPABILITY_CALLERS_OF, CAPABILITY_NEVER_WIRED):
            return self._call_graph_capability(descriptor.id, request)
        return self._provider_error("capability not realized")

    # -- non-answer trace entries (bounded, read directly by the chain) -----

    def non_answer_trace_entry(
        self, descriptor: CapabilityDescriptor
    ) -> TraceEntry | None:
        """When ``has_data`` is ``False`` and ``descriptor`` names one of
        this tier's own capabilities, one bounded ``TraceEntry`` naming the
        exact closed absent/unreadable cause recorded in ``__init__`` --
        reusing the SAME closed D3 cause (``provider-error``) and
        ``TraceEntry`` shape :meth:`_provider_error` already produces.
        Never contributed through :meth:`manifest`/:meth:`resolve`; read
        directly by :class:`CodeFactChain`."""
        if self.has_data or descriptor.id not in _HANDLED_CAPABILITY_IDS:
            return None
        assert self._absence_cause is not None
        return TraceEntry(
            provider_id=self.provider_id,
            event="failed:provider-error",
            scope="complete",
            fault_count=0,
            exemplars=(),
            detail=self._absence_cause,
        )

    def executable_missing_trace_entry(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> TraceEntry | None:
        """Performed BEFORE any lock/subprocess attempt: when this request
        is stale for this capability AND ``graphify`` is not on PATH right
        now, the SAME kind of bounded ``TraceEntry`` naming the closed
        executable-missing phrase -- never a :class:`Failed`. Every OTHER
        regeneration-failure outcome stays inside
        :meth:`_regenerate_and_recheck`, untouched."""
        if descriptor.id not in _HANDLED_CAPABILITY_IDS:
            return None
        if not self._is_stale_for(descriptor.id, request):
            return None
        if shutil.which(_GRAPHIFY_EXECUTABLE_NAME) is not None:
            return None
        return TraceEntry(
            provider_id=self.provider_id,
            event="failed:provider-error",
            scope="complete",
            fault_count=0,
            exemplars=(),
            detail=(
                "index present-but-stale with "
                f"'{_GRAPHIFY_EXECUTABLE_NAME}' executable not on PATH"
            ),
        )

    # -- synchronous regeneration (F-GRAPHIFY-STALE-DEGRADES-SILENTLY) -------

    def ensure_fresh_or_fail(
        self, descriptor: CapabilityDescriptor, request: Mapping[str, object]
    ) -> Failed | None:
        """Called by :class:`CodeFactChain` BEFORE the fold, never by
        :meth:`resolve` itself.

        ``None`` means "proceed to the normal fold" -- either this request
        was never stale (the common case, zero side effects, same as
        before this remedy existed), or it WAS stale and this call
        regenerated the graph SYNCHRONOUSLY and confirmed freshness
        (Ale, 2026-08-24: regeneration is synchronous, not deferred).
        A returned :class:`Failed` means the chain must STOP here and
        answer ``Failed`` directly -- never fall through to
        ``AstAdapter``/``TextSearchAdapter``, which is exactly the silent
        degrade this remedy exists to close. ``resolve_through_fold``'s
        own per-provider ``Failed`` -> ``continue`` semantics are
        untouched (still correct for every OTHER failure cause); this
        method's caller intercepts before the fold ever starts, precisely
        for this one cause.
        """
        if descriptor.id not in _HANDLED_CAPABILITY_IDS:
            return None  # graphify never claims this capability -- not its call
        if not self._is_stale_for(descriptor.id, request):
            self._operation_state["failed_refresh"] = None
            return None
        fingerprint = self._refresh_failure_fingerprint(descriptor.id)
        failed_refresh = self._operation_state["failed_refresh"]
        if failed_refresh is not None and failed_refresh[0] == fingerprint:
            return failed_refresh[1]
        failure = self._regenerate_and_recheck(descriptor.id, request)
        if failure is not None:
            # Regeneration can change graph/manifest and still fail the
            # post-check. Record the state it actually left, not the state
            # before the attempt, so the next identical query does not retry.
            self._operation_state["failed_refresh"] = (
                self._refresh_failure_fingerprint(descriptor.id),
                failure,
            )
        else:
            self._operation_state["failed_refresh"] = None
        return failure

    def _refresh_failure_fingerprint(self, capability_id: str) -> tuple[object, ...]:
        """The cheap measured state that permits one failed refresh retry.

        The graph/manifest pair identifies the index state. The live inputs are
        exactly those whose freshness this capability reads, including an absent
        file as ``None``. This is adapter-local operation state, not a global
        claim that Graphify can never recover.
        """
        assert self._out_dir is not None
        index = tuple(
            self._path_fingerprint(self._out_dir / name)
            for name in (_GRAPH_FILE_NAME, _MANIFEST_FILE_NAME)
        )
        if capability_id == CAPABILITY_ATOMS_IN_FILE:
            # A failed update speaks about the one graph index, not merely the
            # first file that happened to query it. Fingerprint every live
            # Python input under that index so sibling file views coalesce, yet
            # any source change reopens one honest attempt.
            relative_paths = tuple(
                file.resolve().relative_to(self._out_dir.parent.resolve()).as_posix()
                for file in TreeScope(self._out_dir.parent).files(_PYTHON_SOURCE_GLOB)
            )
            inputs = tuple(
                (relative, self._path_fingerprint(self._out_dir.parent / relative))
                for relative in sorted(relative_paths)
            )
        else:
            inputs = tuple(
                (
                    live_file.resolve().as_posix(),
                    self._path_fingerprint(live_file),
                )
                for live_file in TreeScope(self._root).files(_PYTHON_SOURCE_GLOB)
            )
        return capability_id, index, inputs

    @staticmethod
    def _path_fingerprint(path: Path) -> tuple[int, int] | None:
        try:
            state = path.stat()
        except OSError:
            return None
        return state.st_mtime_ns, state.st_size

    def _is_stale_for(self, capability_id: str, request: Mapping[str, object]) -> bool:
        """Reuses the SAME witness checks :meth:`_atoms_in_file`/
        :meth:`_call_graph_capability` already perform (GDP-10: one
        staleness definition, not a second one for the pre-check)."""
        if capability_id == CAPABILITY_ATOMS_IN_FILE:
            relative_paths = self._relative_files_in_scope()
            if relative_paths is None:
                # Not a staleness question at all (root does not resolve
                # under this graph's scope) -- the normal resolve() path
                # reports this exact condition; regenerating cannot fix it.
                return False
            return any(not self._is_fresh(r) for r in relative_paths)
        if capability_id in (CAPABILITY_CALLERS_OF, CAPABILITY_NEVER_WIRED):
            return self._whole_tree_staleness() is not None
        return False

    def _regenerate_and_recheck(
        self, capability_id: str, request: Mapping[str, object]
    ) -> Failed | None:
        """The critical section: acquire the per-graph lock, regenerate
        (unless another process already fixed it while this one waited),
        reload from disk, and confirm freshness -- all synchronously,
        under ONE lock hold, so a caller either gets a fresh answer or an
        honest ``Failed``, never a torn read of a graph mid-rewrite."""
        assert self._out_dir is not None
        executable = shutil.which(_GRAPHIFY_EXECUTABLE_NAME)
        if executable is None:
            return self._provider_error(
                f"stale graph and '{_GRAPHIFY_EXECUTABLE_NAME}' is not on "
                "PATH -- cannot regenerate synchronously"
            )
        lock_path = self._out_dir / _REGEN_LOCK_FILE_NAME
        with open(lock_path, "a", encoding="utf-8") as lock_handle:
            if _HAS_FCNTL:
                fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
            try:
                # Re-check AFTER acquiring the lock: a concurrent caller
                # that got here first may have already regenerated while
                # this process waited -- do not redo that work (the
                # coalescing property).
                self._reload_from_disk()
                if not self._is_stale_for(capability_id, request):
                    return None
                failure_detail = self._run_graphify_update(executable)
                if failure_detail is not None:
                    return self._provider_error(failure_detail)
                self._reload_from_disk()
                if self._is_stale_for(capability_id, request):
                    return self._provider_error(
                        "graphify update completed but this request is "
                        "still stale afterward"
                    )
                return None
            finally:
                if _HAS_FCNTL:
                    fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    def _run_graphify_update(self, executable: str) -> str | None:
        """Runs ``graphify update <scope_root>`` (re-extracts code files,
        no LLM needed -- verified against the real binary). ``None`` on
        success; a failure-detail string otherwise. Bounded by
        ``des.runtime.spawn``'s own generous, operator-overridable default
        tier (the RUN ceiling) rather than a bespoke timeout -- this
        repo's own measured order of magnitude (~80s incremental over
        1,031 files) is well inside it; a from-scratch extraction on a
        much larger tree still has room.

        ``shutil.which`` can legitimately resolve a Python CLI (a console
        script with no native launcher, or this repo's own test stand-in
        under Windows ``PATHEXT``) whose file itself is not directly
        executable by the OS loader on every platform -- a ``.py`` file has
        no POSIX exec bit convention and no Windows PE header. When the
        resolved executable carries that suffix, the interpreter that
        resolved it (``sys.executable``) is prepended so the SAME resolved
        path launches correctly everywhere; a real console-script ``.exe``
        or a POSIX shebang binary is launched exactly as before, unchanged.
        """
        assert self._out_dir is not None
        scope_root = self._out_dir.parent
        argv = (
            [sys.executable, executable, _GRAPHIFY_UPDATE_SUBCOMMAND, str(scope_root)]
            if executable.lower().endswith(".py")
            else [executable, _GRAPHIFY_UPDATE_SUBCOMMAND, str(scope_root)]
        )
        try:
            result = spawn(
                argv,
                capture_output=True,
                text=True,
            )
        except SpawnTimeout as exc:
            return str(exc)
        except OSError as exc:
            return f"failed to start '{executable} update {scope_root}': {exc}"
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip()
            return (
                f"'{executable} update {scope_root}' exited "
                f"{result.returncode}: {detail}"
            )
        return None

    def _reload_from_disk(self) -> None:
        """Re-reads ``graph.json``/``manifest.json`` from disk into
        ``self._graph``/``self._manifest``. On a read/parse fault the
        PREVIOUS in-memory data is kept (never cleared to ``None`` here:
        that would make ``has_data`` flip false mid-query) -- the
        subsequent staleness re-check then correctly reports "still
        stale" and the caller degrades LOUD, rather than this method
        silently discarding a good graph over a transient read glitch."""
        assert self._out_dir is not None
        graph = _load_json_object(self._out_dir / _GRAPH_FILE_NAME)
        manifest = _load_json_object(self._out_dir / _MANIFEST_FILE_NAME)
        if graph is not None and manifest is not None:
            self._graph = graph
            self._manifest = manifest
            self._operation_owner._graph = graph
            self._operation_owner._manifest = manifest
            for view in self._operation_state["views"]:
                view._graph = graph
                view._manifest = manifest

    # -- capability realizations --------------------------------------------

    def _call_graph_capability(
        self, capability_id: str, request: Mapping[str, object]
    ) -> Answered | Failed:
        """Shared realization for ``callers-of``/``never-wired`` — both read
        the SAME ``calls``-edge data, one as presence, one as absence
        (mirrors ``AstAdapter._sites_of``/``_never_wired`` reusing
        ``_call_sites``: one dataset, two envelope shapes)."""
        staleness = self._whole_tree_staleness()
        if staleness is not None:
            return self._provider_error(staleness)
        symbol = self._symbol_of(request)
        callable_name = self._callable_of(symbol)
        sites = self._call_sites(callable_name)
        if capability_id == CAPABILITY_NEVER_WIRED:
            payload: dict[str, object] = {
                "symbol": symbol,
                "never_wired": not sites,
                "call_sites": sites,
            }
        else:
            payload = {"symbol": symbol, "sites": sites}
        return self._answer(payload)

    def _atoms_in_file(self) -> Answered | Failed:
        relative_paths = self._relative_files_in_scope()
        if relative_paths is None:
            return self._provider_error(
                f"{self._root} does not resolve under the located "
                f"graphify-out scope {self._out_dir}, or the graph names "
                "no file under it"
            )
        return self._answer_atoms(relative_paths)

    def _answer_atoms(self, relative_paths: frozenset[str]) -> Answered | Failed:
        for relative in sorted(relative_paths):
            if not self._is_fresh(relative):
                return self._provider_error(
                    f"stale graph data for {relative} (file modified since "
                    "the graph was materialized)"
                )
        assert self._graph is not None
        nodes = self._graph.get("nodes", [])
        basenames = {Path(path).name for path in relative_paths}
        candidates = relative_paths | basenames
        atoms = sorted(
            {
                str(node["label"])
                for node in nodes
                if isinstance(node, dict)
                and node.get("source_file") in candidates
                and node.get("label")
            }
        )
        return self._answer({"atoms": atoms, "unparseable": False})

    def _call_sites(self, callable_name: str) -> list[str]:
        """Every ``"<file>:<line>"`` site of a ``calls`` edge, at
        ``confidence == "EXTRACTED"`` only, whose resolved target node's
        ``label`` names ``callable_name`` (bare or trailing-dotted, same
        ``AstAdapter._callee_matches`` convention). ``INFERRED``-confidence
        ``calls`` edges and ``indirect_call`` edges are never counted here
        (module docstring: LA1-L6 no-inflation)."""
        if not callable_name:
            return []
        assert self._graph is not None and self._out_dir is not None
        node_labels = {
            node.get("id"): node.get("label")
            for node in self._graph.get("nodes", [])
            if isinstance(node, dict)
        }
        scope_root = self._out_dir.parent
        sites: list[str] = []
        edges = self._graph.get("links")
        if edges is None:
            edges = self._graph.get("edges", [])
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            if edge.get("relation") != _CALLS_RELATION:
                continue
            if edge.get("confidence") != _EXTRACTED:
                continue
            target_label = node_labels.get(edge.get("target"))
            if not isinstance(target_label, str) or not self._callee_matches(
                target_label, callable_name
            ):
                continue
            source_file = edge.get("source_file")
            if not isinstance(source_file, str) or not source_file:
                continue
            location = edge.get("source_location")
            line = (
                location[1:]
                if isinstance(location, str) and location.startswith("L")
                else location or ""
            )
            sites.append(f"{scope_root / source_file}:{line}")
        return sites

    def _whole_tree_staleness(self) -> str | None:
        """``None`` when every currently-existing Python file under
        ``self._root`` has a fresh manifest entry; otherwise the detail
        string for a ``provider-error`` (module docstring: whole-tree
        completeness for ``callers-of``/``never-wired`` -- a caller in a
        file graphify never scanned would otherwise be silently invisible,
        turning an honest "could not verify" into a false "never wired")."""
        assert self._out_dir is not None
        scope_root = self._out_dir.parent
        for live_file in TreeScope(self._root).files(_PYTHON_SOURCE_GLOB):
            try:
                relative = (
                    live_file.resolve().relative_to(scope_root.resolve()).as_posix()
                )
            except ValueError:
                return f"{live_file} does not resolve under the graphify-out scope {self._out_dir}"
            if not self._is_fresh(relative):
                return (
                    f"stale or unscanned graph data for {relative} (file added "
                    "or modified since the graph was materialized)"
                )
        return None

    @staticmethod
    def _callee_matches(callee: str, callable_name: str) -> bool:
        """True iff a resolved callee name names ``callable_name`` (bare or
        dotted) -- identical convention to ``AstAdapter._callee_matches``.
        Real graphify emits callable labels with a trailing ``()``
        call-suffix (``"target()"``); exactly one such suffix is stripped
        before comparison so a bare/dotted request matches the real
        label."""
        if callee.endswith("()"):
            callee = callee[:-2]
        return callee == callable_name or callee.endswith(f".{callable_name}")

    @staticmethod
    def _callable_of(symbol: str) -> str:
        """The trailing callable name of an ``Owner.method`` symbol --
        identical convention to ``AstAdapter._callable_of``."""
        return symbol.rsplit(".", maxsplit=1)[-1] if symbol else ""

    @staticmethod
    def _symbol_of(request: Mapping[str, object]) -> str:
        """The symbol/anchor the request targets -- identical convention to
        ``AstAdapter._symbol_of``."""
        for key in ("symbol", "anchor", "name"):
            value = request.get(key)
            if isinstance(value, str) and value:
                return value
        return ""

    def _answer(self, payload: dict[str, object]) -> Answered:
        """Wrap a capability payload in the uniform ``Answered`` envelope
        at this tier's declared ``binding-resolved`` confidence."""
        return Answered(
            provider_id=self.provider_id,
            confidence=self.confidence,
            payload=CodeFactResult(
                provider=self.provider, confidence=self.confidence, payload=payload
            ),
            trace=(
                TraceEntry(
                    provider_id=self.provider_id,
                    event="answered",
                    scope="complete",
                    fault_count=0,
                    exemplars=(),
                    detail="",
                ),
            ),
        )

    # -- witness + scoping ---------------------------------------------------

    def _relative_files_in_scope(self) -> frozenset[str] | None:
        """Every graph-known ``source_file`` this query's ``self._root``
        scopes to, POSIX-relative to the graphify-out's own scope root.

        ``self._root`` is either a single FILE (the established ``atoms-
        in-file`` convention -- one file, one answer) or a DIRECTORY
        (aggregate every graph-known file at or under it, mirroring
        ``AstAdapter``'s own whole-tree ``_atoms`` shape). ``None`` when
        ``self._root`` does not resolve under the located scope at all,
        or (directory case) the graph names no file under it."""
        assert self._out_dir is not None and self._graph is not None
        scope_root = self._out_dir.parent
        try:
            root_relative = (
                self._root.resolve().relative_to(scope_root.resolve()).as_posix()
            )
        except ValueError:
            return None
        if self._root.is_file():
            return frozenset({root_relative})
        prefix = "" if root_relative == "." else f"{root_relative}/"
        known = frozenset(
            node["source_file"]
            for node in self._graph.get("nodes", [])
            if isinstance(node, dict)
            and isinstance(node.get("source_file"), str)
            and node["source_file"]
            and (
                root_relative == "."
                or node["source_file"] == root_relative
                or node["source_file"].startswith(prefix)
            )
        )
        return known or None

    def _is_fresh(self, relative: str) -> bool:
        """LA1-L7 witness check: the manifest's recorded ``mtime`` for
        ``relative`` (matched by full relative path, falling back to the
        bare basename — graphify's own manifest key convention varies by
        invocation scope) must equal the file's CURRENT mtime, exactly.
        A missing/malformed manifest entry, or a file that no longer
        exists at all, is honestly ``False`` — never assumed fresh."""
        assert self._manifest is not None and self._out_dir is not None
        entry = self._manifest.get(relative) or self._manifest.get(Path(relative).name)
        if not isinstance(entry, dict):
            return False
        recorded_mtime = entry.get("mtime")
        if not isinstance(recorded_mtime, (int, float)):
            return False
        absolute = self._out_dir.parent / relative
        try:
            current_mtime = absolute.stat().st_mtime
        except OSError:
            return False
        return current_mtime == recorded_mtime

    def _provider_error(self, detail: str) -> Failed:
        return Failed(
            cause="provider-error",
            trace=(
                TraceEntry(
                    provider_id=self.provider_id,
                    event="failed:provider-error",
                    scope="complete",
                    fault_count=0,
                    exemplars=(),
                    detail=detail[:200],
                ),
            ),
        )
