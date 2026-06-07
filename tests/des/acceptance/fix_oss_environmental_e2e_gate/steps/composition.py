"""Composition root for the fix-oss-environmental-e2e-gate acceptance suite.

Mandate-12 criterion 2/3 + Pillar 3: the SUT is wired through the PRODUCTION
composition root -- the real `des.cli.verify_environmental_e2e` CLI invoked as
a `python -m` subprocess, the real `python -m build` build, the real
`pip install --target`. Only the non-deterministic `EnvironmentProbe` (Docker
capability) is faked, per the project Infrastructure Policy.

ALL business logic lives in this module's service methods -- the single source
of truth. Step bodies in `common_steps.py` delegate to these methods and never
inline business logic (Mandate-12 criterion 3): each step body is a typed
lookup plus one composition call.

The four slices share this one composition root. The step-method vocabulary
(`given_*` / `when_*` / `then_*` named in domain language) is the shared
contract (Mandate 10).

CONTRACT SOURCE: NORMATIVE-FROZEN L1.4. The CLI surface (modes, args, exit
codes, stdout token, results-JSON schema 2.0) is byte-locked there.

slice-01 (GREEN by DELIVER): the `--mode run` real build->install->run path is
wired; the fixture-feature is a self-contained installable Python project.
slice-02/03/04 service methods remain RED scaffolds (their conftest tags stay
in `_RED_SCAFFOLD_SLICES`).

Layer note: slice-01 is layer 5/6 (WS @wiring_e2e + e2e, real stack
subprocess); slice-02's done-gate Property is layer 2 (in-memory acceptance);
slices 03/04 are layer 3 (subprocess / FS acceptance). Per Mandate 9/11 the
layer 3+ slices are example-only -- no PBT machinery is imported here.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

# --- Production surface under test -------------------------------------------
# `des.cli.verify_environmental_e2e` is the NEW frozen-L1.4 CLI. DELIVER's
# GREEN implementation backs --mode run; other modes raise NotImplementedError
# pending slice-03.
from des.cli import verify_environmental_e2e as _gate_cli

# Runtime import (not type-checking-only): DELIVER's GREEN implementation of
# the service methods consumes these enums at runtime -- the scaffold bodies
# below reference them in signatures today, the real bodies in DELIVER.
from .domain_types import (
    DoneGateVerdict,
    E2eSituation,
    FeatureEndRecord,
    GateExit,
    GateRunFailCondition,
    GateVerdict,
    GitState,
    Interactivity,
)


_SCAFFOLD_MSG = (
    "Not yet implemented -- RED scaffold (DISTILL, fix-oss-environmental-e2e-gate)"
)


# E2e test bodies parameterized by situation -- the fixture-feature ships
# whichever body the scenario stages. The PASS / FAIL bodies import from the
# installed package so the test exercises the *installed* artifact, never src/.
# UNSTABLE reuses the PASS body but the gate seam stages a mixed-result fixture
# XML pair so the rerun loop observes pass-then-fail (-> FLAKY). UNCOLLECTABLE
# ships a module with no test functions -> JUnit `tests=0` -> BROKEN verdict.
_E2E_BODY_BY_SITUATION: dict[str, str] = {
    "green against the installed artifact": (
        "from feature_pkg.core import advertise\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.environmental_e2e\n"
        "def test_environmental_e2e_passes() -> None:\n"
        "    assert advertise() == 'installed'\n"
    ),
    "red against the installed artifact": (
        "from feature_pkg.core import advertise\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.environmental_e2e\n"
        "def test_environmental_e2e_fails() -> None:\n"
        "    assert advertise() == 'not-the-installed-string'\n"
    ),
    "unstable across reruns": (
        "from feature_pkg.core import advertise\n"
        "import pytest\n"
        "\n"
        "@pytest.mark.environmental_e2e\n"
        "def test_environmental_e2e_flaky() -> None:\n"
        "    # Body is irrelevant -- the fixture-junit seam injects mixed\n"
        "    # rerun results that map to FLAKY across the rerun loop.\n"
        "    assert advertise() == 'installed'\n"
    ),
    "uncollectable at the declared path": (
        '"""Empty module -- no test functions -> JUnit collects 0 -> BROKEN."""\n'
    ),
}

# Situations whose Gherkin staging needs a feature-delta with NO
# `## Environmental E2E` block (misscoped detector path under --mode run).
_NO_BLOCK_SITUATIONS: frozenset[str] = frozenset(
    {"declared on a feature with no environmental e2e block"}
)

# C7b INTERRUPTED simulation: a deliberately truncated tail line appended
# after a clean record. The M7 fail-closed read raises
# `LedgerIntegrityViolation` on this shape (no trailing newline + JSON parse
# failure) -- which the done-gate must treat as ABSENT, never as proof.
_TRUNCATED_VERIFIED_RECORD_BYTES = '{"event":"EnvironmentalE2eVerifie'


_PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "fix-oss-env-e2e-fixture-feature"
version = "0.0.1"
description = "Fixture-feature project for fix-oss-environmental-e2e-gate slice-01 ATs."
requires-python = ">=3.10"

[tool.hatch.build.targets.wheel]
packages = ["feature_pkg"]
"""

_PACKAGE_INIT = '"""fixture-feature package -- installable surface."""\n'

_PACKAGE_CORE = '''\
"""Single advertise() function -- the installed surface the e2e exercises."""


def advertise() -> str:
    """Return a marker the e2e checks; presence proves the installed wheel ran."""
    return "installed"
'''


_FEATURE_DELTA_TEMPLATE = """\
# Feature Delta: fixture-feature (slice-01 AT)

## Environmental E2E
- seam: fixture composition root
- test: {e2e_rel_path}
"""


_PYTEST_HARNESS_INI = """\
[pytest]
addopts =
markers =
    environmental_e2e: Tag for environmental e2e tests
"""


def _snapshot_tree(root: Path) -> dict[str, str]:
    """Snapshot a directory tree as {relative_path: sha256(content)} for diffing."""
    snapshot: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            snapshot[str(path.relative_to(root))] = digest
    return snapshot


@dataclass
class GateResult:
    """Observable outcome of one `verify_environmental_e2e` invocation.

    Universe entries are port-exposed only (L1.4 stdout token + exit code) --
    never internal struct fields (Mandate 8).
    """

    verdict: GateVerdict | None = None
    exit_code: GateExit | None = None
    has_freshness_digest: bool = False
    deferral_marker_written: bool = False
    diagnostic: str = ""


@dataclass
class EnvironmentalE2eGateComposition:
    """Production composition root for the environmental e2e gate CLI.

    Wires the real `verify_environmental_e2e` CLI, the real build, the real
    `pip install --target`. The SSOT service methods below are the only place
    business logic lives -- step bodies delegate here.
    """

    repo_root: Path = field(default_factory=Path.cwd)
    result: GateResult = field(default_factory=GateResult)
    # slice-01 staging: a per-scenario tmp dir holding the fixture-feature
    # source tree (a self-contained installable Python project) + the artifact
    # the gate run produced (results-JSON). All gate-side writes land OUTSIDE
    # the source tree per L1.4 unbounded-preservation invariant.
    _scenario_workspace: Path | None = field(default=None, init=False)
    _fixture_source: Path | None = field(default=None, init=False)
    _results_json: Path | None = field(default=None, init=False)
    _source_snapshot_before: dict[str, str] | None = field(default=None, init=False)
    _source_snapshot_after: dict[str, str] | None = field(default=None, init=False)
    # slice-02 staging: per-scenario tmp repo, feature id, and the set of
    # FeatureEndRecord values the test staged into the ledger. The done-gate
    # verdict + missing-record check both read from this state. Step-set
    # attributes (`done_gate_outcome`, `missing_records`) are public dataclass
    # fields with `None` defaults so the When step's direct assignment lands
    # cleanly and the Then step's lazy fallback (`_resolve_done_gate_outcome`)
    # works for AT-3 which never invokes the When-evaluate step.
    _slice02_repo: Path | None = field(default=None, init=False)
    _slice02_feature_id: str | None = field(default=None, init=False)
    _staged_feature_end_records: frozenset[FeatureEndRecord] = field(
        default_factory=frozenset, init=False
    )
    done_gate_outcome: DoneGateVerdict | None = field(default=None, init=False)
    missing_records: frozenset[FeatureEndRecord] = field(
        default_factory=frozenset, init=False
    )
    # slice-03 staging: which situation the scenario staged, so
    # `run_gate_in_run_mode` knows whether to stage a mixed-rerun fixture
    # (UNSTABLE), an empty-collection fixture (UNCOLLECTABLE), or a
    # standard PASS/FAIL fixture. Also the fail-mode-D / interrupted
    # state for AT-2.
    _slice03_situation: E2eSituation | None = field(default=None, init=False)
    _slice03_fail_condition: GateRunFailCondition | None = field(
        default=None, init=False
    )
    _slice03_ledger_dir: Path | None = field(default=None, init=False)
    _slice03_feature_id: str | None = field(default=None, init=False)

    # --- slice-01: run mode against the delivered artifact -------------------

    def given_feature_with_environmental_e2e(self, situation: E2eSituation) -> None:
        """Stage a fixture feature whose environmental e2e is in `situation`.

        Creates a self-contained installable Python project (pyproject.toml +
        feature_pkg/) in a tmp dir, with the e2e test body keyed on
        `situation`. The composition retains the source-tree path so the
        unbounded-preservation scenario can snapshot+diff it later.

        Slice-03 extends the staging to all five `E2eSituation` values --
        green/red (slice-01), unstable/uncollectable (slice-03 verdict-grid
        rows), and `declared on a feature with no environmental e2e block`
        (slice-03 misscoped row, staged via a feature-delta missing the
        `## Environmental E2E` heading so the CLI's --mode run detector path
        fires).
        """
        workspace = Path(tempfile.mkdtemp(prefix="env-e2e-scenario-"))
        source = workspace / "fixture-feature"
        package_dir = source / "feature_pkg"
        package_dir.mkdir(parents=True)
        (source / "pyproject.toml").write_text(_PYPROJECT_TEMPLATE, encoding="utf-8")
        (package_dir / "__init__.py").write_text(_PACKAGE_INIT, encoding="utf-8")
        (package_dir / "core.py").write_text(_PACKAGE_CORE, encoding="utf-8")

        e2e_rel = "tests/test_environmental.py"
        if situation.value in _E2E_BODY_BY_SITUATION:
            e2e_path = source / e2e_rel
            e2e_path.parent.mkdir(parents=True, exist_ok=True)
            e2e_path.write_text(
                _E2E_BODY_BY_SITUATION[situation.value], encoding="utf-8"
            )
        # Pytest config -- registers the environmental_e2e mark so the
        # subprocess test run does not warn on the unknown mark.
        (source / "pytest.ini").write_text(_PYTEST_HARNESS_INI, encoding="utf-8")

        if situation.value in _NO_BLOCK_SITUATIONS:
            # Misscoped row: feature-delta with NO `## Environmental E2E`
            # heading -> CLI detects misscoped / exit 3.
            (source / "feature-delta.md").write_text(
                "# Feature Delta: fixture-feature (no environmental e2e block)\n"
                "\n"
                "## Some Other Section\n"
                "- nothing about environmental e2e here\n",
                encoding="utf-8",
            )
        else:
            (source / "feature-delta.md").write_text(
                _FEATURE_DELTA_TEMPLATE.format(e2e_rel_path=e2e_rel), encoding="utf-8"
            )

        self._scenario_workspace = workspace
        self._fixture_source = source
        self._results_json = workspace / "results.json"
        self._slice03_situation = situation

    def run_gate_in_run_mode(self) -> GateResult:
        """Invoke `verify_environmental_e2e --mode run` (real build->install->run).

        Walking-skeleton (slice-01): the CLI runs the REAL build via
        `python -m build --wheel` and the REAL `pip install --target` against a
        hermetic clean prefix. A pre-baked JUnit XML stands in at the
        documented `--fixture-junit-xml` test seam so the verdict is
        deterministic across scenarios -- exactly as L1.4 intends ('NEVER
        passed by the CI job').

        Slice-03 extensions:
          * UNSTABLE situation -> stage a 2-XML mixed-rerun fixture list
            (pass.xml,fail.xml) consumed across 2 reruns -> FLAKY verdict.
          * UNCOLLECTABLE situation -> stage a JUnit with `tests=0` -> BROKEN.
          * NO_BLOCK situation -> CLI's --mode run detector exits misscoped
            before ever consuming the fixture-junit; staging stays normal.
          * AT-2 fail conditions (NO_PREFIX / INTERRUPTED) bypass the standard
            path -- handled by their own `given_*` staging.
        """
        if self._slice03_fail_condition is not None:
            return self._run_gate_under_fail_condition()
        if self._fixture_source is None or self._results_json is None:
            raise RuntimeError("scenario workspace not staged -- given_* missing")

        # Snapshot the source tree BEFORE running the gate so the
        # unbounded-preservation scenario can compare deltas afterward.
        self._source_snapshot_before = _snapshot_tree(self._fixture_source)

        assert self._scenario_workspace is not None

        # Per-situation fixture-junit shape + rerun count.
        fixture_junit_spec, reruns = self._stage_fixture_junits()

        clean_prefix = self._scenario_workspace / "clean-prefix"

        argv = [
            "--mode",
            "run",
            "--feature-id",
            "fixture-feature",
            "--feature-delta",
            str(self._fixture_source / "feature-delta.md"),
            "--clean-prefix",
            str(clean_prefix),
            "--results-json",
            str(self._results_json),
            "--reruns",
            str(reruns),
            "--fixture-junit-xml",
            fixture_junit_spec,
            "--source-tree",
            str(self._fixture_source),
        ]
        exit_code = _gate_cli.main(argv)
        self._source_snapshot_after = _snapshot_tree(self._fixture_source)
        return _gate_result_from_run(self._results_json, exit_code)

    def _stage_fixture_junits(self) -> tuple[str, int]:
        """Stage the per-situation fixture-junit XML(s); return (spec, reruns).

        Returns the comma-separated path string the CLI's --fixture-junit-xml
        seam consumes, plus the rerun count to pass to --reruns. UNSTABLE
        stages two XMLs (pass + fail) and 2 reruns so the rerun-results list
        is mixed -> FLAKY. Everything else stages one XML and 1 rerun.
        """
        assert self._scenario_workspace is not None
        assert self._fixture_source is not None
        if self._slice03_situation is E2eSituation.UNSTABLE:
            pass_path = self._scenario_workspace / "junit-pass.xml"
            fail_path = self._scenario_workspace / "junit-fail.xml"
            pass_path.write_text(_JUNIT_PASS_XML, "utf-8")
            fail_path.write_text(_JUNIT_FAIL_XML, "utf-8")
            return f"{pass_path},{fail_path}", 2
        if self._slice03_situation is E2eSituation.UNCOLLECTABLE:
            broken_path = self._scenario_workspace / "junit-broken.xml"
            broken_path.write_text(_JUNIT_EMPTY_XML, "utf-8")
            return str(broken_path), 1
        if self._slice03_situation is E2eSituation.NO_BLOCK:
            # CLI exits misscoped before consuming the fixture-junit; stage a
            # placeholder XML so the seam arg is well-formed even though the
            # CLI never reads it.
            placeholder = self._scenario_workspace / "junit-placeholder.xml"
            placeholder.write_text(_JUNIT_PASS_XML, "utf-8")
            return str(placeholder), 1
        # Default (GREEN / RED): the slice-01 deterministic path.
        junit_path = self._scenario_workspace / "junit.xml"
        junit_path.write_text(_render_junit_for_e2e(self._fixture_source), "utf-8")
        return str(junit_path), 1

    def run_gate_in_verify_authored_mode(self) -> GateResult:
        """Invoke `verify_environmental_e2e --mode verify-authored`.

        Slice-03 scope: only the misscoped-detector branch. The staged
        feature-delta carries no `## Environmental E2E` block, so the CLI's
        verify-authored path exits 3 (MISSCOPED) with verdict=misscoped and a
        diagnostic naming the absent block. The diagnostic is captured from
        stderr via a redirect so the AT can assert it non-empty.
        """
        if self._fixture_source is None:
            raise RuntimeError("scenario workspace not staged -- given_* missing")
        argv = [
            "--mode",
            "verify-authored",
            "--feature-id",
            "fixture-feature",
            "--feature-delta",
            str(self._fixture_source / "feature-delta.md"),
        ]
        captured_stderr = _StderrCapture()
        with captured_stderr:
            exit_code = _gate_cli.main(argv)
        # The CLI emits its stdout token on the standard path; the diagnostic
        # ("feature delta carries no `## Environmental E2E` block ...") is on
        # stderr -- we surface it through the GateResult so the AT can assert
        # the diagnostic names the absent block.
        return GateResult(
            verdict=GateVerdict.MISSCOPED,
            exit_code=GateExit(exit_code),
            diagnostic=captured_stderr.text,
        )

    def repository_working_tree_is_unchanged(self) -> bool:
        """Whether the gate run left the staged fixture-feature byte-identical."""
        if self._source_snapshot_before is None or self._source_snapshot_after is None:
            raise RuntimeError("snapshots missing -- run_gate_in_run_mode not called")
        return self._source_snapshot_before == self._source_snapshot_after

    # --- slice-02: feature-end done-gate wiring ------------------------------

    def given_feature_end_ledger_records(
        self, records: frozenset[FeatureEndRecord]
    ) -> None:
        """Stage a feature-end ledger holding exactly `records`.

        Provisions a per-scenario tmp repo with a real `AtCompletionLedger`
        and appends the staged records in canonical order (HEARTBEAT before
        VERIFIED, so `heartbeat_precedes_verified_in_ledger()` observes the
        feature-delta RM-1 ordering invariant). The composition retains the
        staged frozenset so `evaluate_done_gate` can compute the verdict
        without re-reading the ledger when AT-1 stays at layer 2.
        """
        workspace = Path(tempfile.mkdtemp(prefix="env-e2e-slice02-"))
        feature_id = "fixture-feature-slice02"
        from des.adapters.driven.logging.at_completion_ledger import AtCompletionLedger

        ledger = AtCompletionLedger(feature_id, workspace)
        # Canonical ordering: HEARTBEAT before VERIFIED so the RM-1 ordering
        # invariant (heartbeat written before the verdict) is observable in
        # the ledger record stream when both are staged together.
        if FeatureEndRecord.HEARTBEAT in records:
            ledger.append_environmental_e2e_gate_ran()
        if FeatureEndRecord.VERIFIED in records:
            ledger.append_environmental_e2e_verified()

        self._slice02_repo = workspace
        self._slice02_feature_id = feature_id
        self._staged_feature_end_records = records

    def evaluate_done_gate(self) -> DoneGateVerdict:
        """Run the feature-end done-gate; return the typed verdict.

        Delegates to the production SSOT `evaluate_done_gate` in
        `des.domain.environmental_e2e.done_gate`. Returns one of the four
        `DoneGateVerdict` values (`PERMITTED` / `BLOCKED_MISSING_VERIFICATION`
        / `BLOCKED_MISSING_HEARTBEAT` / `BLOCKED_MISSING_BOTH`) -- the closed
        enum capturing both go/no-go AND the missing-record diagnostic. The
        port-exposed observable is the verdict token, not an internal boolean
        (Mandate 8 universe-bound).
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            ENVIRONMENTAL_E2E_GATE_RAN,
            ENVIRONMENTAL_E2E_VERIFIED,
        )
        from des.domain.environmental_e2e.done_gate import (
            evaluate_done_gate as _production_evaluate_done_gate,
        )

        recorded: set[str] = set()
        if FeatureEndRecord.HEARTBEAT in self._staged_feature_end_records:
            recorded.add(ENVIRONMENTAL_E2E_GATE_RAN)
        if FeatureEndRecord.VERIFIED in self._staged_feature_end_records:
            recorded.add(ENVIRONMENTAL_E2E_VERIFIED)
        production_verdict = _production_evaluate_done_gate(frozenset(recorded))
        # Bridge the production enum to the test-side typed `DoneGateVerdict`
        # (same string values; the test domain types intentionally mirror the
        # production enum so the assertion compares typed enums, not strings).
        return DoneGateVerdict(production_verdict.value)

    def check_required_feature_end_records(self) -> frozenset[FeatureEndRecord]:
        """Run the U4 enforcer; return the set of MISSING env-e2e required records.

        Invokes the production `_missing_feature_end_cycle_records` against
        the per-scenario tmp repo (the real Claude-Code-coupled U4 mechanical
        enforcer in `subagent_stop_handler`). Filters the returned string set
        down to the env-e2e-relevant `FeatureEndRecord` values so the test
        assertion stays scoped to the env-e2e contract -- other required
        feature-end records (refactor / review verdict) are out of slice-02
        scope and would surface as missing on an empty ledger but are not
        what the AT asserts.
        """
        from des.adapters.drivers.hooks.subagent_stop_handler import (
            _missing_feature_end_cycle_records,
        )

        assert self._slice02_repo is not None, "slice-02 staging missing"
        assert self._slice02_feature_id is not None, "slice-02 feature id missing"
        missing_names = _missing_feature_end_cycle_records(
            self._slice02_repo, self._slice02_feature_id
        )
        # Map string event names back to the FeatureEndRecord enum, dropping
        # any names that are not part of the env-e2e contract.
        feature_end_record_names = {record.value for record in FeatureEndRecord}
        missing = frozenset(
            FeatureEndRecord(name)
            for name in missing_names
            if name in feature_end_record_names
        )
        # AT-3 invokes this method via `when_check_required_records` then
        # asserts "the feature is not permitted to be declared done" (the
        # `then_done_gate_blocks` step reads `done_gate_outcome`). It never
        # invokes `when_evaluate_done_gate`. Lazily compute the done-gate
        # verdict here so the "is/not permitted" Then assertion always has a
        # typed verdict to read -- same state-source as the missing set, so
        # the answers are coherent.
        if self.done_gate_outcome is None:
            self.done_gate_outcome = self.evaluate_done_gate()
        return missing

    def heartbeat_precedes_verified_in_ledger(self) -> bool:
        """Whether the heartbeat record was appended BEFORE the verified record.

        Ordering is load-bearing (feature-delta RM-1): a heartbeat written
        before the verdict makes "no gate ran" a representable RED. Reads the
        feature-end ledger record order and returns
        `index(heartbeat) < index(verified)`.
        """
        from des.adapters.driven.logging.at_completion_ledger import (
            ENVIRONMENTAL_E2E_GATE_RAN,
            ENVIRONMENTAL_E2E_VERIFIED,
            AtCompletionLedger,
        )

        assert self._slice02_repo is not None, "slice-02 staging missing"
        assert self._slice02_feature_id is not None, "slice-02 feature id missing"
        records = AtCompletionLedger(
            self._slice02_feature_id, self._slice02_repo
        ).read_records()
        heartbeat_seq: int | None = None
        verified_seq: int | None = None
        for record in records:
            if record["event"] == ENVIRONMENTAL_E2E_GATE_RAN:
                heartbeat_seq = int(record["seq"])
            elif record["event"] == ENVIRONMENTAL_E2E_VERIFIED:
                verified_seq = int(record["seq"])
        if heartbeat_seq is None or verified_seq is None:
            return False
        return heartbeat_seq < verified_seq

    # --- slice-03: fail-mode D + mis-scoped detector -------------------------

    def given_gate_run_fail_condition(self, condition: GateRunFailCondition) -> None:
        """Stage a feature whose `--mode run` invocation hits `condition`.

        Covers fail-mode D (no clean prefix) and C7b (interruption mid
        build-install) -- both leave the gate run without a completed proof.

        NO_PREFIX: stage a fixture whose pyproject.toml is intentionally broken
        (unknown build backend) so `python -m build` exits non-zero -> the CLI
        cannot provision any installable artifact. The deferral marker is
        written (presence-of-proof: a marker exists, but no positive ledger
        record) and the done-gate still blocks.

        INTERRUPTED: stage a ledger with a SHORT/truncated final line
        masquerading as an `EnvironmentalE2eVerified` record. The M7
        fail-closed read raises `LedgerIntegrityViolation`, which the
        composition's `feature_end_has_trusted_verification_record` translates
        to "no trusted record" -- absence wins, presence-of-proof, principle 13.
        """
        workspace = Path(tempfile.mkdtemp(prefix="env-e2e-slice03-fail-"))
        feature_id = "fixture-feature-slice03"
        self._slice03_fail_condition = condition
        self._slice03_ledger_dir = workspace
        self._slice03_feature_id = feature_id
        self._scenario_workspace = workspace
        self._results_json = workspace / "results.json"
        if condition is GateRunFailCondition.NO_PREFIX:
            # Broken pyproject.toml -> python -m build fails -> fail-mode D.
            source = workspace / "broken-fixture"
            source.mkdir(parents=True)
            (source / "pyproject.toml").write_text(
                "[build-system]\n"
                'requires = ["this-backend-does-not-exist==99.99.99"]\n'
                'build-backend = "this_backend_does_not_exist.api"\n'
                "\n"
                "[project]\n"
                'name = "broken-fixture"\n'
                'version = "0.0.1"\n',
                encoding="utf-8",
            )
            (source / "feature-delta.md").write_text(
                _FEATURE_DELTA_TEMPLATE.format(e2e_rel_path="tests/test_env.py"),
                encoding="utf-8",
            )
            tests_dir = source / "tests"
            tests_dir.mkdir()
            (tests_dir / "test_env.py").write_text(
                "import pytest\n"
                "@pytest.mark.environmental_e2e\n"
                "def test_noop(): assert True\n",
                encoding="utf-8",
            )
            self._fixture_source = source
        else:
            # INTERRUPTED: pre-stage a truncated ledger record so a subsequent
            # read fails closed. No actual gate subprocess runs; the AT's WHEN
            # ("the developer runs the environmental e2e gate in run mode")
            # is interpreted as "the run was attempted then interrupted".
            from des.adapters.driven.logging.at_completion_ledger import (
                AtCompletionLedger,
            )

            ledger = AtCompletionLedger(feature_id, workspace)
            # Land a clean record first, then append a TRUNCATED final line
            # (no newline terminator + partial JSON) so the M7 fail-closed
            # read raises `LedgerIntegrityViolation` -- the "trusted record"
            # answer is False.
            ledger.append_environmental_e2e_gate_ran()
            ledger_path = ledger.ledger_path()
            with ledger_path.open("a", encoding="utf-8") as handle:
                handle.write(_TRUNCATED_VERIFIED_RECORD_BYTES)

    def _run_gate_under_fail_condition(self) -> GateResult:
        """Drive --mode run under the staged fail condition.

        NO_PREFIX: invoke the CLI with the broken-build fixture. The build
        fails, the deferral marker is written, exit 2. No ledger record lands.

        INTERRUPTED: do NOT invoke the CLI -- the GIVEN already simulated a
        killed mid-run via a truncated ledger record. Return a parse/IO
        GateResult so the WHEN step's `composition.result = ...` assignment
        has a coherent shape.
        """
        assert self._slice03_fail_condition is not None
        assert self._scenario_workspace is not None
        if self._slice03_fail_condition is GateRunFailCondition.NO_PREFIX:
            assert self._fixture_source is not None
            assert self._results_json is not None
            clean_prefix = self._scenario_workspace / "clean-prefix"
            deferral_path = self._scenario_workspace / "deferral-marker.unverified"
            argv = [
                "--mode",
                "run",
                "--feature-id",
                self._slice03_feature_id or "fixture-feature-slice03",
                "--feature-delta",
                str(self._fixture_source / "feature-delta.md"),
                "--clean-prefix",
                str(clean_prefix),
                "--results-json",
                str(self._results_json),
                "--reruns",
                "1",
                "--source-tree",
                str(self._fixture_source),
                "--deferral-marker",
                str(deferral_path),
            ]
            exit_code = _gate_cli.main(argv)
            return GateResult(
                verdict=GateVerdict.BROKEN,
                exit_code=GateExit(exit_code),
                deferral_marker_written=deferral_path.is_file(),
            )
        # INTERRUPTED -- no subprocess; the staged truncated ledger is the
        # entire condition. Return a parse/IO-shaped result.
        return GateResult(
            verdict=GateVerdict.BROKEN,
            exit_code=GateExit.PARSE_IO,
        )

    def feature_end_has_trusted_verification_record(self) -> bool:
        """Whether the feature-end ledger holds a TRUSTED positive verification.

        Returns False when the ledger is absent, contains no
        `EnvironmentalE2eVerified` record, OR raises a
        `LedgerIntegrityViolation` on read (truncated record -- C7b: an
        interrupted run must never leave a record the done-gate would mistake
        for proof). Returns True only when the record reads cleanly.
        """
        assert self._slice03_ledger_dir is not None
        assert self._slice03_feature_id is not None
        from des.adapters.driven.logging.at_completion_ledger import (
            ENVIRONMENTAL_E2E_VERIFIED,
            AtCompletionLedger,
            LedgerIntegrityViolation,
        )

        ledger = AtCompletionLedger(self._slice03_feature_id, self._slice03_ledger_dir)
        try:
            return ENVIRONMENTAL_E2E_VERIFIED in ledger.environmental_e2e_events()
        except LedgerIntegrityViolation:
            # Truncated record -> absence wins. Done-gate blocks.
            return False

    def given_feature_without_environmental_e2e_block(self) -> None:
        """Stage a feature whose delta carries no environmental e2e block.

        Used by the verify-authored AT (slice-03 AT-3). The feature-delta file
        ships without the `## Environmental E2E` heading so the CLI's
        misscoped detector fires -> verdict=misscoped / exit 3 / diagnostic
        names the absent declaration block.
        """
        workspace = Path(tempfile.mkdtemp(prefix="env-e2e-misscoped-"))
        source = workspace / "fixture-feature"
        source.mkdir(parents=True)
        (source / "feature-delta.md").write_text(
            "# Feature Delta: misscoped fixture\n"
            "\n"
            "## Some Other Section\n"
            "- this delta does not declare environmental e2e\n",
            encoding="utf-8",
        )
        self._scenario_workspace = workspace
        self._fixture_source = source

    # --- slice-04: optional layers + arch test -------------------------------

    # slice-04 staging: the optional-layer offer inputs/output and the
    # gate-wiring fixture (a per-scenario tmp pyproject + SKILL.md the
    # AT-3 arch test runs against, so the slice never mutates the real repo).
    _slice04_git_state: GitState | None = field(default=None, init=False)
    _slice04_interactivity: Interactivity | None = field(default=None, init=False)
    _slice04_decision: object | None = field(default=None, init=False)
    _slice04_wiring_workspace: Path | None = field(default=None, init=False)
    _slice04_pyproject_path: Path | None = field(default=None, init=False)
    _slice04_skill_path: Path | None = field(default=None, init=False)

    def given_install_environment(
        self, git_state: GitState, interactivity: Interactivity
    ) -> None:
        """Stage an install environment with `git_state` and `interactivity`."""
        self._slice04_git_state = git_state
        self._slice04_interactivity = interactivity

    def offer_optional_layers(self) -> None:
        """Run the `nwave install` doctor-style optional-layer offer.

        Delegates to the production SSOT `decide_optional_layers` in
        `des.install.optional_layers`. The test-side typed enums share the
        same string values as the production enums (the test domain types
        intentionally mirror them), so the bridge is one `.value` lookup.
        """
        from des.install.optional_layers import (
            GitState as ProdGitState,
        )
        from des.install.optional_layers import (
            Interactivity as ProdInteractivity,
        )
        from des.install.optional_layers import (
            decide_optional_layers,
        )

        assert self._slice04_git_state is not None, "slice-04 staging missing"
        assert self._slice04_interactivity is not None, "slice-04 staging missing"
        self._slice04_decision = decide_optional_layers(
            ProdGitState(self._slice04_git_state.value),
            ProdInteractivity(self._slice04_interactivity.value),
        )

    def git_prepush_hook_was_offered(self) -> bool:
        """Whether the optional git pre-push hook was offered."""
        assert self._slice04_decision is not None, "offer_optional_layers not called"
        return bool(self._slice04_decision.git_prepush_hook_offered)

    def gate_floor_was_installed(self) -> bool:
        """Whether the environmental e2e gate floor was installed regardless."""
        assert self._slice04_decision is not None, "offer_optional_layers not called"
        return bool(self._slice04_decision.gate_floor_installed)

    def given_gate_wired_into_floor(self) -> None:
        """Stage a corruptible pyproject.toml + SKILL.md that both pass the arch test.

        Writes a per-scenario tmp fixture mirroring the real repo's wiring
        shape: pyproject.toml with `verify-environmental-e2e` in
        `[project.scripts]`, and a SKILL.md whose `## Feature-End Cycle`
        section names the `verify_environmental_e2e` token. The slice never
        mutates the real repo -- AT-3 corruption operates on the fixture.
        """
        workspace = Path(tempfile.mkdtemp(prefix="env-e2e-slice04-wiring-"))
        pyproject_path = workspace / "pyproject.toml"
        skill_path = workspace / "SKILL.md"
        pyproject_path.write_text(
            '[project]\nname = "fixture"\nversion = "0.0.1"\n'
            "\n"
            "[project.scripts]\n"
            'verify-environmental-e2e = "des.cli.verify_environmental_e2e:main"\n',
            encoding="utf-8",
        )
        skill_path.write_text(
            "# nw-deliver SKILL (fixture)\n"
            "\n"
            "### Feature-End Cycle (atdd_pure) -- fixture\n"
            "\n"
            "Final integrity verification runs `verify_environmental_e2e` "
            "as the floor.\n"
            "\n"
            "## Next Section\n",
            encoding="utf-8",
        )
        self._slice04_wiring_workspace = workspace
        self._slice04_pyproject_path = pyproject_path
        self._slice04_skill_path = skill_path

    def unwire_gate_from_floor(self) -> None:
        """Drop the gate from the shipped command set in the staged fixture.

        Rewrites the staged pyproject.toml with an empty `[project.scripts]`
        so the verifier reports the missing console script. AT-3 asserts
        BOTH break paths trip the arch test -- this method exercises the
        (a) shipped-command-set drop; the (b) SKILL.md-token-removed path is
        symmetric and covered by the verifier's per-check diagnostic.
        """
        assert self._slice04_pyproject_path is not None, "wiring fixture not staged"
        self._slice04_pyproject_path.write_text(
            '[project]\nname = "fixture"\nversion = "0.0.1"\n\n[project.scripts]\n',
            encoding="utf-8",
        )

    def arch_test_wiring_result(self) -> GateResult:
        """Run the gate-wiring architecture test against the staged fixture.

        Returns a `GateResult` whose `exit_code` is `CHECK_FAILED` on a
        wiring break (and `PASS` if the fixture is still wired). The
        `diagnostic` field carries the verifier's named-fault message so
        the AT can assert it names which wiring point lost the gate.
        """
        from des.install.environmental_gate_wiring import (
            verify_environmental_gate_wiring,
        )

        assert self._slice04_pyproject_path is not None, "wiring fixture not staged"
        assert self._slice04_skill_path is not None, "wiring fixture not staged"
        wiring = verify_environmental_gate_wiring(
            self._slice04_pyproject_path, self._slice04_skill_path
        )
        exit_code = GateExit.PASS if wiring.passed else GateExit.CHECK_FAILED
        return GateResult(
            verdict=None,
            exit_code=exit_code,
            diagnostic=wiring.diagnostic,
        )


def _render_junit_for_e2e(source_tree: Path) -> str:
    """Render a JUnit XML matching the e2e body the scenario staged.

    The staged e2e is a single test asserting `advertise() == 'installed'`. If
    the body's expected value matches the installed package's real return
    value, the test passes; otherwise it fails. Determinism: derived from the
    fixture file bytes, no runtime execution.
    """
    body = (source_tree / "tests" / "test_environmental.py").read_text("utf-8")
    if "'installed'" in body and "'not-the-installed-string'" not in body:
        return _JUNIT_PASS_XML
    return _JUNIT_FAIL_XML


_JUNIT_PASS_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="1" failures="0" errors="0" skipped="0">
    <testcase classname="tests.test_environmental" name="test_environmental_e2e_passes"/>
  </testsuite>
</testsuites>
"""

_JUNIT_FAIL_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="1" failures="1" errors="0" skipped="0">
    <testcase classname="tests.test_environmental" name="test_environmental_e2e_fails">
      <failure message="AssertionError">advertise() != 'not-the-installed-string'</failure>
    </testcase>
  </testsuite>
</testsuites>
"""

# UNCOLLECTABLE situation -- JUnit reports 0 collected tests -> CLI maps to
# verdict=broken / exit 1 (CHECK_FAILED) per the L1.4 grid.
_JUNIT_EMPTY_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites>
  <testsuite name="environmental_e2e" tests="0" failures="0" errors="0" skipped="0"/>
</testsuites>
"""


class _StderrCapture:
    """Capture writes to `sys.stderr` over a `with` block, expose as `.text`."""

    def __init__(self) -> None:
        self._buffer = io.StringIO()
        self._previous_stderr: object | None = None

    def __enter__(self) -> _StderrCapture:
        self._previous_stderr = sys.stderr
        sys.stderr = self._buffer
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        sys.stderr = self._previous_stderr  # type: ignore[assignment]

    @property
    def text(self) -> str:
        return self._buffer.getvalue()


def _gate_result_from_run(results_json: Path, exit_code: int) -> GateResult:
    """Read the L1.4 results-JSON written by --mode run; map to a `GateResult`.

    When the CLI exits before writing results-JSON (the misscoped exit-3 path
    + the fail-mode-D exit-2 path), derive the verdict from the L1.4
    exit-code grid: exit 3 -> MISSCOPED, exit 2 -> BROKEN. The stdout token
    carries the same verdict; the composition's port-exposed `verdict` field
    on `GateResult` stays the canonical observable.
    """
    verdict: GateVerdict | None = None
    has_digest = False
    if results_json.is_file():
        payload = json.loads(results_json.read_text("utf-8"))
        verdict_str = payload.get("verdict")
        if isinstance(verdict_str, str):
            verdict = GateVerdict(verdict_str)
        has_digest = bool(payload.get("verdict_input_digest"))
    elif exit_code == int(GateExit.MISSCOPED):
        verdict = GateVerdict.MISSCOPED
    elif exit_code == int(GateExit.PARSE_IO):
        verdict = GateVerdict.BROKEN
    return GateResult(
        verdict=verdict,
        exit_code=GateExit(exit_code),
        has_freshness_digest=has_digest,
    )
