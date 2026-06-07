"""Composition root + shared fixtures for des-spine-control-plane-ssot slice-01.

Pillar 3 (App as in production): the SUT is the REAL installed HOOK ENTRYPOINT —
`python -m des.adapters.drivers.hooks.claude_code_hook_adapter pre-tool-use`
invoked exactly as Claude Code invokes it (benign `{}` JSON on stdin), against a
synthetic installed tree under tmp_path. The freshness gate fires at the hook
adapter import site (Gap A wiring); the AT observes its decision via the process
exit code + the structured stderr event + the persisted audit-log record. Only
the filesystem witnesses (installed tree, drifted repo source, `.git/` adjacency,
audit-log dir) are tmp_path-scoped.

Mandate-13 (invariant 1+2): the driving port is the hook subprocess. This conftest
NEVER does `from des.runtime.freshness import ...` to invoke the gate at the test
boundary — the only production import is the subprocess module-path string.

Mandate-12 criterion 2/3: `HookFreshnessFixture` is the single source of truth for
ALL business logic the step methods need. Step bodies in `steps_slice_01_*.py`
delegate here — each body is ≤2 statements ending in one `fixture.<method>(...)`
call, no control flow inline.

DISTILL-authored RED scaffold (ADR-025): `src/des/runtime/freshness.py` ALREADY
EXISTS, but slice-01's NEW behavior does NOT:
  * Gap A — the hook adapter has ZERO freshness imports (grep-confirmed); the gate
    fires on `des.cli` import but NOT on the hook entrypoint;
  * DV-2 — `assert_fresh_or_explain` has NO `suppress_git_autoskip` param yet, so
    the `.git/`-adjacency autoskip neuters the gate in the #58 topology;
  * Gap B — the probe never re-hashes `manifest.source_tree`'s `src/des`, so the
    repo-moved-on drift is structurally outside the current four-state table;
  * DV-5 — the gate emits to stderr ONLY; there is no dual-emit to the
    `JsonlAuditLogWriter` SSOT (`audit-*.log` under the `AuditLogPathResolver` dir).
So AT-01/04/05 RED-fail with assertion mismatch (the LOUD `install-freshness.stale`
warning + audit record are absent today) — NOT import error (Mandate-7 RED-vs-BROKEN
preserved). AT-02 (customer-silent) + AT-03 (fresh-silent) GREEN-pass today as
regression pins (the wiring must not regress silence on those paths).

Layer 3/4 (subprocess against tmp_path): example-only (Mandate 9 v2 — @real-io
because the driven set includes a real filesystem adapter). No PBT machinery.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from .steps.domain_types import (
    HEALTH_GATE_INSTALL_FRESHNESS_STALE,
    CheckoutAdjacency,
    CheckoutProbe,
    FreshnessOptOut,
    HookInvocationOutcome,
    HookVerdict,
    InstallDrift,
    InstalledSpineProbe,
    StructuredEventName,
)


# Repo root = .../nWave-dev (this file lives 4 dirs deep under tests/des/...).
_REPO_ROOT = Path(__file__).resolve().parents[4]
_REAL_DES_SRC = _REPO_ROOT / "src" / "des"


def _parse_structured_event_line(stderr_text: str) -> tuple[str | None, str | None]:
    """Extract (`event`, `remediation`) from the first freshness JSON line on stderr.

    The gate emits one JSON-per-line; finds the first parseable line whose `event`
    starts with `des.runtime.freshness.` and returns its event + remediation.
    Returns (None, None) when no such line is present. Pure function.
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
            return event, payload.get("remediation")
    return None, None


def _read_audit_records(audit_log_dir: Path) -> tuple[dict, ...]:
    """Parse every JSON line from the `JsonlAuditLogWriter` SSOT log files.

    The SSOT audit sink is `JsonlAuditLogWriter` → daily-rotated `audit-*.log`
    (`jsonl_audit_log_writer.py:104`: `audit-YYYY-MM-DD.log`), read by the
    production `JsonlAuditLogReader` (`jsonl_audit_log_reader.py:90`, same glob) and
    the KPI-1 query path (`cli/verify_slice_ledger_evidence.py`). This reader globs
    `audit-*.log` under the SAME `AuditLogPathResolver`-resolved dir — the fixture
    sets `DES_AUDIT_LOG_DIR` → this dir, honored identically by writer + reader
    (resolver priority 2, `audit_log_path_resolver.py:50`).

    RELOOP_A fix: the previously-frozen `audit.jsonl` filename was an ORPHAN sink
    NO production consumer reads — a second audit-record representation, the exact
    multi-representation-without-SSOT disease this feature exists to kill. Globbing
    `audit-*.log` asserts against the single existing SSOT.

    Returns an empty tuple when no log file exists (the gate never wrote one). Each
    parseable JSONL line across all matched files becomes one dict.
    """
    records: list[dict] = []
    for log_file in sorted(audit_log_dir.glob("audit-*.log")):
        for raw_line in log_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return tuple(records)


class HookFreshnessFixture:
    """Composition-root service for des-spine-control-plane-ssot slice-01 ATs.

    Pillar 3: invokes the SAME hook entrypoint Claude Code invokes, against a
    synthetic installed tree under tmp_path whose `_install_manifest.json` points
    at a synthetic repo-source tree. The #58 drift, the `.git/` autoskip trap, the
    operator opt-out, and the customer-fidelity baseline are all expressed as
    filesystem topology. The AT observes the gate's decision via exit code +
    structured stderr event + persisted audit record.

    Mandate-12 criterion 3: every public method is the SSOT for one piece of
    business logic. Step bodies do typed lookup + one method call; nothing more.
    """

    def __init__(self, tmp_path: Path) -> None:
        self._tmp_path = tmp_path

    # --- installed-spine construction (the installed-vs-source seam) -------

    def build_installed_spine(self, *, drift: InstallDrift) -> InstalledSpineProbe:
        """Lay out a synthetic `lib/python/des/` spine + manifest under tmp_path.

        DRIFTED  → installed tree content DIVERGES from the manifest's source_tree
                   (the #58 condition: an extra/edited byte in the source). manifest
                   present, source_tree reachable, re-hash mismatch.
        MATCHES  → installed tree content EQUALS the manifest's source_tree (fresh
                   reinstall). manifest present, source_tree reachable, hashes equal.
        CUSTOMER → manifest's source_tree points at a NON-EXISTENT path (state A);
                   no source tree to compare → silent PROCEED, install fidelity.
        """
        lib_python = self._tmp_path / "lib" / "python"
        des_root = lib_python / "des"
        # Install-fidelity copy: the SUT is the REAL hook entrypoint, whose import
        # closure spans the whole `des/` package — a minimal-subset copy yields a
        # ModuleNotFoundError (BROKEN, not RED). So mirror the production installer:
        # copytree(src/des → des/) + the `from src.des`→`from des` import rewrite.
        # This makes the synthetic tree a faithful installed copy the hook can import.
        self._copytree_with_rewrite(_REAL_DES_SRC, des_root)

        source_root = self._build_source_tree(des_root, drift=drift)
        self._write_manifest(des_root, source_root=source_root, drift=drift)
        return InstalledSpineProbe(
            installed_root=des_root, source_root=source_root, drift=drift
        )

    @staticmethod
    def _copytree_with_rewrite(src_des: Path, dst_des: Path) -> None:
        """Copy `src/des` → synthetic `des/`, applying the installer import rewrite.

        Mirrors `des_plugin._rewrite_import_paths`: `from src.des`→`from des`,
        `import src.des`→`import des`, `src.des.`→`des.`. The repo tree already
        uses `from des.` for most modules (run via PYTHONPATH at the package
        parent), so the rewrite is mostly a no-op — but applying it keeps the
        synthetic tree byte-faithful to a real install. `__pycache__`/`*.pyc` are
        skipped (they pollute the tree-hash). GIT-FREE, pure filesystem.
        """
        import re

        from_pat = re.compile(r"\bfrom\s+src\.des\b")
        import_pat = re.compile(r"\bimport\s+src\.des\b")
        general_pat = re.compile(r"\bsrc\.des\.")
        for path in src_des.rglob("*"):
            if "__pycache__" in path.parts or path.suffix in (".pyc", ".pyo"):
                continue
            rel = path.relative_to(src_des)
            target = dst_des / rel
            if path.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if path.suffix == ".py":
                content = path.read_text(encoding="utf-8")
                content = from_pat.sub("from des", content)
                content = import_pat.sub("import des", content)
                content = general_pat.sub("des.", content)
                target.write_text(content, encoding="utf-8")
            else:
                shutil.copyfile(path, target)

    def _build_source_tree(
        self, installed_des_root: Path, *, drift: InstallDrift
    ) -> Path | None:
        """Materialise the synthetic repo `src/des` the manifest points back to.

        For CUSTOMER, return None (manifest source_tree → unreachable path, state A).
        For MATCHES, copy the installed `*.py` verbatim (hashes will be equal).
        For DRIFTED, copy then mutate one source file (content divergence → the #58
        repo-moved-on drift the Gap-B re-hash must catch).
        """
        if drift is InstallDrift.CUSTOMER:
            return None
        source_root = self._tmp_path / "repo" / "src" / "des"
        source_root.mkdir(parents=True, exist_ok=True)
        for py_file in installed_des_root.rglob("*.py"):
            rel = py_file.relative_to(installed_des_root)
            dst = source_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(py_file, dst)
        if drift is InstallDrift.DRIFTED:
            # The dev edited src/des after install: a real content divergence the
            # canonical tree-hash (over *.py content) detects. Append a comment to
            # a stable source file so the source hash != installed hash.
            drifted = source_root / "runtime" / "tree_hash.py"
            drifted.write_text(
                drifted.read_text(encoding="utf-8")
                + "\n# dev edit after install — repo moved on (#58)\n",
                encoding="utf-8",
            )
        return source_root

    def _write_manifest(
        self,
        installed_des_root: Path,
        *,
        source_root: Path | None,
        drift: InstallDrift,
    ) -> None:
        """Write `_install_manifest.json` colocated with the installed package.

        Schema v1 (8 fields). `source_tree` points at the synthetic repo source
        (or a non-existent path for CUSTOMER → state A). `tree_hash` is the
        canonical hash of the INSTALLED tree at install time (per production:
        snapshotted from the installed copy). For DRIFTED the source has since moved
        on, so a Gap-B re-hash of source_tree != this installed tree_hash; for
        MATCHES they remain equal.
        """
        # Compute the installed tree_hash the same way production does, using the
        # copied-in canonical hasher (NOT a direct production import at the test
        # boundary — this runs the synthetic tree's own copy).
        installed_hash = self._canonical_hash(installed_des_root)
        if source_root is None:
            source_tree = str(self._tmp_path / "nonexistent-customer-source")
        else:
            source_tree = str(source_root.resolve())
        manifest = {
            "schema_version": 1,
            "installed_version": "0.0.0-test",
            "installed_at_iso": "2026-06-01T00:00:00Z",
            "source_tree": source_tree,
            "source_commit": "",
            "source_dirty": False,
            "source_kind": "dev-checkout",
            "tree_hash": installed_hash,
        }
        (installed_des_root / "_install_manifest.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _canonical_hash(tree_root: Path) -> str:
        """Canonical `*.py` content hash — mirrors `des.runtime.tree_hash` §1.6.

        Reimplemented here (NOT imported from production) so the fixture computes
        the manifest's install-time hash without a direct-domain import at the test
        boundary (Mandate-13). The algorithm matches production byte-for-byte; if
        production's algorithm changes, the sibling parity test catches the drift.
        """
        import hashlib

        sha = hashlib.sha256()
        py_files = sorted(
            tree_root.rglob("*.py"), key=lambda p: p.relative_to(tree_root)
        )
        for py_file in py_files:
            rel = py_file.relative_to(tree_root).as_posix()
            digest = hashlib.md5(py_file.read_bytes()).hexdigest()
            sha.update(f"{rel}\0{digest}\n".encode())
        return f"sha256:{sha.hexdigest()}"

    # --- audit-record observers (DV-5 KPI-1 sink) --------------------------

    @staticmethod
    def stale_audit_records(outcome: HookInvocationOutcome) -> tuple[dict, ...]:
        """Filter the SSOT audit records to the stale-install freshness ones.

        SSOT for the DV-5 record-matching logic so the step body stays a thin
        delegate (Mandate-12 criterion 3 — no inline comprehension in the step).

        The `JsonlAuditLogWriter` serializes the AuditEvent's `event_type` into the
        top-level `event` key (`jsonl_audit_log_writer.py:78` — `"event":
        event.event_type`) and merges `event.data` at the top level. So a stale
        record is recognised by its `event` value being either the structured
        freshness-event name (`des.runtime.freshness.stale`) OR the `EventType`
        member name the DELIVER wave wires (`HEALTH_GATE_INSTALL_FRESHNESS_STALE`,
        DV-5) — whichever the crafter routes through the writer. Both land under the
        same `event` key; there is no separate `event_type` field on disk.
        """
        return tuple(
            r
            for r in outcome.audit_records
            if r.get("event")
            in (StructuredEventName.STALE.value, HEALTH_GATE_INSTALL_FRESHNESS_STALE)
        )

    @staticmethod
    def record_has_remediation(records: tuple[dict, ...]) -> bool:
        """True iff every record carries a non-empty top-level remediation (KPI-2).

        The writer merges `event.data` at the record's TOP level
        (`jsonl_audit_log_writer.py:93` — `entry.update(event.data)`), so a
        `remediation` packed into `event.data` surfaces as a top-level key.
        """
        return all(bool(r.get("remediation")) for r in records)

    # --- checkout-adjacency construction (the #58 autoskip trap) -----------

    def build_checkout(self, *, adjacency: CheckoutAdjacency) -> CheckoutProbe:
        """Lay out a synthetic CWD with the requested `.git/` adjacency. GIT-FREE.

        DEV_CHECKOUT  → `cwd/.git/` directory present (the autoskip trap #58
                        exploits; the hook must suppress it via DV-2).
        CUSTOMER_HOST → plain directory, no `.git/` adjacency.
        """
        cwd = self._tmp_path / "operator-cwd"
        cwd.mkdir(parents=True, exist_ok=True)
        if adjacency is CheckoutAdjacency.DEV_CHECKOUT:
            (cwd / ".git").mkdir(parents=True, exist_ok=True)
        return CheckoutProbe(cwd=cwd, adjacency=adjacency)

    # --- the driving-port fire (real hook subprocess) ----------------------

    def fire_hook(
        self,
        installed: InstalledSpineProbe,
        checkout: CheckoutProbe,
        *,
        opt_out: FreshnessOptOut = FreshnessOptOut.UNSET,
    ) -> HookInvocationOutcome:
        """Fire the REAL installed hook entrypoint on the hot path.

        The freshness gate is wired at the hook adapter's IMPORT TIME (DESIGN
        SYS-2: "Wire `assert_fresh_or_explain` into `claude_code_hook_adapter`
        import"), mirroring the existing `des.cli/__init__.py` composition-root
        call-site. So the driving port that exercises Gap A is IMPORTING the hook
        adapter module exactly as the installed hook process does at startup:

            python -c "import des.adapters.drivers.hooks.claude_code_hook_adapter"

        This is the hook PROCESS STARTUP — the freshness side-effect fires before
        any handler logic, so the slice-01 walking skeleton observes the gate's
        verdict (the LOUD `install-freshness.stale` warning) WITHOUT needing the
        full `lib/nWave/` handler runtime assets (which are a later concern, not
        the freshness wiring this slice ships). PYTHONPATH points at the synthetic
        installed tree; CWD is the checkout (so the autoskip probe sees / does not
        see the `.git/` marker). The audit sink is redirected to a tmp_path dir
        via `DES_AUDIT_LOG_DIR` so AT-05 can read the persisted record.

        Returns a HookInvocationOutcome capturing the port-exposed observables:
        exit code, stderr text, parsed structured event + remediation, verdict,
        and the persisted audit records.
        """
        lib_python = installed.installed_root.parent  # …/lib/python
        audit_log_dir = self._tmp_path / ".nwave" / "des" / "logs"
        audit_log_dir.mkdir(parents=True, exist_ok=True)

        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(lib_python),
            "DES_AUDIT_LOG_DIR": str(audit_log_dir),
        }
        for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
            if var in os.environ:
                env[var] = os.environ[var]
        if opt_out is FreshnessOptOut.SKIP:
            env["NWAVE_FRESHNESS"] = "skip"

        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                "import des.adapters.drivers.hooks.claude_code_hook_adapter",
            ],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(checkout.cwd),
            timeout=30,
        )
        event, remediation = _parse_structured_event_line(completed.stderr)
        verdict = (
            HookVerdict.REFUSE if completed.returncode != 0 else HookVerdict.PROCEED
        )
        return HookInvocationOutcome(
            exit_code=completed.returncode,
            stderr_text=completed.stderr,
            stderr_event=event,
            stderr_remediation=remediation,
            verdict=verdict,
            audit_records=_read_audit_records(audit_log_dir),
        )


# Closed-enum sanity: cite every StructuredEventName the assertions reference so an
# enum rename surfaces here as an unused-name lint at refactor time.
_ENUM_CITATIONS = (
    StructuredEventName.STALE,
    StructuredEventName.SKIPPED,
    StructuredEventName.AUTOSKIPPED,
    StructuredEventName.PROCEED,
    StructuredEventName.REFUSED,
)


@pytest.fixture
def hook_freshness_fixture(tmp_path) -> HookFreshnessFixture:
    """The single composition-root service all step methods delegate to."""
    return HookFreshnessFixture(tmp_path)


@pytest.fixture
def state() -> dict:
    """Per-scenario scratchpad: `installed`, `checkout`, `opt_out`, `outcome`, `before`."""
    return {}


__all__ = [
    "HookFreshnessFixture",
]
