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
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from des.adapters.driven.git.committed_scope_adapter import GitCommittedScopeAdapter
from des.adapters.driven.git.git_subprocess import git_text as _git
from des.cli.carpaccio_slice_gate import _feature_tag_files
from des.cli.human_surface import Verdict, print_human_summary
from des.ports.driven_ports.committed_scope_port import CommittedFileSet
from des.runtime.interpreter import (
    InterpreterUnavailable,
    can_import,
    python_for,
)


# The LOUD health event emitted when the committed-scope mode cannot establish
# the committed contract suite (git absent / not a work-tree / SHA unresolvable).
# Degrade-LOUD contract (`feedback_oss_acl_published_language_cross_tier_2026_05_31`):
# never a silent fall-back to the working tree.
_COMMITTED_SCOPE_INDETERMINATE_EVENT = "health.gate.committed-scope.indeterminate"


# The contract gate scope -- the exact pre-push marker expression
# (.pre-commit-config.yaml). NOT a crafter-picked subset.
_CONTRACT_MARKER = "unit or integration or acceptance"

_GATE_SCOPE_TRAILER_RE = re.compile(r"^Gate-Scope:\s*([0-9a-f]{64})\s*$")

# A Gherkin `@slice-NN` tag -- the carpaccio slice scoping anchor (DDD-5).
_SLICE_TAG_RE = re.compile(r"@(slice-\d+)\b")

# The child-worker marker-line protocol (see des.cli._collect_scope_worker).
# The worker runs pytest's in-process collection API in a FRESH interpreter so
# the gate never nests `pytest.main()` inside an outer pytest session.
_COLLECT_RESULT_PREFIX = "NWAVE_COLLECT_SCOPE:"
_COLLECT_ERROR_PREFIX = "NWAVE_COLLECT_SCOPE_ERROR:"

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


def _emit(payload: dict[str, object]) -> None:
    """Print exactly one single-line JSON object."""
    print(json.dumps(payload))


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


def _collect_node_ids(repo: Path, paths: list[Path] | None = None) -> list[str]:
    """Collect the contract suite's canonical node-ids without running them.

    Thin compatibility seam over `_collect_scope` (DDD-12 -- still the single
    collection seam): returns only the canonical identity list. Callers that
    also need pytest's in-process collected count call `_collect_scope`.
    """
    return _collect_scope(repo, paths).node_ids


def _collect_scope(repo: Path, paths: list[Path] | None = None) -> _CollectedScope:
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

    The worker interpreter is resolved through ``python_for("pytest")`` so the
    F-21 boundary contract holds: if no candidate can import pytest,
    ``InterpreterUnavailable`` is raised rather than a bare
    ``ModuleNotFoundError`` surfacing one frame later.

    Fails closed (raises `_CollectionError`) when the collection is
    untrustworthy: a non-(0,5) pytest exit is a collection error, and a
    populated session whose canonical identities are empty is the vacuous-digest
    defect.
    """
    interpreter = python_for("pytest")
    worker = Path(__file__).with_name("_collect_scope_worker.py")
    completed = subprocess.run(
        [
            interpreter,
            str(worker),
            "--repo",
            str(repo),
            *_path_args(paths),
        ],
        capture_output=True,
        text=True,
    )
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
    """

    collected: int
    passed: bool


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


def _run_arch_invariant_set(repo: Path, arch_paths: list[Path]) -> _ArchVerdict:
    """RUN the architecture-invariant set over ``arch_paths`` and map the verdict.

    Routes through the existing ``_collect_scope_worker.py`` seam via its
    ``--run`` branch (DDD-12 -- the single pytest-argv owner; no new spawn site).
    The only effect (running pytest) stays inside the worker subprocess boundary,
    the same isolation as ``_collect_scope``. The worker interpreter is resolved
    through ``python_for("pytest")`` (F-21 boundary -- never raw
    ``sys.executable``).

    Maps the worker's run-outcome marker line to an ``_ArchVerdict``: pytest exit
    0/5 is GREEN, any other exit is a RED arch run. ``collected_count`` carries
    the M-1-floor signal for a vacuous arch scope.
    """
    interpreter = python_for("pytest")
    worker = Path(__file__).with_name("_collect_scope_worker.py")
    completed = subprocess.run(
        [
            interpreter,
            str(worker),
            "--run",
            "--repo",
            str(repo),
            *_path_args(arch_paths),
        ],
        capture_output=True,
        text=True,
    )
    payload = _parse_worker_line(completed.stdout, _RUN_RESULT_PREFIX)
    if payload is None:
        raise _CollectionError(
            "the arch-invariant run worker emitted no result line "
            f"(exit {completed.returncode}): {completed.stderr.strip()[:500]}"
        )
    raw_exit = payload.get("pytest_exit_code", 1)
    pytest_exit = int(raw_exit) if isinstance(raw_exit, int) else 1
    raw_collected = payload.get("collected_count", 0)
    collected = int(raw_collected) if isinstance(raw_collected, int) else 0
    return _ArchVerdict(collected=collected, passed=pytest_exit in (0, 5))


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


def _run_contract_suite(repo: Path) -> int:
    """Run the whole-tree contract suite; return its pytest exit code.

    Parallel-by-default via pytest-xdist (``-n auto``) -- the perf fix that cuts
    the serial ~30 min whole-suite RUN to ~6 min on 4 cores. Degrades LOUD to
    serial when xdist is absent or when the operator sets ``NWAVE_GATE_JOBS``
    to a serial token (see ``_parallel_pytest_args``).
    """
    interpreter = python_for("pytest")
    completed = subprocess.run(
        [
            interpreter,
            "-m",
            "pytest",
            "-m",
            _CONTRACT_MARKER,
            "-p",
            "no:cacheprovider",
            *_parallel_pytest_args(repo, interpreter),
        ],
        cwd=repo,
    )
    return completed.returncode


def _mode_print_digest(repo: Path) -> int:
    """`--collect-only --print-digest`: emit a fresh digest, run nothing.

    The `GateScopeDigest` event carries BOTH cardinalities from the SAME
    in-process collection (ADR-001): ``node_id_count`` (the digested-set
    cardinality) and ``collected_count`` (``len(session.items)``). They make
    the canonical-coverage parity observable through the driving port.
    """
    try:
        scope = _collect_scope(repo)
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
    print(
        json.dumps(
            {
                "event": "GateScopeDigest",
                "gate_scope_digest": digest,
                "node_id_count": len(scope.node_ids),
                "collected_count": scope.collected_count,
            }
        ),
        file=sys.stderr,
    )
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
    repo: Path, commit: str
) -> _CommittedScopeDigest | _CommittedScopeIndeterminate | _CommittedScopeRefusal:
    """Compute the committed-scope digest of ``commit`` WITHOUT emitting events.

    The single committed-scope digest seam (DDD-12): collects ONLY the committed
    contract-suite file-set at ``commit`` via the `CommittedScopePort`, so the
    digest is invariant to untracked co-resident WIP and reproducible on any
    checkout of that commit. `.feature` specs are excluded by the port (they are
    collected via their bound `@scenario` `.py` step modules, not as direct
    pytest paths), so a committed mixed `.py` + `.feature` suite never trips a
    pytest exit-4 collection error.

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
        scope = _collect_scope(repo, paths=paths)
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
    repo: Path, commit: str
) -> _CommittedScopeDigest | _CommittedScopeRefusal:
    """Fail-closed committed-scope digest of ``commit`` in ``repo``.

    git is REQUIRED. git absent / not a work-tree / SHA unresolvable emits the
    LOUD `health.gate.committed-scope.indeterminate` event and returns a refusal
    (exit 2) -- never silently fingerprinting the working tree (degrade-LOUD).
    This is the seam used by the fail-closed gate roles (`--verify-gate-scope`,
    `--committed-scope-digest`).
    """
    result = _committed_scope_digest_quiet(repo, commit)
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
    """
    _emit(
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


def _mode_verify_gate_scope(repo: Path, commit: str) -> int:
    """`--verify-gate-scope`: compare the commit's digest to a fresh one.

    The fresh digest is the COMMITTED-scope digest of the pinned ``commit`` (the
    slice-01 `--committed-scope-digest` machinery), NOT a working-tree digest.
    One pinned commit therefore verifies BYTE-IDENTICALLY whether or not
    untracked co-resident WIP sits beside it (the daily amend-loop is retired),
    while the whole committed tree's breadth is preserved -- a commit whose
    trailer no longer matches its OWN committed tree still fails verify. git
    absent / not a work-tree inherits the committed-scope LOUD INDETERMINATE
    refusal (exit 2) rather than silently fingerprinting the working tree.
    """
    fresh_result = _committed_scope_digest_value(repo, commit)
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


def _mode_run_suite(repo: Path) -> int:
    """Default mode: run the whole-tree contract suite + emit a digest.

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
    """
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
        suite_code = _run_contract_suite(repo)
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


def _slice_tags(feature_file: Path) -> set[str]:
    """Collect every ``@slice-NN`` tag appearing in one ``.feature`` file.

    Reads the whole file -- file-level and scenario-level tag lines both count
    toward the slice scope. Pure filesystem read: no pytest, no subprocess
    (DDD-12 -- the ``--feature-id`` scoping logic never spawns a test runner).
    """
    text = feature_file.read_text(encoding="utf-8", errors="replace")
    return set(_SLICE_TAG_RE.findall(text))


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


def _feature_scope_malformed(
    feature_id: str, reason: str, error: str, **extra: object
) -> int:
    """Emit a single ``FeatureScopeMalformed`` verdict and return exit 2."""
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
    return 2


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
    """
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
        node_ids = _collect_node_ids(repo, paths=scope_dirs)
    except InterpreterUnavailable as exc:
        return _emit_interpreter_unavailable(exc)
    except _CollectionError as exc:
        return _feature_scope_malformed(
            feature_id,
            "collection-failed",
            f"feature-scoped pytest collection failed: {exc}",
            entering_slice=entering_slice,
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
            return _emit_interpreter_unavailable(exc)
        except _CollectionError as exc:
            return _feature_scope_malformed(
                feature_id,
                "arch-invariant-failed",
                f"the architecture-invariant run could not be trusted: {exc}",
                entering_slice=entering_slice,
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
            )
        arch_collected = arch.collected

    cleared: dict[str, object] = {
        "event": "FeatureScopeCleared",
        "feature_id": feature_id,
        "entering_slice": entering_slice,
        "collected_node_ids": len(node_ids),
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
        "--expected-head",
        help=(
            "The pinned HEAD SHA the gate was launched against (M9). When "
            "present with --verify-gate-scope, the CLI re-reads HEAD and fails "
            "closed with CommitHeadRaced if HEAD has moved off this SHA. When "
            "absent, no race check runs -- behaviour is byte-for-byte unchanged."
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


def main(argv: list[str] | None = None) -> int:
    """Run the canonical ATDD-pure contract gate in the requested role."""
    args = _build_parser().parse_args(argv)
    repo = Path(args.repo)

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
        return _mode_verify_gate_scope(repo, args.commit)

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

    return _mode_run_suite(repo)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
