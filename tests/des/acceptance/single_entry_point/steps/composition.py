"""Composition root for the single-entry-point acceptance suite.

Layer 3 (subprocess / FS acceptance per `nw-tdd-methodology` Layered Test
Discipline). The driving port is the installed `des` console-script. The
driven port is the operating-system filesystem (PATH lookup + subprocess
spawn + stdout/stderr capture + exit code) PLUS the on-disk dispatcher
source (`src/des/cli/__main__.py`) for slice-02 AT-06's bundle-scan check
PLUS the runtime-authoring tree scan (`src/ scripts/ nWave/ tests/`) for
slice-03's grep-zero contract (AT-07, AT-08) PLUS the pyproject.toml
console-script table for slice-03's package-surface contract (AT-09).
Example-only — no PBT machinery (Mandate 9 + Mandate 11).

Pillar 3 — "App as in production": the SUT IS the production composition
root. We invoke the real installed `des` binary via subprocess, the way an
operator would. Nothing in this composition stubs or mocks any nWave logic;
fakes are limited to nothing today (no external non-deterministic ports in
scope for slice-01).

Mandate-12 — SSOT via Types + Services + DSL: all business logic for "how to
run des and capture its output" lives here as `DesCliComposition` methods.
Step bodies in `steps_slice_01.py` are ≤ 2 statements and delegate to these
methods (criterion 3).

RED scaffold posture: today, the production composition root does NOT yet
expose `des` as a console-script (pyproject.toml ships 5 `des-*` instead).
Slice-01 DELIVER creates `src/des/cli/__main__.py` plus the `des` pyproject
entry; until then, every method here raises AssertionError with a clear
"DELIVER slice-01 must implement" message so the AT classifies as RED, not
BROKEN (per `nw-distill` § Mandate 7).
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    EXPECTED_HEALTH_CHECK_NAMES,
    SUBCOMMAND_TABLE,
    HealthCheckVerdict,
    OutputFormat,
    SubcommandRow,
)


# Repo root resolved relative to this composition file (tests/des/acceptance/
# single_entry_point/steps/composition.py → ../../../../../).
_REPO_ROOT: Path = Path(__file__).resolve().parents[5]
_DISPATCHER_PATH: Path = _REPO_ROOT / "src" / "des" / "cli" / "__main__.py"


# ---- slice-03 migration-scan constants (AT-07, AT-08) -------------------

# Runtime-authoring trees scanned by AT-07/AT-08. Per architect's DESIGN
# table: src/ scripts/ nWave/ tests/. Public docs (docs/guides/) live under
# docs/ which is intentionally OUT OF SCOPE here — historical record per
# the architect's split. The 4 listed trees are where runtime authoring
# happens (production code, test scaffolds, skill prose, install plugins).
_AUTHORING_TREES: tuple[str, ...] = ("src", "scripts", "nWave", "tests")

# Forward-drift gate file holds the forbidden patterns AS pattern
# declarations — including it in the scan would self-defeat the gate.
# OQ-3 (DISTILL → DELIVER) explicitly calls out this exclusion. The
# broader list covers files whose JOB is to remember / remove / regression-
# pin the legacy names — they cannot migrate without defeating their
# purpose. Each exclusion is justified by its commented rationale.
_SELF_EXCLUSION_PATHS: tuple[str, ...] = (
    # The forward-drift regression test holds the forbidden patterns AS
    # pattern declarations — self-exclusion is OQ-3.
    "tests/regression/test_no_module_form_in_runtime_emit.py",
    # The acceptance suite itself (composition.py / steps_slice_03.py /
    # domain_types.py / feature file) holds the patterns AS pattern
    # declarations to drive AT-07/AT-08 assertions.
    "tests/des/acceptance/single_entry_point",
    # The DES installer plugin maintains the `LEGACY_DES_SHIMS` SSOT — the
    # canonical list of shim names DELETED on upgrade (R17 residuality of
    # slice-01). Removing the names defeats the upgrade path.
    "scripts/install/plugins/des_plugin.py",
    # nwave-ai doctor test inspects the legacy-shim SSOT — same rationale.
    "tests/nwave_ai/doctor/test_runner.py",
    # Sibling features (ADR-028 D4.1, fix-d4-verify-integrity-mode-awareness)
    # narrate `des-init-log` / `des-verify-integrity` as the SUT-by-name.
    # Forward-only narrative migration is owned by those features.
    "tests/des/acceptance/atdd_pure_init_log_mode_aware",
    "tests/des/acceptance/atdd_pure_verify_integrity_mode_aware",
    # Issue-36 regression PINS the historical "des-roadmap permission
    # prompts" defect — narrative SUT IS the legacy shim names.
    "tests/bugs/test_issue_36_permission_prompts_des_cli.py",
    # Fresh-install e2e pins the historical installed-shim contract for
    # back-compat verification — names are referents, not invocations.
    "tests/e2e/test_fresh_install.py",
    # The rigor-aware integrity / roadmap-only / roadmap-schema bugs pin
    # the legacy shim names against regressions. Their narrative tests keep
    # the historical shim name for traceability.
    "tests/bugs/installer/acceptance",
    # Installer unit test pins the historical shim SSOT contract.
    "tests/installer/unit/plugins/test_des_shim_installation.py",
    # F-11 regression: pins the carpaccio_intercept hook's `python -m
    # des.cli.carpaccio_slice_gate` subprocess form. In the installed
    # `~/.claude/lib/python` layout `python_for(None) -m` always resolves,
    # whereas PATH lookup of the `des` binary is not guaranteed inside the
    # hook process. "Test-pins-production-invariant" rationale.
    "tests/des/unit/test_carpaccio_gate_importable_module.py",
    # reverify-slice-commit unit test exercises the hook-layer U2
    # subprocess that uses `python -m des.cli.X` for the same reason.
    "tests/des/unit/cli/test_reverify_slice_commit.py",
    # E2E install-matrix test verifies cross-venv `python -m des.cli.X`
    # works through every installed environment (uv, poetry, conda, venv);
    # patterns are referents to the cross-env fallback form.
    "tests/e2e/test_install_matrix.py",
    # fix-des-self-hosted-gate-sync acceptance test pins the freshness gate
    # `python -m` invocation as the hook-layer call shape (same F-11 class).
    "tests/installer/acceptance/fix-des-self-hosted-gate-sync",
    # opencode commands path-rewrite test pins the rewriter contract for
    # the opencode plugin: it expects the rewriter to handle `python -m
    # des.cli.X` patterns. Forward-only opencode adapter migration.
    "tests/installer/unit/plugins/test_opencode_commands_path_rewrite.py",
    # D1 human-readable gate-surface tests use the legacy form in driving-
    # port narrative comments referencing what the gate-stack scripts run.
    "tests/scripts/cli/fix_d1_human_readable_gate_surfaces",
    # atdd_pure dispatch lifecycle and nw-deliver-spine tests assert the
    # legacy-shim-name removal contract via string pinning - the shim names
    # are referents to REMOVED tokens, not invocations.
    "tests/des/acceptance/atdd_pure_dispatch_lifecycle/test_atdd_pure_dispatch_template.py",
    "tests/scripts/cli/atdd_pure_nw_deliver_spine",
    # fix-oss-environmental-e2e-gate feature-end-wiring slice narrative
    # references the historical `des-verify-integrity` shim - sibling
    # feature owns the forward migration.
    "tests/des/acceptance/fix_oss_environmental_e2e_gate",
)

# AT-07 / AT-10 — P1 (concrete) capture: `python -m des.cli.<module>` where
# <module> is a real importable module id (lower-snake), NOT a `<glob>`/`*`
# template. The capture group IS the concrete module suffix; a glob template
# (`des.cli.<gate>`) fails the `[a-z_]` lookahead and is therefore P1-excluded.
_CONCRETE_MODULE_FORM: re.Pattern[str] = re.compile(
    r"python3?\s*-m\s+des\.cli\.([a-z_][a-z0-9_]*)"
)

# AT-08 pattern: the five legacy `des-{shim}` console-script names. Word-
# boundary anchored so `des-cli` and `des-roadmap-foo` do NOT match.
_PATTERN_DES_PREFIXED: re.Pattern[str] = re.compile(
    r"\bdes-(log-phase|init-log|verify-integrity|roadmap|health-check)\b"
)

# P2 — registry SSOT oracle. Every `module_path` literal declared in the
# dispatcher's `_REGISTRY` (src/des/cli/__main__.py). Read LIVE from source on
# every scan (no hardcoded list) so a module that LATER gains a subcommand
# becomes a migration candidate automatically. `__main__` is the dispatcher,
# never a registry row, so it can never satisfy P2.
_REGISTRY_MODULE_LITERAL: re.Pattern[str] = re.compile(
    r'"(des\.cli\.[a-z_][a-z0-9_]*)"'
)

# P3 — sanction sentinel. A line, file, or ancestor dir-marker carrying this
# token sanctions the deliberate-SUT / hermetic-AT module-form callsites the
# `nw-distill` skill itself prescribes (`python -m des.cli.<gate>` is THE
# Layer-3 hermetic AT driving port; PATH lookup of the installed binary is not
# hermetic). The token is greppable + mutation-checkable: delete it and the
# hit re-appears → the gate bites again (AT-10 is the non-vacuity control).
_SENTINEL_TOKEN: str = "des:allow-module-form"

# P3 dir-level mechanism: a `.des-allow-module-form` marker file in the hit
# file's directory or any ancestor (up to the scan base root) sanctions every
# module-form callsite beneath it. One marker covers a whole deliberate-SUT
# feature suite without hand-marking each callsite (the file/dir-level rule the
# feature-delta P3 mechanism sanctions). The marker file carries its own reason.
_DIR_MARKER_NAME: str = ".des-allow-module-form"

# Extensions scanned. Skill prose (`.md`), test code (`.py`), feature files
# (`.feature`), shim scripts (no extension, bash + python), config files.
_SCANNED_EXTENSIONS: tuple[str, ...] = (
    ".py",
    ".md",
    ".feature",
    ".sh",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
)


def _registered_module_paths() -> frozenset[str]:
    """P2 oracle — the set of registered `des.cli.<X>` module paths (live).

    Parses the dispatcher source (`src/des/cli/__main__.py`) for every
    ``"des.cli.<module>"`` registry-row literal. Read from source on each call
    so the predicate auto-corrects as the registry grows. Returns an empty set
    only if the dispatcher is unreadable (the scan then reports nothing as a
    registered-subcommand violation — a loud absence, never a silent pass; the
    bundle-scan / AT-06 path already guards dispatcher integrity).
    """
    try:
        source = _DISPATCHER_PATH.read_text(encoding="utf-8")
    except OSError:
        return frozenset()
    return frozenset(_REGISTRY_MODULE_LITERAL.findall(source))


def _ancestor_dir_sanctions(path: Path, base_root: Path) -> bool:
    """True iff `path`'s directory or an ancestor (up to `base_root`) carries a
    ``.des-allow-module-form`` marker (P3 dir-level sanction).

    The walk is bounded by `base_root` (inclusive) so a synthetic scan rooted
    in a tmp dir (AT-10) never reaches a repo-tree marker — preserving the
    non-vacuity control: an unmarked planted hit stays a violation.
    """
    directory = path.parent
    while True:
        if (directory / _DIR_MARKER_NAME).is_file():
            return True
        if directory == base_root:
            return False
        directory = directory.parent


def _concrete_registered_module_form(line: str, registered: frozenset[str]) -> bool:
    """P1 ∧ P2 for one line: a CONCRETE `python -m des.cli.<X>` whose `<X>` is
    a REGISTERED subcommand module. False for glob templates (P1) or
    no-subcommand modules (P2)."""
    match = _CONCRETE_MODULE_FORM.search(line)
    if match is None:
        return False
    return f"des.cli.{match.group(1)}" in registered


def _scan_with_predicate(
    roots: tuple[Path, ...],
    base_root: Path,
    exclusions: tuple[str, ...],
    line_is_candidate: Callable[[str], bool],
) -> tuple[tuple[str, int, str], ...]:
    """Scan `roots` for candidate lines that are GENUINE violations.

    A line is a violation iff it is a candidate (caller's predicate) AND it is
    NOT P3-sanctioned at any granularity: no sentinel token on the line, no
    sentinel anywhere in the file, no ancestor dir-marker, and the file is not
    under a path exclusion. Returns `(relpath, lineno, line)` for each
    violation; relpaths are relative to `base_root`.
    """
    violations: list[tuple[str, int, str]] = []
    for tree_root in roots:
        if not tree_root.exists():
            continue
        for path in sorted(tree_root.rglob("*")):
            if not path.is_file() or path.suffix not in _SCANNED_EXTENSIONS:
                continue
            relpath = path.relative_to(base_root).as_posix()
            if any(relpath == ex or relpath.startswith(ex + "/") for ex in exclusions):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if _SENTINEL_TOKEN in text:  # P3 file-level (covers dir-marker too)
                continue
            if _ancestor_dir_sanctions(path, base_root):  # P3 dir-level
                continue
            for lineno, line in enumerate(text.splitlines(), start=1):
                if not line_is_candidate(line):
                    continue
                if _SENTINEL_TOKEN in line:  # P3 line-level (redundant w/ file)
                    continue
                violations.append((relpath, lineno, line.strip()))
    return tuple(violations)


@dataclass(frozen=True)
class DesInvocation:
    """Observable outcome of one `des [args...]` subprocess invocation.

    Universe-bound observable triple per Mandate 8 (layer 3): `exit_code`,
    `stdout`, `stderr`. These are the port-exposed names the AT will assert
    against — never internal subprocess.CompletedProcess attributes.
    """

    exit_code: int
    stdout: str
    stderr: str


class DesCliComposition:
    """Production composition root for the `des` CLI dispatcher acceptance.

    Methods compose the operator's user-visible interactions with `des`:
    discovery (`--help`), running a subcommand (`health-check`), running with
    a flag (`--json`). Each method returns a `DesInvocation` snapshot —
    business assertions are made by step methods over these snapshots.
    """

    def __init__(self) -> None:
        # Pillar 3: the SUT path is resolved from PATH the way a real operator
        # would. NO test-time PYTHONPATH manipulation. If `des` is absent from
        # PATH the AT fails LOUD with the RED scaffold message — that is the
        # correct RED signal for slice-01 pre-implementation.
        self._des_binary_path: str | None = None

    # ---- driving-port methods (SSOT for step delegation) ----------------

    def resolve_des_binary(self) -> str:
        """Resolve the absolute path to the installed `des` console-script.

        RED scaffold: today the binary does not exist. Raise AssertionError
        with the canonical scaffold message so the snapshot classifier sees
        RED, not BROKEN.
        """
        if self._des_binary_path is not None:
            return self._des_binary_path
        path = shutil.which("des")
        if path is None:
            raise AssertionError(
                "Not yet implemented -- RED scaffold: "
                "slice-01 must ship `des` console-script in pyproject.toml "
                "and `nWave/scripts/des/des` shim payload (DDD-1, DDD-8)."
            )
        self._des_binary_path = path
        return path

    def list_subcommands(self) -> DesInvocation:
        """Invoke `des --help` and capture exit code + stdout + stderr.

        AT-01 driving port. Operator's first contact with the dispatcher:
        "what can `des` do?".
        """
        binary = self.resolve_des_binary()
        completed = subprocess.run(
            [binary, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        return DesInvocation(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def run_subcommand(
        self,
        subcommand: SubcommandRow,
        output_format: OutputFormat = OutputFormat.TEXT,
    ) -> DesInvocation:
        """Invoke `des <subcommand> [--json]` and capture the same observables.

        AT-02 + AT-03 driving port. Operator runs a real subcommand; the
        dispatcher resolves the registry entry, lazily imports the module,
        delegates argv, passes the exit code through unchanged (DDD-6).
        """
        binary = self.resolve_des_binary()
        argv: list[str] = [binary, subcommand.name]
        if output_format is OutputFormat.JSON:
            argv.append("--json")
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            check=False,
        )
        return DesInvocation(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    # ---- observation helpers (SSOT for assertion delegation) ------------

    @staticmethod
    def health_check_row() -> SubcommandRow:
        """Return the typed row for the health-check subcommand."""
        for row in SUBCOMMAND_TABLE:
            if row.name == "health-check":
                return row
        raise AssertionError(
            "health-check row missing from SUBCOMMAND_TABLE — "
            "domain_types.py is out of sync with src/des/cli/."
        )

    @staticmethod
    def verdict_of(invocation: DesInvocation) -> HealthCheckVerdict:
        """Classify a health-check invocation's exit code as HEALTHY/UNHEALTHY."""
        if invocation.exit_code == 0:
            return HealthCheckVerdict.HEALTHY
        return HealthCheckVerdict.UNHEALTHY

    @staticmethod
    def expected_subcommand_names() -> tuple[str, ...]:
        """The 16 names the dispatcher's `--help` MUST advertise.

        SSOT mirror of the architect's 16→16 naming map. AT-01 asserts every
        name in this tuple appears in the help listing.
        """
        return tuple(row.name for row in SUBCOMMAND_TABLE)

    @staticmethod
    def expected_health_check_names() -> tuple[str, ...]:
        """The 7 canonical health-check check names. AT-03 contract surface."""
        return EXPECTED_HEALTH_CHECK_NAMES

    @staticmethod
    def parse_health_check_json(invocation: DesInvocation) -> dict:
        """Parse a `des health-check --json` stdout into a dict.

        RED scaffold-friendly: if stdout is empty (RED scaffold hasn't shipped
        yet), the json.loads raise becomes the RED signal — but the caller
        SHOULD have already failed at resolve_des_binary, so this path is
        post-implementation only.
        """
        return json.loads(invocation.stdout)

    # ---- slice-02 driving-port methods (per-subcommand reachability) ----

    def run_subcommand_help(self, subcommand_name: str) -> DesInvocation:
        """Invoke `des <subcommand> --help` and capture observables.

        AT-04 driving port. Operator asks each registered subcommand to print
        its own help — every row in SUBCOMMAND_TABLE MUST be reachable through
        the dispatcher; the dispatcher delegates argv to the subcommand's main.
        """
        binary = self.resolve_des_binary()
        completed = subprocess.run(
            [binary, subcommand_name, "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        return DesInvocation(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    def run_subcommand_with_unknown_flag(self, subcommand_name: str) -> DesInvocation:
        """Invoke `des <subcommand> --__nwave_unknown_flag` and capture observables.

        AT-05 driving port. The dispatcher MUST pass argparse exit codes
        through unchanged (DDD-6): an unknown flag is argparse's exit code 2.
        The sentinel flag name is unlikely to collide with any real CLI flag.
        """
        binary = self.resolve_des_binary()
        completed = subprocess.run(
            [binary, subcommand_name, "--__nwave_unknown_flag"],
            capture_output=True,
            text=True,
            check=False,
        )
        return DesInvocation(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )

    # ---- slice-03 migration-scan port (AT-07, AT-08 grep-zero) ----------

    @staticmethod
    def scan_runtime_authoring_trees_for_module_form() -> tuple[
        tuple[str, int, str], ...
    ]:
        """Return every GENUINE `python -m des.cli.X` migration violation.

        AT-07 contract surface (RESCOPED, slice-04). Scans the four runtime-
        authoring trees (`src/`, `scripts/`, `nWave/`, `tests/`) and reports a
        hit only when the rescoped P1∧P2∧P3 predicate holds: P1 the invocation
        is CONCRETE (a real `des.cli.<module>`, not a `<glob>`/`*` template),
        P2 `<module>` is a REGISTERED subcommand in the `_REGISTRY` SSOT, and
        P3 the line/file/ancestor-dir carries NO `# des:allow-module-form`
        sanction sentinel. No-subcommand modules (P2) and the deliberate-SUT /
        hermetic-AT driving ports (P3) are therefore NOT violations. The
        `_SELF_EXCLUSION_PATHS` pre-filter is retained for the self-reference +
        shim-name-SSOT paths. Returns empty tuple on PASS.
        """
        registered = _registered_module_paths()
        return _scan_with_predicate(
            roots=tuple(_REPO_ROOT / tree for tree in _AUTHORING_TREES),
            base_root=_REPO_ROOT,
            exclusions=_SELF_EXCLUSION_PATHS,
            line_is_candidate=lambda line: _concrete_registered_module_form(
                line, registered
            ),
        )

    @staticmethod
    def scan_runtime_authoring_trees_for_des_prefixed_shims() -> tuple[
        tuple[str, int, str], ...
    ]:
        """Return every GENUINE legacy `des-{shim}` migration violation.

        AT-08 contract surface (RESCOPED, slice-04). Scans the four runtime-
        authoring trees for the five legacy `des-*` console-script names. A
        `des-{shim}` token is a violation only when it carries NO
        `# des:allow-module-form` sanction sentinel (P3, at line / file /
        ancestor-dir granularity) and is not under a `_SELF_EXCLUSION_PATHS`
        prefix — so a shim NAME referenced in prose/docstring/comment for
        history or the shim-resolver's own parameter domain is NOT a violation.
        Returns empty tuple on PASS.
        """
        return _scan_with_predicate(
            roots=tuple(_REPO_ROOT / tree for tree in _AUTHORING_TREES),
            base_root=_REPO_ROOT,
            exclusions=_SELF_EXCLUSION_PATHS,
            line_is_candidate=lambda line: (
                _PATTERN_DES_PREFIXED.search(line) is not None
            ),
        )

    @staticmethod
    def regression_test_self_exclusion_paths() -> tuple[str, ...]:
        """The relpaths that AT-07/AT-08 explicitly exclude from the scan.

        The regression test (`tests/regression/test_no_module_form_in_runtime_emit.py`)
        holds the forbidden patterns AS pattern declarations — including it
        in the scan would self-defeat the gate.
        """
        return _SELF_EXCLUSION_PATHS

    # ---- slice-04 negative-control port (AT-10 non-vacuity) --------------

    @staticmethod
    def plant_unmarked_module_form_invocation(
        root: Path, subcommand_module: str
    ) -> Path:
        """Write a synthetic NON-test authoring file under ``root`` carrying one
        UNMARKED module-form invocation of a registered subcommand.

        AT-10 precondition setup (slice-04). The written file is a synthetic
        runtime-authoring emit — NOT a test, and it carries NO
        ``# des:allow-module-form`` sanction sentinel — so under the rescoped
        rule it is P1✓ concrete, P2✓ registered (caller passes a registered
        ``des.cli.<X>`` module suffix), P3✗ unmarked → a genuine violation the
        rescoped scan MUST still report. This is pure INPUT-STATE setup: it
        plants the violation the negative control detects; NO production
        classification logic lives here. Returns ``root``.

        The module-form token is assembled from parts so this composition
        source file never holds the contiguous ``python -m des.cli.`` literal
        (defence-in-depth; the suite directory is already self-excluded).
        """
        authoring_file = root / "generated_authoring" / "emit_invocation.py"
        authoring_file.parent.mkdir(parents=True, exist_ok=True)
        invocation = " ".join(
            ("python", "-m", "des.cli." + subcommand_module, "--help")
        )
        authoring_file.write_text(
            "# synthetic runtime-authoring emit -- NOT a test, NO sanction sentinel\n"
            f"INVOCATION = {invocation!r}\n",
            encoding="utf-8",
        )
        return root

    @staticmethod
    def scan_directory_for_unmarked_registered_module_form(
        root: Path,
    ) -> tuple[tuple[str, int, str], ...]:
        """Apply the rescoped P1∧P2∧P3 migration-violation predicate under ``root``.

        AT-10 contract surface (slice-04 negative control / Earned-Trust probe).
        Returns every ``(relpath, lineno, line)`` under ``root`` that is a
        GENUINE migration violation under the rescoped rule:

          P1 — concrete ``des.cli.<module>`` (not a ``<glob>``/``*`` template),
          P2 — ``des.cli.<module>`` is a registered subcommand in ``_REGISTRY``
               (read from ``src/des/cli/__main__.py``; ``__main__`` excluded),
          P3 — the line carries NO ``# des:allow-module-form: <reason>`` sentinel.

        Non-empty == the rescoped gate STILL bites (mutation-checkable
        non-vacuity). Empty against a planted unmarked-registered hit would
        prove the rescope went vacuously green.

        Applies the SAME rescoped P1∧P2∧P3 predicate as the AT-07 scan, but
        rooted at ``root`` (a synthetic tmp fixture) with NO path exclusions
        and the dir-marker walk bounded by ``root`` — so a planted, unmarked,
        concrete, registered-subcommand module-form invocation is reported,
        proving the rescope is not vacuously green.
        """
        registered = _registered_module_paths()
        return _scan_with_predicate(
            roots=(root,),
            base_root=root,
            exclusions=(),
            line_is_candidate=lambda line: _concrete_registered_module_form(
                line, registered
            ),
        )

    # ---- slice-03 package-surface port (AT-09 pyproject scripts) --------

    @staticmethod
    def read_packaged_console_script_entries() -> tuple[str, ...]:
        """Return sorted tuple of `[project.scripts]` entry names from pyproject.toml.

        AT-09 contract surface. The packaged console-script surface MUST
        include the dispatcher (`des`) and the installer (`nwave-ai`), and
        MUST NOT contain any `des-{shim}` legacy entries.
        """
        try:
            import tomllib
        except ImportError:  # pragma: no cover — py<3.11 fallback
            import tomli as tomllib  # type: ignore[no-redef]

        pyproject_path = _REPO_ROOT / "pyproject.toml"
        with pyproject_path.open("rb") as handle:
            data = tomllib.load(handle)
        scripts = data["project"]["scripts"]
        return tuple(sorted(scripts.keys()))

    # ---- slice-02 bundle-scan port (AT-06 stdlib-only invariant) --------

    @staticmethod
    def dispatcher_third_party_imports() -> tuple[str, ...]:
        """Return import names in the dispatcher that are NOT stdlib or des.*.

        AT-06 contract surface. The dispatcher (`src/des/cli/__main__.py`) is
        the bundle entry point; it MUST stay stdlib-only at import time
        (DDD-2 bundle-scan compliance). Any third-party import here would
        propagate into every nWave runtime invocation.

        Walks the dispatcher's AST and returns the sorted tuple of top-level
        module names that are NEITHER in `sys.stdlib_module_names` (Python
        3.10+ canonical set) NOR start with `des`. Empty tuple == PASS.
        """
        import ast
        import sys as _sys

        source = _DISPATCHER_PATH.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(_DISPATCHER_PATH))
        imported_top_levels: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_top_levels.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                imported_top_levels.add(node.module.split(".", 1)[0])
        stdlib = set(_sys.stdlib_module_names)
        forbidden = sorted(
            name for name in imported_top_levels if name not in stdlib and name != "des"
        )
        return tuple(forbidden)
