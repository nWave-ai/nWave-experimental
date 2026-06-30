"""Composition root for f-spine-runs-tests-not-git-hooks (slices 01 + 02).

Drives the REAL in-tree spine slice-AT EXECUTOR ``python -m des.cli.run_slice_ats``
via its ARGS protocol (Mandate-13, Layer-3 subprocess). The executor is the
NEW machinery this feature builds (CRITICAL-1/CRITICAL-2): it consults
``TestRunnerPort.resolve`` FIRST (DDD-2, HIGH-2 short-circuit), gets the entering
slice's scoped node-ids from ``run_contract_gate.run_slice_ats`` (the collect-only
SCOPE seam, REUSED), then RUNS them via ``RunnerAdapter.run`` (the NEW run-facet)
and maps the exit to a verdict. At HEAD the module ``des.cli.run_slice_ats`` does
NOT exist (verified: `__main__.py` registers no ``run-slice-ats`` row), so the
subprocess exits non-zero on module-absence -- NEITHER the expected PASS (0) nor
the expected FAIL (1) -- a semantic AssertionError against the expected verdict
(active-RED, NOT @skip; the AT imports NOTHING from the absent SUT -- it shells out).

DRIVING PORT (Mandate-13, Layer-3 subprocess): ``python -m des.cli.run_slice_ats``
with ``--repo-root`` / ``--entering-slice``. The observable is the process EXIT
CODE (PASS=0 / FAIL=1 / INDETERMINATE != {0,1} / NOT_APPLICABLE=0) plus the one
JSON line on stdout {event, entering_slice, verdict, runner, ran_node_ids,
ran_whole_tree}. No executor logic is re-implemented in the step bodies (the AT
drives the real shipped gate, never a test-local reimplementation -- the
protocol-driver contract).

DORMANT-SEAM (D11 / Mandate-15): the net-new load-bearing seams this slice
declares load-bearing in the DESIGN driving-surface are
  (a) the ``des.cli.run_slice_ats`` executor (resolve->scope->RUN->verdict),
  (b) ``RunnerAdapter.run(scoped_node_ids) -> verdict`` (the NEW run facet on the
      ``name``-only frozen dataclass),
  (c) ``des.adapters.driven.runner.pytest_runner`` (the package does NOT exist
      today -- empty glob),
  (d) ``resolve()`` consulted FIRST, BEFORE the pytest-bound collection (HIGH-2).
Each witnessing AT drives THAT seam through the real entry point
(``python -m des.cli.run_slice_ats``) and asserts the exit-code observable
effect -- never a claim a symbol "exists".

HERMETIC: a tmp workspace only. No ``~/.claude`` / ``Path.home()`` /
``expanduser`` anywhere (the ``tests/meta/test_acceptance_hermeticity.py`` guard
rejects it at collection). The entering slice's ATs are PLANTED into the tmp
workspace by the harness (a real green-or-RED ``@<slice>`` scenario + its
pytest-bdd binding) so the executor has a genuine, scoped suite to RUN.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

import pytest

from des.cli.run_contract_gate import main as _run_contract_gate_main
from des.cli.run_slice_ats import main as _run_slice_ats_main
from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types import SliceAtColour, SliceVerdict, TargetRunner


# tests/des/acceptance/f_spine_runs_tests_not_git_hooks/steps/<this file> when
# collected: parents[5] = REPO_ROOT (mirrors the sibling composition root).
REPO_ROOT = Path(__file__).resolve().parents[5]

_PROBE_SLICE = "slice-probe"

# Lockfile shapes that make TestRunnerPort.resolve() pick each runner (slice-02).
# Genuine target manifests (read by resolve()'s real filesystem inspection),
# never a caller-supplied runner name.
_RUNNER_MANIFEST: dict[TargetRunner, tuple[str, str]] = {
    TargetRunner.PYTEST: ("pyproject.toml", "[project]\nname = 'probe-target'\n"),
    TargetRunner.VITEST: ("package.json", '{"devDependencies": {"vitest": "1.0.0"}}'),
    TargetRunner.GO_TEST: ("go.mod", "module probe-target\n\ngo 1.22\n"),
    TargetRunner.CARGO_TEST: ("Cargo.toml", "[package]\nname = 'probe-target'\n"),
}


@pytest.fixture
def spine() -> SliceRunComposition:
    return SliceRunComposition()


@dataclass
class SliceRunComposition:
    """Drives the REAL ``des.cli.run_slice_ats`` executor over its ARGS protocol.

    DRIVING PORT (Mandate-13, Layer-3 subprocess): ``python -m des.cli.run_slice_ats``
    with ``--repo-root`` / ``--entering-slice``. The observable is the exit code
    (PASS=0 / FAIL=1 / INDETERMINATE != {0,1} / NOT_APPLICABLE=0) + the one JSON
    line on stdout.
    """

    _workspace: Path | None = None
    _entering_slice: str = _PROBE_SLICE
    _exit_code: int | None = None
    _stdout: str = ""
    _runner_explicitly_set: bool = False

    # ---- GIVEN: arm the tmp workspace + the entering slice's planted ATs -------

    def use_workspace(self, root: Path) -> None:
        """Arm a hermetic tmp workspace (no developer-home read anywhere)."""
        self._workspace = root
        (root / ".nwave" / "des").mkdir(parents=True, exist_ok=True)
        # Mark the tmp workspace as a developer checkout so the `des.cli`
        # freshness gate AUTOSKIPS instead of fail-closed exit 78 on the
        # manifest-less tmp tree, BEFORE the slice-AT gate runs. Harness wiring
        # only -- changes neither the args nor any asserted observable.
        seed_dev_checkout_marker(root)

    def given_target_runner(self, runner: TargetRunner) -> None:
        """Write the target manifest that makes resolve() pick this runner.

        ``ABSENT`` writes NO recognized lockfile (a bare workspace) so resolve()
        returns ``Indeterminate`` -- the degrade-LOUD path the gate maps to
        INDETERMINATE (slice-02, CT-4). Marks the runner as EXPLICITLY chosen so
        the AT-planting default (pytest) is NOT applied over a deliberate ABSENT.
        """
        assert self._workspace is not None
        self._runner_explicitly_set = True
        if runner is TargetRunner.ABSENT:
            return
        filename, content = _RUNNER_MANIFEST[runner]
        (self._workspace / filename).write_text(content, encoding="utf-8")

    def given_planted_slice_at(self, colour: SliceAtColour) -> None:
        """Plant a REAL ``@<slice>`` acceptance test (green or RED) into the workspace.

        A genuine, collectable slice AT under ``tests/<slice>/`` -- a real Gherkin
        scenario tagged ``@<entering_slice>`` and a pytest-bdd binding whose ``then``
        step asserts a true (green) or false (RED) behavior. The executor RUNS this
        planted suite; a RED one must make the gate VETO (FAIL). This is the
        precondition that distinguishes the RUN (slice-01) from the obsolete
        collect-only walk -- a RED AT must FAIL, not collect-green.
        """
        assert self._workspace is not None
        # The planted slice suite is a genuine pytest project. When the scenario
        # did NOT explicitly choose a target runner (slice-01: it never calls
        # `given_target_runner`), default the workspace to the pytest dogfood
        # target so `TestRunnerPort.resolve` (consulted FIRST by the executor)
        # recognizes it rather than degrading to INDETERMINATE. A scenario that
        # DID choose a runner (slice-02 CT-3/CT-4) owns the manifest state --
        # never overridden here, so a deliberate ABSENT stays ABSENT. Harness
        # wiring only; changes no asserted observable.
        if not self._runner_explicitly_set:
            (self._workspace / "pyproject.toml").write_text(
                "[project]\nname = 'probe-target'\n", encoding="utf-8"
            )
        slug = self._entering_slice.replace("-", "_")
        slice_dir = self._workspace / "tests" / slug
        slice_dir.mkdir(parents=True, exist_ok=True)
        (slice_dir / "__init__.py").write_text("", encoding="utf-8")
        (slice_dir / f"{slug}.feature").write_text(
            f"@feature-probe @{self._entering_slice}\n"
            "Feature: planted probe slice\n\n"
            f"  @{self._entering_slice}\n"
            "  Scenario: the planted slice behaves\n"
            "    Given a planted slice precondition\n"
            "    When the planted slice acts\n"
            "    Then the planted slice outcome holds\n",
            encoding="utf-8",
        )
        outcome = "0 == 0" if colour is SliceAtColour.GREEN else "0 == 1"
        (slice_dir / f"test_{slug}.py").write_text(
            "from pytest_bdd import given, when, then, scenarios\n\n"
            f'scenarios("{slug}.feature")\n\n\n'
            '@given("a planted slice precondition")\n'
            "def _given():\n    pass\n\n\n"
            '@when("the planted slice acts")\n'
            "def _when():\n    pass\n\n\n"
            '@then("the planted slice outcome holds")\n'
            f"def _then():\n    assert {outcome}\n",
            encoding="utf-8",
        )

    def given_no_planted_slice_at(self) -> None:
        """Arm a workspace with NO real ``.feature`` for the entering slice.

        slice-02 / CT-8 / DDD-8: the live gate must return NOT_APPLICABLE and NOT
        fabricate an always-green AT (no ``_materialize_representative_slice_at``
        on the live path). The workspace's ``tests/`` carries no slice ``.feature``.
        """
        assert self._workspace is not None
        (self._workspace / "tests").mkdir(parents=True, exist_ok=True)

    # ---- WHEN: drive the REAL executor (Layer-3 subprocess, hermetic) ----------

    def _run_executor(self) -> None:
        assert self._workspace is not None
        # Set the PYTHONPATH the subprocess passed via env= in-process (save/restore
        # in finally) so the executor's own child-worker pytest spawn resolves des
        # identically. The executor self-isolates pytest in a fresh child worker, so
        # driving its main(argv) in-process never nests pytest in this session.
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(REPO_ROOT)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                [
                    "--repo-root",
                    str(self._workspace),
                    "--entering-slice",
                    self._entering_slice,
                ],
                cwd=self._workspace,
                main=_run_slice_ats_main,
            )
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._exit_code = exit_code
        self._stdout = stdout + stderr

    def when_slice_gate_runs(self) -> None:
        """Drive the REAL spine slice-AT executor over its ARGS protocol."""
        self._run_executor()

    # ---- THEN: assert the observable exit-code effect --------------------------

    def _verdict_json(self) -> dict[str, object]:
        for line in self._stdout.splitlines():
            stripped = line.strip()
            if stripped.startswith("{") and "verdict" in stripped:
                try:
                    return json.loads(stripped)
                except json.JSONDecodeError:
                    continue
        return {}

    def then_verdict_is(self, verdict: SliceVerdict) -> None:
        """Assert the executor projected the expected verdict onto its exit code.

        Exit-code contract (DDD-6): PASS->0, FAIL->1, INDETERMINATE->!={0,1},
        NOT_APPLICABLE->0. At HEAD the module is ABSENT -> non-zero module-absent
        exit -> NEITHER 0 nor 1 in the shape the verdict requires -> semantic
        AssertionError (active-RED).
        """
        if verdict is SliceVerdict.PASS:
            assert self._exit_code == 0, (
                f"expected PASS (exit 0); got exit {self._exit_code}. "
                f"stdout/stderr:\n{self._stdout}"
            )
        elif verdict is SliceVerdict.FAIL:
            assert self._exit_code == 1, (
                f"expected FAIL (exit 1 -- the RED slice AT vetoes); got exit "
                f"{self._exit_code}. stdout/stderr:\n{self._stdout}"
            )
            # A bare module-absent `python -m` exit is ALSO 1 -- so exit-code
            # alone cannot discriminate a GENUINE veto from mere module-absence
            # (the fixture-theater trap). Require the FAIL verdict JSON: only a
            # real RUN of the RED slice AT emits it. At HEAD the executor module
            # is absent -> no JSON -> this RED-fails for the right reason
            # (active-RED), never a false-green via exit-1-on-absence.
            assert self._verdict_json().get("verdict") == "FAIL", (
                "expected the verdict JSON to name FAIL -- proving the spine "
                "genuinely RAN the RED slice AT and vetoed (not a collect-only "
                "pass, not a bare module-absent exit-1); got "
                f"{self._verdict_json()!r}. stdout/stderr:\n{self._stdout}"
            )
        elif verdict is SliceVerdict.NOT_APPLICABLE:
            assert self._exit_code == 0, (
                f"expected NOT_APPLICABLE (exit 0, no-real-AT); got exit "
                f"{self._exit_code}. stdout/stderr:\n{self._stdout}"
            )
            assert self._verdict_json().get("verdict") == "NOT_APPLICABLE", (
                "expected the verdict JSON to name NOT_APPLICABLE (the live gate "
                "did not fabricate an always-green AT); got "
                f"{self._verdict_json()!r}. stdout/stderr:\n{self._stdout}"
            )
        elif verdict is SliceVerdict.INDETERMINATE:
            assert self._exit_code not in (0, 1), (
                f"expected INDETERMINATE (exit != 0 and != 1, degrade-LOUD); got "
                f"exit {self._exit_code}. stdout/stderr:\n{self._stdout}"
            )

    def then_ran_only_entering_slice(self) -> None:
        """Assert the executor RAN only the entering slice's scoped node-ids.

        CT-1: ``ran_whole_tree`` False and ``out_of_slice_ran`` empty -- the
        acceleration (proportional, never the whole tree).
        """
        payload = self._verdict_json()
        assert payload.get("ran_whole_tree") is False, (
            "expected ran_whole_tree False (the slice gate runs ONLY the entering "
            f"slice, never the whole tree); got {payload!r}. stdout:\n{self._stdout}"
        )
        assert payload.get("out_of_slice_ran") in ([], (), None), (
            "expected no out-of-slice node-ids ran (scope is proportional); got "
            f"{payload!r}. stdout:\n{self._stdout}"
        )

    def then_runner_resolved_is(self, runner: TargetRunner) -> None:
        """Assert the RUN executed in the runner resolve() returned (CT-3).

        Not a hardcoded pytest -- the executor consulted ``TestRunnerPort.resolve``
        FIRST and ran in the resolved runner named on the verdict JSON.
        """
        payload = self._verdict_json()
        assert payload.get("runner") == runner.value, (
            f"expected the RUN to execute in the resolved runner {runner.value!r} "
            f"(resolve() consulted first, no hardcoded pytest); got {payload!r}. "
            f"stdout:\n{self._stdout}"
        )

    def then_degrade_loud_reason_named(self) -> None:
        """Assert the INDETERMINATE verdict NAMES a degrade-LOUD reason (CT-4).

        The unrecognized-runner reason must be on the verdict JSON / stdout -- a
        health.gate.* signal, never a silent pass and never a pytest fallback.
        """
        payload = self._verdict_json()
        reason = str(payload.get("reason", "")) + self._stdout
        assert "INDETERMINATE" in (str(payload.get("verdict", "")) + self._stdout), (
            "expected an INDETERMINATE verdict naming the unrecognized runner; got "
            f"{payload!r}. stdout:\n{self._stdout}"
        )
        assert ("runner" in reason.lower()) or ("pytest" in reason.lower()), (
            "expected the degrade-LOUD reason to name the runner-resolution failure "
            f"(never silent); got reason {reason!r}. stdout:\n{self._stdout}"
        )


# ---------------------------------------------------------------------------
# slice-03 composition root -- the shipped .pre-commit-config.yaml read as DATA.
#
# DRIVING SURFACE (Mandate-13, @contract-shape:pure-function): a config-shape
# assertion has no subprocess / composition entry -- the "port" IS the shipped
# `.pre-commit-config.yaml` at the repo root, read as the REAL artifact (never an
# inline test string -- the protocol-driver prose-surface case). The observable
# is the presence/absence of named hook ids at each git stage + the literal
# interim-marker phrase. No YAML business logic in step bodies; the composition
# reads the file once and exposes typed queries.
#
# ACTIVE-RED: at HEAD `.pre-commit-config.yaml` STILL carries `pytest-validation`
# at pre-commit AND carries NO interim marker on the pre-push full-suite. Each
# `then_*` assertion fails with a semantic AssertionError against the expected
# post-removal / marked state. GREEN once DELIVER removes the entry + adds the
# marker.
# ---------------------------------------------------------------------------

# The discriminating multi-word phrase the pre-push full-suite must carry once
# DELIVER lands DDD-4 (the interim marker). A discriminating phrase (not a
# substring of a common word) per the prose-surface protocol-driver rule.
_INTERIM_MARKER_PHRASE = "INTERIM safety net -- removable only when"

_PRE_COMMIT_CONFIG = REPO_ROOT / ".pre-commit-config.yaml"


@pytest.fixture
def precommit() -> PreCommitConfigComposition:
    return PreCommitConfigComposition()


@dataclass
class PreCommitConfigComposition:
    """Reads the shipped ``.pre-commit-config.yaml`` as DATA (slice-03).

    DRIVING SURFACE (Mandate-13, pure-function): the real shipped config at the
    repo root. The observable is which hook ids fire at which git stage + the
    literal interim-marker phrase in the config text.
    """

    _config_text: str = ""

    # ---- GIVEN ----------------------------------------------------------------

    def load_shipped_config(self) -> None:
        self._config_text = _PRE_COMMIT_CONFIG.read_text(encoding="utf-8")

    # ---- WHEN (no-op markers; the read already happened in GIVEN) --------------

    def inspect_commit_stage(self) -> None:
        """Marker step -- the config is the SSOT; staged-scoping is a query."""
        assert self._config_text, "config must be loaded before inspection"

    def inspect_push_stage(self) -> None:
        assert self._config_text, "config must be loaded before inspection"

    # ---- THEN -----------------------------------------------------------------

    def _hook_block(self, hook_id: str) -> str:
        """The text block of a named hook id (id line -> next id line / EOF).

        A read-only slice over the loaded config text -- never a YAML re-parse in
        the step body. Returns "" when the id is absent.
        """
        marker = f"- id: {hook_id}"
        start = self._config_text.find(marker)
        if start == -1:
            return ""
        rest = self._config_text[start + len(marker) :]
        next_id = rest.find("- id: ")
        return rest if next_id == -1 else rest[:next_id]

    def _stages_of(self, hook_id: str) -> str:
        """The ``stages: [...]`` line text for a named hook (or "")."""
        block = self._hook_block(hook_id)
        idx = block.find("stages:")
        if idx == -1:
            return ""
        return block[idx : block.find("\n", idx)]

    def then_commit_stage_hook_absent(self, hook_id: str) -> None:
        """Assert the named hook does NOT fire at pre-commit (CT-5).

        A hook fires at pre-commit if it is present AND (its ``stages`` includes
        pre-commit OR it declares no ``stages`` -- pre-commit is the default
        stage). The test hook must be removed from the commit stage.
        """
        block = self._hook_block(hook_id)
        if not block:
            return  # entirely removed -> not at pre-commit (the goal state)
        stages = self._stages_of(hook_id)
        fires_at_commit = ("pre-commit" in stages) or (stages == "")
        assert not fires_at_commit, (
            f"expected the {hook_id!r} test hook absent from the COMMIT stage "
            f"(the spine slice-AT gate is the commit-time test authority); it "
            f"still fires at pre-commit. stages line: {stages!r}"
        )

    def then_commit_stage_hook_present(self, hook_id: str) -> None:
        """Assert the named fast hook STILL fires at pre-commit (CT-5)."""
        block = self._hook_block(hook_id)
        assert block, f"expected the fast hook {hook_id!r} present; it is absent"
        stages = self._stages_of(hook_id)
        fires_at_commit = ("pre-commit" in stages) or (stages == "")
        assert fires_at_commit, (
            f"expected the fast hook {hook_id!r} to STILL fire at pre-commit "
            f"(it is not the slow test path -- it stays); stages line: {stages!r}"
        )

    def then_push_stage_hook_present(self, hook_id: str) -> None:
        """Assert the named full-suite hook STILL fires at pre-push (CT-6)."""
        block = self._hook_block(hook_id)
        assert block, (
            f"expected the pre-push full-suite hook {hook_id!r} present (the net "
            "is kept); it is absent"
        )
        stages = self._stages_of(hook_id)
        assert "pre-push" in stages, (
            f"expected {hook_id!r} to fire at pre-push (the interim net); stages "
            f"line: {stages!r}"
        )

    def then_interim_marker_present(self) -> None:
        """Assert the pre-push full-suite carries the explicit interim marker (CT-6).

        The marker is a discriminating multi-word phrase naming the removal
        precondition -- so the net cannot be silently dropped before certainty.
        At HEAD the config carries NO such phrase -> semantic AssertionError.
        """
        assert _INTERIM_MARKER_PHRASE in self._config_text, (
            "expected the pre-push full-suite to carry the explicit interim "
            f"removal marker {_INTERIM_MARKER_PHRASE!r} (DDD-4 -- the net is "
            "removable only when the feature-end certainty is proven); the "
            "shipped config carries no such marker."
        )


# ---------------------------------------------------------------------------
# slice-04 composition root -- the REAL feature-end full-suite leg (CT-7).
#
# DRIVING SURFACE (Mandate-13, Layer-3 subprocess): the feature-end full-suite
# leg invokes `python -m des.cli.run_contract_gate --repo <repo>` ONCE at
# feature-end (the RETAINED whole-tree run, owned by `_full_suite_marker_args`).
# We drive THAT real subprocess over a tmp repo whose planted contract suite is
# green vs RED, and assert the leg's observable: green -> exit 0 (the cycle would
# emit FullSuiteLegRan); PRESENT-but-RED -> exit != 0 (the cycle -> CycleRefusal,
# NO record -- anti-theater). The leg itself is REUSED from
# f-nonbypassable-attestation (already built); CT-7 pins the certainty contract
# the git-hook-removal is gated on, through the real entry point.
#
# HERMETIC: a tmp repo only. The planted contract test carries a `unit` marker
# (via `pytestmark`) so the full-suite marker expression
# (`unit or integration or acceptance`) collects + runs it.
# ---------------------------------------------------------------------------


@pytest.fixture
def feature_end() -> FeatureEndCertaintyComposition:
    return FeatureEndCertaintyComposition()


@dataclass
class FeatureEndCertaintyComposition:
    """Drives the REAL feature-end full-suite leg subprocess (slice-04, CT-7).

    DRIVING SURFACE (Mandate-13, Layer-3 subprocess): `python -m
    des.cli.run_contract_gate --repo <tmp>` -- the exact subprocess the
    feature-end cycle's full-suite leg invokes. observable = exit code
    (green->0 / red->!=0), the leg's emit-only-when-green contract.
    """

    _repo: Path | None = None
    _exit_code: int | None = None
    _stdout: str = ""

    # ---- GIVEN ----------------------------------------------------------------

    def _plant_marked_contract_test(self, colour: SliceAtColour) -> None:
        """Plant a `unit`-marked contract test (green or RED) in the tmp repo.

        The `pytestmark = pytest.mark.unit` makes the full-suite marker
        expression (`unit or integration or acceptance`) collect + run it, so the
        feature-end full-suite leg has a REAL suite whose colour it certifies.
        """
        assert self._repo is not None
        tests_dir = self._repo / "tests"
        tests_dir.mkdir(parents=True, exist_ok=True)
        (tests_dir / "__init__.py").write_text("", encoding="utf-8")
        # A local conftest registers the `unit` marker so the planted repo is a
        # self-contained pytest project (no dependence on the host conftest).
        (self._repo / "conftest.py").write_text(
            "def pytest_configure(config):\n"
            '    config.addinivalue_line("markers", "unit: unit tier")\n',
            encoding="utf-8",
        )
        (self._repo / "pyproject.toml").write_text(
            "[tool.pytest.ini_options]\ntestpaths = ['tests']\n",
            encoding="utf-8",
        )
        outcome = "0 == 0" if colour is SliceAtColour.GREEN else "0 == 1"
        (tests_dir / "test_planted_contract.py").write_text(
            "import pytest\n\n"
            "pytestmark = pytest.mark.unit\n\n\n"
            "def test_planted_contract():\n"
            f"    assert {outcome}\n",
            encoding="utf-8",
        )

    def given_full_suite(self, colour: SliceAtColour) -> None:
        """Arm a tmp repo whose full contract suite is green or RED.

        Seeds the tmp repo as a developer checkout (empty `.git/`) so the
        `des.cli` freshness gate AUTOSKIPS instead of fail-closed exit 78 ("no
        install manifest") BEFORE the full-suite leg runs -- otherwise the leg
        never reaches the planted suite and the RED is a setup failure, not the
        behavioral green/red-suite contract. Harness wiring only; changes no
        asserted observable.
        """
        import tempfile

        self._repo = Path(tempfile.mkdtemp(prefix="spine-ct7-"))
        seed_dev_checkout_marker(self._repo)
        self._plant_marked_contract_test(colour)

    # ---- WHEN -----------------------------------------------------------------

    def when_full_suite_leg_runs(self) -> None:
        """Drive the REAL full-suite leg in-process over the tmp repo.

        The gate self-isolates its pytest run in a fresh child worker (it never
        nests pytest.main() in the caller's session), so driving its main(argv)
        in-process is faithful to the subprocess boundary. PYTHONPATH is set
        in-process (save/restore in finally) to mirror the subprocess env=.
        """
        assert self._repo is not None
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(REPO_ROOT)
        try:
            exit_code, stdout, stderr = run_cli_in_process(
                ["--repo", str(self._repo)],
                cwd=self._repo,
                main=_run_contract_gate_main,
            )
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath
        self._exit_code = exit_code
        self._stdout = stdout + stderr

    # ---- THEN -----------------------------------------------------------------

    def then_full_suite_leg_attested(self) -> None:
        """Assert a green full suite is attested by the leg (exit 0 -> FullSuiteLegRan)."""
        assert self._exit_code == 0, (
            "expected the green feature-end full suite to pass (exit 0 -> the "
            "cycle emits FullSuiteLegRan); got exit "
            f"{self._exit_code}. stdout/stderr:\n{self._stdout}"
        )

    def then_cycle_refused_no_record(self) -> None:
        """Assert a RED full suite is refused (exit != 0 -> CycleRefusal, no record)."""
        assert self._exit_code not in (None, 0), (
            "expected the PRESENT-but-RED feature-end full suite to fail-close "
            "(exit != 0 -> the cycle refuses, NO FullSuiteLegRan record -- "
            f"anti-theater); got exit {self._exit_code}. stdout/stderr:\n"
            f"{self._stdout}"
        )
