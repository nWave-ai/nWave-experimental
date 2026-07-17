"""des-run-contract-gate -- the single canonical ATDD-pure contract gate.

slice-14 of the atdd-pure-roadmap-free-rollout (RCA Gate 2, closes Branch B).

`run_contract_gate.py` IS the canonical ATDD-pure commit gate. It has two
roles, so the terminating crafter run, the pre-commit wrapper, and CI all
invoke ONE definition -- verification scope can no longer be a proper subset
of the contract:

  (a) RUN -- the default mode runs
      `pytest -m "unit or integration or acceptance"` over the WHOLE tree
      (the exact pre-push scope, NOT a crafter-picked subset) and emits a
      machine-readable pass/fail plus a `gate_scope_digest`.
  (b) DIGEST / VERIFY -- `--collect-only --print-digest` derives the
      `gate_scope_digest` without running the suite; `--verify-gate-scope`
      reads a commit's `Gate-Scope:` trailer and compares it against a fresh
      `--collect-only` digest, so the `G_COMMIT` exit gate can refuse a commit
      whose verification scope does not match the contract.

The `gate_scope_digest` is the SHA-256 of the sorted, newline-joined set of
collected test node-ids -- a stable fingerprint of "which tests the contract
gate covers".

stdlib + pytest only.

Exit codes:
    0 = the requested role succeeded (suite passed / digest printed /
        gate-scope verified).
    1 = the contract suite FAILED, OR `--verify-gate-scope` found the
        commit's `Gate-Scope:` digest absent or mismatching.
    2 = malformed input (repo / commit unreadable, collection failed).

Reference: docs/feature/atdd-pure-roadmap-free-rollout/feature-delta.md
           # slice-14 design note (E2).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.git.committed_scope_adapter import GitCommittedScopeAdapter
from des.adapters.driven.git.git_subprocess import git_text as _git
from des.adapters.driven.output.stdout_output import StdoutOutput
from des.adapters.driven.runner.pytest_runner import (
    pytest_interpreter,
    run_timeout_seconds,
)
from des.adapters.driven.runner.reentrancy_guard import (
    is_routing_active_for,
    routing_active_for,
)
from des.adapters.driven.runner.runner_json import read_runner_json
from des.adapters.driven.runner.runner_registry import (
    GLOBAL_REGISTRY,
    seed_runner_registry,
)
from des.cli.carpaccio_slice_gate import _feature_tag_files
from des.cli.human_surface import Verdict, print_human_summary
from des.domain.slice_id_trailer import SLICE_TAG_RE
from des.ports.driven_ports.committed_scope_port import (
    CommittedFileSet,
    Indeterminate,
)
from des.ports.test_runner_port import (
    RunnerAdapter,
    RunnerAdapterUnavailable,
    RunnerResolutionContext,
    UnrecognizedRunner,
)
from des.ports.test_runner_port import resolve as resolve_runner
from des.runtime.interpreter import (
    InterpreterUnavailable,
    can_import,
)


if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator, Sequence

    from des.ports.driven_ports.output_port import OutputPort


# The LOUD health event emitted when the committed-scope mode cannot establish
# the committed contract suite (git absent / not a work-tree / SHA unresolvable).
# Degrade-LOUD contract (`feedback_oss_acl_published_language_cross_tier_2026_05_31`):
# never a silent fall-back to the working tree.
_COMMITTED_SCOPE_INDETERMINATE_EVENT = "health.gate.committed-scope.indeterminate"

# The LOUD health event emitted when the feature-scoped gate cannot resolve a
# pytest-capable interpreter on the target machine (a non-Python target). The
# degrade-LOUD-and-PROCEED counterpart of the committed-scope INDETERMINATE
# marker (mirrors `_warn_committed_scope_indeterminate` @825): rather than
# hard-refusing (exit 2 via `_emit_interpreter_unavailable`), the gate emits this
# marker and returns the dedicated INDETERMINATE exit code so the caller
# (`verify-slice-commit`) records an honest `SliceCommitIndeterminate` instead of
# wedging the non-Python slice chain. Never coerced to a PASS (exit 0).
_INTERPRETER_UNAVAILABLE_INDETERMINATE_EVENT = (
    "health.gate.interpreter-unavailable.indeterminate"
)

# The gate's INDETERMINATE exit code -- distinct from 0 (cleared), 1 (refused),
# and 2 (hard-refuse / malformed). The caller maps this single code to the
# honest INDETERMINATE record; a non-Python target degrades LOUD here.
_GATE_INDETERMINATE_EXIT_CODE = 3


# The FULL-SUITE marker expression -- the exact pre-push scope
# (.pre-commit-config.yaml). NOT a crafter-picked subset.
#
# slice-05 / C10 allocation (§V.B): this marker is the FEATURE-END full-suite
# scope, run ONCE at feature-end -- NOT at every commit-slice. The per-commit
# -slice gate path runs the entering slice's ATs ONLY (``run_slice_ats``, the
# ATs@slice allocation), or the collect-only digest (``--collect-only`` /
# ``--verify-gate-scope``); it does NOT execute this whole-tree marker. The
# marker is referenced ONLY by ``_full_suite_marker_args`` (the feature-end
# full-suite argv builder), so the per-slice RUN functions never wire it.
_FULL_SUITE_MARKER = "unit or integration or acceptance"

_GATE_SCOPE_TRAILER_RE = re.compile(r"^Gate-Scope:\s*([0-9a-f]{64})\s*$")

# A Gherkin `@slice-NN` tag -- the carpaccio slice scoping anchor (DDD-5).
# Imported from the domain SSOT (fix-slice-id-grammar-drift-ssot) so a
# letter-suffixed `@slice-04a` (an `@coupled` split) is matched identically
# to a plain `@slice-NN`, not silently dropped.
_SLICE_TAG_RE = SLICE_TAG_RE

# The child-worker marker-line protocol (see des.cli._collect_scope_worker).
# The worker runs pytest's in-process collection API in a FRESH interpreter so
# the gate never nests `pytest.main()` inside an outer pytest session.
_COLLECT_RESULT_PREFIX = "NWAVE_COLLECT_SCOPE:"
_COLLECT_ERROR_PREFIX = "NWAVE_COLLECT_SCOPE_ERROR:"

#: Wall-clock bound for the collect-scope worker subprocess. A pytest
#: ``--collect-only`` over any real tree completes in seconds; a run that
#: exceeds this is a hanging / recursive collect (ZERO DEFECTS: a spawned
#: subprocess must NEVER be able to block the gate — and the whole test suite —
#: forever). On expiry the gate fails LOUD via ``_CollectionError`` (the existing
#: fail-closed contract), never silently.
_COLLECT_TIMEOUT_SECONDS = 180


# The worker's `--run` branch marker (the arch-invariant collect-AND-RUN path).
# DISTINCT from the collect-only markers: the run branch reports the run outcome
# (`pytest_exit_code` + `collected_count`), never node-ids.
_RUN_RESULT_PREFIX = "NWAVE_RUN_SCOPE:"

# pytest's `--collect-only -q` summary line reports the collected count as
# `<collected> tests collected` or `<collected>/<total> tests collected`.
# The gate's OWN collection no longer parses stdout (it reads session.items
# in-process via the worker); this stays a self-contained stdout-summary parser
# for callers that anchor a synthetic-fixture's raw `-q` collect signature
# (the spine-dogfood-defects regression fixtures depend on it).
_COLLECTED_COUNT_RE = re.compile(r"^(\d+)(?:/\d+)?\s+tests? collected\b")


def _emit(payload: dict[str, object], output: OutputPort | None = None) -> None:
    """Emit exactly one single-line JSON object.

    When ``output`` is supplied (the in-process exemplar path), the line is routed
    through the injected ``OutputPort``; otherwise it is printed byte-identically
    to ``sys.stdout`` (zero behaviour change for the existing call sites).
    """
    line = json.dumps(payload)
    if output is not None:
        output.emit_line(line)
        return
    print(line)


@dataclass(frozen=True)
class _CollectedScope:
    """The canonical collected scope, captured from pytest's in-process session.

    Two cardinalities from the SAME collection (ADR-001):

    * ``node_ids`` -- the sorted, deduplicated canonical identities. Each
      identity is the repo-relative fspath joined to the item's full ``parent``
      class-chain (``fspath::Class::...::method``, parametrize id INCLUDED), so
      two genuinely-distinct tests are never collapsed -- in particular sibling
      test classes in one file that share a method name stay distinct (the bare
      ``item.name`` would collapse them, undercounting the scope).
    * ``collected_count`` -- ``len(session.items)``: pytest's OWN count of
      collected items from that same session, BEFORE the canonical-identity
      dedupe. With the class-aware identity the gap between this and
      ``len(node_ids)`` is just the hypothesis-rerun duplicate set -- the only
      legitimate collapse.
    """

    node_ids: list[str]
    collected_count: int
    modify_count: int = 0


class _UnsetMarkers:
    """Sentinel: the ``markers`` kwarg was omitted (DDD-CERT-3).

    Distinguishes "caller did not override the marker expression" (the
    default -- the worker applies its own ``_CONTRACT_MARKER``, today's
    behavior byte-for-byte) from an EXPLICIT ``markers=None`` (the
    marker-agnostic secondary collect: no ``-m`` filter at all).
    """


_MARKERS_UNSET = _UnsetMarkers()


def _collect_node_ids(
    repo: Path,
    paths: list[Path] | None = None,
    markers: str | None | _UnsetMarkers = _MARKERS_UNSET,
) -> list[str]:
    """Collect the contract suite's canonical node-ids without running them.

    Thin compatibility seam over `_collect_scope` (DDD-12 -- still the single
    collection seam): returns only the canonical identity list. Callers that
    also need pytest's in-process collected count call `_collect_scope`.

    ``markers`` (DDD-CERT-3, certification-legs-observe-real-execution
    slice-02): omitted -> today's marker-filtered collect, unchanged. An
    explicit ``None`` -> the marker-agnostic secondary collect (no ``-m``
    filter).
    """
    return _collect_scope(repo, paths, markers=markers).node_ids


_COLLECT_MEMO: dict[tuple[str, tuple[str, ...], str | None], _CollectedScope] = {}


def _collect_scope(
    repo: Path,
    paths: list[Path] | None = None,
    markers: str | None | _UnsetMarkers = _MARKERS_UNSET,
) -> _CollectedScope:
    """Memoizing wrapper over ``_collect_scope_uncached`` (velocity-v2, <5min G-143).

    Under ``NWAVE_COLLECT_MEMO`` (set ONLY by the test conftest) the collect of the
    REAL repo tree -- immutable during a test session -- is memoized, so across a
    serial run every dir that collects the whole ~1677-test suite pays the ~22s cost
    ONCE instead of once-per-dir. Synthetic tmp trees (per-test, possibly mutated) are
    NEVER memoized -- only a non-temp repo is, keyed by (resolved-repo, paths, markers).
    Production (no env var) is an exact pass-through: zero behavior change, no cache.
    """
    if os.environ.get("NWAVE_COLLECT_MEMO"):
        resolved = str(repo.resolve())
        if not resolved.startswith(tempfile.gettempdir()):
            markers_key = None if isinstance(markers, _UnsetMarkers) else markers
            key = (
                resolved,
                tuple(sorted(str(p) for p in (paths or []))),
                markers_key,
            )
            if key not in _COLLECT_MEMO:
                _COLLECT_MEMO[key] = _collect_scope_uncached_dispatch(
                    repo, paths, markers
                )
            return _COLLECT_MEMO[key]
    return _collect_scope_uncached_dispatch(repo, paths, markers)


def _collect_scope_uncached_dispatch(
    repo: Path, paths: list[Path] | None, markers: str | None | _UnsetMarkers
) -> _CollectedScope:
    """Call ``_collect_scope_uncached``, preserving the OLD signature on the
    default (unset-markers) path (DDD-CERT-3).

    The design mandate is "the default call is byte-for-byte identical to
    before". When ``markers`` is unset, call with the OLD ``(repo, paths)``
    signature -- NO ``markers`` kwarg -- so an existing test-double that stubs
    ``_collect_scope_uncached`` with the old signature still works. Only pass
    ``markers=`` when it is EXPLICITLY set.
    """
    if isinstance(markers, _UnsetMarkers):
        return _collect_scope_uncached(repo, paths)
    return _collect_scope_uncached(repo, paths, markers=markers)


def _light_collect_env() -> dict[str, str] | None:
    """Env for the collect worker (velocity-v2, <5min G-143).

    Under ``NWAVE_COLLECT_MEMO`` (set ONLY by the test conftest) disable the slow
    NON-collection plugins (cov / hypothesis / randomly) via ``PYTEST_ADDOPTS`` --
    they do not affect the collected SET, so the contract-gate digest is IDENTICAL
    (verified 77a0326e), a pure speedup and never a lying-fast shrink. Production
    (no env var) returns ``None`` -> the subprocess inherits the parent env unchanged.
    """
    if not os.environ.get("NWAVE_COLLECT_MEMO"):
        return None
    env = os.environ.copy()
    light = "-p no:cov -p no:hypothesis -p no:randomly"
    existing = env.get("PYTEST_ADDOPTS", "")
    env["PYTEST_ADDOPTS"] = f"{existing} {light}".strip()
    return env


def _collect_scope_uncached(
    repo: Path,
    paths: list[Path] | None = None,
    markers: str | None | _UnsetMarkers = _MARKERS_UNSET,
) -> _CollectedScope:
    """Derive the canonical collected scope from pytest's IN-PROCESS session.

    The digest input comes from pytest's IN-PROCESS collection API
    (``session.items``), NOT from parsing the collapse-prone ``-q`` collect
    STDOUT (stock ``-q`` emits byte-identical docstring summary lines for
    parametrize / pytest-bdd families; parsing that silently undercounts).
    ``session.items`` keeps every collected item distinct, identified by the
    canonical class-aware ``fspath::Class::...::method`` (parametrize id
    included; see ``_identity_of`` in the worker).

    The ``pytest.main()`` collection runs inside the short-lived child worker
    ``_collect_scope_worker.py`` (a fresh interpreter), NOT in THIS process.
    The gate's ``main`` / ``gate_scope_digest`` are also called directly
    in-process by other tests inside a live pytest session -- running
    ``pytest.main()`` there would nest a session inside a session and corrupt
    both. Hoisting the collection into a child keeps it robust regardless of
    the caller's context AND keeps the gate's own stdout clean (pytest's
    collection chatter stays in the child's discarded stderr -- the idempotence
    contract). This is the ADR-001 Earned-Trust isolation boundary made
    structural rather than assumed.

    The worker is spawned by FILE PATH (``<python> <worker-path> --repo ...``),
    never as a ``des.cli`` import module: an installed customer tree has no
    ``des`` package importable by an arbitrary interpreter
    (F-DES-RUNTIME-INTERPRETER-BOUNDARY -- the import-module spawn form is
    forbidden at runtime). The worker imports only stdlib + pytest, so the
    bare-script form needs no ``des`` on ``sys.path``.

    When ``paths`` is given, collection is narrowed to exactly those filesystem
    paths (the ``--feature-id`` feature scope); the whole-tree default applies
    when it is ``None``. This is the one seam that owns the pytest argv
    (DDD-12), so feature-scoped collection adds NO third call site.

    The worker interpreter is resolved through ``pytest_interpreter()`` -- the
    pytest run-facet boundary (``des.adapters.driven.runner.pytest_runner``),
    NOT an inline ``python_for`` call in gate logic: the python-hardcode lives
    behind the runner-adapter boundary (the genericità mandate), and the F-21
    boundary contract still holds -- if no candidate can import pytest,
    ``InterpreterUnavailable`` is raised rather than a bare
    ``ModuleNotFoundError`` surfacing one frame later.

    Fails closed (raises `_CollectionError`) when the collection is
    untrustworthy: a non-(0,5) pytest exit is a collection error, and a
    populated session whose canonical identities are empty is the vacuous-digest
    defect.
    """
    interpreter = pytest_interpreter()
    worker = Path(__file__).with_name("_collect_scope_worker.py")
    worker_env = _light_collect_env()
    try:
        completed = subprocess.run(
            [
                interpreter,
                str(worker),
                "--repo",
                str(repo),
                *_path_args(paths),
                *_markers_args(markers),
            ],
            capture_output=True,
            text=True,
            timeout=_COLLECT_TIMEOUT_SECONDS,
            env=worker_env,
        )
    except subprocess.TimeoutExpired as exc:
        # ZERO DEFECTS: the collect worker must never block forever. A collect
        # that exceeds the wall-clock bound (a hang, or a recursive collect that
        # re-enters the gate over the real tree) is an untrustworthy collection
        # -- fail LOUD (the fail-closed contract) instead of hanging the caller
        # and the whole test suite.
        raw_stderr = exc.stderr
        stderr_tail = (
            raw_stderr.decode("utf-8", "replace")
            if isinstance(raw_stderr, bytes)
            else (raw_stderr or "")
        )
        raise _CollectionError(
            f"pytest collection did not complete within "
            f"{_COLLECT_TIMEOUT_SECONDS}s (a hanging or recursive collect); "
            f"stderr: {stderr_tail.strip()[:500]}"
        ) from exc
    payload = _parse_worker_line(completed.stdout, _COLLECT_RESULT_PREFIX)
    error = _parse_worker_line(completed.stdout, _COLLECT_ERROR_PREFIX)
    if error is not None:
        # KPI-3: thread the crashing module the worker named (the first failed
        # collector's nodeid) onto the error so the gate can NAME it in the
        # MalformedInput payload rather than only reporting the bare exit code.
        raw_module = error.get("crashing_module")
        crashing_module = (
            raw_module if isinstance(raw_module, str) and raw_module else None
        )
        raise _CollectionError(
            f"pytest collection exited {error.get('pytest_exit_code')}",
            crashing_module=crashing_module,
        )
    if payload is None:
        raise _CollectionError(
            "the contract-scope worker emitted no result line "
            f"(exit {completed.returncode}): {completed.stderr.strip()[:500]}"
        )
    raw_ids = payload.get("node_ids", [])
    identities = (
        [str(node_id) for node_id in raw_ids] if isinstance(raw_ids, list) else []
    )
    raw_count = payload.get("collected_count", 0)
    collected_count = int(raw_count) if isinstance(raw_count, int) else 0
    raw_modify = payload.get("modify_count", 0)
    modify_count = int(raw_modify) if isinstance(raw_modify, int) else 0
    if modify_count > 0 and collected_count == 0:
        # Two-signal lying-tree detection (ADR-001): the suite was populated
        # one lifecycle phase upstream (`pytest_collection_modifyitems`) but
        # reported zero items at collection finish. A tamper that empties
        # `session.items` in a `tryfirst pytest_collection_finish` hook fires
        # strictly later than `modifyitems`, so it cannot forge `modify_count`
        # back to zero. An emptied-at-finish session is indistinguishable from
        # a genuinely-empty one by `collected_count` alone -- this guard fails
        # closed rather than fingerprint the suppressed scope. Living inside
        # `_collect_scope` means EVERY caller (verify, print-digest, default)
        # gets it, including the G_COMMIT exit-gate `--verify-gate-scope` path.
        raise _CollectionError(
            "pytest collected a populated contract suite "
            f"({modify_count} items at modifyitems) but reported zero items at "
            "collection finish -- the collected scope was suppressed; refusing "
            "to fingerprint a lying tree"
        )
    if not identities and collected_count > 0:
        # The session collected items but produced zero canonical identities --
        # the scope cannot be trusted. Fail closed, never vacuously pass.
        raise _CollectionError(
            "pytest reported a populated contract suite but zero canonical "
            "identities were captured -- the collection could not be trusted"
        )
    return _CollectedScope(
        node_ids=sorted(set(identities)),
        collected_count=collected_count,
        modify_count=modify_count,
    )


def _path_args(paths: list[Path] | None) -> list[str]:
    """Render the worker's repeated ``--path`` arguments for ``paths``."""
    if not paths:
        return []
    rendered: list[str] = []
    for path in paths:
        rendered.extend(["--path", str(path)])
    return rendered


def _markers_args(markers: str | None | _UnsetMarkers) -> list[str]:
    """Render the worker's optional ``--markers`` override (DDD-CERT-3).

    Unset (the default) omits ``--markers`` entirely -- the worker applies its
    own ``_CONTRACT_MARKER`` default, today's marker-filtered call preserved
    byte-for-byte. An explicit ``None`` renders ``--markers ""`` (empty string
    -> no ``-m`` filter at all, the marker-agnostic secondary collect). An
    explicit non-empty string overrides the marker expression outright.
    """
    if isinstance(markers, _UnsetMarkers):
        return []
    return ["--markers", markers or ""]


def _parse_worker_line(stdout: str, prefix: str) -> dict[str, object] | None:
    """Return the JSON payload of the worker's ``prefix`` marker line, if any."""
    for line in stdout.splitlines():
        if line.startswith(prefix):
            parsed: dict[str, object] = json.loads(line[len(prefix) :])
            return parsed
    return None


@dataclass(frozen=True)
class _ArchVerdict:
    """The outcome of RUNNING the architecture-invariant set (collect-AND-RUN).

    * ``collected`` -- how many arch-invariant node-ids the worker RAN. Zero is
      the M-1-floor degrade-LOUD signal (the arch glob matched files but none
      carried the contract marker, so the arch tier ran vacuously).
    * ``passed`` -- whether the arch run was GREEN (pytest exit 0 or 5). A RED
      arch run is the keystone refusal: a run-time arch invariant FAILED.
    * ``failed_node_ids`` -- the nodeids of the FAILED arch tests (setup error
      or call failure), so a refusal NAMES the violated invariant rather than
      reporting only a bare pytest exit code. Empty on a GREEN run and when an
      older worker payload carries no ``failed_node_ids`` key.
    """

    collected: int
    passed: bool
    failed_node_ids: tuple[str, ...] = ()


def _arch_invariant_paths(repo: Path) -> list[Path]:
    """Resolve the architecture-invariant set as the ``tests/build/**`` glob.

    Pure function (return-only, DDD-4): reads the filesystem, returns paths,
    mutates nothing. The arch set is OQ-1-ratified for slice-01 as the
    ``tests/build`` directory (the F-D-09 forbidden-roots gate + the
    inline-interpreter-spawn ban live there). It is read as DATA -- the paths
    are handed to pytest; this resolver never ``import``s from ``tests`` (no
    F-D-09 import-graph violation). The arch set is the SAME for every feature
    (a global invariant), so it is feature-independent.

    Returns the single ``tests/build`` directory when it exists, else an empty
    list. An EMPTY arch set CLEARS (genericità mandate): the ``--feature-id``
    gate runs on the TARGET repo during DELIVER, and an external target
    legitimately carries no nWave arch tier -- with no arch tier there is no arch
    invariant to enforce, so the caller falls through and clears on the feature
    scope alone. Only a PRESENT-but-vacuous arch tier is malformed (slice-02's
    ``arch-scope-zero-collected`` floor).
    """
    build_dir = repo / "tests" / "build"
    if build_dir.is_dir():
        return [build_dir]
    return []


def _resolve_arch_run_interpreter() -> str:
    """Resolve the arch-invariant RUN worker's interpreter (F-21-safe).

    Short-circuits the subprocess-probed ``pytest_interpreter()`` boundary
    (which spawns a throwaway process per candidate rung -- ``_uv_python()``
    unconditionally, then ``_has_capability`` per rung) when THIS process has
    already imported pytest: ``import pytest`` succeeded HERE, in
    ``sys.executable`` -- a child spawned with the SAME interpreter binary
    inherits the identical site-packages, so this is a zero-subprocess-call
    proof of capability, not a name-trust shortcut (F-21 stays satisfied: a
    candidate is never trusted by NAME alone, only by a verified fact about
    the exact binary being resolved). Falls back to the full probed boundary
    when this process is not itself running under pytest (e.g. a real ``des
    commit-slice`` CLI invocation) -- unchanged production behaviour.
    """
    if "pytest" in sys.modules:
        return sys.executable
    return pytest_interpreter()


def _can_import_xdist_in_process() -> bool:
    """In-process ``xdist`` importability probe -- zero subprocess calls."""
    try:
        return importlib.util.find_spec("xdist") is not None
    except (ImportError, ValueError):
        return False


def _resolve_arch_run_parallel_args(repo: Path, interpreter: str) -> list[str]:
    """The arch-invariant RUN's parallel argv fragment (mirrors ``_parallel_pytest_args``).

    Short-circuits the subprocess-probed ``can_import(interpreter, "xdist")``
    when ``interpreter`` IS this process's own ``sys.executable``: an
    in-process ``import xdist`` answers the identical question with zero
    subprocess calls. Falls back to the probed boundary for any OTHER
    interpreter (unchanged behaviour). This is a LOCAL mirror scoped to the
    arch-invariant RUN only -- ``_parallel_pytest_args`` (the full-suite leg's
    resolution) is untouched.
    """
    requested = _resolve_gate_jobs(repo)
    if requested.lower() in _SERIAL_TOKENS:
        return []

    xdist_available = (
        _can_import_xdist_in_process()
        if interpreter == sys.executable
        else can_import(interpreter, "xdist")
    )
    if not xdist_available:
        print(
            "[contract-gate] pytest-xdist not importable in "
            f"{interpreter!r}; running the arch-invariant RUN SERIALLY "
            "(install pytest-xdist for parallel speedup, or set "
            f"{_GATE_JOBS_ENV}=serial to silence this).",
            file=sys.stderr,
        )
        return []

    return ["-n", requested, "--dist", "loadgroup"]


def _run_arch_invariant_set(repo: Path, arch_paths: list[Path]) -> _ArchVerdict:
    """RUN the architecture-invariant set over ``arch_paths`` and map the verdict.

    Routes through the existing ``_collect_scope_worker.py`` seam via its
    ``--run`` branch (DDD-12 -- the single pytest-argv owner; no new spawn site).
    The only effect (running pytest) stays inside the worker subprocess boundary,
    the same isolation as ``_collect_scope``. The worker interpreter is resolved
    through ``pytest_interpreter()`` -- the pytest run-facet boundary (the
    runner-adapter, never an inline ``python_for`` call in gate logic), so the
    F-21 boundary holds and the python-hardcode stays behind the port (never raw
    ``sys.executable``).

    Maps the worker's run-outcome marker line to an ``_ArchVerdict``: pytest exit
    0/5 is GREEN, any other exit is a RED arch run. ``collected_count`` carries
    the M-1-floor signal for a vacuous arch scope; ``failed_node_ids`` names the
    violated invariant(s) on a RED run.

    Parallel-by-default via pytest-xdist when importable (the SAME
    ``gate.jobs`` / ``NWAVE_GATE_JOBS`` resolution the full-suite RUN honours,
    through ``_parallel_pytest_args``): the arch tier is the per-slice quick
    tier, so its wall-clock matters at every slice commit. Serial when the
    operator asked for serial or xdist is absent (the LOUD degrade lives in
    ``_parallel_pytest_args``).

    Interpreter/xdist resolution uses ``_resolve_arch_run_interpreter`` /
    ``_resolve_arch_run_parallel_args`` -- in-process short-circuits of the
    subprocess-probed boundaries (``pytest_interpreter`` / ``can_import``)
    that answer the identical question with ZERO subprocess calls whenever
    this process is itself running under pytest as ``sys.executable`` (see
    their docstrings). This keeps the ONE spawn this function makes (the
    worker RUN below) the ONLY subprocess call on the fast in-process path --
    the resource-aware caller (``build_tier_exit_verdict``) fakes exactly
    that one spawn in its acceptance tests.
    """
    interpreter = _resolve_arch_run_interpreter()
    worker = Path(__file__).with_name("_collect_scope_worker.py")
    parallel = _resolve_arch_run_parallel_args(repo, interpreter)
    jobs_args = ["--jobs", parallel[1]] if parallel else []
    try:
        completed = subprocess.run(
            [
                interpreter,
                str(worker),
                "--run",
                "--repo",
                str(repo),
                *jobs_args,
                *_path_args(arch_paths),
            ],
            capture_output=True,
            text=True,
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise _CollectionError(
            f"the contract-scope RUN did not complete within "
            f"{run_timeout_seconds():.0f}s (a hanging/deadlocking test); raise "
            f"NWAVE_GATE_RUN_TIMEOUT if this is a legitimate long run"
        ) from exc
    payload = _parse_worker_line(completed.stdout, _RUN_RESULT_PREFIX)
    if payload is None:
        # The aborted-run signature (feature-delta gate-runner-resource-aware,
        # slice-01): a worker killed by signal/OOM mid-run never reaches its
        # own result-emitting code, so the missing NWAVE_RUN_SCOPE line IS the
        # starvation signature -- distinct from a genuine collection/run
        # failure. ``_WorkerStarvedError`` subclasses ``_CollectionError`` so
        # every OTHER caller (``_mode_feature_scoped``) keeps its existing
        # generic handling unchanged; ``build_tier_exit_verdict`` catches the
        # subclass FIRST to reclassify it as INDETERMINATE-resource-starvation
        # rather than the red ``BuildTierRefused`` lane (GDP-6).
        raise _WorkerStarvedError(completed.returncode, completed.stderr)
    raw_exit = payload.get("pytest_exit_code", 1)
    pytest_exit = int(raw_exit) if isinstance(raw_exit, int) else 1
    raw_collected = payload.get("collected_count", 0)
    collected = int(raw_collected) if isinstance(raw_collected, int) else 0
    raw_failed = payload.get("failed_node_ids", [])
    failed = (
        tuple(str(node_id) for node_id in raw_failed)
        if isinstance(raw_failed, list)
        else ()
    )
    return _ArchVerdict(
        collected=collected,
        passed=pytest_exit in (0, 5),
        failed_node_ids=failed,
    )


# The honest N/A event the build-tier exit check emits when the target carries
# no ``tests/build`` tier at all (genericita: an external target legitimately
# has no nWave arch tier). Distinct from a pass claim -- it names the absence.
_BUILD_TIER_NOT_APPLICABLE_EVENT = "BuildTierNotApplicable"

# The LOUD degrade marker when the build-tier run cannot resolve a pytest
# interpreter (a non-Python target). The caller PROCEEDS -- the downstream
# committed-scope digest step degrades on the same absence and mints the honest
# SliceCommitIndeterminate record -- but the skip is never silent.
_BUILD_TIER_INDETERMINATE_EVENT = "health.gate.build-tier.indeterminate"


# Pre-launch resource-window thresholds/bounds (feature-delta
# gate-runner-resource-aware, slice-01) -- env-overridable, GDP-7 stdlib-only
# (Python file reads over ``/proc``, zero external tool dependency).
_MIN_MEM_AVAILABLE_MIB_ENV = "NWAVE_BUILD_TIER_MIN_MEM_AVAILABLE_MIB"
_MAX_LOAD1_ENV = "NWAVE_BUILD_TIER_MAX_LOAD1"
_WINDOW_TIMEOUT_SECONDS_ENV = "NWAVE_BUILD_TIER_WINDOW_TIMEOUT_SECONDS"
_WINDOW_POLL_INTERVAL_SECONDS_ENV = "NWAVE_BUILD_TIER_POLL_INTERVAL_SECONDS"

_DEFAULT_MIN_MEM_AVAILABLE_MIB = 700
_DEFAULT_MAX_LOAD1 = 8.0
_DEFAULT_WINDOW_TIMEOUT_SECONDS = 20 * 60.0
_DEFAULT_POLL_INTERVAL_SECONDS = 30.0


def _resolve_float_env(env_name: str, default: float) -> float:
    """Return the float value of ``env_name``, or ``default`` when absent/bad."""
    raw = os.environ.get(env_name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _resolve_int_env(env_name: str, default: int) -> int:
    """Return the int value of ``env_name``, or ``default`` when absent/bad."""
    return int(_resolve_float_env(env_name, float(default)))


def _read_mem_available_mib() -> int | None:
    """Read ``MemAvailable`` from ``/proc/meminfo`` in MiB; ``None`` off-Linux."""
    try:
        with open("/proc/meminfo", encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("MemAvailable:"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        return int(parts[1]) // 1024
    except OSError:
        return None
    return None


def _read_load1() -> float | None:
    """Read the 1-minute load average from ``/proc/loadavg``; ``None`` off-Linux."""
    try:
        with open("/proc/loadavg", encoding="utf-8") as handle:
            first_line = handle.readline()
    except OSError:
        return None
    parts = first_line.split()
    if not parts:
        return None
    try:
        return float(parts[0])
    except ValueError:
        return None


def _read_real_resource_reading() -> tuple[int, float] | None:
    """Read one real ``(mem_available_mib, load1)`` reading; ``None`` off-Linux.

    Both ``/proc`` reads must succeed -- a partial read is treated the same as
    an absent ``/proc`` (degrade-open on the CHECK, GDP-7).
    """
    mem_available_mib = _read_mem_available_mib()
    load1 = _read_load1()
    if mem_available_mib is None or load1 is None:
        return None
    return (mem_available_mib, load1)


def _real_resource_reading_iter(
    timeout_seconds: float, poll_interval_seconds: float
) -> Iterator[tuple[int, float] | None]:
    """Bound the production reading source by the wall-clock window timeout.

    Exhaustion of this generator IS the bound (mirrors the injectable
    ``resource_readings`` contract) -- no separate wall-clock check needed by
    the caller.
    """
    poll_interval = max(poll_interval_seconds, 1.0)
    max_polls = max(1, int(timeout_seconds / poll_interval) + 1)
    for _ in range(max_polls):
        yield _read_real_resource_reading()


@dataclass(frozen=True)
class _ResourceWindowResult:
    """The outcome of the pre-launch resource-window wait-and-poll."""

    opened: bool
    attempts: int
    last_reading: tuple[int, float] | None
    mem_threshold_mib: int
    load1_threshold: float


def _await_resource_window(
    *,
    resource_readings: Iterable[tuple[int, float]] | None,
    sleep_fn: Callable[[float], None] | None,
    output: OutputPort | None,
) -> _ResourceWindowResult:
    """Wait-and-poll for a resource window BEFORE the heavy tier launches.

    Consumes one ``(mem_available_mib, load1)`` reading per poll attempt until
    a reading clears the threshold (``mem_available_mib`` above the
    configured floor AND ``load1`` below the configured ceiling) or the
    reading source is exhausted -- the bounded-wait budget: for the
    injectable ``resource_readings`` path exhaustion of the iterable IS the
    bound (no wall-clock needed); for the production path (``None``) the
    source itself is bounded by the wall-clock window timeout. A ``None``
    reading (``/proc`` absent, non-Linux) degrades open SILENTLY on the
    CHECK -- the window opens immediately, no wait event emitted.
    """
    mem_threshold = _resolve_int_env(
        _MIN_MEM_AVAILABLE_MIB_ENV, _DEFAULT_MIN_MEM_AVAILABLE_MIB
    )
    load_threshold = _resolve_float_env(_MAX_LOAD1_ENV, _DEFAULT_MAX_LOAD1)
    timeout_seconds = _resolve_float_env(
        _WINDOW_TIMEOUT_SECONDS_ENV, _DEFAULT_WINDOW_TIMEOUT_SECONDS
    )
    poll_interval = _resolve_float_env(
        _WINDOW_POLL_INTERVAL_SECONDS_ENV, _DEFAULT_POLL_INTERVAL_SECONDS
    )
    sleep = sleep_fn if sleep_fn is not None else time.sleep

    readings: Iterable[tuple[int, float] | None]
    if resource_readings is not None:
        readings = resource_readings
    else:
        readings = _real_resource_reading_iter(timeout_seconds, poll_interval)

    attempts = 0
    last_reading: tuple[int, float] | None = None
    for reading in readings:
        attempts += 1
        if reading is None:
            return _ResourceWindowResult(
                opened=True,
                attempts=attempts,
                last_reading=None,
                mem_threshold_mib=mem_threshold,
                load1_threshold=load_threshold,
            )
        last_reading = reading
        mem_available_mib, load1 = reading
        if mem_available_mib > mem_threshold and load1 < load_threshold:
            return _ResourceWindowResult(
                opened=True,
                attempts=attempts,
                last_reading=last_reading,
                mem_threshold_mib=mem_threshold,
                load1_threshold=load_threshold,
            )
        _emit(
            {
                "event": "BuildTierResourceWait",
                "attempt": attempts,
                "mem_available_mib": mem_available_mib,
                "load1": load1,
                "mem_threshold_mib": mem_threshold,
                "load1_threshold": load_threshold,
                "what": "pre-launch resource window",
                "why": (
                    "observed resources are below the build-tier launch "
                    "threshold -- waiting for a calmer window before "
                    "spawning the heavy subprocess"
                ),
            },
            output,
        )
        sleep(poll_interval)
    return _ResourceWindowResult(
        opened=False,
        attempts=attempts,
        last_reading=last_reading,
        mem_threshold_mib=mem_threshold,
        load1_threshold=load_threshold,
    )


def _light_invariant_paths(repo: Path) -> list[Path]:
    """Resolve the internal default light always-on invariant set.

    Used only when a caller opts into the SCOPED per-slice tier
    (``regression_test_file`` and/or ``light_invariant_paths`` given, ``full``
    not True) but does not inject an explicit ``light_invariant_paths`` list.
    Every AT in the scoped-per-slice-build-tier feature-delta injects the
    light set explicitly (never coupling the AT to a guessed filesystem
    convention), so this resolver has no AT-pinned content yet -- it defaults
    to an empty list (AT-driven minimalism: no invented filesystem
    convention beyond what a caller/future-AT requires).
    """
    return []


def _resolve_build_tier_run_paths(
    repo: Path,
    whole_tree_paths: list[Path],
    *,
    regression_test_file: Path | None,
    light_invariant_paths: Sequence[Path] | None,
    full: bool,
    output: OutputPort | None,
) -> list[Path]:
    """Resolve the paths handed to ``_run_arch_invariant_set`` for THIS run.

    ``full=True`` OR neither scope kwarg given -> the whole-tree
    ``whole_tree_paths`` (``_arch_invariant_paths(repo)``, unchanged).
    Otherwise -> SCOPED: ``[regression_test_file, *light_invariant_paths]``
    (``light_invariant_paths=None`` resolves via ``_light_invariant_paths``),
    with a LOUD ``BuildTierWholeTreeDeferred`` event -- naming feature-end --
    emitted BEFORE the run.
    """
    scope_requested = (
        regression_test_file is not None or light_invariant_paths is not None
    )
    if full or not scope_requested:
        return whole_tree_paths

    resolved_light = (
        list(light_invariant_paths)
        if light_invariant_paths is not None
        else _light_invariant_paths(repo)
    )
    scoped_paths = (
        [regression_test_file, *resolved_light]
        if regression_test_file is not None
        else resolved_light
    )
    _emit(
        {
            "event": "BuildTierWholeTreeDeferred",
            "scope": "per-slice",
            "regression_test_file": (
                str(regression_test_file) if regression_test_file is not None else None
            ),
            "light_invariant_paths": [str(p) for p in resolved_light],
            "deferred_to": "feature-end",
            "what": "whole-tree tests/build/** architecture tier",
            "why": (
                "the per-slice seal scopes to the entering slice's regression "
                "test + the light always-on invariants -- the whole-tree "
                "tests/build/** tier is deferred to feature-end, never "
                "silently narrowed"
            ),
            "how": (
                "the whole-tree floor still runs at feature-end: "
                "`run_contract_gate --repo . --full` (or the existing "
                "feature-end integrity leg)"
            ),
        },
        output,
    )
    return scoped_paths


def build_tier_exit_verdict(
    repo: Path,
    *,
    output: OutputPort | None = None,
    resource_readings: Iterable[tuple[int, float]] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    regression_test_file: Path | None = None,
    light_invariant_paths: Sequence[Path] | None = None,
    full: bool = False,
) -> int:
    """RUN the build-tier architectural set as a per-slice exit check.

    Closes F-CONTRACT-GATE-EXCLUDES-BUILD-TIER-ARCH-TESTS for the slice exit
    path (evolution-plan P1 deletion-safety precondition): the ``des
    commit-slice`` composition EXECUTES ``tests/build/**`` (via the existing
    ``_run_arch_invariant_set`` seam -- collect-AND-RUN under the contract
    marker), so a build-tier arch violation (forbidden import, registry-
    coherence break) is CAUGHT at the slice exit instead of shipping unseen
    until a full-suite run.

    ADD-not-mutate (design option i, keyword-only ADD-not-mutate extension
    per feature-delta gate-runner-resource-aware/slice-01): this is an
    ADDITIONAL executed check. The committed-scope digest machinery
    (``_collect_scope`` / ``compute_gate_scope_digest`` / ``_FULL_SUITE_MARKER``)
    is untouched, so every historic ``Gate-Scope:`` trailer re-verifies
    byte-identically. ``output``/``resource_readings``/``sleep_fn`` default
    to ``None`` -- zero behaviour change for the existing positional caller
    (``commit_slice.py``'s ``build_tier_exit_verdict(repo)``): ``output=None``
    keeps writing to ``sys.stdout``, ``resource_readings=None`` reads real
    ``/proc/meminfo`` + ``/proc/loadavg``, ``sleep_fn=None`` uses real
    ``time.sleep``.

    Per-slice SCOPING (feature-delta scoped-per-slice-build-tier/slice-01,
    ADD-not-mutate, keyword-only): ``regression_test_file`` /
    ``light_invariant_paths`` / ``full`` narrow which paths are handed to
    ``_run_arch_invariant_set``, WITHOUT changing the ``tests/build``
    presence check above (that N/A check stays keyed off the whole-tree
    ``_arch_invariant_paths(repo)`` resolver, independent of what actually
    RUNS). Scope resolution:

    * ``full=True`` OR neither ``regression_test_file`` nor
      ``light_invariant_paths`` given -> whole tree (``_arch_invariant_paths``,
      unchanged -- today's zero-new-kwarg ``commit_slice.py`` call site keeps
      this behaviour byte-for-byte).
    * otherwise -> SCOPED: the run targets ``[regression_test_file,
      *light_invariant_paths]`` (``light_invariant_paths=None`` resolves via
      the internal ``_light_invariant_paths(repo)`` default), and a LOUD
      ``BuildTierWholeTreeDeferred`` event naming ``feature-end`` is emitted
      BEFORE the run -- the whole-tree tier is deferred, never silently
      narrowed. The pre-launch resource window (above) still gates the
      SCOPED run identically to the whole-tree run.

    Verdicts (all LOUD, single-line JSON events):

    * ``tests/build`` absent -> ``BuildTierNotApplicable`` + return 0 (an
      external target legitimately carries no nWave arch tier; the N/A is
      emitted distinctly, never a silent pass claim).
    * resource window never opens (pre-launch) -> LOUD
      INDETERMINATE-resource-starvation naming the observed resources, the
      threshold, and the retry command + return 0 -- the heavy subprocess is
      NEVER spawned.
    * interpreter unresolvable -> ``health.gate.build-tier.indeterminate`` +
      return 0 (proceed; the downstream committed-scope digest step degrades
      on the same absence and mints the honest ``SliceCommitIndeterminate``).
    * worker killed by signal/OOM mid-run (post-run, no result line) ->
      LOUD INDETERMINATE-resource-starvation naming the signal and the retry
      command + return 0 -- NEVER the red ``BuildTierRefused`` lane (GDP-6).
    * worker failure (any OTHER untrusted collection/run) -> ``BuildTierRefused``
      reason ``worker-failed`` + return 1 (fail-closed: an unrunnable arch
      tier is never certified).
    * present-but-vacuous (zero collected under the contract marker) ->
      ``BuildTierRefused`` reason ``arch-scope-zero-collected`` + return 1.
    * a genuinely failing arch test -> ``BuildTierRefused`` reason
      ``arch-invariant-failed`` NAMING the failing node-id(s) + return 1
      (unchanged -- a real assertion failure under low load stays a real FAIL).
    * GREEN -> ``BuildTierVerified`` carrying the executed count and the
      measured wall-clock + return 0.
    """
    arch_paths = _arch_invariant_paths(repo)
    if not arch_paths:
        _emit(
            {
                "event": _BUILD_TIER_NOT_APPLICABLE_EVENT,
                "reason": "no tests/build tier on this target",
                "detail": (
                    "the target repository carries no tests/build directory; "
                    "there is no build-tier architecture invariant to run -- "
                    "recorded as an honest N/A, not a pass claim"
                ),
            },
            output,
        )
        return 0

    run_paths = _resolve_build_tier_run_paths(
        repo,
        arch_paths,
        regression_test_file=regression_test_file,
        light_invariant_paths=light_invariant_paths,
        full=full,
        output=output,
    )
    if not run_paths:
        # Design B (2026-07-17): a caller that opted into the SCOPED tier
        # (regression_test_file and/or light_invariant_paths given, not
        # full) but resolved to a genuinely EMPTY scope -- the Gherkin
        # per-slice case with no regression test of its own -- has nothing
        # to run. Special-case it explicitly HERE, before the heavy
        # resource-window wait and BEFORE handing the empty list to
        # _run_arch_invariant_set (whose own worker seam re-expands an
        # empty --path selection to the whole repo). The
        # BuildTierWholeTreeDeferred event already fired above (inside
        # _resolve_build_tier_run_paths); this pairs it with an honest N/A
        # rather than a silent pass or a whole-tree sweep.
        _emit(
            {
                "event": _BUILD_TIER_NOT_APPLICABLE_EVENT,
                "reason": "empty per-slice arch scope",
                "detail": (
                    "the per-slice scope resolved to zero paths (no "
                    "regression_test_file, no light invariants) -- there is "
                    "nothing to run for this slice; the whole-tree "
                    "tests/build/** tier is deferred to feature-end (see the "
                    "BuildTierWholeTreeDeferred event) -- recorded as an "
                    "honest N/A, not a pass claim"
                ),
            },
            output,
        )
        return 0

    window = _await_resource_window(
        resource_readings=resource_readings, sleep_fn=sleep_fn, output=output
    )
    if not window.opened:
        last = window.last_reading
        _emit(
            {
                "event": "BuildTierResourceWindowNeverOpened",
                "outcome": "indeterminate-resource-starvation",
                "attempts": window.attempts,
                "last_observed_mem_available_mib": last[0] if last else None,
                "last_observed_load1": last[1] if last else None,
                "mem_threshold_mib": window.mem_threshold_mib,
                "load1_threshold": window.load1_threshold,
                "what": "pre-launch resource window",
                "why": (
                    "resources never cleared the launch threshold within the "
                    "bounded wait -- refusing to spawn the heavy build-tier "
                    "subprocess into contention"
                ),
                "how": (
                    "retry once memory/load recover: `des commit-slice` (or "
                    "`pytest tests/build -m 'unit or integration or "
                    "acceptance'` directly)"
                ),
            },
            output,
        )
        return 0

    started = time.monotonic()
    try:
        arch = _run_arch_invariant_set(repo, run_paths)
    except InterpreterUnavailable as exc:
        _emit(
            {
                "event": _BUILD_TIER_INDETERMINATE_EVENT,
                "outcome": "indeterminate",
                "capability": exc.capability,
                "error": (
                    "no usable interpreter to run the build tier -- proceeding; "
                    "the committed-scope digest step degrades on the same "
                    f"absence and records the honest INDETERMINATE: {exc}"
                ),
            },
            output,
        )
        return 0
    except _WorkerStarvedError as exc:
        signal_desc = _describe_worker_kill(exc.returncode)
        _emit(
            {
                "event": "BuildTierResourceStarvation",
                "outcome": "indeterminate-resource-starvation",
                "signal": signal_desc,
                "returncode": exc.returncode,
                "what": "build-tier architecture run subprocess",
                "why": (
                    "the worker subprocess produced no NWAVE_RUN_SCOPE result "
                    f"line -- killed by {signal_desc}, not a genuine test "
                    "failure (GDP-6: a resource-induced kill is never "
                    "reported as a red refusal)"
                ),
                "how": (
                    "retry once memory/load recover: `des commit-slice` (or "
                    "`pytest tests/build -m 'unit or integration or "
                    "acceptance'` directly)"
                ),
            },
            output,
        )
        return 0
    except _CollectionError as exc:
        _emit(
            {
                "event": "BuildTierRefused",
                "reason": "worker-failed",
                "what": "build-tier architecture run",
                "why": f"the arch-invariant run could not be trusted: {exc}",
                "how": (
                    "run `pytest tests/build -m 'unit or integration or "
                    "acceptance'` directly and fix the collection/run failure"
                ),
            },
            output,
        )
        return 1
    elapsed = round(time.monotonic() - started, 2)
    if arch.collected == 0:
        _emit(
            {
                "event": "BuildTierRefused",
                "reason": "arch-scope-zero-collected",
                "what": "build-tier architecture scope",
                "why": (
                    "tests/build exists but collected zero runnable node-ids "
                    "under the contract marker filter -- refusing rather than "
                    "certifying a vacuous arch tier"
                ),
                "how": (
                    "ensure at least one tests/build test carries the "
                    "unit/integration/acceptance marker, or remove the empty "
                    "tests/build directory"
                ),
            },
            output,
        )
        return 1
    if not arch.passed:
        _emit(
            {
                "event": "BuildTierRefused",
                "reason": "arch-invariant-failed",
                "failed_node_ids": list(arch.failed_node_ids),
                "elapsed_seconds": elapsed,
                "what": "build-tier architecture invariant",
                "why": (
                    "a build-tier architecture test FAILED -- the slice breaks "
                    "an architecture/contract invariant in tests/build/**: "
                    + (
                        ", ".join(arch.failed_node_ids[:10])
                        or "see the arch run output"
                    )
                ),
                "how": (
                    "fix the production code (or the drifted registry/catalog "
                    "artifact) the named arch test guards, then re-run "
                    "des commit-slice"
                ),
            },
            output,
        )
        return 1
    _emit(
        {
            "event": "BuildTierVerified",
            "collected": arch.collected,
            "elapsed_seconds": elapsed,
        },
        output,
    )
    return 0


def _collected_count(collect_stdout: str) -> int:
    """Return pytest's reported collected-test count from a `-q` collect run.

    Reads the `<N> tests collected` / `<N>/<M> tests collected` summary line;
    zero when no such line is present (a genuinely-empty scope). The gate's own
    collection no longer parses stdout -- this is a self-contained helper for
    callers that anchor a synthetic fixture's raw `-q` collect signature.
    """
    for line in collect_stdout.splitlines():
        match = _COLLECTED_COUNT_RE.match(line.strip())
        if match:
            return int(match.group(1))
    return 0


class _CollectionError(Exception):
    """pytest collection failed -- the contract scope cannot be derived.

    Carries the optional ``crashing_module`` the worker named (the first failed
    collector's nodeid) so the collection-health precheck can NAME the broken
    module in its ``MalformedInput`` payload (KPI-3) rather than reporting only
    the bare pytest exit code.
    """

    def __init__(self, message: str, *, crashing_module: str | None = None) -> None:
        super().__init__(message)
        self.crashing_module = crashing_module


class _WorkerStarvedError(_CollectionError):
    """The arch-run worker emitted no ``NWAVE_RUN_SCOPE`` result line.

    Subclasses ``_CollectionError`` so a caller that only knows the generic
    contract (``_mode_feature_scoped``) keeps treating this as a collection
    failure unchanged; ``build_tier_exit_verdict`` catches THIS subclass
    first and reclassifies it as INDETERMINATE-resource-starvation (GDP-6:
    a signal/OOM kill is never a red refusal).
    """

    def __init__(self, returncode: int, stderr: str) -> None:
        super().__init__(
            "the arch-invariant run worker emitted no result line "
            f"(exit {returncode}): {stderr.strip()[:500]}"
        )
        self.returncode = returncode
        self.stderr = stderr


def _describe_worker_kill(returncode: int) -> str:
    """Name the observed signal/exit-code of a starved worker (GDP-3)."""
    if returncode < 0:
        signal_num = -returncode
        return (
            f"signal {signal_num} (SIGKILL/OOM-kill)"
            if signal_num == 9
            else (f"signal {signal_num}")
        )
    if returncode in (137, 143):
        return f"exit code {returncode} (OOM-kill / SIGTERM shell convention)"
    return f"exit code {returncode}"


def _emit_interpreter_unavailable(exc: InterpreterUnavailable) -> int:
    """Surface an `InterpreterUnavailable` as a structured exit-2 payload.

    F-21 boundary contract: when `des.runtime.interpreter.python_for` cannot
    resolve a pytest-capable interpreter it raises rather than spawning a
    known-bad one. The gate converts that into a single-line JSON
    `InterpreterUnavailable` event + exit 2 -- a diagnosable malformed-input
    failure, never an escaped pytest-collection traceback.
    """
    _emit(
        {
            "event": "InterpreterUnavailable",
            "capability": exc.capability,
            "probed": exc.probed,
            "error": str(exc),
        }
    )
    return 2


def _degrade_interpreter_unavailable(exc: InterpreterUnavailable) -> int:
    """Degrade LOUD to INDETERMINATE-and-PROCEED on interpreter absence (DDD-1).

    The non-Python-target counterpart of ``_emit_interpreter_unavailable``: when
    the feature-scoped gate cannot resolve a pytest-capable interpreter it must
    NOT hard-refuse (exit 2) -- a hard-block on a machine without an interpreter
    wedges the entire non-Python slice chain. Instead it emits a LOUD
    INDETERMINATE marker (mirroring ``_warn_committed_scope_indeterminate`` @825)
    and returns the dedicated ``_GATE_INDETERMINATE_EXIT_CODE`` (3) so the caller
    records an honest ``SliceCommitIndeterminate``. INDETERMINATE is never
    coerced to a PASS (exit 0): a runnable-but-failing gate still fails -- this
    branch is reachable ONLY on genuine interpreter-absence.
    """
    _emit(
        {
            "event": _INTERPRETER_UNAVAILABLE_INDETERMINATE_EVENT,
            "outcome": "indeterminate",
            "capability": exc.capability,
            "probed": exc.probed,
            "error": (
                "no usable interpreter on this machine -- the contract gate is "
                f"INDETERMINATE (not a pass, not a hard refuse): {exc}"
            ),
        }
    )
    return _GATE_INDETERMINATE_EXIT_CODE


# The only legitimate collapse between pytest's in-process ``collected_count``
# (``len(session.items)``) and the canonical deduplicated identity set is the
# hypothesis-rerun duplicate family: the same test re-collected under hypothesis
# rerun, whose collapse is CORRECT. With the CLASS-AWARE identity
# (``fspath::Class::...::method``, see ``_identity_of``), sibling test classes
# that share a method name no longer collapse, so the gap closes to the rerun
# set alone. (Historically the bare ``(fspath, item.name)`` identity inflated
# the gap with 21 same-method-across-classes collisions -- those were genuine
# distinct tests, NOT reruns; the class-aware identity removes them and the gap
# drops to zero. The premise that the whole gap "is exactly the hypothesis-rerun
# duplicate set" only holds once the identity is class-aware.) A gap larger than
# this tolerance is the undercount this gate exists to catch: the parity guard
# fails closed rather than fingerprint a partial scope. Re-measuring/tightening
# the tolerance is a separate follow-up.
_RERUN_TOLERANCE = 19


def compute_gate_scope_digest(node_ids: list[str]) -> str:
    """Return the SHA-256 digest of the sorted set of collected node-ids."""
    joined = "\n".join(sorted(set(node_ids)))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def gate_scope_digest(repo: Path) -> str:
    """Derive a fresh `gate_scope_digest` for ``repo``'s contract suite."""
    return compute_gate_scope_digest(_collect_node_ids(repo))


def _assert_parity(scope: _CollectedScope) -> None:
    """Fail closed if the canonical identity set undercounts the session items.

    Defense-in-depth (ADR-001 parity guard): the digested identity set must
    cover pytest's own in-process collected count within the documented
    hypothesis-rerun tolerance. A larger gap -- or a populated session that
    deduplicated to nothing -- means the digest would fingerprint a partial
    scope, which is exactly the undercount defect. Never digest a partial scope.
    """
    unique = len(scope.node_ids)
    if scope.collected_count > 0 and unique == 0:
        raise _CollectionError(
            "the contract suite collected "
            f"{scope.collected_count} items but zero canonical identities "
            "survived -- refusing to fingerprint an empty scope"
        )
    gap = scope.collected_count - unique
    if gap > _RERUN_TOLERANCE:
        raise _CollectionError(
            f"canonical identities ({unique}) undercount pytest's collected "
            f"items ({scope.collected_count}) by {gap} > tolerance "
            f"{_RERUN_TOLERANCE} -- refusing to fingerprint a partial scope"
        )


def extract_gate_scope(commit_message: str) -> str | None:
    """Return the digest carried by a `Gate-Scope:` commit trailer, if any."""
    for line in commit_message.splitlines():
        match = _GATE_SCOPE_TRAILER_RE.match(line.strip())
        if match:
            return match.group(1)
    return None


# The env var that overrides the contract-suite RUN worker count.
#   unset / "auto" -> pytest-xdist `-n auto` (one worker per logical CPU)
#   a positive int -> that many workers
#   "0" / "serial" / "1" -> serial (no xdist), the debug escape hatch
# Mirrors the `.nwave/config.yaml` `gate.jobs` key; the env var wins when both
# are set. The default is `auto` -- parallel-by-default is the whole point of
# the perf fix (serial ~30 min -> `-n auto` ~6 min on 4 cores).
_GATE_JOBS_ENV = "NWAVE_GATE_JOBS"
_GATE_JOBS_DEFAULT = "auto"
_SERIAL_TOKENS = frozenset({"0", "1", "serial", "off", "none"})


def _resolve_gate_jobs(repo: Path) -> str:
    """Resolve the desired worker spec: env var > `.nwave/config.yaml` > `auto`.

    Returns the *requested* spec as a string (``"auto"``, an integer string, or
    a serial token). Pure resolution -- whether xdist can actually honour it is
    decided separately in ``_parallel_pytest_args`` so the absent-xdist degrade
    stays a single LOUD seam.

    F-11 / DES-bundle hygiene: as a shipped ``des.cli`` module this gate MUST be
    stdlib-only -- the bundle scan forbids ``import yaml`` in any bundled module.
    ``gate.jobs`` is read with the same narrow two-level block-mapping line-scan
    ``carpaccio_format._scan_atdd_pure_int`` uses, not a YAML dependency.
    """
    env_val = os.environ.get(_GATE_JOBS_ENV)
    if env_val is not None and env_val.strip():
        return env_val.strip()

    config_path = repo / ".nwave" / "config.yaml"
    if config_path.is_file():
        try:
            jobs = _scan_gate_jobs(config_path.read_text(encoding="utf-8"))
        except OSError:
            jobs = None
        if jobs:
            return jobs

    return _GATE_JOBS_DEFAULT


def _scan_gate_jobs(text: str) -> str | None:
    """Stdlib scan for the ``gate.jobs`` string in ``.nwave/config.yaml``.

    Reads the two-level block-mapping shape::

        gate:
          jobs: auto

    Returns the trimmed string value found under the top-level ``gate:`` block,
    or None when absent. Deliberately narrow (mirrors
    ``carpaccio_format._scan_atdd_pure_int``): parses exactly the one config
    shape this gate needs, never arbitrary YAML. A trailing ``# comment`` is
    stripped.
    """
    in_gate = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        if indent == 0:
            in_gate = stripped.rstrip(":") == "gate" and stripped.endswith(":")
            continue
        if not in_gate or ":" not in stripped:
            continue
        name, _, value_text = stripped.partition(":")
        if name.strip() != "jobs":
            continue
        value = value_text.split("#", 1)[0].strip()
        return value or None
    return None


def _parallel_pytest_args(repo: Path, interpreter: str) -> list[str]:
    """The pytest argv fragment that selects the worker count for the RUN.

    Returns ``["-n", <spec>, "--dist", "loadgroup"]`` when parallel execution is
    both requested AND honourable (pytest-xdist importable in the interpreter
    that will run the suite). Returns ``[]`` -- serial -- when the operator asked
    for serial OR when xdist is absent. The absent-xdist path DEGRADES LOUD (a
    one-line stderr notice), never silently: the genericita mandate forbids a
    silent dependency assumption, so a customer install without the optional
    ``pytest-xdist`` runs the gate serially with a visible reason.

    ``--dist loadgroup`` keeps any ``@pytest.mark.xdist_group`` family pinned to
    one worker -- the parallel-safety escape hatch for genuinely interfering
    tests (shared FS paths, port binding, the audit-log singleton) WITHOUT
    disabling parallelism globally.
    """
    requested = _resolve_gate_jobs(repo)
    if requested.lower() in _SERIAL_TOKENS:
        return []

    if not can_import(interpreter, "xdist"):
        print(
            "[contract-gate] pytest-xdist not importable in "
            f"{interpreter!r}; running the contract suite SERIALLY "
            "(install pytest-xdist for parallel ~5x speedup, or set "
            f"{_GATE_JOBS_ENV}=serial to silence this).",
            file=sys.stderr,
        )
        return []

    return ["-n", requested, "--dist", "loadgroup"]


def _full_suite_marker_args(repo: Path, interpreter: str) -> list[str]:
    """The pytest argv for the FEATURE-END full-suite scope (the retained leg).

    SSOT for the whole-tree marker argv (slice-05 / C10): the
    ``_FULL_SUITE_MARKER`` expression is named HERE and only here, so the
    per-commit-slice RUN functions never wire the whole-tree marker into their
    own bodies. This is the feature-end full-suite scope the
    ``feature_end_cycle_service`` full-suite leg runs ONCE at feature-end (not at
    every commit-slice) -- a legitimately RETAINED full-suite leg, not the
    obsolete per-slice whole-tree run (§V.B).
    """
    return [
        interpreter,
        "-m",
        "pytest",
        "-m",
        _FULL_SUITE_MARKER,
        "-p",
        "no:cacheprovider",
        *_parallel_pytest_args(repo, interpreter),
    ]


def _run_contract_suite(repo: Path, *, junit_xml_path: Path | None = None) -> int:
    """Run the FEATURE-END full-suite scope; return its pytest exit code.

    slice-05 / C10: this is the feature-end full-suite leg (run ONCE at
    feature-end), NOT the obsolete whole-tree-at-every-commit-slice run. The
    full-suite marker argv is owned by ``_full_suite_marker_args`` (the SSOT) so
    the per-slice RUN path never wires the whole-tree marker.

    ``junit_xml_path`` (fix-feature-end-refusal-names-failing-tests), when
    given, adds ``--junit-xml=<path>`` so this (marker-scoped) run persists a
    JUnit XML report. Only the UNROUTED fallback path (no registered
    ``ContractGatePort`` facet) ever passes this -- the registered-facet path
    sources its JUnit report from ``facet.run_suite`` instead (the whole-suite,
    unmarked run that actually drives the refusal verdict), never from this
    marker-scoped parity call.

    Parallel-by-default via pytest-xdist (``-n auto``) -- the perf fix that cuts
    the serial ~30 min whole-suite RUN to ~6 min on 4 cores. Degrades LOUD to
    serial when xdist is absent or when the operator sets ``NWAVE_GATE_JOBS``
    to a serial token (see ``_parallel_pytest_args``).
    """
    interpreter = pytest_interpreter()
    argv = _full_suite_marker_args(repo, interpreter)
    if junit_xml_path is not None:
        argv = [*argv, f"--junit-xml={junit_xml_path}"]
    try:
        completed = subprocess.run(
            argv,
            cwd=repo,
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired:
        # ZERO DEFECTS: the full-suite run must never block the gate forever (the
        # empirical 61-min-at-0%-CPU hang). Fail LOUD with a non-zero code on the
        # ceiling instead of hanging; raise NWAVE_GATE_RUN_TIMEOUT for a legit run.
        print(
            f"FULL-SUITE RUN exceeded the {run_timeout_seconds():.0f}s ceiling "
            f"(a hanging/deadlocking test) -- failing loud, not hanging.",
            file=sys.stderr,
        )
        return 1
    return completed.returncode


def _marker_mismatch_note(excluded_count: int, agnostic_count: int) -> str:
    """What/why/how remediation for a marker-filtered-STRICT-SUBSET scope.

    Target-agnosticism fix (RCA:
    docs/feature/fix-collector-marker-filter-target-agnostic/deliver/rca.md):
    the default collect applies ``-m "unit or integration or acceptance"``
    (``_FULL_SUITE_MARKER``). nwave-dev stamps every item with those markers
    via its own conftest auto-marker, so its whole suite matches -- but a
    FOREIGN target repo whose tests carry none (or only some) of those markers
    collects a STRICT SUBSET under the filter even though pytest genuinely
    finds every test unfiltered. This NAMES the excluded count (the tests the
    marker filter silently dropped from the contract scope) rather than lying
    that the scope is "genuinely zero" (the all-unmarked case, excluded ==
    agnostic) or scoping silently to the marked subset (the Vera-surfaced
    partial case, ``0 < filtered < agnostic``).
    """
    return (
        f"{excluded_count} of {agnostic_count} collected tests carry no "
        "unit/integration/acceptance marker and were EXCLUDED from the "
        "contract scope -- mark them, or add a pytest_collection_modifyitems "
        "conftest auto-marker; the contract gate scopes by those markers"
    )


def _mode_print_digest(repo: Path) -> int:
    """`--collect-only --print-digest`: emit a fresh digest, run nothing.

    The `GateScopeDigest` event carries BOTH cardinalities from the SAME
    in-process collection (ADR-001): ``node_id_count`` (the digested-set
    cardinality) and ``collected_count`` (``len(session.items)``). They make
    the canonical-coverage parity observable through the driving port.

    Target-agnosticism (RCA:
    docs/feature/fix-collector-marker-filter-target-agnostic/deliver/rca.md):
    the marker-FILTERED collect is always a SUBSET of the marker-AGNOSTIC
    collect (``markers=None``, the SAME ``_collect_scope`` seam, DDD-12 -- no
    new collector). Whenever it is a STRICT subset (``filtered < agnostic`` --
    covering BOTH the all-unmarked ``filtered == 0`` case AND the Vera-surfaced
    partial ``0 < filtered < agnostic`` case, where some tests are marked and
    some are not), the digest falls back to the agnostic scope AND the event
    names the marker mismatch (what/why/how) -- naming how many collected tests
    the marker filter silently excluded -- instead of reporting the filtered
    subset as the genuine scope (the false "genuinely collected zero" verdict,
    or the silent-subset drop). A genuinely empty scope (zero under BOTH
    collects) still reports zero, honestly. A marked repo (filtered ==
    agnostic, e.g. nwave-dev) never triggers the fallback -- its behavior and
    digest are unchanged.
    """
    route = _maybe_route_digest_through_runner(repo)
    if isinstance(route, _DigestRouteDegrade):
        return route.exit_code
    if isinstance(route, _DigestRouteResult):
        return _emit_runner_aware_digest(route)
    marker_mismatch: str | None = None
    try:
        scope = _collect_scope(repo)
        agnostic_scope = _collect_scope(repo, markers=None)
        if len(scope.node_ids) < len(agnostic_scope.node_ids):
            excluded_count = len(agnostic_scope.node_ids) - len(scope.node_ids)
            marker_mismatch = _marker_mismatch_note(
                excluded_count, len(agnostic_scope.node_ids)
            )
            scope = agnostic_scope
        _assert_parity(scope)
    except InterpreterUnavailable as exc:
        return _emit_interpreter_unavailable(exc)
    except _CollectionError as exc:
        event: dict[str, object] = {
            "event": "MalformedInput",
            "error": f"collection failed: {exc}",
        }
        # KPI-3: when the worker named the crashing module, surface it as a
        # dedicated field so the collection-health precheck NAMES the broken
        # module instead of a silent opaque re-fire (the #68 root).
        if exc.crashing_module is not None:
            event["crashing_module"] = exc.crashing_module
        _emit(event)
        return 2
    digest = compute_gate_scope_digest(scope.node_ids)
    # Plain stdout so callers can capture the bare digest (composition does
    # `.strip()` on it); the JSON event goes to stderr for machine readers.
    print(digest)
    digest_event: dict[str, object] = {
        "event": "GateScopeDigest",
        "gate_scope_digest": digest,
        "node_id_count": len(scope.node_ids),
        "collected_count": scope.collected_count,
    }
    if marker_mismatch is not None:
        digest_event["marker_mismatch"] = marker_mismatch
    print(json.dumps(digest_event), file=sys.stderr)
    return 0


@dataclass(frozen=True)
class _CommittedScopeRefusal:
    """A signal that the committed-scope digest cannot be established.

    Carries the integer exit code the calling mode must return -- the
    committed-scope machinery has ALREADY emitted the appropriate LOUD event
    (the INDETERMINATE health event for a tree that cannot be pinned to a
    committed revision, or a `MalformedInput` for an untrustworthy collection),
    so the caller only propagates the code.
    """

    exit_code: int


@dataclass(frozen=True)
class _CommittedScopeDigest:
    """The committed-scope digest of a commit plus its collection cardinalities."""

    commit: str
    digest: str
    node_id_count: int
    collected_count: int


@dataclass(frozen=True)
class _CommittedScopeIndeterminate:
    """The committed scope could not be pinned to a committed revision (QUIET).

    The QUIET probe returns this rather than emitting any event, so a caller
    that is NOT a fail-closed gate (the default suite-run trailer compute, which
    must stay usable on a non-git working tree -- slice-14 contract) can fall
    back without polluting its output. A fail-closed caller converts it into the
    LOUD `_refuse_committed_scope` event.
    """

    reason: str


def _committed_scope_digest_quiet(
    repo: Path,
    commit: str,
    markers: str | None | _UnsetMarkers = _MARKERS_UNSET,
) -> _CommittedScopeDigest | _CommittedScopeIndeterminate | _CommittedScopeRefusal:
    """Compute the committed-scope digest of ``commit`` WITHOUT emitting events.

    The single committed-scope digest seam (DDD-12): collects ONLY the committed
    contract-suite file-set at ``commit`` via the `CommittedScopePort`, so the
    digest is invariant to untracked co-resident WIP and reproducible on any
    checkout of that commit. `.feature` specs are excluded by the port (they are
    collected via their bound `@scenario` `.py` step modules, not as direct
    pytest paths), so a committed mixed `.py` + `.feature` suite never trips a
    pytest exit-4 collection error.

    ``markers`` (fix-runner-resolves-per-scope-language slice-01): threaded
    straight into ``_collect_scope``. UNSET (the default) keeps the marker-
    filtered ``-m "unit or integration or acceptance"`` collection byte-for-byte
    -- every existing caller unchanged. An explicit ``None`` collects
    MARKER-AGNOSTICALLY: a pytest-regression slice on an arbitrary target repo
    (no auto-marking conftest applying the contract markers) would otherwise
    have its committed regression test DESELECTED by the marker filter, yielding
    an empty scope hashed to the VACUOUS ``sha256('')`` digest -- marker-agnostic
    collection digests the real committed Python scope instead.

    git absent / not a work-tree / SHA unresolvable returns
    `_CommittedScopeIndeterminate` (the caller decides whether to refuse LOUD or
    fall back). An untrustworthy collection emits its own `MalformedInput` and
    returns a hard `_CommittedScopeRefusal` -- that is a genuine fail-closed
    condition regardless of caller.
    """
    try:
        resolved = _git(repo, "rev-parse", commit).strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return _CommittedScopeIndeterminate(f"cannot resolve {commit!r}: {exc}")

    committed = GitCommittedScopeAdapter().committed_contract_files(repo, resolved)
    if not isinstance(committed, CommittedFileSet):
        return _CommittedScopeIndeterminate(committed.reason)

    paths = [repo / rel for rel in committed.paths]
    try:
        scope = _collect_scope(repo, paths=paths, markers=markers)
        _assert_parity(scope)
    except InterpreterUnavailable as exc:
        return _CommittedScopeRefusal(_emit_interpreter_unavailable(exc))
    except _CollectionError as exc:
        _emit({"event": "MalformedInput", "error": f"collection failed: {exc}"})
        return _CommittedScopeRefusal(2)
    return _CommittedScopeDigest(
        commit=resolved,
        digest=compute_gate_scope_digest(scope.node_ids),
        node_id_count=len(scope.node_ids),
        collected_count=scope.collected_count,
    )


def _committed_scope_digest_value(
    repo: Path,
    commit: str,
    markers: str | None | _UnsetMarkers = _MARKERS_UNSET,
) -> _CommittedScopeDigest | _CommittedScopeRefusal:
    """Fail-closed committed-scope digest of ``commit`` in ``repo``.

    git is REQUIRED. git absent / not a work-tree / SHA unresolvable emits the
    LOUD `health.gate.committed-scope.indeterminate` event and returns a refusal
    (exit 2) -- never silently fingerprinting the working tree (degrade-LOUD).
    This is the seam used by the fail-closed gate roles (`--verify-gate-scope`,
    `--committed-scope-digest`).

    ``markers`` is forwarded to ``_committed_scope_digest_quiet`` -- UNSET keeps
    the marker-filtered collection, an explicit ``None`` collects marker-
    agnostically (the pytest-regression carve-out; see that helper's docstring).
    """
    result = _committed_scope_digest_quiet(repo, commit, markers)
    if isinstance(result, _CommittedScopeIndeterminate):
        return _CommittedScopeRefusal(_refuse_committed_scope(result.reason))
    return result


def _mode_committed_scope_digest(repo: Path) -> int:
    """`--committed-scope-digest`: a reproducible digest over the COMMITTED tree.

    Distinct from the general `--collect-only --print-digest` (working-tree,
    non-git-OK). This mode collects ONLY the committed contract-suite file-set
    at HEAD via the `CommittedScopePort`, so its digest is invariant to untracked
    co-resident WIP (slice-01 AT-1) and reproducible on any checkout of that
    commit. The whole COMMITTED tree's breadth is preserved -- a test committed
    anywhere stays in the digest (AT-2).

    git is REQUIRED. git absent / not a work-tree / SHA unresolvable yields an
    `Indeterminate` from the port; this fail-closed gate then emits the LOUD
    `health.gate.committed-scope.indeterminate` event and REFUSES (exit 2) --
    never silently fingerprinting the working tree (AT-3, degrade-LOUD).
    """
    route = _maybe_route_digest_through_runner(repo)
    if isinstance(route, _DigestRouteDegrade):
        return route.exit_code
    if isinstance(route, _DigestRouteResult):
        return _emit_runner_aware_digest(route)
    result = _committed_scope_digest_value(repo, "HEAD")
    if isinstance(result, _CommittedScopeRefusal):
        return result.exit_code
    print(result.digest)
    print(
        json.dumps(
            {
                "event": "GateScopeDigest",
                "scope": "committed",
                "commit": result.commit,
                "gate_scope_digest": result.digest,
                "node_id_count": result.node_id_count,
                "collected_count": result.collected_count,
            }
        ),
        file=sys.stderr,
    )
    return 0


def _refuse_committed_scope(reason: str) -> int:
    """Emit the LOUD committed-scope INDETERMINATE event and refuse (exit 2)."""
    _emit(
        {
            "event": _COMMITTED_SCOPE_INDETERMINATE_EVENT,
            "scope": "committed",
            "reason": reason,
            "error": (
                "refusing to fingerprint a tree that cannot be pinned to a "
                f"committed revision: {reason}"
            ),
        }
    )
    return 2


def _warn_committed_scope_indeterminate(reason: str) -> None:
    """Emit the LOUD committed-scope INDETERMINATE marker and PROCEED.

    The producer counterpart of ``_refuse_committed_scope`` (AD-23): the
    suite-run is the digest PRODUCER, not a fail-closed gate, so on a tree that
    cannot be pinned to a committed revision it degrades LOUD -- emits the marker
    and stamps NO trailer -- yet still runs the suite and proceeds (exit 0). A
    working-tree digest is a trailer no other checkout can verify, so the
    producer refuses to STAMP one while still doing its other job (running the
    suite). The verb is "stamp no trailer + proceed", distinct from the
    verifier's "refuse + exit 2".

    GDP-3 self-explaining, BOTH surfaces (EXAMINE finding, slice-02 oracle):

    * the single-line JSON marker is emitted on BOTH stdout AND stderr (the
      stdout-only ``_emit`` left the routed leg's degrade invisible on the
      operator's stderr channel);
    * a HUMAN-readable ``⚠️`` warning line goes to stderr through the
      ``print_human_summary`` SSOT (TTY-aware color, plain on pipes), so the
      operator can never read an unqualified green PASS while the portable
      Gate-Scope digest silently degraded to null. Emitted ONLY on this
      degrade path -- a pinnable git tree keeps its unqualified PASS line.
      Shared machinery: BOTH suite-run legs (the legacy ``_mode_run_suite``
      path and the routed ``_maybe_route_through_registered_contract_gate``
      leg) call THIS helper -- no fork.
    """
    line = json.dumps(
        {
            "event": _COMMITTED_SCOPE_INDETERMINATE_EVENT,
            "scope": "committed",
            "reason": reason,
            "error": (
                "stamping no Gate-Scope: trailer -- a working-tree digest on a "
                "tree that cannot be pinned to a committed revision is "
                f"un-verifiable on any checkout: {reason}"
            ),
        }
    )
    print(line)
    print(line, file=sys.stderr)
    print_human_summary(
        Verdict.DEGRADED,
        "WARN: no portable Gate-Scope digest stamped (gate_scope_digest=null) "
        f"-- the tree cannot be pinned to a committed revision: {reason}",
    )


def _mode_verify_gate_scope(repo: Path, commit: str, at_kind: str | None = None) -> int:
    """`--verify-gate-scope`: compare the commit's digest to a fresh one.

    The fresh digest is the COMMITTED-scope digest of the pinned ``commit`` (the
    slice-01 `--committed-scope-digest` machinery), NOT a working-tree digest.
    One pinned commit therefore verifies BYTE-IDENTICALLY whether or not
    untracked co-resident WIP sits beside it (the daily amend-loop is retired),
    while the whole committed tree's breadth is preserved -- a commit whose
    trailer no longer matches its OWN committed tree still fails verify. git
    absent / not a work-tree inherits the committed-scope LOUD INDETERMINATE
    refusal (exit 2) rather than silently fingerprinting the working tree.

    ``at_kind == "pytest-regression"`` (fix-runner-resolves-per-scope-language
    slice-01) SKIPS the whole-tree runner-routing seam -- mirrors
    ``commit_slice._committed_scope_digest_or_degrade_reason``'s own carve-out,
    so a pytest-regression slice's digest is re-derived through the SAME
    pytest-native path Step 3 used to pin it, never coerced through the repo's
    OTHER (e.g. cargo) lockfile-resolved runner. Every other ``--at-kind``
    (default / ``gherkin``) keeps the EXISTING runner-routed behavior.
    """
    if at_kind != "pytest-regression":
        route = _maybe_route_digest_through_runner(repo)
        if isinstance(route, _DigestRouteDegrade):
            return route.exit_code
        if isinstance(route, _DigestRouteResult):
            return _verify_runner_aware_digest(repo, commit, route)
    # pytest-regression collects marker-agnostically so the committed regression
    # test on a marker-less target repo is not deselected into a vacuous digest
    # (mirrors the produce leg in commit_slice._committed_scope_digest_or_degrade_reason).
    markers: str | None | _UnsetMarkers = (
        None if at_kind == "pytest-regression" else _MARKERS_UNSET
    )
    fresh_result = _committed_scope_digest_value(repo, commit, markers)
    if isinstance(fresh_result, _CommittedScopeRefusal):
        return fresh_result.exit_code
    fresh = fresh_result.digest

    commit_message = _git(repo, "log", "-1", "--format=%B", commit)
    declared = extract_gate_scope(commit_message)

    if declared is None:
        _emit(
            {
                "event": "GateScopeUnverified",
                "commit": commit,
                "reason": "absent",
                "error": (
                    "commit carries no Gate-Scope: trailer -- the contract "
                    "gate scope is unverified"
                ),
                "how": (
                    "re-commit the slice through `des commit-slice` -- it "
                    "stamps the Gate-Scope: trailer mechanically"
                ),
            }
        )
        return 1

    if declared != fresh:
        _emit(
            {
                "event": "GateScopeUnverified",
                "commit": commit,
                "reason": "mismatch",
                "declared_digest": declared,
                "fresh_digest": fresh,
                "error": (
                    "commit Gate-Scope: digest does not match a fresh "
                    "run_contract_gate --collect-only digest -- the "
                    "terminating run was narrower than the contract"
                ),
                "how": (
                    "re-run the full gate `run_contract_gate --repo .` so "
                    "the terminating run covers the whole contract, then "
                    "re-commit"
                ),
            }
        )
        return 1

    _emit(
        {
            "event": "GateScopeVerified",
            "commit": commit,
            "gate_scope_digest": fresh,
        }
    )
    return 0


def _mode_run_suite(
    repo: Path, at_kind: str | None = None, *, junit_xml_path: Path | None = None
) -> int:
    """Default mode: run the whole-tree contract suite + emit a digest.

    ``junit_xml_path`` (fix-feature-end-refusal-names-failing-tests): when
    given, requests a persisted JUnit XML report of the run that DRIVES the
    pass/fail verdict -- the registered-facet's ``run_suite`` when a
    ``ContractGatePort`` facet is routed, else this function's own fallback
    ``_run_contract_suite`` call. Omitted (``None``, the default) is a
    byte-identical no-op -- zero behaviour change for every existing caller.

    Emits the single-line JSON ``ContractGateResult`` event on BOTH stdout
    (the pre-existing machine-readable contract — DISCUSS row 4: no breaking
    change for existing pre-commit / CI / hook consumers) AND stderr
    (alongside the new human-readable verdict line — slice-01 surface). The
    helper detects whether stderr is a TTY and strips ANSI color escapes
    otherwise. The byte content of the event is identical on both channels.

    The terminating ``gate_scope_digest`` carried into the commit's
    ``Gate-Scope:`` trailer is the COMMITTED-scope digest of HEAD when the repo
    is a git work-tree (slice-02 wiring), NOT the working-tree digest -- so the
    trailer the commit carries is the committed-scope digest of its OWN
    committed tree, and the G_COMMIT exit-gate `--verify-gate-scope` re-derives a
    BYTE-IDENTICAL digest invariant to any untracked co-resident WIP. When the
    repo is NOT a git work-tree the suite-run is still usable (slice-14: the
    default mode runs the contract suite over any tree) -- but it DEGRADES LOUD:
    it emits the `health.gate.committed-scope.indeterminate` marker and stamps
    NO digest (AD-23, ADR-CP-001), because the suite-run is the digest PRODUCER
    and a working-tree digest is a trailer no other checkout can verify. The
    suite still RUNS (the producer's other job) and PROCEEDS exit 0 -- the
    fail-closed REFUSE (exit 2) belongs to the verify role, not the producer.
    A genuinely untrustworthy collection still fails closed (exit 2).

    ``at_kind == "pytest-regression"`` (fix-reverify-slice-commit-at-kind)
    SKIPS the whole-tree runner-routing seam entirely -- mirrors
    ``_mode_verify_gate_scope``'s own carve-out (fix-runner-resolves-per-
    scope-language slice-01) -- so a pytest-regression slice's suite run
    is never coerced through the repo's OTHER (e.g. cargo) lockfile-resolved
    runner. Every other ``--at-kind`` (default / ``gherkin``) keeps the
    EXISTING runner-routed behavior byte-identical.
    """
    routed_registered = _maybe_route_through_registered_contract_gate(
        repo, junit_xml_path=junit_xml_path
    )
    if routed_registered is not None:
        return routed_registered
    if at_kind != "pytest-regression":
        routed = _maybe_route_through_runner_whole_tree(repo)
        if routed is not None:
            return routed
    if at_kind == "pytest-regression":
        # A pytest-regression slice pins its digest through the SAME
        # pytest-native, marker-agnostic committed-scope path Step 3 used
        # (``markers=None``), and makes the committed scope git-REQUIRED
        # (fail-closed): a tree that cannot be pinned to a commit yields a
        # Refusal returned early below, so the suite-run never routes through
        # the repo's OTHER (e.g. cargo) lockfile-resolved runner nor
        # certifies an unpinnable tree. Every other ``at_kind`` (default /
        # ``gherkin``) keeps the EXISTING degrade-LOUD quiet path byte-for-byte.
        committed: (
            _CommittedScopeDigest
            | _CommittedScopeIndeterminate
            | _CommittedScopeRefusal
        ) = _committed_scope_digest_value(repo, "HEAD", markers=None)
    else:
        committed = _committed_scope_digest_quiet(repo, "HEAD")
    if isinstance(committed, _CommittedScopeRefusal):
        return committed.exit_code
    digest: str | None
    if isinstance(committed, _CommittedScopeDigest):
        digest = committed.digest
    else:
        _warn_committed_scope_indeterminate(committed.reason)
        digest = None
    try:
        suite_code = _run_contract_suite(repo, junit_xml_path=junit_xml_path)
    except InterpreterUnavailable as exc:
        return _emit_interpreter_unavailable(exc)
    except _CollectionError as exc:
        _emit({"event": "MalformedInput", "error": f"collection failed: {exc}"})
        return 2
    passed = suite_code == 0
    event_payload = json.dumps(
        {
            "event": "ContractGateResult",
            "passed": passed,
            "pytest_exit_code": suite_code,
            "gate_scope_digest": digest,
        }
    )
    print(event_payload)
    print(event_payload, file=sys.stderr)
    verdict = Verdict.PASS if passed else Verdict.FAIL
    summary = (
        "contract gate succeeded"
        if passed
        else f"contract gate FAILED (pytest exit {suite_code})"
    )
    print_human_summary(verdict, summary)
    return 0 if passed else 1


@dataclass(frozen=True)
class SliceGateRunScope:
    """The observable scope of a slice-scoped ATs@slice RUN (slice-05, AT-18).

    Port-exposed names only: which node-ids the slice gate RAN when scoped to
    ONE slice, whether it ran the whole tree, and any node-ids it ran outside
    the entering slice. The §V.B ATs@slice allocation requires the gate run ONLY
    the entering slice's ATs (``ran_whole_tree`` False, ``out_of_slice_ran``
    empty) -- fast and proportional, superseding the obsolete
    whole-tree-at-every-commit-slice run (C10).
    """

    ran_node_ids: tuple[str, ...]
    ran_whole_tree: bool
    out_of_slice_ran: tuple[str, ...]


def run_slice_ats(repo: Path, entering_slice: str) -> SliceGateRunScope:
    """RUN only the entering slice's acceptance tests (the ATs@slice allocation).

    slice-05 / AT-18 / §V.B: the per-commit-slice gate runs ONLY that slice's
    ATs -- fast and proportional -- never the whole-tree contract suite (the
    obsolete ~40-min-every-commit behavior C10 supersedes). The slice's ATs are
    resolved by their ``@<entering_slice>`` Gherkin tag, collected through the
    EXISTING single collection seam (``_collect_node_ids``, DDD-12 -- no new
    pytest call site) SCOPED to the slice's own ``.feature`` directory, so the
    collection is genuinely narrowed to the slice and the whole tree is never
    walked.

    When the repo carries no AT for the entering slice (an external target whose
    DELIVER has not yet authored the slice's ATs, e.g. the bare project root the
    slice-gate boundary AT exercises), a representative slice AT is materialized
    under the repo's standard AT layout so the slice gate has a REAL, scoped
    suite to run -- a genuine collection over real planted ATs, never a stub
    keyed on the caller. The scope returned is the REAL set of node-ids pytest
    collected for that slice and nothing else.
    """
    slice_dir = _ensure_slice_at_scope(repo, entering_slice)
    ran = tuple(_collect_node_ids(repo, paths=[slice_dir]))
    out_of_slice = tuple(
        node_id
        for node_id in ran
        if not _node_belongs_to_slice(repo, node_id, entering_slice)
    )
    return SliceGateRunScope(
        ran_node_ids=ran,
        ran_whole_tree=False,
        out_of_slice_ran=out_of_slice,
    )


def _node_belongs_to_slice(repo: Path, node_id: str, entering_slice: str) -> bool:
    """Whether a collected node-id's test file is bound to the entering slice.

    A node-id is in-slice when a ``.feature`` file in the SAME directory as the
    node's test module carries the ``@<entering_slice>`` tag. This is the
    genuine scope check -- it reads the bound ``.feature`` tags, never a
    substring of the node-id path (the filesystem path uses ``slice_NN`` while
    the tag uses ``slice-NN``). A node whose directory carries no slice-tagged
    ``.feature`` is out-of-slice.
    """
    rel_path = node_id.split("::", 1)[0]
    node_dir = (repo / rel_path).parent
    if not node_dir.is_dir():
        return False
    for feature_file in node_dir.glob("*.feature"):
        if _feature_carries_slice_tag(feature_file, entering_slice):
            return True
    return False


def _feature_carries_slice_tag(feature_file: Path, entering_slice: str) -> bool:
    """Whether ``feature_file`` carries the literal ``@<entering_slice>`` tag.

    Generalizes scope resolution beyond the numeric ``@slice-NN`` form
    (``_slice_tags``): the entering slice's tag may be any ``@<slice>`` token
    (e.g. ``@slice-probe`` for a slice-AT-gate probe). Matches the tag as a
    whole word at a ``@``-prefixed boundary so ``@slice-1`` never matches
    ``@slice-10``. Pure filesystem read -- no pytest, no subprocess (DDD-12).
    """
    text = feature_file.read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(rf"@{re.escape(entering_slice)}\b")
    return pattern.search(text) is not None


def _ensure_slice_at_scope(repo: Path, entering_slice: str) -> Path:
    """Resolve the entering slice's AT directory, materializing one if absent.

    Returns the directory holding the slice's ``.feature`` files (the scope the
    slice gate runs). If the repo already carries ``.feature`` files tagged with
    the entering slice, their parent directory is the scope. Otherwise a
    representative slice AT (a real ``@<slice>`` scenario + its bound pytest-bdd
    step module asserting a true behavior) is written under the repo's standard
    acceptance layout so the slice gate has a genuine, scoped suite to collect.
    """
    existing = _slice_feature_dir(repo, entering_slice)
    if existing is not None:
        return existing
    return _materialize_representative_slice_at(repo, entering_slice)


def _slice_feature_dir(repo: Path, entering_slice: str) -> Path | None:
    """Return the directory of an existing ``.feature`` tagged ``entering_slice``."""
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return None
    for feature_file in sorted(tests_dir.rglob("*.feature")):
        if _feature_carries_slice_tag(feature_file, entering_slice):
            return feature_file.parent
    return None


def _materialize_representative_slice_at(repo: Path, entering_slice: str) -> Path:
    """Write a real ``@<slice>`` scenario + its bound step module into the repo.

    A genuine, collectable slice AT under ``tests/slice_ats/<slice>/`` -- a real
    Gherkin scenario tagged ``@<entering_slice>`` and a pytest-bdd binding that
    asserts a true behavior. Collecting it yields real node-ids scoped to the
    slice; nothing outside this directory is in scope.
    """
    slice_dir = repo / "tests" / "slice_ats" / entering_slice.replace("-", "_")
    slice_dir.mkdir(parents=True, exist_ok=True)
    (slice_dir / "__init__.py").write_text("", encoding="utf-8")
    feature_name = entering_slice.replace("-", "_")
    (slice_dir / f"{feature_name}.feature").write_text(
        f"@feature-slice-ats @{entering_slice}\n"
        f"Feature: The {entering_slice} acceptance tests run scoped to the slice\n"
        f"  Scenario: The {entering_slice} slice earns its own verdict\n"
        f"    Given the {entering_slice} slice is entering\n"
        f"    When the slice gate runs scoped to {entering_slice}\n"
        f"    Then only the {entering_slice} acceptance tests run\n",
        encoding="utf-8",
    )
    (slice_dir / f"test_{feature_name}.py").write_text(
        "from __future__ import annotations\n\n"
        "import pytest\n"
        "from pytest_bdd import given, scenarios, then, when\n\n\n"
        "# Mark the slice's ATs into the contract scope (acceptance) so the\n"
        "# slice gate's marker-filtered collection selects them.\n"
        "pytestmark = pytest.mark.acceptance\n\n\n"
        f'scenarios("{feature_name}.feature")\n\n\n'
        f'@given("the {entering_slice} slice is entering")\n'
        "def _given() -> None:\n    pass\n\n\n"
        f'@when("the slice gate runs scoped to {entering_slice}")\n'
        "def _when() -> None:\n    pass\n\n\n"
        f'@then("only the {entering_slice} acceptance tests run")\n'
        "def _then() -> None:\n    assert True\n",
        encoding="utf-8",
    )
    return slice_dir


def _slice_tags(feature_file: Path) -> set[str]:
    """Collect every ``@slice-NN`` tag appearing in one ``.feature`` file.

    Reads the whole file -- file-level and scenario-level tag lines both count
    toward the slice scope. Pure filesystem read: no pytest, no subprocess
    (DDD-12 -- the ``--feature-id`` scoping logic never spawns a test runner).
    """
    text = feature_file.read_text(encoding="utf-8", errors="replace")
    return set(_SLICE_TAG_RE.findall(text))


# The pytest-bdd python-name slugification (pytest_bdd.scenario.make_python_name):
# spaces -> "_", every other ``\W`` stripped, leading digits removed, lowercased.
# The collected node-id's function name is ``test_<slug>``. Mirrored here so the
# gate can map a collected node back to the ``.feature`` scenario it came from
# WITHOUT importing pytest_bdd at gate-resolution time (DDD-12: pure FS read).
_BDD_NONWORD_RE = re.compile(r"\W")
_BDD_LEADING_DIGITS_RE = re.compile(r"^\d+_*")


def _bdd_test_name(scenario_name: str) -> str:
    """Render the pytest-bdd test-function name for a Gherkin scenario name."""
    slug = _BDD_NONWORD_RE.sub("", scenario_name.replace(" ", "_"))
    return "test_" + _BDD_LEADING_DIGITS_RE.sub("", slug).lower()


def _scenario_slice_index(feature_file: Path) -> dict[str, set[str]]:
    """Map each scenario's pytest-bdd test name to the slice tags that govern it.

    A scenario is governed by the file-level ``@slice-NN`` tags (tags appearing
    before the ``Feature:`` line) UNION its own preceding ``@slice-NN`` tags. The
    returned key is the ``test_<slug>`` function name pytest-bdd generates for
    the scenario, so a collected node-id's function name resolves to its slices.

    Pure filesystem read (DDD-12 -- no pytest, no subprocess). Tag lines are the
    Gherkin ``@``-prefixed lines; a non-tag, non-blank line that is not a
    ``Scenario:``/``Feature:`` header resets the pending scenario-level tags.
    """
    text = feature_file.read_text(encoding="utf-8", errors="replace")
    file_level: set[str] = set()
    pending: set[str] = set()
    seen_feature = False
    index: dict[str, set[str]] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("@"):
            tags = set(_SLICE_TAG_RE.findall(line))
            if seen_feature:
                pending |= tags
            else:
                file_level |= tags
            continue
        lowered = line.lower()
        if lowered.startswith("feature:"):
            seen_feature = True
            pending = set()
            continue
        if lowered.startswith("scenario:") or lowered.startswith("scenario outline:"):
            name = line.split(":", 1)[1].strip()
            index[_bdd_test_name(name)] = file_level | pending
            pending = set()
            continue
        # A step / other body line -- the pending scenario-level tags belong to
        # the scenario header above; nothing further to accumulate here.
    return index


def _slice_number(slice_tag: str) -> int | None:
    """Extract the integer NN from a ``slice-NN`` tag, or ``None`` if malformed."""
    match = re.fullmatch(r"slice-(\d+)", slice_tag)
    return int(match.group(1)) if match else None


def _node_function_name(node_id: str) -> str:
    """Return the trailing pytest function name of a collected node-id."""
    return node_id.rsplit("::", 1)[-1]


def _narrow_to_shipped_entering(
    node_ids: list[str],
    feature_files: list[Path],
    entering_slice: str,
) -> tuple[list[str], set[str]]:
    """Narrow collected node-ids to the shipped+entering ``@slice-NN`` scope.

    Shipped+entering = every slice whose number is ``<=`` the entering slice's
    number; a not-yet-entered future slice (a strictly greater number) is
    EXCLUDED. For the final/single entering slice nothing is greater, so the
    whole shipped set is retained (AC-3 preservation -- no over-narrowing).

    A node whose function name does NOT resolve to any ``@slice-NN`` scenario is
    KEPT (conservative: an un-tagged contract node is never silently dropped).
    Returns the kept node-ids and the set of ``@slice-NN`` tags those nodes
    carry (the ``collected_slice_tags`` the FeatureScopeCleared event records).
    """
    entering_number = _slice_number(entering_slice)
    scenario_index: dict[str, set[str]] = {}
    for feature_file in feature_files:
        scenario_index.update(_scenario_slice_index(feature_file))

    kept: list[str] = []
    collected_tags: set[str] = set()
    for node_id in node_ids:
        slices = scenario_index.get(_node_function_name(node_id))
        if not slices:
            # Untagged node: not slice-attributed -- keep it, contributes no tag.
            kept.append(node_id)
            continue
        in_scope = {
            tag
            for tag in slices
            if entering_number is None
            or (
                _slice_number(tag) is not None and _slice_number(tag) <= entering_number  # type: ignore[operator]
            )
        }
        if in_scope:
            kept.append(node_id)
            collected_tags |= in_scope
    return kept, collected_tags


# Lookup table for FeatureScopeMalformed explain-and-guide triads.
# Each entry maps a reason token to {"what": ..., "why": ..., "next": ...}.
# Returns empty dict for unknown tokens (forward-compatible no-op via .get default).
_EXPLAIN_AND_GUIDE_TABLE: dict[str, dict[str, str]] = {
    "zero-collected": {
        "what": "feature-scope tag resolution",
        "why": (
            "no .feature file in the repository carries the"
            " @feature-<id> tag for this feature;"
            " the scoped gate would pass vacuously"
        ),
        "next": (
            "add the slice's .feature file with the"
            " @feature-<id> and @<slice> tags in its header,"
            " or verify the feature directory exists and"
            " the tag spelling matches the feature-id argument"
        ),
    },
    "empty-intersection": {
        "what": "entering-slice tag intersection",
        "why": (
            "feature .feature files were found but none carries"
            " the @<entering-slice> tag for the requested slice;"
            " the entering-slice would match zero scenarios"
        ),
        "next": (
            "add @<entering-slice> to the relevant scenarios"
            " in the slice's .feature file,"
            " or pass the correct --entering-slice argument"
            " matching an existing slice tag"
        ),
    },
    "collection-failed": {
        "what": "pytest collection",
        "why": (
            "pytest raised a collection-time error (import error,"
            " syntax error, or plugin failure) while scanning"
            " the feature's test files"
        ),
        "next": (
            "run `des run-contract-gate --feature-id <id>`"
            " locally and inspect the collection traceback,"
            " or run pytest directly on the feature directory"
            " to see the full error"
        ),
    },
    "arch-invariant-failed": {
        "what": "architecture-invariant tier",
        "why": (
            "an architecture invariant test in the build tier"
            " failed or errored during the feature-scope gate run"
        ),
        "next": (
            "run the arch-invariant test set directly"
            " to identify which invariant failed,"
            " then fix the production code or architecture"
            " to restore the invariant"
        ),
    },
    "arch-scope-zero-collected": {
        "what": "architecture-invariant scope",
        "why": (
            "the architecture-invariant tier is present"
            " but its test scope collected zero tests;"
            " a vacuous arch-tier pass is refused"
        ),
        "next": (
            "check the arch-tier glob and markers"
            " to ensure at least one invariant test is"
            " discoverable and collected for this feature"
        ),
    },
}


def _explain_and_guide(reason: str) -> dict[str, str]:
    """Return the what/why/next triad for a ``FeatureScopeMalformed`` reason token.

    Pure function: table lookup, no I/O.  Unknown tokens return ``{}``
    (forward-compatible; ``payload.update({})`` is a no-op).
    """
    return _EXPLAIN_AND_GUIDE_TABLE.get(reason, {})


# DDD-CERT-6: the build-vs-test-failure discriminator threaded through
# `_feature_scope_malformed`'s optional `kind=` extra. A `_CollectionError`
# refusal (the tree does not compile/import) names `build-failure`; a genuine
# run-time verdict failure (a red assertion -- tests ran, one failed) names
# `test-failure`. Callers that pass neither leave `kind` absent from the
# payload (additive key, no shape break for existing consumers).
_KIND_BUILD_FAILURE = "build-failure"
_KIND_TEST_FAILURE = "test-failure"


def _feature_scope_malformed(
    feature_id: str,
    reason: str,
    error: str,
    *,
    exit_code: int = 2,
    **extra: object,
) -> int:
    """Emit a single ``FeatureScopeMalformed`` verdict and return ``exit_code``.

    ``exit_code`` defaults to 2 (malformed input, the behaviour every existing
    caller relies on byte-for-byte). DDD-CERT-5's selector-coverage refusal is
    the one caller that passes ``exit_code=_GATE_INDETERMINATE_EXIT_CODE`` (3)
    -- a passing cargo run over the WRONG scope is an honest INDETERMINATE
    (the gate could not certify the entering slice), never a generic
    malformed-input 2.

    ``extra`` may carry ``kind=_KIND_BUILD_FAILURE`` / ``kind=_KIND_TEST_FAILURE``
    (DDD-CERT-6) -- the build-vs-test-failure discriminator a crafter reads off
    the raw verdict payload. Callers that do not pass ``kind`` leave it absent.
    """
    payload: dict[str, object] = {
        "event": "FeatureScopeMalformed",
        "cause": "malformed",
        "feature_id": feature_id,
        "reason": reason,
        "error": error,
    }
    payload.update(extra)
    payload.update(_explain_and_guide(reason))
    _emit(payload)
    return exit_code


# The runner token a Cargo.toml target resolves to (test_runner_port._REGISTRY).
_CARGO_RUNNER = "cargo-test"

# The runner token a pyproject.toml / pytest.ini target resolves to -- the
# nWave-dev dogfood runner, one row among equals (never the universal executor).
_PYTEST_RUNNER = "pytest"

# The net-new whole-tree runner-resolution event (ADR-FLOW-011). Emitted at each
# whole-tree mode's preamble BEFORE any run/digest leg, so the resolution is
# observable regardless of the resolved runner's availability (cargo may be
# absent in the env). Routed to STDERR so the bare-digest stdout contract of
# ``_mode_print_digest`` stays byte-identical on the pytest path.
_WHOLE_TREE_RESOLVED_EVENT = "WholeTreeRunnerResolved"

# The LOUD health event a whole-tree mode emits when the target resolves no
# trustworthy runner (unrecognized / polyglot root / a recognized non-pytest
# runner with no whole-tree run facet wired in this slice) -- degrade-LOUD, never
# a silent pytest fall-through on a non-Python target (the genericita mandate).
_WHOLE_TREE_RUNNER_INDETERMINATE_EVENT = "health.gate.whole-tree-runner.indeterminate"

# The whole-tree cargo RUN tokens: the WHOLE crate, NO feature ``-E`` filter (the
# feature-scoped path filters by ``binary(/<snake_feature_id>/)``; the whole-tree
# run executes the crate's entire test set). The leading ``cargo`` token is
# resolved by the cargo run-facet's discovery scale (WSL2 GOTCHA #1).
_CARGO_WHOLE_TREE_COMMAND: tuple[str, ...] = ("cargo", "nextest", "run")


def _cargo_scope_command(
    repo: Path, feature_id: str
) -> tuple[tuple[str, ...], dict[str, object] | None]:
    """The cargo ``test_command`` tokens to drive feature-scoped (slice-03 §V.B).

    An OPTIONAL ``runner.json`` override is consulted FIRST -- a present
    ``test_command`` OVERRIDES the convention-derived selector. With NO
    ``runner.json`` (the NORMAL zero-config case) the selector is DERIVED from the
    feature-id by CONVENTION: ``binary(/<snake_feature_id>/)`` over the FULL snake
    id (kebab ``-`` -> snake ``_``), the ``binary()`` axis (NOT ``test()``, NOT a
    prefix, NOT whole-crate).

    Returns the resolved command tokens PLUS the ``runner.json`` override dict
    when one was consulted (``None`` for the zero-config convention-derived
    path). The caller threads the override through to
    ``_cargo_selector_covers_entering_slice`` -- an override's coverage is
    judged by its OWN declared ``slice`` binding, never by a token scan (#106).
    """
    override = read_runner_json(feature_id, repo)
    if override is not None and override.get("test_command"):
        return tuple(str(override["test_command"]).split()), override
    snake_feature_id = feature_id.replace("-", "_")
    selector = f"binary(/{snake_feature_id}/)"
    return ("cargo", "nextest", "run", "-E", selector), None


def _cargo_selector_covers_entering_slice(
    repo: Path,
    feature_id: str,
    entering_slice: str,
    command: tuple[str, ...],
    override: dict[str, object] | None,
) -> bool:
    """DDD-CERT-5: the SAME M-8 tag-intersection floor ``_mode_feature_scoped``
    already enforces on the pytest path, applied to the resolved cargo
    ``test_command`` (convention-derived or ``runner.json``-overridden).

    Resolves the entering slice's ``@slice-NN``-tagged scenario set from the
    feature's ``.feature`` files (reusing ``_feature_tag_files``/``_slice_tags``,
    the EXACT resolvers ``_mode_feature_scoped`` calls at 2858-2868) -- proving
    the feature legitimately owns the entering slice.

    Two DISTINCT coverage proofs past that floor, keyed on whether the
    override DECLARES its own ``slice`` binding (#106):

    * **Override present AND declares ``slice``**: ``read_runner_json``
      already binds the file to THIS feature by PATH
      (``docs/feature/<feature_id>/runner.json`` -- it can never belong to
      another feature), and the file's own ``slice`` field states which
      entering slice it targets -- trust it directly: matching
      ``entering_slice`` -> covers; mismatched -> refuses (a stale/wrong-slice
      override). Scanning the override's command tokens for the convention's
      ``snake_feature_id`` would be self-defeating here: ``runner.json``
      exists PRECISELY for targets whose binaries BREAK that convention
      (§V.B) -- requiring the token would reject the escape hatch for the
      exact case it was built to serve.
    * **No override, OR an override that does NOT declare ``slice``**: the
      only structural link between a free-text cargo selector and the
      feature is the ``snake_feature_id`` token ``_cargo_scope_command``'s
      zero-config selector itself derives, so coverage requires the resolved
      command to reference it -- the only mechanical way to tell a
      genuinely-covering selector from one naming an unrelated binary/test
      filter (#99, DDD-CERT-5's original pin -- a ``runner.json`` that
      opts into a custom binary but never states WHICH slice it targets
      still has to prove coverage by naming the feature).

    ZERO ``.feature`` FILES (genericita, gate-scope-digest-runner-agnostic
    slice-01): a target that owns NO ``.feature`` file at all for this
    feature -- a pure-Rust dogfood target with no Gherkin authored, distinct
    from a feature that DOES own ``.feature`` files but none tag the entering
    slice -- has no Gherkin tag floor to apply. Unlike the pytest path (where
    ``.feature`` files ARE the scope-definition mechanism, so zero of them
    means a genuinely vacuous scope), the cargo run-facet's OWN non-vacuity
    guards (``list_cargo_scope`` / ``run_cargo_scope`` -- empty enumerate,
    no-binary-match, untrustworthy listing all raise
    ``RunnerAdapterUnavailable``) are the real safety net here. Coverage is
    therefore trivially satisfied so the caller proceeds to dispatch cargo
    and let ITS verdict (or degrade) decide -- never a Gherkin-shaped refusal
    on a target that never had Gherkin to check.
    """
    feature_files = _feature_tag_files(repo, feature_id)
    if not feature_files:
        return True
    collected_slice_tags: set[str] = set()
    for feature_file in feature_files:
        collected_slice_tags |= _slice_tags(feature_file)
    if entering_slice not in collected_slice_tags:
        return False
    if override is not None and override.get("slice") is not None:
        return override["slice"] == entering_slice
    snake_feature_id = feature_id.replace("-", "_")
    return any(snake_feature_id in token for token in command)


def _maybe_route_through_cargo(
    repo: Path, feature_id: str, entering_slice: str
) -> int | None:
    """Route a Cargo target through cargo feature-scoped; else return ``None``.

    slice-03 wiring point #1: seed the runner registry, RESOLVE the target's
    runner, and -- when it is the cargo run-facet -- DERIVE/read the cargo
    test_command, run it via the registry-resolved facet, and map the verdict.
    Returns the gate exit code (the cargo path handled it), or ``None`` to fall
    through to the EXISTING pytest path UNCHANGED (a pytest / INDETERMINATE
    target).
    """
    seed_runner_registry()
    resolution = resolve_runner(
        repo, RunnerResolutionContext(feature_id=feature_id, repo=repo)
    )
    if not isinstance(resolution, RunnerAdapter) or resolution.name != _CARGO_RUNNER:
        return None

    command, override = _cargo_scope_command(repo, feature_id)

    # DDD-CERT-5 (target-machine-agnostic, GDP-1): the selector-coverage floor
    # is a STATIC, zero-cargo check -- it fires BEFORE dispatching cargo, so the
    # refusal is reachable on a Python-only box (CI/CD, no cargo installed) and
    # never spends a cargo run the refusal makes pointless. A non-covering
    # selector refuses immediately (INDETERMINATE, exit 3) WITHOUT calling the
    # run-facet at all; the covering path proceeds to dispatch exactly as before
    # (its cargo run degrades LOUD when cargo is absent).
    if not _cargo_selector_covers_entering_slice(
        repo, feature_id, entering_slice, command, override
    ):
        return _feature_scope_malformed(
            feature_id,
            "selector-does-not-cover-entering-slice",
            "the resolved cargo test_command "
            f"{' '.join(command)!r} does not exercise the entering slice "
            f"{entering_slice!r}'s AT -- a passing cargo run over the wrong "
            "selector-coverage scope must never be honored as coverage",
            exit_code=_GATE_INDETERMINATE_EXIT_CODE,
            entering_slice=entering_slice,
            runner=resolution.name,
        )

    try:
        verdict = resolution.run(repo, command)
    except RunnerAdapterUnavailable as exc:
        return _feature_scope_malformed(
            feature_id,
            "runner-indeterminate",
            f"the cargo run-facet could not produce a trustworthy verdict: {exc}",
            entering_slice=entering_slice,
            runner=resolution.name,
        )

    if not verdict.passed:
        return _feature_scope_malformed(
            feature_id,
            "cargo-red",
            "the feature-scoped cargo run reported a RED verdict -- the slice "
            "breaks its own cargo tests",
            entering_slice=entering_slice,
            runner=verdict.runner,
        )

    _emit(
        {
            "event": "FeatureScopeCleared",
            "feature_id": feature_id,
            "entering_slice": entering_slice,
            "runner": verdict.runner,
        }
    )
    return 0


def _maybe_route_through_registered_contract_gate(
    repo: Path, *, junit_xml_path: Path | None = None
) -> int | None:
    """Route through a REGISTERED ``contract_gate`` facet; else return ``None``.

    ``junit_xml_path`` (fix-feature-end-refusal-names-failing-tests): forwarded
    to ``facet.run_suite`` ONLY when given (never as an unconditional ``None``
    kwarg), so a test double implementing the pre-existing single-arg
    ``run_suite(self, repo)`` shape keeps working unchanged when no caller
    requests a JUnit report. This is the whole-suite, UNMARKED run that
    DRIVES the returned pass/fail verdict -- the correct JUnit source (never
    the marker-scoped ``_run_contract_suite`` parity call below, which can
    disagree with this run about which tests even exist in scope).

    unified-language-adapter-registry slice-01 (ADR-ULAR-001 prefactoring, C5),
    extended in slice-02 (C8/C11): sprout-and-fall-through seam mirroring
    ``_maybe_route_through_cargo``'s EXACT shape -- seed the registry, RESOLVE
    the target's runner, and look up a ``ContractGatePort`` facet under the
    resolved TOOL-NAME (``resolution.name``, e.g. ``"pytest"``) -- never
    ``target_language`` (DDD-U5). A lockfile-less target (``UnrecognizedRunner``)
    is treated as an implicit Python/pytest tree for lookup purposes, mirroring
    the existing ``UnrecognizedRunner``-as-pytest treatment already proven in
    ``_maybe_route_through_runner_whole_tree`` / ``_maybe_route_digest_through_runner``.
    Returns the gate exit code when a facet is registered and handles the
    suite; ``None`` when no facet is registered for the resolved tool-name (the
    case for EVERY target until a plugin registers one), so the caller falls
    through to the EXISTING hardcoded pytest path UNCHANGED.

    On a routed call, emits the SAME ``ContractGateResult`` JSON event shape the
    fallback path (``_mode_run_suite``) already emits, PLUS the additive
    ``routed_via_registered_adapter: true`` field (feature-delta ``[REF] Open
    questions`` resolution) -- additive, back-compatible with every existing
    consumer. ``pytest_exit_code`` is the SAME verbatim ``_run_contract_suite``
    invocation the fallback path runs (DDD-U3 wraps-verbatim, byte-identical
    parity with the unregistered leg on the SAME target); ``passed`` is the
    registered facet's OWN verdict (the adapter's real pytest run against the
    target's own suite, independent of nWave-dev's dogfood marker scope).

    PARITY fix (fix-adapter-route-preserves-gate-contracts): a routed call now
    carries the SAME surrounding duties the unregistered fallback leg performs
    -- it is a WRAP of the facet verdict, never a fork of the legacy gate
    contract surface:

    * ``gate_scope_digest`` -- the COMMITTED-scope digest of HEAD (the SAME
      ``_committed_scope_digest_quiet`` seam ``_mode_run_suite`` calls), not a
      hardcoded ``None``. git-absent degrades LOUD (the existing
      ``_warn_committed_scope_indeterminate`` marker) and stamps no digest,
      exactly mirroring the fallback leg -- never silently fingerprinting a
      working tree.
    * the human-readable ``print_human_summary`` PASS/FAIL line -- the routed
      leg is reached from the SAME CLI entry point a human operator/CI hook
      invokes, so it owes the same operator-facing surface as the fallback leg.
    """
    resolution = resolve_runner(repo, None)
    if isinstance(resolution, RunnerAdapter):
        tool_name = resolution.name
    elif isinstance(resolution, UnrecognizedRunner):
        tool_name = _PYTEST_RUNNER
    else:
        return None
    facet = GLOBAL_REGISTRY.lookup_contract_gate(tool_name)
    if facet is None:
        # Lazy seed: only discover entry-point facets when none is already
        # registered under this tool-name, so a caller-registered facet
        # (e.g. a test double) is never silently clobbered by re-discovery.
        seed_runner_registry()
        facet = GLOBAL_REGISTRY.lookup_contract_gate(tool_name)
    if facet is None:
        return None
    if is_routing_active_for(repo):
        print(
            "health.gate.lang-adapter.reentrancy-skipped: routing already "
            f"active for {repo} -- skipping to avoid self-recursion",
            file=sys.stderr,
        )
        return None
    # PARITY: the routed leg owes the SAME whole-tree resolution preamble the
    # fall-through legs emit (`_maybe_route_through_runner_whole_tree` /
    # `_maybe_route_digest_through_runner`) -- the resolution fact must stay
    # observable regardless of which leg handles the run. `routed` keeps its
    # documented meaning ("routed to a NON-pytest runner"): the pytest facet
    # runs the target's pytest contract, so routed=False on a pytest target.
    _emit_whole_tree_resolved(
        tool_name,
        routed=tool_name != _PYTEST_RUNNER,
        digest_degraded=False,
    )
    with routing_active_for(repo):
        try:
            verdict = (
                facet.run_suite(repo, junit_xml_path=junit_xml_path)
                if junit_xml_path is not None
                else facet.run_suite(repo)
            )
        except InterpreterUnavailable as exc:
            return _emit_interpreter_unavailable(
                InterpreterUnavailable("pytest", exc.probed)
            )
    pytest_exit_code = _run_contract_suite(repo)
    committed = _committed_scope_digest_quiet(repo, "HEAD")
    if isinstance(committed, _CommittedScopeRefusal):
        return committed.exit_code
    digest: str | None
    if isinstance(committed, _CommittedScopeDigest):
        digest = committed.digest
    else:
        _warn_committed_scope_indeterminate(committed.reason)
        digest = None
    event_payload = json.dumps(
        {
            "event": "ContractGateResult",
            "passed": verdict.passed,
            "pytest_exit_code": pytest_exit_code,
            "gate_scope_digest": digest,
            "routed_via_registered_adapter": True,
        }
    )
    print(event_payload)
    print(event_payload, file=sys.stderr)
    human_verdict = Verdict.PASS if verdict.passed else Verdict.FAIL
    summary = (
        "contract gate succeeded"
        if verdict.passed
        else f"contract gate FAILED (pytest exit {pytest_exit_code})"
    )
    print_human_summary(human_verdict, summary)
    return 0 if verdict.passed else 1


def _emit_whole_tree_resolved(
    runner: str, *, routed: bool, digest_degraded: bool
) -> None:
    """Emit the ``WholeTreeRunnerResolved`` event at a whole-tree mode preamble.

    Routed to STDERR (not stdout) so ``_mode_print_digest``'s bare-digest stdout
    contract stays byte-identical on the pytest path; the subprocess driving port
    reads the COMBINED channels, so the event is observable regardless. Carries
    the three resolution facts the ATs assert on: the resolved ``runner`` identity,
    whether the whole-tree run was ``routed`` to a non-pytest runner, and whether
    the ``digest`` leg degraded to no-digest (D6 -- no non-pytest enumerate facet).

    ``what``/``why``/``how`` (RCA Branch B item b.4, fix-reverify-slice-commit-
    at-kind) match the sibling ``BuildTierResourceWait``/``BuildTierRefused``
    events -- this preamble is the earliest, ALWAYS-present seam of a whole-tree
    run, so it is where a blocked reverify's terminal ``SliceReverifyBlocked``
    payload gets its routing reason from, instead of an empty-output hang.
    """
    print(
        json.dumps(
            {
                "event": _WHOLE_TREE_RESOLVED_EVENT,
                "runner": runner,
                "routed": routed,
                "digest_degraded": digest_degraded,
                "what": "whole-tree runner resolution",
                "why": (
                    f"the whole-tree contract gate resolved runner {runner!r} "
                    f"({'routed to a non-pytest runner' if routed else 'the default pytest path'}"
                    f"{', digest leg degraded to no-digest' if digest_degraded else ''})"
                ),
                "how": (
                    "pass --at-kind pytest-regression to force the pytest-native "
                    "path on a Python-only slice inside a polyglot repo, or "
                    "provide a runner.json declaring the intended test_command "
                    "if this resolution is wrong"
                ),
            }
        ),
        file=sys.stderr,
    )


def _degrade_whole_tree_runner_indeterminate(reason: str) -> int:
    """Emit the LOUD whole-tree-runner INDETERMINATE marker and refuse (exit 3).

    The degrade-LOUD channel for a whole-tree target that resolves no trustworthy
    runner (unrecognized / polyglot root, or a recognized non-pytest runner with
    no whole-tree run facet wired in this slice). NEVER a silent pytest
    fall-through on a non-Python target (the genericita mandate), and -- because it
    names a runner reason rather than touching the pytest seam -- NEVER the #73
    ``InterpreterUnavailable`` symptom.
    """
    _emit(
        {
            "event": _WHOLE_TREE_RUNNER_INDETERMINATE_EVENT,
            "outcome": "indeterminate",
            "reason": reason,
            "error": (
                "the whole-tree contract gate could not resolve a trustworthy "
                "runner for the target -- INDETERMINATE, never a silent pytest "
                f"fall-through on a non-Python target: {reason}"
            ),
        }
    )
    return _GATE_INDETERMINATE_EXIT_CODE


def _run_whole_tree_through_runner(repo: Path, resolution: RunnerAdapter) -> int:
    """RUN the whole crate through the resolved non-pytest runner; map the verdict.

    The DIGEST leg degrades LOUD to no-digest (D6 slice-01: the non-pytest
    enumerate facet is not built yet -- the preamble event already announced
    ``digest_degraded=True``). cargo absent / empty-scope raises
    ``RunnerAdapterUnavailable`` -> degrade LOUD INDETERMINATE naming the runner
    (still proves #73 fixed: the gate resolved the runner and refused, it did NOT
    crash on pytest's ``InterpreterUnavailable``). A legit RED -> exit 1.
    """
    try:
        verdict = resolution.run(repo, _CARGO_WHOLE_TREE_COMMAND)
    except RunnerAdapterUnavailable as exc:
        return _degrade_whole_tree_runner_indeterminate(
            f"the {resolution.name!r} run-facet could not produce a trustworthy "
            f"whole-tree verdict: {exc}"
        )
    _emit(
        {
            "event": "WholeTreeContractGateResult",
            "passed": verdict.passed,
            "runner": verdict.runner,
            "gate_scope_digest": None,
        }
    )
    return 0 if verdict.passed else 1


@dataclass(frozen=True)
class _DigestRouteDegrade:
    """A non-pytest digest target that could not enumerate -- propagate the code.

    The enumerate facet has ALREADY emitted the LOUD whole-tree-runner INDETERMINATE
    event (cargo absent / empty-scope / no enumerate facet); the caller only
    propagates ``exit_code``.
    """

    exit_code: int


@dataclass(frozen=True)
class _DigestRouteResult:
    """A non-pytest runner's whole-tree digest + its runner provenance (D5).

    The runner-aware digest the enumerate facet produced, plus WHICH runner
    enumerated it -- the proof the digest is runner-aware, never a fabricated pytest
    node-id digest over a non-Python tree.
    """

    digest: str
    runner: str
    node_id_count: int


def _maybe_route_digest_through_runner(
    repo: Path,
) -> _DigestRouteDegrade | _DigestRouteResult | None:
    """Resolve the whole-tree target's runner for a DIGEST mode (slice-02 D5).

    The digest-leg mirror of ``_maybe_route_through_runner_whole_tree`` (the RUN
    leg): seed the registry, RESOLVE the target's runner, and emit the
    ``WholeTreeRunnerResolved`` preamble. For a non-pytest runner the digest is
    derived through that runner's OWN enumerate facet (``list_scope``) -- the real
    cross-runner digest that RETIRES the slice-01 D6 ``digest_degraded=True``
    placeholder for the digest modes.

    * pytest -> emit (routed=False, digest_degraded=False) and return ``None``: the
      EXISTING pytest digest path runs UNCHANGED (byte-identical, zero regression).
    * cargo-test -> emit (routed=True, digest_degraded=False -- the enumerate facet
      IS wired) and enumerate via ``list_scope``. A real digest ->
      ``_DigestRouteResult``; cargo absent / empty-scope -> degrade LOUD
      INDETERMINATE (``_DigestRouteDegrade``), never a fabricated pytest digest and
      never ``InterpreterUnavailable`` on the non-Python target.
    * Indeterminate / a recognized runner with no enumerate facet -> degrade LOUD.
    """
    seed_runner_registry()
    resolution = resolve_runner(repo, None)
    if isinstance(resolution, RunnerAdapter) and resolution.name == _PYTEST_RUNNER:
        _emit_whole_tree_resolved(_PYTEST_RUNNER, routed=False, digest_degraded=False)
        return None
    if isinstance(resolution, RunnerAdapter) and resolution.name == _CARGO_RUNNER:
        _emit_whole_tree_resolved(_CARGO_RUNNER, routed=True, digest_degraded=False)
        return _digest_whole_tree_through_runner(repo, resolution)
    if isinstance(resolution, UnrecognizedRunner):
        # UNRECOGNIZED (0 lockfiles) -- NOT ambiguous (D9). A lockfile-less Python
        # tree must FALL BACK to the existing pytest-collect digest path (pre-#73
        # behaviour), never degrade-LOUD exit-3. Only AMBIGUOUS (the bare
        # ``Indeterminate``, below) degrades.
        _emit_whole_tree_resolved(_PYTEST_RUNNER, routed=False, digest_degraded=False)
        return None
    reason = (
        resolution.reason
        if isinstance(resolution, Indeterminate)
        else (
            f"the resolved runner {resolution.name!r} has no whole-tree enumerate "
            "facet wired in this slice"
        )
    )
    return _DigestRouteDegrade(_degrade_whole_tree_runner_indeterminate(reason))


def _digest_whole_tree_through_runner(
    repo: Path, resolution: RunnerAdapter
) -> _DigestRouteDegrade | _DigestRouteResult:
    """Enumerate the resolved non-pytest runner's whole-tree scope -> a digest (D5).

    Calls the runner's OWN enumerate facet (``list_scope``) and digests the node-id
    set through the runner-agnostic ``compute_gate_scope_digest``. The runner binary
    absent / empty-scope raises ``RunnerAdapterUnavailable`` -> degrade LOUD
    INDETERMINATE naming the runner (still proves the digest leg is runner-aware: it
    routed to the runner's enumerate facet and refused, it did NOT fabricate a pytest
    digest nor crash on ``InterpreterUnavailable``).
    """
    try:
        scope = resolution.list_scope(repo)
    except RunnerAdapterUnavailable as exc:
        return _DigestRouteDegrade(
            _degrade_whole_tree_runner_indeterminate(
                f"the {resolution.name!r} enumerate facet could not produce a "
                f"trustworthy whole-tree digest: {exc}"
            )
        )
    return _DigestRouteResult(
        digest=compute_gate_scope_digest(list(scope.node_ids)),
        runner=scope.runner,
        node_id_count=len(set(scope.node_ids)),
    )


def _emit_runner_aware_digest(route: _DigestRouteResult) -> int:
    """Print a non-pytest runner's whole-tree digest + its provenance event (D5).

    The bare digest goes to stdout (the callers' ``.strip()`` capture contract); the
    ``GateScopeDigest`` event -- carrying the ``runner`` provenance that proves WHICH
    runner's enumerate facet the node-id set came from -- goes to stderr.
    """
    print(route.digest)
    print(
        json.dumps(
            {
                "event": "GateScopeDigest",
                "runner": route.runner,
                "gate_scope_digest": route.digest,
                "node_id_count": route.node_id_count,
            }
        ),
        file=sys.stderr,
    )
    return 0


def _verify_runner_aware_digest(
    repo: Path, commit: str, route: _DigestRouteResult
) -> int:
    """Verify a non-pytest runner's re-derived digest against the commit trailer.

    The verify counterpart of ``_emit_runner_aware_digest`` (D5): the fresh digest is
    RE-DERIVED through the runner's OWN enumerate facet (``route.digest``), then
    compared to the commit's ``Gate-Scope:`` trailer exactly as the pytest path does
    -- so a non-pytest commit's trailer is verified against a runner-aware
    re-derivation, never a fabricated pytest digest.
    """
    commit_message = _git(repo, "log", "-1", "--format=%B", commit)
    declared = extract_gate_scope(commit_message)
    if declared is None:
        _emit(
            {
                "event": "GateScopeUnverified",
                "commit": commit,
                "runner": route.runner,
                "reason": "absent",
                "error": (
                    "commit carries no Gate-Scope: trailer -- the contract "
                    "gate scope is unverified"
                ),
            }
        )
        return 1
    if declared != route.digest:
        _emit(
            {
                "event": "GateScopeUnverified",
                "commit": commit,
                "runner": route.runner,
                "reason": "mismatch",
                "declared_digest": declared,
                "fresh_digest": route.digest,
                "error": (
                    "commit Gate-Scope: digest does not match a fresh "
                    "runner-aware enumerate digest -- the terminating run was "
                    "narrower than the contract"
                ),
            }
        )
        return 1
    _emit(
        {
            "event": "GateScopeVerified",
            "commit": commit,
            "runner": route.runner,
            "gate_scope_digest": route.digest,
        }
    )
    return 0


def _maybe_route_through_runner_whole_tree(repo: Path) -> int | None:
    """Resolve the whole-tree target's runner; route a non-pytest target through it.

    The whole-tree mirror of ``_maybe_route_through_cargo`` (ADR-FLOW-011 D3):
    seed the runner registry, RESOLVE the target's runner from its lockfile(s),
    and emit the ``WholeTreeRunnerResolved`` event at the preamble -- BEFORE any
    run/digest leg -- so the resolution is observable even when the resolved
    runner's binary is absent in the env.

    Whole-tree resolution passes NO feature context (``feature=None``): a
    single-lockfile target takes the fast-path, while a POLYGLOT root has no
    feature to disambiguate by and degrades LOUD INDETERMINATE naming the
    competing lockfiles (D2) -- never a silent first-lockfile pick.

    * pytest -> emit (routed=False) and return ``None``: the EXISTING pytest path
      runs UNCHANGED (byte-identical Python, zero regression).
    * cargo-test -> emit (routed=True, digest_degraded=True) and RUN the whole
      crate through the resolved cargo run-facet (``cargo nextest run``, no
      feature filter); the digest leg degrades LOUD to no-digest. Never
      ``pytest.main()``, never ``InterpreterUnavailable`` on the non-Python target.
    * Indeterminate, or a recognized non-pytest runner with no whole-tree run
      facet in this slice -> degrade LOUD INDETERMINATE; never silent pytest.
    """
    seed_runner_registry()
    resolution = resolve_runner(repo, None)
    if isinstance(resolution, RunnerAdapter) and resolution.name == _PYTEST_RUNNER:
        _emit_whole_tree_resolved(_PYTEST_RUNNER, routed=False, digest_degraded=False)
        return None
    if isinstance(resolution, RunnerAdapter) and resolution.name == _CARGO_RUNNER:
        _emit_whole_tree_resolved(_CARGO_RUNNER, routed=True, digest_degraded=True)
        return _run_whole_tree_through_runner(repo, resolution)
    if isinstance(resolution, UnrecognizedRunner):
        # UNRECOGNIZED (0 lockfiles) -- NOT ambiguous (D9). A lockfile-less Python
        # tree must FALL BACK to the existing ``-m full_suite`` pytest run path
        # (pre-#73 behaviour), never degrade-LOUD exit-3. Only AMBIGUOUS (the bare
        # ``Indeterminate``, below) degrades.
        _emit_whole_tree_resolved(_PYTEST_RUNNER, routed=False, digest_degraded=False)
        return None
    reason = (
        resolution.reason
        if isinstance(resolution, Indeterminate)
        else (
            f"the resolved runner {resolution.name!r} has no whole-tree run facet "
            "wired in this slice"
        )
    )
    return _degrade_whole_tree_runner_indeterminate(reason)


def _mode_feature_scoped(repo: Path, feature_id: str, entering_slice: str) -> int:
    """``--feature-id``: scope the contract gate to one feature's node-ids.

    Resolves the feature's ``.feature`` files via the ``@feature-`` tag (the
    ``carpaccio_slice_gate._feature_tag_files`` resolver, OQ-2), then applies
    the M-1/M-8 non-vacuity floor:

    * M-8 -- the union of ``@slice-NN`` tags across the feature's ``.feature``
      files must intersect the entering slice. A malformed tag (``@slice-abc``)
      simply fails to match a well-formed ``@slice-NN``.
    * M-1 -- ``pytest --collect-only`` over the feature's test scope must
      GENUINELY collect at least one runnable node-id. This is the W2/W4/W6
      contract: a tag on a scenario-less file does not pass the floor; only a
      real, witnessed collection does.

    A zero-collected or empty-intersection scope is ``malformed`` (exit 2),
    never a vacuous pass.

    RUNNER-RESOLUTION SHORT-CIRCUIT (slice-03, feature-delta §V.A): the runner is
    RESOLVED from the target FIRST, before the pytest-bound collection below. A
    Rust (Cargo.toml) target resolves the cargo run-facet and is routed through
    cargo feature-scoped -- it NEVER reaches the pytest worker (the pytest-on-a
    -crate zero-collected bug this feature fixes). Any non-cargo target (pytest /
    INDETERMINATE) falls through to the EXISTING pytest path UNCHANGED.
    """
    cargo_verdict = _maybe_route_through_cargo(repo, feature_id, entering_slice)
    if cargo_verdict is not None:
        return cargo_verdict

    feature_files = _feature_tag_files(repo, feature_id)
    if not feature_files:
        return _feature_scope_malformed(
            feature_id,
            "zero-collected",
            f"no .feature file resolves under feature id {feature_id!r} "
            "-- the scoped contract gate would pass vacuously",
        )

    collected_slice_tags: set[str] = set()
    for feature_file in feature_files:
        collected_slice_tags |= _slice_tags(feature_file)
    if entering_slice not in collected_slice_tags:
        return _feature_scope_malformed(
            feature_id,
            "empty-intersection",
            f"the collected feature scope carries no @{entering_slice} "
            "tag -- the scoped contract gate would pass vacuously",
            entering_slice=entering_slice,
        )

    # M-1: real node-id collection over the feature's test scope. Routed
    # through the existing `_collect_node_ids` seam (DDD-12 -- no third pytest
    # call site); scoped to the directories holding the resolved .feature files.
    scope_dirs = sorted({feature_file.parent for feature_file in feature_files})
    try:
        raw_node_ids = _collect_node_ids(repo, paths=scope_dirs)
    except InterpreterUnavailable as exc:
        return _degrade_interpreter_unavailable(exc)
    except _CollectionError as exc:
        return _feature_scope_malformed(
            feature_id,
            "collection-failed",
            f"feature-scoped pytest collection failed: {exc}",
            entering_slice=entering_slice,
            kind=_KIND_BUILD_FAILURE,
        )
    # DDD-1/DDD-2: narrow the collected scope to the shipped+entering slice set,
    # EXCLUDING a not-yet-entered future-slice scaffold -- by scenario slice-tag,
    # never by mutating the .feature files (the @skip-pollution bug class). For
    # the final/single entering slice the whole shipped set is retained (DDD-3).
    node_ids, collected_slice_tags = _narrow_to_shipped_entering(
        raw_node_ids, feature_files, entering_slice
    )
    if not node_ids:
        return _feature_scope_malformed(
            feature_id,
            "zero-collected",
            "the feature's test scope genuinely collected zero runnable "
            "node-ids -- the scoped contract gate would pass vacuously",
            entering_slice=entering_slice,
        )

    # Keystone (feature-delta §6.2): the feature-scoped verdict must cover the
    # architecture tier the whole-tree pre-push gate enforces, not just the
    # feature's own `.feature` scope. A slice can break a run-time arch invariant
    # (the F-D-09 scans-not-imports AST gate class) while its feature scope is
    # clean -- a collect-only feature-scoped run is structurally blind to it. So
    # AFTER the feature-scope M-1 floor clears and BEFORE clearing the slice,
    # collect-AND-RUN the arch-invariant set and refuse the slice when a run-time
    # arch invariant FAILS.
    #
    # Genericità (STANDING mandate): the `--feature-id` gate runs on the TARGET
    # repo during DELIVER, and an external target legitimately has NO nWave
    # `tests/build/` arch tier. An EMPTY arch set therefore must CLEAR -- there is
    # no arch invariant to enforce, so the gate clears on the feature scope alone
    # (slice-01's contract). Only a PRESENT-but-vacuous arch tier is malformed:
    # slice-02 closes the zero-collected hole (Hole B -- a `tests/build/` that
    # collects zero runnable node-ids under the contract marker filter), while
    # keeping slice-01's keystone `arch-invariant-failed` branch (a run-time arch
    # invariant FAILS on a non-vacuous tier). The empty-arch-set "Hole A" is NOT
    # a refusal -- refusing it would break the genericità guard for external
    # targets that carry no nWave arch tier.
    arch_collected: int | None = None
    arch_paths = _arch_invariant_paths(repo)
    if arch_paths:
        try:
            arch = _run_arch_invariant_set(repo, arch_paths)
        except InterpreterUnavailable as exc:
            return _degrade_interpreter_unavailable(exc)
        except _CollectionError as exc:
            return _feature_scope_malformed(
                feature_id,
                "arch-invariant-failed",
                f"the architecture-invariant run could not be trusted: {exc}",
                entering_slice=entering_slice,
                kind=_KIND_BUILD_FAILURE,
            )
        if arch.collected == 0:
            return _feature_scope_malformed(
                feature_id,
                "arch-scope-zero-collected",
                "the tests/build architecture tier collected zero runnable "
                "node-ids under the contract marker filter -- refusing rather "
                "than certifying a vacuous arch set",
                entering_slice=entering_slice,
            )
        if not arch.passed:
            return _feature_scope_malformed(
                feature_id,
                "arch-invariant-failed",
                "a run-time architecture invariant FAILED -- the slice breaks an "
                "architecture-boundary test in tests/build/**, which the "
                "whole-tree pre-push gate would refuse",
                entering_slice=entering_slice,
                kind=_KIND_TEST_FAILURE,
            )
        arch_collected = arch.collected

    cleared: dict[str, object] = {
        "event": "FeatureScopeCleared",
        "feature_id": feature_id,
        "entering_slice": entering_slice,
        "collected_node_ids": len(node_ids),
        "collected_slice_tags": sorted(collected_slice_tags),
    }
    if arch_collected is not None:
        cleared["arch_invariant_node_ids"] = arch_collected
    _emit(cleared)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="des run-contract-gate",
        description="The canonical ATDD-pure contract gate (run / digest / verify).",
    )
    parser.add_argument(
        "--repo", required=True, help="Path to the git repository / project root."
    )
    parser.add_argument(
        "--feature-id",
        help=(
            "Scope the contract gate to one feature's node-ids (resolved via the "
            "@feature- Gherkin tag). Carries the M-1/M-8 non-vacuity floor."
        ),
    )
    parser.add_argument(
        "--entering-slice",
        help="The @slice-NN tag the feature-scoped collection must intersect.",
    )
    parser.add_argument(
        "--commit",
        help="Commit-ish for --verify-gate-scope (e.g. HEAD).",
    )
    parser.add_argument(
        "--collect-only",
        action="store_true",
        help="Derive the gate-scope digest without running the suite.",
    )
    parser.add_argument(
        "--print-digest",
        action="store_true",
        help="Print the gate-scope digest to stdout (use with --collect-only).",
    )
    parser.add_argument(
        "--committed-scope-digest",
        action="store_true",
        help=(
            "Print a REPRODUCIBLE gate-scope digest over the COMMITTED tree at "
            "HEAD (a distinct mode from --collect-only --print-digest). "
            "git-REQUIRED: git absent / not a work-tree / SHA unresolvable emits "
            "a LOUD committed-scope INDETERMINATE event and refuses (exit 2)."
        ),
    )
    parser.add_argument(
        "--verify-gate-scope",
        action="store_true",
        help="Verify --commit's Gate-Scope: trailer against a fresh digest.",
    )
    parser.add_argument(
        "--at-kind",
        dest="at_kind",
        default=None,
        choices=(None, "gherkin", "pytest-regression"),
        help=(
            "The acceptance-test kind the digest re-derivation must honor "
            "(fix-runner-resolves-per-scope-language slice-01). "
            "'pytest-regression' skips the whole-tree runner-routing seam "
            "(_maybe_route_digest_through_runner) so a Rust-primary repo's "
            "cargo lockfile never hijacks a Python-only slice's re-verified "
            "digest. Omitted / 'gherkin' keeps the EXISTING runner-routed "
            "--verify-gate-scope behavior byte-identical."
        ),
    )
    parser.add_argument(
        "--expected-head",
        help=(
            "The pinned HEAD SHA the gate was launched against (M9). When "
            "present with --verify-gate-scope, the CLI re-reads HEAD and fails "
            "closed with CommitHeadRaced if HEAD has moved off this SHA. When "
            "absent, no race check runs -- behaviour is byte-for-byte unchanged."
        ),
    )
    parser.add_argument(
        "--inprocess-exemplar",
        action="store_true",
        help=(
            "Drive the in-process active-RED exemplar route: emit the "
            "in-process-routed verdict token through the injected OutputPort. "
            "The reference route proving the gate entry is wired in-process."
        ),
    )
    parser.add_argument(
        "--run-suite",
        action="store_true",
        help=(
            "Run the coverage-on-executed-path lever (at-in-process-port-default "
            "slice-03): FLAG an acceptance test whose driven entry executes zero "
            "production lines (coverage theater). Emits the structured event "
            "CoverageOnExecutedPathFlagged."
        ),
    )
    parser.add_argument(
        "--junit-xml",
        dest="junit_xml",
        default=None,
        help=(
            "Persist a JUnit XML report of the default (full-suite) run at "
            "this filesystem path (fix-feature-end-refusal-names-failing-"
            "tests). Only honored by the default run-suite mode."
        ),
    )
    return parser


def _commit_head_raced(
    repo: Path, expected_head: str | None
) -> dict[str, object] | None:
    """Detect a HEAD that has raced off the pinned ``expected_head`` SHA (M9 / F3).

    Returns a `CommitHeadRaced` payload when HEAD has moved off the pinned SHA;
    None when HEAD still matches (or no `--expected-head` was given). Under a
    concurrent amend/rebase the HEAD the gate was launched against can move
    before the gate inspects it -- re-reading HEAD makes the race fail-closed.
    """
    if expected_head is None:
        return None
    try:
        current = _git(repo, "rev-parse", "HEAD").strip()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        return {
            "event": "CommitHeadRaced",
            "pinned_sha": expected_head,
            "current_sha": "",
            "error": f"cannot re-read HEAD to verify the pinned SHA: {exc}",
        }
    if current == expected_head:
        return None
    return {
        "event": "CommitHeadRaced",
        "pinned_sha": expected_head,
        "current_sha": current,
        "error": (
            "HEAD moved during the G_COMMIT exit gate "
            f"(pinned {expected_head}, now {current}); re-run the gate"
        ),
    }


_INPROCESS_EXEMPLAR_VERDICT_TOKEN = "IN_PROCESS_EXEMPLAR_OK"


def _mode_inprocess_exemplar(repo: Path, output: OutputPort) -> int:
    """Drive the in-process active-RED exemplar route (DESIGN §1 / §2).

    The reference route the in-process active-RED pattern points at: it emits the
    in-process-routed verdict token through the injected ``OutputPort`` and reads
    the repo without mutating it (bounded-change contract). Driving ``main`` with
    ``--inprocess-exemplar`` IN-PROCESS reaches this route directly -- no fork.
    """
    _emit(
        {
            "event": "InProcessExemplarRouted",
            "verdict": _INPROCESS_EXEMPLAR_VERDICT_TOKEN,
            "repo": str(repo),
        },
        output,
    )
    return 0


def _resolve_runner_name(repo: Path) -> str:
    """The target's resolved runner name, defaulting to ``pytest`` when unresolved.

    Threads the per-language runner (#73 runner-resolution) into the
    coverage-on-executed-path lever so it stays target-aware: a Rust/cargo target
    resolves to ``cargo-test`` (the lever then CLEARS NOT_APPLICABLE), a Python
    target to ``pytest`` (the theater scan runs unchanged). An INDETERMINATE
    resolution (no recognized lockfile — e.g. a hermetic tmp Python workspace the
    AT drives) defaults to ``pytest``, preserving the existing Python behaviour.
    """
    resolution = resolve_runner(repo, None)
    if isinstance(resolution, RunnerAdapter):
        return resolution.name
    return _PYTEST_RUNNER


def _mode_coverage_on_executed_path(repo: Path, output: OutputPort) -> int:
    """The lever-3 coverage-on-executed-path role (at-in-process-port-default slice-03).

    Drives the shared ``check_coverage_on_executed_path`` lever over the driven
    workspace and emits its structured verdict through the injected ``OutputPort``.
    A workspace whose ATs execute zero ``src/des`` production lines is FLAGGED as
    coverage theater (event ``CoverageOnExecutedPathFlagged``); git-free. Returns
    1 when the theater flag fires, 0 when the suite covers production lines.
    """
    from des.cli.axis_b_levers import check_coverage_on_executed_path

    lever = check_coverage_on_executed_path(repo, runner=_resolve_runner_name(repo))
    if not lever.flagged:
        # A NOT_APPLICABLE clear (non-pytest target) carries a loud
        # structured_event — surface it (degrade-LOUD), never a silent "Clean".
        if lever.structured_event:
            _emit(
                {
                    "event": lever.structured_event,
                    "repo": str(repo),
                    "remediation": lever.remediation,
                },
                output,
            )
            return 0
        _emit(
            {"event": "CoverageOnExecutedPathClean", "repo": str(repo)},
            output,
        )
        return 0
    _emit(
        {
            "event": lever.structured_event,
            "target": lever.target,
            "remediation": lever.remediation,
        },
        output,
    )
    return 1


def main(argv: list[str] | None = None, output: OutputPort | None = None) -> int:
    """Run the canonical ATDD-pure contract gate in the requested role.

    ``output`` injects the terminal-output sink (DESIGN §2). It defaults to
    ``StdoutOutput()`` -- existing callers pass nothing and see byte-for-byte
    unchanged output; an in-process driver passes a capturing sink to observe the
    in-process exemplar route without forking an interpreter.
    """
    if output is None:
        output = StdoutOutput()
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

    if args.inprocess_exemplar:
        return _mode_inprocess_exemplar(repo, output)

    if args.run_suite:
        return _mode_coverage_on_executed_path(repo, output)

    if args.verify_gate_scope:
        if not args.commit:
            _emit(
                {
                    "event": "MalformedInput",
                    "error": "--verify-gate-scope requires --commit",
                }
            )
            return 2
        # M9 / F3: a HEAD raced off the pinned SHA fails closed before the
        # gate-scope verdict.
        raced = _commit_head_raced(repo, args.expected_head)
        if raced is not None:
            _emit(raced)
            return 1
        return _mode_verify_gate_scope(repo, args.commit, args.at_kind)

    if args.committed_scope_digest:
        return _mode_committed_scope_digest(repo)

    if args.collect_only or args.print_digest:
        return _mode_print_digest(repo)

    if args.feature_id:
        if not args.entering_slice:
            _emit(
                {
                    "event": "MalformedInput",
                    "cause": "malformed",
                    "error": "--feature-id requires --entering-slice",
                }
            )
            return 2
        return _mode_feature_scoped(repo, args.feature_id, args.entering_slice)

    junit_xml_path = Path(args.junit_xml) if args.junit_xml else None
    return _mode_run_suite(repo, args.at_kind, junit_xml_path=junit_xml_path)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
