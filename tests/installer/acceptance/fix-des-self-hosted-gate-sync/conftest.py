"""Shared fixtures for fix-des-self-hosted-gate-sync acceptance tests.

DISTILL authored these RED scaffolds. DELIVER fills in the composition-root
service (`FreshnessProbeFixture`) once `des.runtime.freshness` exists.

Placed at the feature root (sibling of .feature files), NOT under steps/, to
avoid pytest plugin-name collision with sibling features that also contain a
steps/conftest.py (see codex-empirical-e2e-support precedent).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


# The feature directory uses kebab-case (matching sibling acceptance trees);
# Python module paths require snake_case. Inject the feature root onto
# sys.path so `from steps.domain_types import ...` resolves against this
# feature's local `steps/` package without colliding with other features'
# `steps/` packages (each feature's path is injected only when its own
# conftest loads).
_FEATURE_ROOT = Path(__file__).resolve().parent
if str(_FEATURE_ROOT) not in sys.path:
    sys.path.insert(0, str(_FEATURE_ROOT))

from steps.domain_types import (  # noqa: E402  (sys.path manipulation above)
    CorruptionKind,
    FreshnessOptOut,
    GateInvocationOutcome,
    GateVerdict,
    InstalledPathProbe,
    InstalledTree,
    InstallManifest,
    RepoPathProbe,
    SourceTreeKind,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/...)
_REPO_ROOT = _FEATURE_ROOT.parents[3]
_REAL_DES_SRC = _REPO_ROOT / "src" / "des"

# The minimum set of production files that comprise the freshness chain.
# Copying ONLY these (rather than the full src/des/ tree) keeps each AT
# spawn fast AND skips the heavyweight des/__init__.py re-export soup that
# would otherwise transitively import the entire DES package on every
# `import des.cli`. The composition-root contract under test is the gate
# firing at `des.cli/__init__.py` — which only needs these files to exist.
_FRESHNESS_PRODUCTION_FILES = (
    Path("runtime") / "freshness.py",
    # §1.6 canonical hash — imported by repo_source_probe; required for the
    # synthetic install tree to satisfy the freshness chain's import closure
    # (added 2026-05-23 alongside slice-02 step-decorator dedup, same RCA
    # class as the step collision: test infra must keep parity with the
    # production module graph the gate transitively imports).
    Path("runtime") / "tree_hash.py",
    Path("ports") / "driven_ports" / "freshness_port.py",
    Path("adapters") / "driven" / "freshness" / "__init__.py",
    Path("adapters") / "driven" / "freshness" / "repo_source_probe.py",
    Path("adapters") / "driven" / "freshness" / "null_probe.py",
)

# Package-marker `__init__.py` files needed to make the synthetic des/ tree
# a valid Python package hierarchy. Each is intentionally empty — the real
# `des/__init__.py` pulls in DESOrchestrator + every adapter, which would
# defeat the slice-01 contract of "the gate fires before anything heavy
# loads".
_PACKAGE_MARKERS = (
    Path("__init__.py"),
    Path("cli") / "__init__.py",  # OVERWRITTEN below with composition-root call
    Path("runtime") / "__init__.py",
    Path("ports") / "__init__.py",
    Path("ports") / "driven_ports" / "__init__.py",
    Path("adapters") / "__init__.py",
    Path("adapters") / "driven" / "__init__.py",
)


# Composition root contents — MUST stay byte-identical to src/des/cli/__init__.py
# so the test exercises the same import-time wiring as production.
_COMPOSITION_ROOT_INIT = (
    '"""des.cli — composition root for every ``python -m des.cli.*`` invocation.\n\n'
    "Synthesised under tmp_path for the freshness-gate acceptance tests; matches\n"
    "src/des/cli/__init__.py byte-for-byte.\n"
    '"""\n\n'
    "from des.runtime.freshness import assert_fresh_or_explain\n\n\n"
    "assert_fresh_or_explain()\n"
)


# --- Test-only composition root ------------------------------------------


class _SilentLogger:
    """Minimal Logger surface for install plugin invocations under tests.

    The real `scripts.install.install_utils.Logger` writes to stderr / log
    file; the AT-side fixture runs ~3 installs per test, so silence is the
    contract. Each level method is a no-op.
    """

    def info(self, msg: str) -> None:
        pass

    def warn(self, msg: str) -> None:
        pass

    def error(self, msg: str) -> None:
        pass

    def step(self, msg: str) -> None:
        pass


def _stage_source_tree(tmp_path: Path, source_kind: SourceTreeKind) -> Path:
    """Lay out a source tree of the requested kind under ``tmp_path``.

    Returns the path the install plugin's ``_install_des_module`` should treat
    as ``source_dir``:

    * ``DEV_CHECKOUT`` → ``tmp_path/repo/src/des`` (project_root = .../repo).
    * ``PRE_BUILT``    → ``tmp_path/dist/lib/python/des`` (framework_source
      = .../dist; install plugin's ``using_prebuilt`` branch fires).
    * ``WHEEL``        → ``tmp_path/site-packages/wheel_repo/src/des`` — the
      ``site-packages`` segment in the source_dir path trips the install
      plugin's classification heuristic to ``source_kind = "wheel"`` (§1.4).
    """
    if source_kind is SourceTreeKind.DEV_CHECKOUT:
        target = tmp_path / "repo" / "src" / "des"
    elif source_kind is SourceTreeKind.PRE_BUILT:
        target = tmp_path / "dist" / "lib" / "python" / "des"
    else:
        target = tmp_path / "site-packages" / "wheel_repo" / "src" / "des"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        _REAL_DES_SRC,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo"),
    )
    return target


class FreshnessProbeFixture:
    """Composition-root service for the freshness-gate acceptance tests.

    Per Pillar 3 (App as in production): in DELIVER this fixture will
    instantiate the SAME `RepoSourceProbe` adapter wired by
    `des.cli.__init__.py:assert_fresh_or_explain`, then spawn a subprocess
    against the synthesised installed tree. The step methods invoke
    `spawn_gate_against(...)` and observe one `GateInvocationOutcome` —
    they never reach into Popen/file primitives themselves.

    RED scaffold: every method raises AssertionError so the AT fails for
    the right reason (implementation missing), per Mandate 7 / RED-gate.
    """

    def build_installed_tree(
        self,
        tmp_path: Path,
        *,
        with_manifest: bool,
        manifest_content: dict | None = None,
    ) -> InstalledPathProbe:
        """Lay out a synthetic `lib/python/des/` package under tmp_path.

        Mirrors the real installer layout: `tmp_path/lib/python/des/` is the
        package root the gate inspects. Only the freshness chain is copied
        from `src/des/` (production single source of truth); empty package
        markers stand in for the rest of `des/` so `import des.cli` runs the
        composition root WITHOUT triggering the heavyweight re-exports of the
        real `des/__init__.py`.

        When `with_manifest=True`, writes `_install_manifest.json` with the
        provided `manifest_content` (schema per §1.4) into the package root.
        """
        lib_python = tmp_path / "lib" / "python"
        des_root = lib_python / "des"
        des_root.mkdir(parents=True, exist_ok=True)

        for marker in _PACKAGE_MARKERS:
            target = des_root / marker
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

        # Overwrite the cli __init__ with the composition-root call — the
        # one production-code-mirror that wires the gate at import time.
        (des_root / "cli" / "__init__.py").write_text(
            _COMPOSITION_ROOT_INIT, encoding="utf-8"
        )

        # Copy the freshness production files verbatim from src/des/. This
        # is the single source of truth: any future change to the gate's
        # production code automatically flows through the AT.
        for relpath in _FRESHNESS_PRODUCTION_FILES:
            src = _REAL_DES_SRC / relpath
            dst = des_root / relpath
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)

        manifest_path = des_root / "_install_manifest.json"
        if with_manifest:
            manifest_path.write_text(
                json.dumps(manifest_content or {}), encoding="utf-8"
            )

        return InstalledPathProbe(
            root=des_root,
            has_manifest=with_manifest,
            manifest_path=manifest_path,
        )

    def build_repo_source_tree(
        self,
        tmp_path: Path,
        *,
        present: bool,
    ) -> RepoPathProbe:
        """Lay out a synthetic `src/des/` source tree under tmp_path.

        When `present=False`, returns a `RepoPathProbe(source_tree=None,
        present=False)` modeling the customer-no-repo scenario.
        """
        if not present:
            return RepoPathProbe(source_tree=None, present=False)
        source_tree = tmp_path / "repo" / "src" / "des"
        source_tree.mkdir(parents=True, exist_ok=True)
        (source_tree / "__init__.py").write_text("", encoding="utf-8")
        return RepoPathProbe(source_tree=source_tree, present=True)

    def spawn_gate_against(
        self,
        installed: InstalledPathProbe,
        *,
        opt_out: FreshnessOptOut = FreshnessOptOut.UNSET,
    ) -> GateInvocationOutcome:
        """Run `python -c "import des.cli"` against the synthetic installed tree.

        PYTHONPATH points at the installed tree's parent so `import des.cli`
        resolves there. NWAVE_FRESHNESS is set per `opt_out` (UNSET means the
        env var is unset entirely). Returns a GateInvocationOutcome capturing
        exit code, stderr text, and parsed structured event/state.
        """
        lib_python = installed.root.parent  # …/lib/python (parent of `des/`)

        # Build a hermetic env: only PATH (so the interpreter resolves
        # supporting binaries when needed) and PYTHONPATH (so `import des`
        # lands in the synthetic tree, not the repo's src/des). NWAVE_FRESHNESS
        # is set only when the opt_out sentinel asks us to.
        #
        # NWAVE_FRESHNESS_FORCE_GATE=1 is set unconditionally: the subprocess
        # inherits the parent's CWD (the repo root, which has `.git/`), so
        # without the bypass the production dev-checkout autoskip short-circuit
        # would PROCEED every customer-scenario test regardless of the gate's
        # four-state classification. This env var bypasses ONLY the autoskip
        # probe; the four-state classifier (DEGRADED / A / C / D) and the
        # `NWAVE_FRESHNESS=skip` operator opt-out still fire as in production.
        # Friction #12 closure (2026-05-27).
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(lib_python),
            "NWAVE_FRESHNESS_FORCE_GATE": "1",
        }
        # Preserve the interpreter's locale / encoding env so subprocess I/O
        # is well-defined on minimal CI images.
        for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
            if var in os.environ:
                env[var] = os.environ[var]
        if opt_out is not FreshnessOptOut.UNSET:
            env["NWAVE_FRESHNESS"] = opt_out.value

        completed = subprocess.run(
            [sys.executable, "-c", "import des.cli"],
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        stderr_text = completed.stderr
        event, state_field = parse_structured_event_line(stderr_text)
        verdict = (
            GateVerdict.REFUSE if completed.returncode != 0 else GateVerdict.PROCEED
        )
        return GateInvocationOutcome(
            exit_code=completed.returncode,
            stderr_text=stderr_text,
            stderr_event=event,
            stderr_state=state_field,
            verdict=verdict,
        )

    # --- slice-02 services -------------------------------------------------

    def run_install_plugin(
        self,
        tmp_path: Path,
        *,
        source_kind: SourceTreeKind,
    ) -> InstalledTree:
        """Stage a fresh source tree of the requested kind and run the real
        install plugin against it; return the freshly-installed tree + parsed
        manifest.

        Per Pillar 3 (App as in production) this invokes
        `DESPlugin._install_des_module` (or its successor entry point) against
        a `tmp_path`-staged source tree mirroring each of the three install
        topologies declared in §1.4 + §2.2 Addition 1:

        - `SourceTreeKind.DEV_CHECKOUT`: stage `src/des/` from the live repo
          into `tmp_path/repo/src/des/`, run the plugin pointing at it.
        - `SourceTreeKind.PRE_BUILT`: stage a pre-rewritten `lib/python/des/`
          dist layout under `tmp_path/dist/lib/python/des/` (the install
          plugin's `using_prebuilt` branch).
        - `SourceTreeKind.WHEEL`: stage a wheel-staging directory under
          `tmp_path/wheel_staging/des/` whose `source_tree` will be transient
          (PyPI install topology).

        Output dir: `tmp_path/install_prefix/.claude/lib/python/des/`.
        """
        from scripts.install.plugins.base import InstallContext
        from scripts.install.plugins.des_plugin import DESPlugin

        source_dir = _stage_source_tree(tmp_path, source_kind)
        install_prefix = tmp_path / "install_prefix"
        claude_dir = install_prefix / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
        # Route via project_root (src/des layout) or framework_source (pre-built)
        # so the install plugin's source-discovery resolves to the staged path.
        # DEV_CHECKOUT and WHEEL both use project_root = .../<repo>/  the WHEEL
        # case stages under .../site-packages/wheel_repo/src/des so the source
        # classification trips on the path segment.
        if source_kind is SourceTreeKind.PRE_BUILT:
            project_root = None
            framework_source = source_dir.parent.parent.parent  # dist/
        else:
            project_root = source_dir.parent.parent  # repo with src/des
            framework_source = None
        context = InstallContext(
            claude_dir=claude_dir,
            scripts_dir=claude_dir / "scripts",
            templates_dir=claude_dir / "templates",
            logger=_SilentLogger(),
            project_root=project_root,
            framework_source=framework_source,
        )
        plugin = DESPlugin()
        result = plugin._install_des_module(context)
        assert result.success, f"install plugin failed: {result.message}"
        package_root = claude_dir / "lib" / "python" / "des"
        manifest_path = package_root / "_install_manifest.json"
        return InstalledTree(
            package_root=package_root,
            manifest_path=manifest_path,
            manifest=parse_install_manifest(manifest_path),
        )

    def mutate_installed_file(
        self,
        installed: InstalledTree,
        rel_path: Path,
    ) -> None:
        """Rewrite bytes of one `.py` file inside the installed tree to
        provoke a tree-hash divergence (state D scenario per §1.3).

        `rel_path` is relative to `installed.package_root`. After mutation,
        the on-disk content's tree-hash MUST diverge from
        `installed.manifest.tree_hash` — that divergence is the observable
        the gate uses to refuse with state D.

        After mutation, the on-disk content's tree-hash MUST diverge from
        `installed.manifest.tree_hash`.
        """
        target = installed.package_root / rel_path
        assert target.exists() and target.suffix == ".py", (
            f"mutate_installed_file expects a .py file under the installed "
            f"tree; got rel_path={rel_path!r} resolving to target={target}"
        )
        original = target.read_text(encoding="utf-8")
        # Prepend a deterministic comment so the byte content changes but the
        # file remains syntactically valid Python.
        mutated = "# slice-02 AT mutation marker\n" + original
        target.write_text(mutated, encoding="utf-8")

    def recompute_tree_hash(self, installed: InstalledTree) -> str:
        """Recompute the canonical tree-hash of the installed package per §1.6."""
        from des.runtime.tree_hash import canonical_tree_hash

        return canonical_tree_hash(installed.package_root)

    # --- slice-04 services -------------------------------------------------

    def build_optout_grid_install(
        self,
        tmp_path: Path,
        *,
        install_state: str,
    ) -> InstalledPathProbe:
        """Build an `InstalledPathProbe` for the slice-04 opt-out grid.

        `install_state` is the Gherkin Examples-cell vocabulary:

        * ``"fresh"`` — runs the real install plugin against a dev-checkout
          source tree (Pillar 3: production composition root). Returns a
          probe wrapping the just-installed `~/.claude/lib/python/des/` tree
          with a valid `_install_manifest.json` whose tree-hash matches the
          installed content. The freshness gate against this probe yields
          state C (PROCEED).

        * ``"stale"`` — runs the real install plugin THEN mutates one file
          under the installed tree so the tree-hash diverges from the
          manifest's `tree_hash` field. The freshness gate against this
          probe yields state D (REFUSE with exit 78).

        Returns an `InstalledPathProbe` (NOT an `InstalledTree`) so the
        slice-01 `When the operator imports \\`des.cli\\` against that
        installed tree` step can consume it unchanged — Mandate-12 SSOT for
        the When-step vocabulary across slices.

        Slice-04 mutation file (`runtime/freshness.py`) mirrors slice-02
        AT-02-C's representative-file choice — chosen for visibility +
        independence from the bytecode-clear pass run by the install plugin.
        """
        installed_tree = self.run_install_plugin(
            tmp_path, source_kind=SourceTreeKind.DEV_CHECKOUT
        )
        if install_state == "stale":
            self.mutate_installed_file(installed_tree, Path("runtime") / "freshness.py")
        return InstalledPathProbe(
            root=installed_tree.package_root,
            has_manifest=installed_tree.manifest is not None,
            manifest_path=installed_tree.manifest_path,
        )

    # --- slice-05 services -------------------------------------------------

    def corrupt_manifest(
        self,
        installed: InstalledPathProbe,
        *,
        kind: CorruptionKind,
    ) -> InstalledPathProbe:
        """Rewrite the manifest at ``installed.manifest_path`` to a malformed
        shape selected by ``kind``.

        Per Pillar 3 the SUT under test is the production gate's
        ``RepoSourceProbe._read_install_manifest`` classifier; this fixture
        only writes the named corruption shape to the on-disk manifest file.
        Each kind exercises a distinct classifier branch (§1.3 DEGRADED row
        + DDD-6):

        * ``UNKNOWN_SCHEMA_VERSION`` — JSON-valid + all required fields, but
          ``schema_version`` is an integer the gate does not recognise (e.g.
          ``999``). Classifier MUST emit ``schema_version`` substring.
        * ``MISSING_REQUIRED_FIELD`` — JSON-valid dict missing one of the
          eight §1.4 required fields (``installed_at_iso`` chosen as the
          representative omission). Classifier MUST cite ``required field``.
        * ``NON_JSON_CONTENT`` — bytes that are not valid JSON at all (e.g.
          a raw string). Classifier MUST cite ``parse``.
        * ``EMPTY_FILE`` — zero-byte file. Classifier MUST cite ``parse``.

        Returns a refreshed ``InstalledPathProbe`` so the caller can chain
        the gate-spawn step without re-reading the disk state. The probe
        reports ``has_manifest=True`` because the file exists on disk — the
        gate's job is to discover the manifest is malformed AND classify it
        as DEGRADED, not to discover an absent file.
        """
        payload = _serialize_corruption(kind)
        installed.manifest_path.write_bytes(payload)
        return InstalledPathProbe(
            root=installed.root,
            has_manifest=True,
            manifest_path=installed.manifest_path,
        )

    # --- slice-03 services -------------------------------------------------

    def discover_shims(self, source_dir: Path) -> frozenset[str]:
        """Invoke the production `_discover_shims(source_dir)` helper.

        Per Pillar 3 (App as in production) this delegates to the SAME
        helper the install plugin uses at install time to enumerate CLI
        modules under `<source_dir>` — no test-local re-implementation, no
        in-memory double. The AT exercises the production helper against
        the real `src/des/cli/` directory; any discovery shortfall vs the
        regression floor reds the test.

        Returns a frozenset of shim names (CLI module stems, without `.py`
        suffix or leading underscore). Returns an empty frozenset when the
        production helper does not yet exist (RED scaffold path) — the
        downstream `superset_of_floor` assertion then naturally fails the
        AT with a domain-readable message rather than ImportError.
        """
        try:
            from scripts.install.plugins.des_plugin import _discover_shims
        except ImportError as exc:
            raise AssertionError(
                "Not yet implemented -- RED scaffold: "
                "`scripts.install.plugins.des_plugin._discover_shims` is missing. "
                "DELIVER must add the helper per feature-delta §2.2 Addition 2 + "
                f"DDD-4 (slice-03). Underlying ImportError: {exc}"
            ) from exc
        return frozenset(_discover_shims(source_dir))

    def discovery_floor(self) -> frozenset[str]:
        """Return the production `DES_SHIMS_FLOOR` regression-floor constant.

        Per Pillar 3 the constant lives in production code (`des_plugin`),
        NOT in this test fixture — the test reads it from the production
        module so the floor is the canonical SSOT a release-time engineer
        edits when introducing a new load-bearing CLI module. Returns a
        frozenset of shim names.

        Raises AssertionError when the production constant is not yet
        defined, so the AT fails for the right reason (missing production
        artifact) rather than NameError.
        """
        from scripts.install.plugins import des_plugin as _des_plugin_mod

        floor = getattr(_des_plugin_mod, "DES_SHIMS_FLOOR", None)
        if floor is None:
            raise AssertionError(
                "Not yet implemented -- RED scaffold: "
                "`scripts.install.plugins.des_plugin.DES_SHIMS_FLOOR` is missing. "
                "DELIVER must declare the frozen regression-floor set per "
                "feature-delta §2.2 Addition 2 + DDD-4 (slice-03)."
            )
        return frozenset(floor)


@pytest.fixture
def freshness_probe() -> FreshnessProbeFixture:
    """The single composition-root service all step methods delegate to."""
    return FreshnessProbeFixture()


@pytest.fixture
def state() -> dict:
    """Per-scenario scratchpad for capturing the GateInvocationOutcome.

    Keyed only by domain-readable names: `installed`, `repo`, `outcome`.
    """
    return {}


# --- Helpers for parsing the structured stderr line (used by Then steps) -


def parse_structured_event_line(stderr_text: str) -> tuple[str | None, str | None]:
    """Extract (event, state) from the first structured-JSON line on stderr.

    The gate emits one JSON-per-line; this helper finds the first parseable
    line whose `event` starts with `des.runtime.freshness.` and returns its
    `event` + `state`. Returns (None, None) when no such line is present.

    Pure function — no I/O, no side effects.
    """
    for raw_line in stderr_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = payload.get("event")
        if isinstance(event, str) and event.startswith("des.runtime.freshness."):
            state_field = payload.get("state")
            return event, state_field if isinstance(state_field, str) else None
    return None, None


# --- Slice-02 install manifest parser ------------------------------------


def parse_install_manifest(manifest_path: Path) -> InstallManifest | None:
    """Parse `_install_manifest.json` into an `InstallManifest`.

    Returns `None` when the file is absent, malformed, or missing one of the
    eight §1.4 required fields. The contract is: an `InstalledTree` whose
    `manifest is None` represents a tree the gate would REFUSE as DEGRADED
    (Mandate-12: domain types absorb the failure mode).

    Pure function — no side effects beyond reading the file.
    """
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    required = (
        "schema_version",
        "installed_version",
        "installed_at_iso",
        "source_tree",
        "source_commit",
        "source_dirty",
        "source_kind",
        "tree_hash",
    )
    if any(field not in raw for field in required):
        return None
    try:
        return InstallManifest(
            schema_version=int(raw["schema_version"]),
            installed_version=str(raw["installed_version"]),
            installed_at_iso=str(raw["installed_at_iso"]),
            source_tree=str(raw["source_tree"]),
            source_commit=str(raw["source_commit"]),
            source_dirty=bool(raw["source_dirty"]),
            source_kind=str(raw["source_kind"]),
            tree_hash=str(raw["tree_hash"]),
        )
    except (TypeError, ValueError):
        return None


# --- Step definition registration (kebab-case dir workaround) ------------
# Pattern mirrors tests/installer/acceptance/backup-retention-policy/conftest.py
# Load each `steps/steps_*.py` module by file path and inject its public
# attributes into THIS conftest's globals so pytest-bdd's discovery (which
# searches the conftest's namespace) finds the @given/@when/@then decorators.

import importlib.util as _importlib_util  # noqa: E402


_steps_dir = _FEATURE_ROOT / "steps"
for _step_module_name in [
    "steps_slice_01_walking_skeleton",
    "steps_slice_02_install_manifest",
    "steps_slice_03_shim_discovery",
    "steps_slice_04_optout_grid",
    "steps_slice_05_manifest_corruption",
]:
    _step_file = _steps_dir / f"{_step_module_name}.py"
    if _step_file.exists():
        _spec = _importlib_util.spec_from_file_location(
            f"fix_des_self_hosted_gate_sync_steps.{_step_module_name}",
            str(_step_file),
        )
        _mod = _importlib_util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        for _attr_name in dir(_mod):
            if not _attr_name.startswith("_"):
                globals()[f"_step_{_step_module_name}_{_attr_name}"] = getattr(
                    _mod, _attr_name
                )


def _serialize_corruption(kind: CorruptionKind) -> bytes:
    """Pure serializer mapping a CorruptionKind to its on-disk byte payload.

    Each kind exercises a distinct classifier branch in
    ``RepoSourceProbe._read_install_manifest`` (§1.3 DEGRADED row):

    * ``UNKNOWN_SCHEMA_VERSION`` — JSON-valid, every §1.4 required field
      present, but ``schema_version`` is an out-of-band integer (``999``).
    * ``MISSING_REQUIRED_FIELD`` — JSON-valid dict with ``installed_at_iso``
      omitted (representative of the eight-field §1.4 requirement contract).
    * ``NON_JSON_CONTENT`` — bytes that are valid UTF-8 but not JSON.
    * ``EMPTY_FILE`` — zero bytes.

    Pure function — no I/O, no side effects.
    """
    if kind is CorruptionKind.UNKNOWN_SCHEMA_VERSION:
        return json.dumps(
            {
                "schema_version": 999,
                "installed_version": "3.15.1",
                "installed_at_iso": "2026-05-23T02:14:33Z",
                "source_tree": "/nonexistent/source/tree",
                "source_commit": "",
                "source_dirty": False,
                "source_kind": SourceTreeKind.WHEEL.value,
                "tree_hash": "sha256:placeholder",
            }
        ).encode("utf-8")
    if kind is CorruptionKind.MISSING_REQUIRED_FIELD:
        # Omit `installed_at_iso` — one of the eight §1.4 required fields.
        return json.dumps(
            {
                "schema_version": 1,
                "installed_version": "3.15.1",
                "source_tree": "/nonexistent/source/tree",
                "source_commit": "",
                "source_dirty": False,
                "source_kind": SourceTreeKind.WHEEL.value,
                "tree_hash": "sha256:placeholder",
            }
        ).encode("utf-8")
    if kind is CorruptionKind.NON_JSON_CONTENT:
        return b"this is not json at all { ] :: <<<"
    if kind is CorruptionKind.EMPTY_FILE:
        return b""
    raise AssertionError(f"unknown corruption kind: {kind!r}")


__all__ = [
    "CorruptionKind",
    "FreshnessOptOut",
    "FreshnessProbeFixture",
    "GateInvocationOutcome",
    "GateVerdict",
    "InstallManifest",
    "InstalledPathProbe",
    "InstalledTree",
    "RepoPathProbe",
    "SourceTreeKind",
    "parse_install_manifest",
    "parse_structured_event_line",
]
