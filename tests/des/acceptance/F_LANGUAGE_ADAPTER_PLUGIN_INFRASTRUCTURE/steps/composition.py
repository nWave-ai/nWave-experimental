"""Composition root for F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE slice-01.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root -- the real ``scripts/cli/validate_language_adapter_catalog``
CLI and the real ``des doctor`` subcommand, both invoked as subprocesses
against the real port catalog SSOT at ``nWave/data/language-adapter-ports.yaml``.

ALL business logic lives in this module's service methods -- the single
source of truth. Step bodies in ``test_slice_01_*.py`` delegate to these
methods and never inline business logic (Mandate-12 criterion 3): each step
body is a typed lookup plus one composition call.

RED scaffold (Mandate 7 / ADR-025): every scenario reds for the RIGHT
reason -- the production catalog YAML, schema, validator CLI, and ``des
doctor`` subcommand do NOT YET exist (per empirical reads at DISTILL time:
``nWave/data/language-adapter-ports.yaml`` absent, ``nWave/schemas/language-
adapter-ports.schema.json`` absent, ``scripts/cli/validate_language_adapter_
catalog.py`` absent, ``src/des/cli/doctor.py`` absent, ``des doctor``
subcommand not registered in ``_REGISTRY`` at ``src/des/cli/__main__.py``).
The composition exercises real production code paths; the AT assertions fail
because the production artifacts are absent (FileNotFoundError /
SubcommandUnknown subprocess exit), not because the test infrastructure is
broken.

Layer note: every scenario here is layer 3 (subprocess / FS acceptance
against real production CLIs) -- example-only, no PBT (Mandate 9/11). Every
state-mutating step asserts via port-exposed observables -- subprocess exit
codes + stdout JSON shapes (Mandate 8 universe-bound).

Driving ports (per DESIGN §Reuse Analysis + DDD ratification):
- ``des doctor --target-language=<lang>`` subcommand (slice-01 floor;
  full gap matrix in slice-03)
- ``python -m scripts.cli.validate_language_adapter_catalog`` (slice-01)
- ``importlib.metadata.entry_points(group="nwave.lang.adapter")``
  (slice-01 floor; full LanguageAdapterPlugin ABC in slice-02)

Walking-skeleton T1 (installed-artifact tier): all three driving ports are
exercised via subprocess against the as-installed nWave runtime. No direct
domain-module imports (friction #32 anti-pattern avoidance: F-ATDD-PURE-AT-
DIRECT-DOMAIN-TESTING-ANTI-PATTERN).
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from scripts.cli.validate_language_adapter_catalog import main as _validate_catalog_main
from tests.common.in_process_cli import run_cli_in_process

from .domain_types import (
    CatalogPresence,
    CatalogValidationOutcome,
    DoctorReportShape,
    TargetLanguage,
)


# Repo root -- the SSOT catalog + schema + scripts live under here.
# Composition drives the real CLI EDGE / discovery snippet IN-PROCESS
# (corpus-migration-in-process) so the SUT is the real install path, not a
# fresh-interpreter fork.
_REPO_ROOT = Path(__file__).resolve().parents[5]


# The entry-points discovery snippet the slice-01 walking-skeleton floor pins.
# Driven in-process via ``_run_py_snippet_in_process`` -- ``entry_points`` reads
# the same installed dist metadata in-process as a forked interpreter did.
_ENTRY_POINT_DISCOVERY_SNIPPET = (
    "import json\n"
    "from importlib.metadata import entry_points\n"
    "names = sorted(ep.name for ep in entry_points(group='nwave.lang.adapter'))\n"
    "print(json.dumps(names))\n"
)


def _run_py_snippet_in_process(snippet: str, *, cwd: Path) -> tuple[int, str, str]:
    """Drive a ``python -c <snippet>`` fork IN-PROCESS (corpus-migration-in-process).

    Reuses ``run_cli_in_process`` to ``exec`` the IDENTICAL snippet under ``cwd``
    with stdout/stderr captured and any ``sys.exit(n)`` mapped onto the exit
    code -- behaviour-identical to the fresh-interpreter fork the corpus ran,
    minus the interpreter spawn. Returns ``(exit_code, stdout, stderr)``.
    """

    def _exec_snippet(_argv: list[str]) -> int:
        exec(compile(snippet, "<in-process-snippet>", "exec"), {"__name__": "__main__"})
        return 0

    return run_cli_in_process([], cwd=cwd, main=_exec_snippet)


# --- Domain observation types ------------------------------------------------


@dataclass(frozen=True)
class CatalogValidatorResult:
    """The user-observable verdict of one ``validate_language_adapter_catalog`` run.

    Port-exposed observable: validator exit code + stdout. Frozen: a result is
    an immutable observation, never mutated by an assertion.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def outcome(self) -> CatalogValidationOutcome:
        """Whether the catalog validated VALID (exit 0) or INVALID (non-zero)."""
        return (
            CatalogValidationOutcome.VALID
            if self.exit_code == 0
            else CatalogValidationOutcome.INVALID
        )

    @property
    def reports_minimum_language_bound_ports(self) -> bool:
        """Whether stdout names the three slice-01-required LANGUAGE_BOUND CLIs.

        DESIGN slice-01 requires the catalog to enumerate AT LEAST the three
        Nova-audited LANGUAGE_BOUND gate CLIs (the witnesses listed in
        ``docs/architecture/language-adapter-catalog.md`` §Summary Tables):
        ``run_contract_gate``, ``verify_environmental_e2e``,
        ``check_robustness_density``. The validator's stdout summary names
        them when the catalog is well-formed.
        """
        required = (
            "run_contract_gate",
            "verify_environmental_e2e",
            "check_robustness_density",
        )
        return all(name in self.stdout for name in required)


@dataclass(frozen=True)
class DoctorCliResult:
    """The user-observable verdict of one ``des doctor`` invocation.

    Port-exposed observable: CLI exit code + stdout JSON envelope.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def parsed_report(self) -> dict | None:
        """The structured JSON envelope on stdout, or None if unparseable.

        Slice-01 floor: the CLI emits a JSON object with at minimum the keys
        ``target_language``, ``shape`` (one of ``ready|gaps|unknown``),
        ``covered_ports``, ``missing_ports``, ``registered_plugins``. Slice-03
        finalizes the schema and ships ADR-031's machine-readable contract.
        """
        try:
            return json.loads(self.stdout)
        except (json.JSONDecodeError, ValueError):
            return None

    @property
    def shape(self) -> DoctorReportShape | None:
        """The ``shape`` field of the JSON envelope, or None if absent."""
        report = self.parsed_report
        if report is None:
            return None
        raw = report.get("shape")
        if raw not in {s.value for s in DoctorReportShape}:
            return None
        return DoctorReportShape(raw)

    @property
    def reports_missing_language_bound_ports(self) -> bool:
        """Whether the JSON envelope's ``missing_ports`` is non-empty for GAPS shape.

        Slice-01 floor: on first invocation no per-language plugins are
        registered yet (slice-02 ships the ABC + slice-05a ships the first
        Python plugin). So for ANY target language the report should be GAPS
        with the full LANGUAGE_BOUND set in ``missing_ports``.
        """
        report = self.parsed_report
        if report is None:
            return False
        missing = report.get("missing_ports", [])
        return isinstance(missing, list) and len(missing) > 0


@dataclass(frozen=True)
class PluginDiscoveryResult:
    """The user-observable outcome of one entry-point group query.

    Port-exposed observable: subprocess exit code + JSON list of registered
    plugin names on stdout. The query runs as a subprocess executing
    ``python -c "import json; from importlib.metadata import entry_points;
    print(json.dumps([ep.name for ep in entry_points(group='nwave.lang.adapter')]))"``
    -- exercising the real Python entry-points discovery mechanism per
    DESIGN Option C.
    """

    exit_code: int
    stdout: str
    stderr: str

    @property
    def registered_plugin_names(self) -> list[str] | None:
        """The list of registered plugin names, or None if discovery failed."""
        try:
            value = json.loads(self.stdout)
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(value, list):
            return None
        return value


# --- Composition root --------------------------------------------------------


@dataclass
class LanguageAdapterInfrastructureComposition:
    """Production-composition root for slice-01 ATs.

    Each ``given_*`` / ``when_*`` / ``then_*`` is a single service method. Step
    bodies in ``common_steps.py`` invoke exactly one of these per Gherkin step
    (Mandate-12 criterion 3).
    """

    _catalog_path: Path | None = None
    _catalog_presence: CatalogPresence | None = None
    _target_language: TargetLanguage | None = None
    validator_result: CatalogValidatorResult | None = None
    doctor_result: DoctorCliResult | None = None
    discovery_result: PluginDiscoveryResult | None = None

    # --- Given services ----------------------------------------------------

    def given_catalog_in_state(self, presence: CatalogPresence) -> None:
        """Bind the per-scenario catalog state to the SSOT path.

        Slice-01 uses the REAL SSOT catalog path -- ``nWave/data/language-
        adapter-ports.yaml``. The composition observes the on-disk state at
        the moment the validator / doctor CLI runs; it does NOT stage a
        synthetic catalog (that would violate Pillar 3, app-as-in-production).

        At slice-01 RED the file is ABSENT -- DELIVER creates it at GREEN.
        Slice-01 GREEN (post-DELIVER) flips to PRESENT_WELL_FORMED.
        PRESENT_MALFORMED is a future negative-path scenario for slice-05b's
        non-vacuity gate (F-D-07) and is included here only as the typed enum
        third state -- no AT exercises it in slice-01.
        """
        self._catalog_path = (
            _REPO_ROOT / "nWave" / "data" / "language-adapter-ports.yaml"
        )
        self._catalog_presence = presence

    def given_target_language(self, language: TargetLanguage) -> None:
        """Bind the per-scenario target-language identifier."""
        self._target_language = language

    # --- When services -----------------------------------------------------

    def when_catalog_validator_runs(self) -> CatalogValidatorResult:
        """Run the production catalog validator CLI EDGE in-process.

        Drives ``scripts.cli.validate_language_adapter_catalog.main(argv)``
        in-process (the in-process analogue of ``python -m
        scripts.cli.validate_language_adapter_catalog`` -- corpus-migration-in-
        process) against the SSOT catalog path. The CLI exits 0 when the catalog
        is schema-valid AND every cited ``src/...`` path grep-finds; non-zero
        otherwise. Slice-01 RED: CLI module does not exist, exits with
        import-error / module-not-found (non-zero), so outcome=INVALID.
        Slice-01 GREEN (post-DELIVER): CLI exists + catalog exists + schema
        validates + paths grep-find, outcome=VALID.
        """
        exit_code, stdout, stderr = run_cli_in_process(
            [str(self._catalog_path)],
            cwd=_REPO_ROOT,
            main=_validate_catalog_main,
        )
        result = CatalogValidatorResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr
        )
        self.validator_result = result
        return result

    def when_des_doctor_runs(self) -> DoctorCliResult:
        """Run the production ``des doctor --target-language=<lang>`` subprocess.

        Invokes the real ``des`` CLI dispatcher with the new ``doctor``
        subcommand (DESIGN slice-01 / slice-03 walking-skeleton floor). The
        ``--target-language`` flag carries the typed-NewType value from the
        domain. Slice-01 RED: ``doctor`` is not registered in the ``_REGISTRY``
        tuple at ``src/des/cli/__main__.py`` AND ``src/des/cli/doctor.py``
        does not exist -- subprocess exits non-zero with "unknown subcommand".
        """
        assert self._target_language is not None, "target language not bound"
        proc = subprocess.run(
            [
                "des",
                "doctor",
                "--target-language",
                str(self._target_language),
            ],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
        )
        result = DoctorCliResult(
            exit_code=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
        )
        self.doctor_result = result
        return result

    def when_entry_point_discovery_runs(self) -> PluginDiscoveryResult:
        """Run the production entry-points discovery query in-process.

        Exercises the real Python ``importlib.metadata.entry_points`` against
        the canonical group ``nwave.lang.adapter`` (Option C discovery
        substrate per DESIGN slice-01). The identical discovery snippet runs
        in-process (corpus-migration-in-process) -- ``entry_points`` reads the
        same installed dist metadata whether forked or not. Slice-01 RED: zero
        plugins registered in the group (the ABC + first plugin land in
        slice-02 + slice-05a), so the discovered list is empty -- the AT pins
        the empty-list shape as the walking-skeleton floor.
        """
        exit_code, stdout, stderr = _run_py_snippet_in_process(
            _ENTRY_POINT_DISCOVERY_SNIPPET, cwd=_REPO_ROOT
        )
        result = PluginDiscoveryResult(
            exit_code=exit_code, stdout=stdout, stderr=stderr
        )
        self.discovery_result = result
        return result

    # --- Then services -----------------------------------------------------

    def then_catalog_validator_outcome_matches(
        self, expected: CatalogValidationOutcome
    ) -> None:
        """Assert the validator's exit-coded outcome matches expectation.

        Port-exposed observable: validator subprocess exit code -> typed enum
        outcome (Mandate 8 universe-bound; the universe is the one
        observable, the validator's exit verdict).
        """
        assert self.validator_result is not None, "validator not run"
        actual = self.validator_result.outcome
        assert actual is expected, (
            f"catalog validator outcome mismatch: "
            f"expected={expected.value}, actual={actual.value}\n"
            f"exit={self.validator_result.exit_code}\n"
            f"stdout: {self.validator_result.stdout}\n"
            f"stderr: {self.validator_result.stderr}"
        )

    def then_catalog_enumerates_minimum_language_bound_ports(self) -> None:
        """Assert the validator stdout names the three required LANGUAGE_BOUND CLIs.

        Slice-01 contract: the SSOT catalog MUST enumerate the three Nova-
        audited LANGUAGE_BOUND gate CLIs as the walking-skeleton floor.
        """
        assert self.validator_result is not None, "validator not run"
        assert self.validator_result.reports_minimum_language_bound_ports, (
            f"validator stdout must name run_contract_gate, "
            f"verify_environmental_e2e, check_robustness_density "
            f"(the three slice-01 LANGUAGE_BOUND CLIs); actual stdout:\n"
            f"{self.validator_result.stdout}"
        )

    def then_doctor_report_shape_is(self, expected: DoctorReportShape) -> None:
        """Assert the doctor CLI JSON envelope's ``shape`` field matches expectation.

        Port-exposed observable: stdout JSON ``shape`` field. Slice-01 RED:
        no JSON emitted (subcommand absent), so ``shape`` resolves to None,
        which never equals any DoctorReportShape -- assertion fails for the
        right reason.
        """
        assert self.doctor_result is not None, "doctor CLI not run"
        actual = self.doctor_result.shape
        assert actual is expected, (
            f"des doctor report shape mismatch: "
            f"expected={expected.value}, actual={actual.value if actual else None}\n"
            f"exit={self.doctor_result.exit_code}\n"
            f"stdout: {self.doctor_result.stdout}\n"
            f"stderr: {self.doctor_result.stderr}"
        )

    def then_doctor_report_lists_missing_language_bound_ports(self) -> None:
        """Assert the doctor JSON envelope's ``missing_ports`` is non-empty.

        Slice-01 floor: no per-language plugins are registered yet, so for
        ANY target language with a GAPS shape the missing_ports list is
        non-empty (enumerating the catalog's LANGUAGE_BOUND port set).
        """
        assert self.doctor_result is not None, "doctor CLI not run"
        assert self.doctor_result.reports_missing_language_bound_ports, (
            f"des doctor JSON envelope must list non-empty missing_ports "
            f"on GAPS shape (no plugins registered at slice-01); actual "
            f"stdout:\n{self.doctor_result.stdout}"
        )

    def then_entry_point_discovery_succeeds(self) -> None:
        """Assert the entry-points discovery subprocess exits 0 with a parseable JSON list.

        Port-exposed observable: subprocess exit code + JSON-list parse
        outcome. Slice-01 floor: the list is empty (zero plugins registered
        in ``nwave.lang.adapter`` group). The assertion pins (a) the group
        is queryable as the canonical substrate and (b) the JSON shape is a
        list -- subsequent slices extend with non-empty discovery.
        """
        assert self.discovery_result is not None, "entry-point discovery not run"
        assert self.discovery_result.exit_code == 0, (
            f"entry-points discovery subprocess must exit 0; "
            f"actual exit={self.discovery_result.exit_code}\n"
            f"stderr: {self.discovery_result.stderr}"
        )
        names = self.discovery_result.registered_plugin_names
        assert names is not None, (
            f"entry-points discovery stdout must be a JSON list; actual "
            f"stdout:\n{self.discovery_result.stdout}"
        )

    def then_entry_point_discovery_lists_floor(
        self, *, expected_minimum_count: int
    ) -> None:
        """Assert the entry-point discovery list contains at least the expected floor.

        Slice-01 floor: ``expected_minimum_count=0`` -- the group is
        queryable and the result is a list (possibly empty). Slice-02
        bumps the floor to ≥1 (the LanguageAdapterPlugin ABC ships its
        Python reference entry-point); slice-05a bumps to ≥1 named
        ``python``; future slices bump per the per-language plugins.
        """
        assert self.discovery_result is not None, "entry-point discovery not run"
        names = self.discovery_result.registered_plugin_names
        assert names is not None, "entry-points stdout not JSON-list-parseable"
        assert len(names) >= expected_minimum_count, (
            f"entry-point discovery list must contain at least "
            f"{expected_minimum_count} entries; actual list={names}"
        )
