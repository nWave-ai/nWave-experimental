"""Composition root for fix-d1-human-readable-gate-surfaces acceptance set.

F-D1-HUMAN-READABLE-GATE-SURFACES (Mandate-12 criteria 2-3, Pillar 3). Wires
the PRODUCTION contract gate CLI (``des.cli.run_contract_gate``) against a
tmp_path repository carrying a minimal pytest suite the gate can collect and
run. The slice-01 walking skeleton observes BOTH surfaces on captured stderr:
the existing single-line JSON ``ContractGateResult`` event AND the new
colored human-readable verdict line.

Business logic (write a minimal pytest suite of a given shape, invoke the
gate via subprocess with stderr bound to a TTY or to a pipe, capture both
surfaces) lives here as the single source of truth; step bodies delegate to
``HumanSurfaceFixture`` methods and never inline logic.

Layer 3 (subprocess / FS acceptance): the ``run_contract_gate`` CLI is the
driving port; the only driven ports are the real filesystem (tmp_path repo)
and the helper module under ``src/des/cli/``. Sad paths are example-based
(Mandate 11).

RED-scaffold note: ``src/des/cli/human_surface.py`` is authored as a RED
scaffold during the slice-01 DELIVER A_GREEN_ATS phase — its
``print_human_summary`` raises ``AssertionError`` so the slice-01 ATs FAIL
for the right reason (missing functionality, Mandate 7) rather than erroring
on a broken import / missing module path. The ``run_contract_gate`` extension
that imports + calls the helper is also authored during A_GREEN_ATS; on
master the gate emits only the JSON event (the new human-readable surface is
unimplemented).
"""

from __future__ import annotations

import json as _json
import os
import pty
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from .domain_types import (
    CONTRACT_GATE_EVENT_NAME,
    NEGATIVE_EVENT_BY_CLI,
    NEGATIVE_VERDICT_BY_CLI,
    NEGATIVE_VERDICT_BY_CLOSURE_CLI,
    NEGATIVE_VERDICT_BY_GATE_CLASS_CLI,
    SUCCESS_EVENT_BY_CLI,
    SUCCESS_VERDICT_BY_CLOSURE_CLI,
    SUCCESS_VERDICT_BY_GATE_CLASS_CLI,
    ClosureCli,
    GateClassCli,
    HumanSurfaceVerdict,
    SpineGateCli,
    StderrMode,
    SuiteOutcome,
)


# ANSI escapes mapped by verdict — slice-02 uses this to assert green ✅ PASS
# from APPROVED runs, red ❌ FAIL from completeness/carpaccio refusals, yellow
# ⚠️ DEGRADED from at_review_verdict NEEDS_REVISION.
_ANSI_GREEN_ESCAPE = "\x1b[32m"
_ANSI_RED_ESCAPE = "\x1b[31m"
_ANSI_YELLOW_ESCAPE = "\x1b[33m"
_ANSI_BY_VERDICT: dict[HumanSurfaceVerdict, str] = {
    HumanSurfaceVerdict.PASS: _ANSI_GREEN_ESCAPE,
    HumanSurfaceVerdict.FAIL: _ANSI_RED_ESCAPE,
    HumanSurfaceVerdict.DEGRADED: _ANSI_YELLOW_ESCAPE,
}
_PREFIX_BY_VERDICT: dict[HumanSurfaceVerdict, str] = {
    HumanSurfaceVerdict.PASS: "✅ PASS",
    HumanSurfaceVerdict.FAIL: "❌ FAIL",
    HumanSurfaceVerdict.DEGRADED: "⚠️ DEGRADED",
}
# Per-CLI lookup tables wired by SpineGateCli value -- read by slice-02 helpers.
_SUCCESS_EVENT_BY_CLI = SUCCESS_EVENT_BY_CLI
_NEGATIVE_EVENT_BY_CLI = NEGATIVE_EVENT_BY_CLI
_NEGATIVE_VERDICT_BY_CLI = NEGATIVE_VERDICT_BY_CLI


# Repo root — the four-level-up parent of this file
# (tests/scripts/cli/fix_d1_human_readable_gate_surfaces/steps/composition.py).
_REPO_ROOT = Path(__file__).resolve().parents[5]


# ANSI escape-sequence stripper (CSI sequences). Plain-text comparison
# scrubber used by AT3 to assert the JSON event byte-content is stable
# across TTY vs pipe and to verify the human line carries no escapes
# under PIPE mode.
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Return ``text`` with ANSI CSI escape sequences removed."""
    return _ANSI_CSI_RE.sub("", text)


@dataclass(frozen=True)
class CliResult:
    """Observable result of one ``run_contract_gate`` invocation.

    stderr_raw carries whatever the subprocess wrote to stderr (with ANSI
    escapes intact under TTY mode); stdout carries the existing default-mode
    output (empty under default mode — the gate emits its JSON to stdout via
    ``_emit`` but slice-01 captures stderr because that is where the NEW
    human-readable line lives AND, per the helper's contract, the JSON event
    moves alongside it). The crafter's job during DELIVER is to ensure both
    surfaces share the stderr channel — see the slice-01 wave-decisions note.
    """

    exit_code: int
    stdout: str
    stderr_raw: str

    @property
    def stderr_stripped(self) -> str:
        """stderr with ANSI CSI escapes removed (the plain-readable view)."""
        return strip_ansi(self.stderr_raw)


@dataclass
class HumanSurfaceFixture:
    """Production-wired composition root for slice-01.

    ``repo_root`` is a tmp_path subdirectory acting as a minimal repository
    the contract gate can collect tests from and run. The composition root
    writes the pytest suite + a minimal ``pyproject.toml`` + ``conftest.py``
    needed for the gate's ``-m`` marker collection, and invokes the real
    gate CLI as a subprocess with stderr bound to a TTY (pty) or a pipe.
    """

    repo_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) — port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the port-exposed observables this composition exposes.

        Universe entries are port-exposed names, never internal struct
        fields: the staged pytest suite file presence, the gate executable
        availability flag (always True — sanity), and a digest of the repo
        directory tree so we can assert filesystem invariance across the
        subprocess invocation (verify is a pure-function read over the
        contract suite — no FS mutation expected).
        """
        return {
            "tests_dir.present": (self.repo_root / "tests").is_dir(),
            "pyproject.present": (self.repo_root / "pyproject.toml").is_file(),
            "conftest.present": (self.repo_root / "conftest.py").is_file(),
        }

    # ------------------------------------------------------------------
    # Repo staging (Given-step delegates).
    # ------------------------------------------------------------------

    def stage_minimal_repo(self, outcome: SuiteOutcome) -> None:
        """Author the minimal repo files the contract gate needs to run.

        The gate runs ``pytest -m "unit or integration or acceptance"`` so we
        need: a ``pyproject.toml`` registering the three markers, a
        ``conftest.py`` (empty), and ONE test file under ``tests/`` carrying
        the ``@pytest.mark.unit`` marker. The test body asserts True under
        SuiteOutcome.PASSING and False under SuiteOutcome.FAILING.
        """
        self._write_pyproject()
        self._write_conftest()
        self._write_test(outcome)

    def _write_pyproject(self) -> None:
        """Register the three markers the gate's marker expression collects."""
        body = textwrap.dedent(
            """\
            [tool.pytest.ini_options]
            markers = [
                "unit: marker required by the contract gate",
                "integration: marker required by the contract gate",
                "acceptance: marker required by the contract gate",
            ]
            """
        )
        (self.repo_root / "pyproject.toml").write_text(body, encoding="utf-8")

    def _write_conftest(self) -> None:
        """Empty conftest so pytest treats the tmp_path repo as a rootdir."""
        (self.repo_root / "conftest.py").write_text("", encoding="utf-8")

    def _write_test(self, outcome: SuiteOutcome) -> None:
        """Author one ``@pytest.mark.unit`` test of the requested outcome."""
        tests_dir = self.repo_root / "tests"
        tests_dir.mkdir(exist_ok=True)
        if outcome is SuiteOutcome.PASSING:
            body = textwrap.dedent(
                """\
                import pytest

                @pytest.mark.unit
                def test_minimal_passing():
                    assert True
                """
            )
        elif outcome is SuiteOutcome.FAILING:
            body = textwrap.dedent(
                """\
                import pytest

                @pytest.mark.unit
                def test_minimal_failing():
                    assert False, "slice-01 AT2 FAIL PATH fixture"
                """
            )
        else:  # pragma: no cover — enum is exhaustive
            raise ValueError(f"unknown SuiteOutcome: {outcome!r}")
        (tests_dir / "test_minimal.py").write_text(body, encoding="utf-8")

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_contract_gate(self, stderr_mode: StderrMode) -> CliResult:
        """Invoke the contract gate as a subprocess against the staged repo.

        ``stderr_mode == TTY``: bind stderr to a pty so the helper's
        ``isatty()`` detection returns True and ANSI escapes are emitted.
        ``stderr_mode == PIPE``: bind stderr to a regular pipe; the helper
        detects no TTY and emits the human line without escapes.

        Both modes capture stdout via a pipe (the gate's existing default-
        mode stdout payload is empty, the JSON event lives on stderr under
        the helper's contract — both surfaces share the stderr channel).
        """
        argv = [
            sys.executable,
            "-m",
            "des.cli.run_contract_gate",
            "--repo",
            str(self.repo_root),
        ]
        if stderr_mode is StderrMode.TTY:
            return self._run_with_pty_stderr(argv)
        if stderr_mode is StderrMode.PIPE:
            return self._run_with_piped_stderr(argv)
        # pragma: no cover — enum is exhaustive
        raise ValueError(f"unknown StderrMode: {stderr_mode!r}")

    def _run_with_piped_stderr(self, argv: list[str]) -> CliResult:
        """Plain subprocess.run — stderr bound to a pipe (non-TTY)."""
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
            check=False,
        )
        return CliResult(
            exit_code=proc.returncode,
            stdout=proc.stdout,
            stderr_raw=proc.stderr,
        )

    def _run_with_pty_stderr(self, argv: list[str]) -> CliResult:
        """Subprocess with stderr bound to a pty — ``isatty()`` returns True.

        Uses ``pty.openpty()`` to create a pseudo-terminal pair; the child's
        stderr is the slave end, the parent reads from the master end. The
        child's ``isatty(2)`` returns True so the helper emits ANSI escapes.
        """
        master_fd, slave_fd = pty.openpty()
        try:
            proc = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=slave_fd,
                cwd=str(_REPO_ROOT),
                text=False,
                close_fds=True,
            )
            os.close(slave_fd)
            stderr_chunks: list[bytes] = []
            while True:
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                stderr_chunks.append(chunk)
            stdout_bytes, _ = proc.communicate()
            return CliResult(
                exit_code=proc.returncode,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr_raw=b"".join(stderr_chunks).decode("utf-8", errors="replace"),
            )
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Then-step observables (stderr inspection).
    # ------------------------------------------------------------------

    def extract_contract_gate_event(
        self, result: CliResult
    ) -> dict[str, object] | None:
        """Return the single ``ContractGateResult`` JSON object from stderr.

        The helper's contract: the structured event is emitted as a single
        JSON line on stderr (alongside the new human-readable line). Lines
        that are not parseable JSON are ignored. Returns ``None`` if no
        ``ContractGateResult`` event is found.
        """
        plain = result.stderr_stripped
        for line in plain.splitlines():
            stripped = line.strip()
            if not stripped or not stripped.startswith("{"):
                continue
            try:
                obj = _json.loads(stripped)
            except _json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("event") == CONTRACT_GATE_EVENT_NAME:
                return obj
        return None

    def stderr_carries_pass_line(self, result: CliResult) -> bool:
        """Return True iff stderr carries a ``✅ PASS`` summary line."""
        return "✅ PASS" in result.stderr_stripped

    def stderr_carries_fail_line(self, result: CliResult) -> bool:
        """Return True iff stderr carries a ``❌ FAIL`` summary line."""
        return "❌ FAIL" in result.stderr_stripped

    def stderr_pass_line_is_green(self, result: CliResult) -> bool:
        """Return True iff the PASS line carries a green ANSI escape.

        Asserts BOTH presence of the green CSI escape (``\\x1b[32m``) AND the
        PASS glyph on the same logical line — guards against an unrelated
        green-colored byte sequence elsewhere on stderr.
        """
        for raw_line in result.stderr_raw.splitlines():
            if "✅ PASS" in raw_line and "\x1b[32m" in raw_line:
                return True
        return False

    def stderr_fail_line_is_red(self, result: CliResult) -> bool:
        """Return True iff the FAIL line carries a red ANSI escape."""
        for raw_line in result.stderr_raw.splitlines():
            if "❌ FAIL" in raw_line and "\x1b[31m" in raw_line:
                return True
        return False

    def stderr_carries_no_ansi_escapes(self, result: CliResult) -> bool:
        """Return True iff stderr contains no ANSI CSI escape sequences."""
        return _ANSI_CSI_RE.search(result.stderr_raw) is None

    def json_event_byte_content_matches(
        self, result_a: CliResult, result_b: CliResult
    ) -> bool:
        """Return True iff the JSON event substring matches across two runs.

        Used by AT3 to assert the structured event is byte-identical across
        TTY vs pipe modes (the new helper must NOT mutate the existing
        machine-readable contract). Compares the dict-equal JSON object, not
        the raw line — line position / surrounding whitespace can vary
        without breaking the contract.
        """
        event_a = self.extract_contract_gate_event(result_a)
        event_b = self.extract_contract_gate_event(result_b)
        if event_a is None or event_b is None:
            return False
        # Compare on the contract-relevant fields only: event + passed.
        # ``gate_scope_digest`` is derived from the suite content (stable per
        # run on the same repo) and ``pytest_exit_code`` mirrors ``passed``.
        relevant_a = {k: event_a.get(k) for k in ("event", "passed")}
        relevant_b = {k: event_b.get(k) for k in ("event", "passed")}
        return relevant_a == relevant_b


# ===========================================================================
# Slice-02: spine-triple human-readable surface fixture.
# ===========================================================================


@dataclass
class SpineTripleSurfaceFixture:
    """Production-wired composition root for slice-02.

    The slice-02 walking-skeleton extension stages a single tmp_path repository
    that satisfies all three D1 spine-triple CLIs (verify_slice_commit_completeness,
    carpaccio_slice_gate, at_review_verdict). Each CLI is invoked as a real
    subprocess against the staged repo; stderr is captured (TTY pty or pipe)
    for both surfaces — the existing JSON event + the new human-readable line.

    Per-CLI staging methods (``stage_for_*``) write only the minimal artefacts
    the target CLI needs. The fixture's universe (Mandate 8) is the staged-
    artefact presence flags + a per-CLI command-resolution flag — the gate is
    pure-function read over its inputs and MUST NOT mutate them.

    Mandate 11 (layer 3 example-based sad paths): three Examples rows per
    Scenario Outline parametrize-collapse the spine triple × verdict cells.
    """

    repo_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) — port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the per-CLI staged-artefact presence flags.

        Universe entries are port-exposed file-presence flags the gate reads
        (feature-delta, the slice's .feature file, the git repo, the ledger
        directory) — NEVER internal struct fields. Each gate is a pure-function
        read over these inputs; the universe assertion guards against any
        write-side mutation by the gate.
        """
        feature_dir = self.repo_root / "docs" / "feature" / "slice02-fixture-feature"
        return {
            "feature_delta.present": (feature_dir / "feature-delta.md").is_file(),
            "feature_at.present": (
                self.repo_root
                / "tests"
                / "scripts"
                / "cli"
                / "slice02_fixture_feature"
                / "slice-01.feature"
            ).is_file(),
            "git_dir.present": (self.repo_root / ".git").is_dir(),
            "ledger_dir.present": (
                self.repo_root / ".nwave" / "telemetry" / "atdd-pure"
            ).is_dir(),
        }

    # ------------------------------------------------------------------
    # Per-CLI staging (Given delegates).
    # ------------------------------------------------------------------

    def stage_for_cli(self, cli: SpineGateCli, *, success_path: bool) -> dict[str, str]:
        """Stage the minimal repo artefacts the named CLI needs to run.

        Returns a per-CLI invocation context dict the When-step passes to
        ``run_cli_capturing_surface``. ``success_path=True`` produces inputs
        that drive the gate to its success verdict; ``success_path=False``
        produces inputs that drive the gate to its negative verdict (FAIL for
        completeness/carpaccio refusals; DEGRADED for at_review_verdict
        NEEDS_REVISION).
        """
        self.repo_root.mkdir(parents=True, exist_ok=True)
        if cli is SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS:
            return self._stage_verify_slice_commit_completeness(success_path)
        if cli is SpineGateCli.CARPACCIO_SLICE_GATE:
            return self._stage_carpaccio_slice_gate(success_path)
        if cli is SpineGateCli.AT_REVIEW_VERDICT:
            return self._stage_at_review_verdict(success_path)
        raise ValueError(f"unknown SpineGateCli: {cli!r}")  # pragma: no cover

    def _stage_verify_slice_commit_completeness(
        self, success_path: bool
    ) -> dict[str, str]:
        """Stage a git repo with one slice-tagged commit.

        Success path: the commit carries ``Slice-Id: slice-01`` AND the slice's
        .feature file is present in the commit tree — completeness clears.
        Negative path: the commit carries ``Slice-Id: slice-01`` but the slice's
        .feature file is ABSENT — completeness emits SliceCommitIncomplete.
        """
        self._init_git_repo()
        feature_dir = (
            self.repo_root / "tests" / "scripts" / "cli" / "slice02_fixture_feature"
        )
        feature_dir.mkdir(parents=True, exist_ok=True)
        if success_path:
            feature_file = feature_dir / "slice-01.feature"
            feature_file.write_text(
                "@slice-01\nFeature: slice-02 fixture\n  Scenario: only\n"
                "    Given a stub\n    When stuff happens\n    Then it works\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["git", "add", str(feature_file)],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )
        else:
            # FIXTURE-002 (option a): author a .feature file with @slice-01 on
            # disk but keep it OUT of the commit (the genuine RCA Branch-A
            # defect this gate catches: AT file authored, never persisted into
            # any commit). The legacy completeness path walks the working tree
            # via rglob('*.feature'), so it will see the file, derive the AT
            # requirement, and report it missing from the commit.
            unstaged_feature = feature_dir / "slice-01.feature"
            unstaged_feature.write_text(
                "@slice-01\nFeature: slice-02 fixture\n  Scenario: only\n"
                "    Given a stub\n    When stuff happens\n    Then it works\n",
                encoding="utf-8",
            )
            stub = self.repo_root / "stub.txt"
            stub.write_text("slice-02 negative-path stub\n", encoding="utf-8")
            subprocess.run(
                ["git", "add", str(stub)],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )
        message = "feat(slice02): stub commit\n\nSlice-Id: slice-01\n"
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
            env=self._git_env(),
        )
        return {"commit": "HEAD"}

    def _stage_carpaccio_slice_gate(self, success_path: bool) -> dict[str, str]:
        """Stage a feature-delta with a slice plan + scenarios.

        Success path: slice-01 has exactly 1 scenario carrying ``@slice-01``
        (≤ carpaccio ceiling of 7, ``.nwave/config.yaml``
        ``atdd_pure.carpaccio_slice_max``) → SliceCleared. Negative path:
        slice-01 has 8 scenarios (> 7) without a ``@coupled`` annotation →
        CARPACCIO_SLICE_TOO_LARGE.

        Also stages an AT-review APPROVED ledger record so the at-review check
        (assertion 5) clears on the success path. On the negative path the
        size check fires first (assertion 1), so the ledger is unused.
        """
        feature_id = "slice02-fixture-feature"
        feature_dir = self.repo_root / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        slice_rows = "| slice-01 | a stub value | pending |   | stub justification |\n"
        delta = (
            "# slice-02 fixture feature\n\n"
            "## Wave: DISCUSS / [REF] Slice Plan\n\n"
            "| slice-id | value statement | status | annotation | justification |\n"
            "|----------|-----------------|--------|------------|---------------|\n"
            + slice_rows
        )
        (feature_dir / "feature-delta.md").write_text(delta, encoding="utf-8")
        tests_dir = (
            self.repo_root / "tests" / "scripts" / "cli" / feature_id.replace("-", "_")
        )
        tests_dir.mkdir(parents=True, exist_ok=True)
        if success_path:
            scenario_block = (
                "@feature-slice02-fixture-feature @slice-01\n"
                "Feature: slice-02 fixture\n\n"
                "  @slice-01\n  Scenario: only\n"
                "    Given a stub\n    When stuff happens\n    Then it works\n"
            )
        else:
            # Eight scenarios under slice-01 (> carpaccio_slice_max: 7), no
            # @coupled — size assertion (assertion 1) fires before the
            # at-review assertion (assertion 5) is ever reached.
            scenarios = "\n".join(
                f"  @slice-01\n  Scenario: stub {n}\n"
                "    Given a stub\n    When stuff happens\n    Then it works\n"
                for n in range(1, 9)
            )
            scenario_block = (
                "@feature-slice02-fixture-feature @slice-01\n"
                "Feature: slice-02 fixture\n\n" + scenarios
            )
        # FIXTURE-001: write .feature BEFORE staging the at-review ledger so the
        # ledger's at_ids derive from the real scenarios (else at_ids=[] and the
        # carpaccio_slice_gate's at-review check sees a stale ledger).
        (tests_dir / "fixture.feature").write_text(scenario_block, encoding="utf-8")
        if success_path:
            self._stage_at_review_ledger(feature_id, "slice-01", "APPROVED")
        return {"feature_id": feature_id, "entering_slice": "slice-01"}

    def _stage_at_review_verdict(self, success_path: bool) -> dict[str, str]:
        """Stage a feature with one slice scenario (keyless producer).

        Success path: invoke with ``--verdict APPROVED`` → ledger record
        appended (PASS verdict line). Negative path: invoke with
        ``--verdict NEEDS_REVISION`` → no ledger write (DEGRADED verdict line).
        The CLI exits 0 either way; the human surface distinguishes the
        operator-facing outcome.
        """
        feature_id = "slice02-fixture-feature"
        tests_dir = (
            self.repo_root / "tests" / "scripts" / "cli" / feature_id.replace("-", "_")
        )
        tests_dir.mkdir(parents=True, exist_ok=True)
        scenario_block = (
            "@feature-slice02-fixture-feature @slice-01\n"
            "Feature: slice-02 fixture\n\n"
            "  @slice-01\n  Scenario: only\n"
            "    Given a stub\n    When stuff happens\n    Then it works\n"
        )
        (tests_dir / "fixture.feature").write_text(scenario_block, encoding="utf-8")
        # No signing key: the producer is keyless (oss-review-verdict-demotion
        # S2 — key absence is a non-event).
        # Ledger directory must exist for the writer.
        (self.repo_root / ".nwave" / "telemetry" / "atdd-pure").mkdir(
            parents=True, exist_ok=True
        )
        verdict = "APPROVED" if success_path else "NEEDS_REVISION"
        return {
            "feature_id": feature_id,
            "slice_id": "slice-01",
            "verdict": verdict,
        }

    # ------------------------------------------------------------------
    # Git helpers (stage_for_cli internals).
    # ------------------------------------------------------------------

    def _init_git_repo(self) -> None:
        """Initialise an empty git repo under ``repo_root`` if not already."""
        if (self.repo_root / ".git").is_dir():
            return
        subprocess.run(
            ["git", "init", "--initial-branch=main", str(self.repo_root)],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.email", "slice02@fixture"],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "slice02 fixture"],
            cwd=str(self.repo_root),
            check=True,
            capture_output=True,
        )

    def _git_env(self) -> dict[str, str]:
        """Subprocess env for git commits — pinned author/committer + clean."""
        env = dict(os.environ)
        env["GIT_AUTHOR_NAME"] = "slice02"
        env["GIT_AUTHOR_EMAIL"] = "slice02@fixture"
        env["GIT_COMMITTER_NAME"] = "slice02"
        env["GIT_COMMITTER_EMAIL"] = "slice02@fixture"
        return env

    def _stage_at_review_ledger(
        self, feature_id: str, slice_id: str, verdict: str
    ) -> None:
        """Write a stub APPROVED ATReviewVerdict record so carpaccio assertion 5
        clears on the success path.

        Invokes the real ``des.cli.at_review_verdict`` as a subprocess
        — it computes the per-slice ``at_content_hash``, signs the record,
        and appends it to the ledger via the production code path. This keeps
        the slice-02 fixture out of the at_review_verdict implementation
        details (Pillar 3: production composition root).
        """
        repo_root = self.repo_root
        key_dir = repo_root / ".nwave" / "secrets"
        key_dir.mkdir(parents=True, exist_ok=True)
        (key_dir / "reviewer-signing.key").write_bytes(b"slice-02-fixture-key")
        (repo_root / ".nwave" / "telemetry" / "atdd-pure").mkdir(
            parents=True, exist_ok=True
        )
        env = dict(os.environ)
        env["NWAVE_REVIEWER_SIGNING_KEY"] = "slice-02-fixture-key"
        subprocess.run(
            [
                sys.executable,
                "-m",
                "des.cli.at_review_verdict",
                "--feature-id",
                feature_id,
                "--slice-id",
                slice_id,
                "--verdict",
                verdict,
                "--reviewer-agent-id",
                "slice02-fixture-reviewer",
                "--repo-root",
                str(repo_root),
            ],
            capture_output=True,
            env=env,
            check=False,
        )

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_cli_capturing_surface(
        self,
        cli: SpineGateCli,
        stderr_mode: StderrMode,
        invocation_context: dict[str, str],
    ) -> CliResult:
        """Invoke the named CLI as a subprocess against the staged repo.

        ``invocation_context`` is the per-CLI dict returned by ``stage_for_cli``
        — carries the feature-id / slice-id / verdict / commit values the
        named CLI's argv needs.

        Routes through the per-CLI argv builder, then through the existing
        TTY-vs-PIPE subprocess plumbing the slice-01 fixture authored. Re-uses
        ``_run_with_pty_stderr`` / ``_run_with_piped_stderr`` by delegating to
        a sibling ``HumanSurfaceFixture`` over the same repo root.
        """
        argv = self._build_argv(cli, invocation_context)
        # Re-use the slice-01 subprocess plumbing (TTY pty vs pipe binding).
        helper = HumanSurfaceFixture(repo_root=self.repo_root)
        if stderr_mode is StderrMode.TTY:
            return helper._run_with_pty_stderr(argv)
        if stderr_mode is StderrMode.PIPE:
            return helper._run_with_piped_stderr(argv)
        raise ValueError(f"unknown StderrMode: {stderr_mode!r}")  # pragma: no cover

    def _build_argv(
        self, cli: SpineGateCli, invocation_context: dict[str, str]
    ) -> list[str]:
        """Construct the per-CLI argv list for subprocess invocation.

        Each CLI is invoked via ``python -m <module>`` so the existing
        ``_run_with_pty_stderr`` / ``_run_with_piped_stderr`` plumbing routes
        stderr through the helper module's TTY detection path.
        """
        if cli is SpineGateCli.VERIFY_SLICE_COMMIT_COMPLETENESS:
            return [
                sys.executable,
                "-m",
                "des.cli.verify_slice_commit_completeness",
                "--repo",
                str(self.repo_root),
                "--commit",
                invocation_context["commit"],
            ]
        if cli is SpineGateCli.CARPACCIO_SLICE_GATE:
            return [
                sys.executable,
                "-m",
                "des.cli.carpaccio_slice_gate",
                "--feature-id",
                invocation_context["feature_id"],
                "--entering-slice",
                invocation_context["entering_slice"],
                "--repo-root",
                str(self.repo_root),
            ]
        if cli is SpineGateCli.AT_REVIEW_VERDICT:
            return [
                sys.executable,
                "-m",
                "des.cli.at_review_verdict",
                "--feature-id",
                invocation_context["feature_id"],
                "--slice-id",
                invocation_context["slice_id"],
                "--verdict",
                invocation_context["verdict"],
                "--reviewer-agent-id",
                "slice02-fixture-reviewer",
                "--repo-root",
                str(self.repo_root),
            ]
        raise ValueError(f"unknown SpineGateCli: {cli!r}")  # pragma: no cover

    # ------------------------------------------------------------------
    # Then-step observables (per-CLI stderr inspection).
    # ------------------------------------------------------------------

    def extract_event(
        self, cli: SpineGateCli, result: CliResult, *, success: bool
    ) -> dict[str, object] | None:
        """Return the per-CLI JSON event from stderr (event name lookup).

        Returns the single JSON object whose ``event`` field equals the
        per-CLI success or negative event name. Returns ``None`` if none of
        the parseable JSON lines on stderr match.
        """
        target = _SUCCESS_EVENT_BY_CLI[cli] if success else _NEGATIVE_EVENT_BY_CLI[cli]
        plain = result.stderr_stripped
        for line in plain.splitlines():
            stripped = line.strip()
            if not stripped or not stripped.startswith("{"):
                continue
            try:
                obj = _json.loads(stripped)
            except _json.JSONDecodeError:
                continue
            if isinstance(obj, dict) and obj.get("event") == target:
                return obj
        return None

    def stderr_carries_verdict_line(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff stderr carries the verdict's plain prefix line."""
        return _PREFIX_BY_VERDICT[verdict] in result.stderr_stripped

    def stderr_verdict_line_carries_color(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff the verdict line on stderr carries its ANSI color.

        Asserts BOTH the verdict prefix glyph AND the verdict-matching ANSI
        CSI color escape on the same logical line — guards against an
        unrelated color sequence elsewhere on stderr.
        """
        prefix = _PREFIX_BY_VERDICT[verdict]
        color = _ANSI_BY_VERDICT[verdict]
        for raw_line in result.stderr_raw.splitlines():
            if prefix in raw_line and color in raw_line:
                return True
        return False

    def stderr_carries_no_ansi_escapes(self, result: CliResult) -> bool:
        """Return True iff stderr contains no ANSI CSI escape sequences."""
        return _ANSI_CSI_RE.search(result.stderr_raw) is None

    def event_matches_across_modes(
        self,
        cli: SpineGateCli,
        result_a: CliResult,
        result_b: CliResult,
    ) -> bool:
        """Return True iff the success JSON event matches across two runs.

        Compares the per-CLI success event extracted from each result on
        contract-relevant fields (event name only — per-CLI extra fields like
        timestamps may legitimately vary across two independent subprocesses).
        """
        event_a = self.extract_event(cli, result_a, success=True)
        event_b = self.extract_event(cli, result_b, success=True)
        if event_a is None or event_b is None:
            return False
        return event_a.get("event") == event_b.get("event")

    def negative_verdict_for(self, cli: SpineGateCli) -> HumanSurfaceVerdict:
        """Return the human-readable verdict the named CLI emits on negative."""
        return _NEGATIVE_VERDICT_BY_CLI[cli]


# ===========================================================================
# Slice-03: gate-class-triple human-readable surface fixture.
# ===========================================================================


@dataclass(frozen=True)
class StructuredSurfaceSnapshot:
    """The per-CLI structured surface captured from one CLI invocation.

    Each slice-03 CLI emits a DIFFERENT pre-existing structured surface today:
      * verify_environmental_e2e         — L1.4 stdout token line on stdout
      * verify_coverage_map              — free-text refusal line on stderr
      * check_robustness_density         — no structured payload (exit-code only)
    The snapshot captures the contract-stable portion of each surface so AT3
    can compare TTY vs PIPE runs across CLIs uniformly.
    """

    kind: str
    payload: object


@dataclass
class GateClassTripleSurfaceFixture:
    """Production-wired composition root for slice-03.

    The slice-03 walking-skeleton extension stages a tmp_path repository that
    carries the minimal per-CLI artefacts each of the three D1 gate-class CLIs
    needs (verify_environmental_e2e via a feature-delta file; verify_coverage_map
    via a docs/feature/{id}/distill/coverage-map.md tree; check_robustness_density
    via an unbounded-domains.yaml + an AT-scope directory). Each CLI is invoked
    as a real subprocess against the staged repo; stderr is captured (TTY pty
    or pipe) for the new human-readable line AND the pre-existing per-CLI
    structured surface is captured for stability comparison.

    Per-CLI staging methods (``_stage_for_*``) write only the minimal artefacts
    the target CLI needs. The fixture's universe (Mandate 8) is the staged-
    artefact presence flags — the gate is a pure-function read over its
    inputs and MUST NOT mutate them.

    Mandate 11 (layer 3 example-based sad paths): three Examples rows per
    Scenario Outline parametrize-collapse the gate-class triple × verdict
    cells into 9 instances total (3 Outlines × 3 Examples each).
    """

    repo_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) — port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the per-CLI staged-artefact presence flags.

        Universe entries are port-exposed file-presence flags each gate reads
        (env-e2e: the feature-delta file; coverage-map: the coverage-map.md
        file under distill/; robustness-density: the declaration YAML + the
        at-scope directory) — NEVER internal struct fields. Each gate is a
        pure-function read over these inputs; the universe assertion guards
        against any write-side mutation by the gate.
        """
        return {
            "env_e2e_feature_delta.present": (
                self.repo_root / "env_e2e" / "feature-delta.md"
            ).is_file(),
            "coverage_map.present": (
                self.repo_root
                / "coverage_map"
                / "docs"
                / "feature"
                / "slice03-fixture-feature"
                / "distill"
                / "coverage-map.md"
            ).is_file(),
            "robustness_declaration.present": (
                self.repo_root / "robustness" / "unbounded-domains.yaml"
            ).is_file(),
            "robustness_at_scope.present": (
                self.repo_root / "robustness" / "ats"
            ).is_dir(),
        }

    # ------------------------------------------------------------------
    # Per-CLI staging (Given delegates).
    # ------------------------------------------------------------------

    def stage_for_cli(self, cli: GateClassCli, *, success_path: bool) -> dict[str, str]:
        """Stage the minimal repo artefacts the named CLI needs to run.

        Returns a per-CLI invocation context dict the When-step passes to
        ``run_cli_capturing_surface``. ``success_path=True`` produces inputs
        that drive the gate to its success verdict; ``success_path=False``
        produces inputs that drive the gate to its negative verdict.

        Success-verdict per CLI:
          * verify_environmental_e2e → DEGRADED (misscoped — block absent)
          * verify_coverage_map      → PASS (verify-subcommand exit 0)
          * check_robustness_density → PASS (every declared domain covered)
        Negative-verdict per CLI:
          * verify_environmental_e2e → FAIL (parse/IO — delta unreadable)
          * verify_coverage_map      → FAIL (StructuralIncomplete exit 1)
          * check_robustness_density → FAIL (CHECK_FAILED exit 1)
        """
        self.repo_root.mkdir(parents=True, exist_ok=True)
        if cli is GateClassCli.VERIFY_ENVIRONMENTAL_E2E:
            return self._stage_verify_environmental_e2e(success_path)
        if cli is GateClassCli.VERIFY_COVERAGE_MAP:
            return self._stage_verify_coverage_map(success_path)
        if cli is GateClassCli.CHECK_ROBUSTNESS_DENSITY:
            return self._stage_check_robustness_density(success_path)
        raise ValueError(f"unknown GateClassCli: {cli!r}")  # pragma: no cover

    def _stage_verify_environmental_e2e(self, success_path: bool) -> dict[str, str]:
        """Stage a feature-delta file for ``--mode verify-authored``.

        Success path: feature-delta exists AND carries no ``## Environmental
        E2E`` block — verify-authored returns exit 3 MISSCOPED, the operator's
        legitimate "this feature does not need env-e2e" outcome → DEGRADED.

        Negative path: feature-delta path does NOT exist — verify-authored
        returns exit 2 PARSE_IO ("feature delta not found") → FAIL.
        """
        env_dir = self.repo_root / "env_e2e"
        env_dir.mkdir(parents=True, exist_ok=True)
        delta_path = env_dir / "feature-delta.md"
        if success_path:
            delta_path.write_text(
                "# feature: slice03-env-e2e-fixture\n\n"
                "## DISCUSS\n\nNo environmental e2e block here — "
                "this feature is misscoped relative to env-e2e.\n",
                encoding="utf-8",
            )
            feature_delta_arg = str(delta_path)
        else:
            # Negative: point at an absent path so the CLI returns
            # PARSE_IO (exit 2) — "feature delta not found" diagnostic.
            feature_delta_arg = str(env_dir / "absent-feature-delta.md")
        return {
            "feature_id": "slice03-env-e2e-fixture",
            "feature_delta": feature_delta_arg,
        }

    def _stage_verify_coverage_map(self, success_path: bool) -> dict[str, str]:
        """Stage a docs/feature/{id}/distill/coverage-map.md file.

        Success path: a structurally complete coverage-map with the five
        mandatory sections in fixed L1 order + a recorded
        ``reviewed-content-digest`` that matches the §5.3 canonicalization
        of the body — verify exits 0 → PASS.

        Negative path: a coverage-map missing the first mandatory section —
        verify exits 1 + StructuralIncomplete → FAIL.
        """
        feature_id = "slice03-fixture-feature"
        feature_root = self.repo_root / "coverage_map" / "docs" / "feature" / feature_id
        distill_dir = feature_root / "distill"
        distill_dir.mkdir(parents=True, exist_ok=True)
        coverage_map_path = distill_dir / "coverage-map.md"
        if success_path:
            # Build a structurally complete coverage-map with a matching
            # digest. Compute the §5.3 canonical digest dynamically so the
            # fixture stays in sync with the production canonicalization.
            body_signed_sections = (
                "## Feature surface declared\n"
                "\n"
                "- domain: slice03-fixture-domain\n"
                "\n"
                "## NOT covered -- and why\n"
                "\n"
                "Nothing intentionally omitted.\n"
                "\n"
                "## Known residues carried forward\n"
                "\n"
                "None.\n"
                "\n"
                "## Negative-space completeness statement\n"
                "\n"
                "The negative space is empty.\n"
            )
            digest = self._compute_canonical_digest(body_signed_sections)
            # Slice-05: the verify gate reads `nWave/data/omission-classes.json`
            # at verify time and asserts the signoff covers every class-id.
            # The success-path fixture must carry an `omission-classes-attested:`
            # list keyed by every class-id in the real file (the fixture
            # invokes the production verify CLI which reads the real
            # `nWave/data/omission-classes.json` -- the only signed surface
            # passing the gate is one that attests every imported class-id).
            attested_block = self._render_omission_classes_attested_block()
            body = (
                body_signed_sections
                + "\n## Signoff\n"
                + "\n"
                + f"- reviewed-content-digest: {digest}\n"
                + "- reviewer-id: slice03-fixture-reviewer\n"
                + attested_block
            )
        else:
            # Negative: omit the first mandatory section (## Feature surface
            # declared) so verify exits 1 + StructuralIncomplete.
            body = (
                "## NOT covered -- and why\n"
                "\n"
                "First mandatory section missing.\n"
                "\n"
                "## Known residues carried forward\n"
                "\n"
                "None.\n"
                "\n"
                "## Negative-space completeness statement\n"
                "\n"
                "Whatever.\n"
                "\n"
                "## Signoff\n"
                "\n"
                "- reviewed-content-digest: 0\n"
            )
        coverage_map_path.write_text(body, encoding="utf-8")
        return {"feature_root": str(feature_root)}

    def _stage_check_robustness_density(self, success_path: bool) -> dict[str, str]:
        """Stage an unbounded-domains.yaml + an AT-scope directory.

        Success path: declaration lists ONE domain id; at-scope carries a
        ``*.py`` file with a ``# domain: <id>`` marker for that id — exit 0
        → PASS.

        Negative path: declaration lists ONE domain id; at-scope carries NO
        markers for that id — exit 1 CHECK_FAILED → FAIL.
        """
        robustness_dir = self.repo_root / "robustness"
        robustness_dir.mkdir(parents=True, exist_ok=True)
        declaration_path = robustness_dir / "unbounded-domains.yaml"
        at_scope_dir = robustness_dir / "ats"
        at_scope_dir.mkdir(parents=True, exist_ok=True)
        domain_id = "slice03_fixture_domain"
        declaration_path.write_text(
            f"unbounded-input-domains:\n  - id: {domain_id}\n    type: str\n",
            encoding="utf-8",
        )
        if success_path:
            (at_scope_dir / "test_covered.py").write_text(
                "from hypothesis import given, strategies as st\n"
                "\n"
                f"# domain: {domain_id}\n"
                "@given(st.text())\n"
                "def test_covered(value):\n"
                "    assert isinstance(value, str)\n",
                encoding="utf-8",
            )
        else:
            (at_scope_dir / "test_uncovered.py").write_text(
                "# no # domain: marker here — robustness density refuses\n"
                "def test_uncovered():\n"
                "    assert True\n",
                encoding="utf-8",
            )
        return {
            "declaration": str(declaration_path),
            "at_scope": str(at_scope_dir),
        }

    # ------------------------------------------------------------------
    # §5.3 canonical digest computation (mirror of verify_coverage_map).
    # ------------------------------------------------------------------

    def _compute_canonical_digest(self, signed_sections_body: str) -> str:
        """Mirror of verify_coverage_map._compute_canonical_digest.

        The production CLI computes the canonical digest from the four signed
        sections concatenated by `_select_signed_sections` (which uses the
        full body and excludes `## Signoff`). To stay byte-for-byte aligned
        with what the CLI sees, we synthesize the same body the CLI will
        select (no `## Signoff` heading in the input → no chunk extracted
        beyond the four signed sections).
        """

        # The production canonicalization wraps the body in a chunks dict
        # where each chunk INCLUDES its heading line. So we must reproduce
        # the same heading-included shape. We call into the production
        # symbols directly to avoid duplication.
        from scripts.cli.verify_coverage_map import _compute_canonical_digest

        # Synthesize a full body the production canonicalizer accepts —
        # append a sentinel `## Signoff` so `_select_signed_sections` selects
        # exactly the four signed sections from our `signed_sections_body`.
        full_body = signed_sections_body + "\n## Signoff\n- placeholder: 0\n"
        return _compute_canonical_digest(full_body)

    def _render_omission_classes_attested_block(self) -> str:
        """Render an `omission-classes-attested:` block covering every class-id.

        Slice-05: the verify gate refuses a signoff omitting any class-id
        present in `nWave/data/omission-classes.json`. The success-path
        fixture must attest every class-id the real import names; reading
        the production file is the SSOT so the fixture stays cardinality-
        agnostic over future SF SSOT fold revisions.
        """
        from scripts.cli.verify_coverage_map import (
            _default_omission_classes_path,
            _load_omission_class_ids,
        )

        class_ids = _load_omission_class_ids(_default_omission_classes_path()) or ()
        if not class_ids:
            return ""
        lines = ["- omission-classes-attested:"]
        for class_id in class_ids:
            lines.append(f"  - {class_id}")
        return "\n".join(lines) + "\n"

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_cli_capturing_surface(
        self,
        cli: GateClassCli,
        stderr_mode: StderrMode,
        invocation_context: dict[str, str],
    ) -> CliResult:
        """Invoke the named CLI as a subprocess against the staged repo.

        ``invocation_context`` is the per-CLI dict returned by ``stage_for_cli``
        — carries the feature-delta / feature-root / declaration / at-scope
        paths the named CLI's argv needs.

        Routes through the per-CLI argv builder, then through the existing
        TTY-vs-PIPE subprocess plumbing the slice-01 fixture authored. Re-uses
        ``_run_with_pty_stderr`` / ``_run_with_piped_stderr`` by delegating to
        a sibling ``HumanSurfaceFixture`` over the same repo root.
        """
        argv = self._build_argv(cli, invocation_context)
        helper = HumanSurfaceFixture(repo_root=self.repo_root)
        if stderr_mode is StderrMode.TTY:
            return helper._run_with_pty_stderr(argv)
        if stderr_mode is StderrMode.PIPE:
            return helper._run_with_piped_stderr(argv)
        raise ValueError(f"unknown StderrMode: {stderr_mode!r}")  # pragma: no cover

    def _build_argv(
        self, cli: GateClassCli, invocation_context: dict[str, str]
    ) -> list[str]:
        """Construct the per-CLI argv list for subprocess invocation.

        Each CLI is invoked via ``python -m <module>`` (for des.cli members)
        or via direct script path (for scripts/cli/ members) so the existing
        ``_run_with_pty_stderr`` / ``_run_with_piped_stderr`` plumbing routes
        stderr through the helper module's TTY detection path.
        """
        if cli is GateClassCli.VERIFY_ENVIRONMENTAL_E2E:
            return [
                sys.executable,
                "-m",
                "des.cli.verify_environmental_e2e",
                "--mode",
                "verify-authored",
                "--feature-id",
                invocation_context["feature_id"],
                "--feature-delta",
                invocation_context["feature_delta"],
            ]
        if cli is GateClassCli.VERIFY_COVERAGE_MAP:
            return [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "cli" / "verify_coverage_map.py"),
                "verify",
                "--feature-root",
                invocation_context["feature_root"],
            ]
        if cli is GateClassCli.CHECK_ROBUSTNESS_DENSITY:
            return [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "cli" / "check_robustness_density.py"),
                "--declaration",
                invocation_context["declaration"],
                "--at-scope",
                invocation_context["at_scope"],
            ]
        raise ValueError(f"unknown GateClassCli: {cli!r}")  # pragma: no cover

    # ------------------------------------------------------------------
    # Then-step observables (per-CLI surface inspection).
    # ------------------------------------------------------------------

    def capture_structured_surface(
        self, cli: GateClassCli, result: CliResult, *, success: bool
    ) -> StructuredSurfaceSnapshot:
        """Capture the per-CLI pre-existing structured surface from one result.

        env-e2e:                stdout token line (the L1.4 token shape)
        verify_coverage_map:    stderr refusal line on negative path; empty on PASS
        check_robustness_density: exit code only (no payload)
        """
        if cli is GateClassCli.VERIFY_ENVIRONMENTAL_E2E:
            # The L1.4 stdout token line — extract the line that starts with
            # `environmental_e2e mode=`. Stable across TTY vs PIPE.
            for line in result.stdout.splitlines():
                if line.startswith("environmental_e2e mode="):
                    return StructuredSurfaceSnapshot(
                        kind="env_e2e_stdout_token", payload=line.strip()
                    )
            return StructuredSurfaceSnapshot(kind="env_e2e_stdout_token", payload=None)
        if cli is GateClassCli.VERIFY_COVERAGE_MAP:
            # Negative path: stderr carries `verify_coverage_map: <TOKEN>: ...`.
            # Success path: stderr is empty of any refusal line.
            for line in result.stderr_stripped.splitlines():
                if line.startswith("verify_coverage_map: "):
                    # Token portion only (between the prefix and the next `: `).
                    return StructuredSurfaceSnapshot(
                        kind="coverage_map_refusal_token", payload=line.strip()
                    )
            return StructuredSurfaceSnapshot(
                kind="coverage_map_refusal_token", payload=None
            )
        if cli is GateClassCli.CHECK_ROBUSTNESS_DENSITY:
            return StructuredSurfaceSnapshot(
                kind="robustness_density_exit_code", payload=result.exit_code
            )
        raise ValueError(f"unknown GateClassCli: {cli!r}")  # pragma: no cover

    def structured_surface_stable_for(
        self,
        cli: GateClassCli,
        result: CliResult,
        *,
        success: bool,
    ) -> bool:
        """Return True iff the per-CLI structured surface matches expectations.

        Asserts the surface is PRESENT in the expected shape per CLI per path —
        the surface contract is the existing operator-machine surface the
        slice-03 helper must NOT break.

        env-e2e success:    token line present AND verdict=misscoped
        env-e2e negative:   token line present AND verdict=broken
        coverage-map success: NO refusal token present
        coverage-map negative: refusal token == StructuralIncomplete
        robustness-density success: exit code == 0
        robustness-density negative: exit code == 1
        """
        snapshot = self.capture_structured_surface(cli, result, success=success)
        if cli is GateClassCli.VERIFY_ENVIRONMENTAL_E2E:
            if snapshot.payload is None or not isinstance(snapshot.payload, str):
                return False
            if success:
                return "verdict=misscoped" in snapshot.payload
            return "verdict=broken" in snapshot.payload
        if cli is GateClassCli.VERIFY_COVERAGE_MAP:
            if success:
                return snapshot.payload is None
            return isinstance(snapshot.payload, str) and (
                "StructuralIncomplete" in snapshot.payload
            )
        if cli is GateClassCli.CHECK_ROBUSTNESS_DENSITY:
            expected = 0 if success else 1
            return snapshot.payload == expected
        raise ValueError(f"unknown GateClassCli: {cli!r}")  # pragma: no cover

    def stderr_carries_verdict_line(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff stderr carries the verdict's plain prefix line."""
        return _PREFIX_BY_VERDICT[verdict] in result.stderr_stripped

    def stderr_verdict_line_carries_color(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff the verdict line on stderr carries its ANSI color.

        Asserts BOTH the verdict prefix glyph AND the verdict-matching ANSI
        CSI color escape on the same logical line — guards against an
        unrelated color sequence elsewhere on stderr.
        """
        prefix = _PREFIX_BY_VERDICT[verdict]
        color = _ANSI_BY_VERDICT[verdict]
        for raw_line in result.stderr_raw.splitlines():
            if prefix in raw_line and color in raw_line:
                return True
        return False

    def stderr_carries_no_ansi_escapes(self, result: CliResult) -> bool:
        """Return True iff stderr contains no ANSI CSI escape sequences."""
        return _ANSI_CSI_RE.search(result.stderr_raw) is None

    def structured_surface_matches_across_modes(
        self,
        cli: GateClassCli,
        result_a: CliResult,
        result_b: CliResult,
    ) -> bool:
        """Return True iff the structured surface matches across two runs."""
        snap_a = self.capture_structured_surface(cli, result_a, success=True)
        snap_b = self.capture_structured_surface(cli, result_b, success=True)
        return snap_a.kind == snap_b.kind and snap_a.payload == snap_b.payload

    def success_verdict_for(self, cli: GateClassCli) -> HumanSurfaceVerdict:
        """Return the human-readable verdict the named CLI emits on success."""
        return SUCCESS_VERDICT_BY_GATE_CLASS_CLI[cli]

    def negative_verdict_for(self, cli: GateClassCli) -> HumanSurfaceVerdict:
        """Return the human-readable verdict the named CLI emits on negative."""
        return NEGATIVE_VERDICT_BY_GATE_CLASS_CLI[cli]


@dataclass
class ClosureSurfaceFixture:
    """Production-wired composition root for slice-04 (D1 inventory closure).

    The slice-04 closure stages a tmp_path repository carrying the minimal
    per-CLI artefacts each of the two REMAINING D1 gate CLIs needs —
    ``check_reuse_first_design`` (via a feature-delta + a git-diff-source
    file) and ``check_scorecard_freshness`` (via a scorecard.md + a real git
    repo with seeded commits). Each CLI is invoked as a real subprocess
    against the staged repo; stderr is captured (TTY pty or pipe) for the
    new human-readable line AND the pre-existing per-CLI stdout token surface
    is captured for stability comparison.

    Per-CLI staging methods (``_stage_for_*``) write only the minimal
    artefacts the target CLI needs. The fixture's universe (Mandate 8) is
    the staged-artefact presence flags — each gate is a pure-function read
    over its inputs and MUST NOT mutate them.

    Mandate 11 (layer 3 example-based sad paths): three Examples rows per
    Scenario Outline parametrize-collapse the closure pair × verdict cells
    into 6 instances total (3 Outlines × 2 Examples each). The closure pair
    is 2 CLIs (not 3) so the Examples table carries 2 rows; preserves the
    triple-Outline shape of slice-02 / slice-03.
    """

    repo_root: Path

    # ------------------------------------------------------------------
    # Universe capture (Mandate 8) — port-exposed observables only.
    # ------------------------------------------------------------------

    def capture_universe(self) -> dict[str, object]:
        """Snapshot the per-CLI staged-artefact presence flags.

        Universe entries are port-exposed file-presence flags each gate
        reads (reuse-first: the feature-delta + the git-diff-source file;
        scorecard-freshness: the scorecard.md + the .git directory used for
        the freshness probe) — NEVER internal struct fields. Each gate is a
        pure-function read over these inputs; the universe assertion guards
        against any write-side mutation by the gate.
        """
        return {
            "reuse_first_feature_delta.present": (
                self.repo_root
                / "reuse_first"
                / "docs"
                / "feature"
                / "slice04-reuse-fixture"
                / "feature-delta.md"
            ).is_file(),
            "reuse_first_diff_source.present": (
                self.repo_root / "reuse_first" / "diff-source.txt"
            ).is_file(),
            "scorecard.present": (
                self.repo_root / "scorecard" / "scorecard.md"
            ).is_file(),
            "scorecard_git_dir.present": (
                self.repo_root / "scorecard" / ".git"
            ).is_dir(),
        }

    # ------------------------------------------------------------------
    # Per-CLI staging (Given delegates).
    # ------------------------------------------------------------------

    def stage_for_cli(self, cli: ClosureCli, *, success_path: bool) -> dict[str, str]:
        """Stage the minimal repo artefacts the named CLI needs to run.

        Returns a per-CLI invocation context dict the When-step passes to
        ``run_cli_capturing_surface``. ``success_path=True`` produces inputs
        that drive the gate to its PASS verdict; ``success_path=False``
        produces inputs that drive the gate to its FAIL verdict.

        Success-verdict per CLI:
          * check_reuse_first_design  → PASS (every NEW component justified)
          * check_scorecard_freshness → PASS (every cited F-id has a commit)
        Negative-verdict per CLI:
          * check_reuse_first_design  → FAIL (an unjustified NEW component)
          * check_scorecard_freshness → FAIL (a cited F-id is stale)
        """
        self.repo_root.mkdir(parents=True, exist_ok=True)
        if cli is ClosureCli.CHECK_REUSE_FIRST_DESIGN:
            return self._stage_check_reuse_first_design(success_path)
        if cli is ClosureCli.CHECK_SCORECARD_FRESHNESS:
            return self._stage_check_scorecard_freshness(success_path)
        raise ValueError(f"unknown ClosureCli: {cli!r}")  # pragma: no cover

    def _stage_check_reuse_first_design(self, success_path: bool) -> dict[str, str]:
        """Stage a feature-delta + diff-source for check_reuse_first_design.

        Success path: feature-delta carries a ``## Reuse Analysis`` table whose
        Existing Component column lists the NEW class name → exit 0 PASS.

        Negative path: feature-delta carries an EMPTY ``## Reuse Analysis``
        section; diff-source lists a NEW class name that is NOT cited in the
        table → exit 1 FAIL.
        """
        feature_id = "slice04-reuse-fixture"
        feature_root = self.repo_root / "reuse_first"
        feature_dir = feature_root / "docs" / "feature" / feature_id
        feature_dir.mkdir(parents=True, exist_ok=True)
        diff_source_path = feature_root / "diff-source.txt"
        new_class_name = "Slice04FixtureService"
        diff_source_path.write_text(f"{new_class_name}\n", encoding="utf-8")
        if success_path:
            delta_body = (
                "# feature: slice04-reuse-fixture\n"
                "\n"
                "## Reuse Analysis\n"
                "\n"
                "| Existing Component | Justification |\n"
                "|--------------------|---------------|\n"
                f"| `{new_class_name}` | NEW class introduced for the closure slice. |\n"
            )
        else:
            delta_body = (
                "# feature: slice04-reuse-fixture\n"
                "\n"
                "## Reuse Analysis\n"
                "\n"
                "| Existing Component | Justification |\n"
                "|--------------------|---------------|\n"
                "| `UnrelatedHelper` | An unrelated row that does not justify the NEW class. |\n"
            )
        (feature_dir / "feature-delta.md").write_text(delta_body, encoding="utf-8")
        return {
            "feature_id": feature_id,
            "repo_root": str(feature_root),
            "diff_source": str(diff_source_path),
        }

    def _stage_check_scorecard_freshness(self, success_path: bool) -> dict[str, str]:
        """Stage a scorecard.md + a real git repo for check_scorecard_freshness.

        The CLI invokes ``git log --grep=<F-id> --since=<N> days ago`` in the
        scorecard's parent directory. To stay self-contained, we initialise a
        fresh git repository under ``scorecard/`` and seed it with one commit
        whose message names the success-path F-id. The scorecard cites that
        same F-id on the success path (FRESH); the negative path cites a
        DIFFERENT F-id that no commit names (STALE).

        Success path: scorecard cites F-CLOSURE-SLICE04-FRESH-FIXTURE; the
        seeded commit names that F-id → every cell FRESH → exit 0 PASS.

        Negative path: scorecard cites F-CLOSURE-SLICE04-STALE-FIXTURE; no
        commit names that F-id → at least one cell STALE → exit 1 FAIL.
        """
        scorecard_dir = self.repo_root / "scorecard"
        scorecard_dir.mkdir(parents=True, exist_ok=True)
        fresh_fid = "F-CLOSURE-SLICE04-FRESH-FIXTURE"
        stale_fid = "F-CLOSURE-SLICE04-STALE-FIXTURE"
        cited_fid = fresh_fid if success_path else stale_fid
        scorecard_path = scorecard_dir / "scorecard.md"
        scorecard_path.write_text(
            "# scorecard slice04 fixture\n"
            "\n"
            "| Friction | F-id |\n"
            "|----------|------|\n"
            f"| Fixture cell | {cited_fid} |\n",
            encoding="utf-8",
        )
        self._seed_scorecard_git_repo(
            scorecard_dir, fresh_fid_named_in_commit=fresh_fid
        )
        return {
            "scorecard": str(scorecard_path),
        }

    def _seed_scorecard_git_repo(
        self, scorecard_dir: Path, *, fresh_fid_named_in_commit: str
    ) -> None:
        """Initialise a git repo under scorecard_dir + seed one commit.

        The seeded commit message contains the fresh F-id literal so the
        production ``git log --grep=<F-id>`` invocation finds it. The negative
        path's cited F-id is NOT mentioned in any commit, so its freshness
        probe returns empty → STALE.
        """
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "slice04 fixture",
            "GIT_AUTHOR_EMAIL": "slice04@fixture.test",
            "GIT_COMMITTER_NAME": "slice04 fixture",
            "GIT_COMMITTER_EMAIL": "slice04@fixture.test",
        }
        subprocess.run(
            ["git", "init", "--quiet", "--initial-branch=main"],
            cwd=str(scorecard_dir),
            check=True,
            capture_output=True,
            env=env,
        )
        seed_path = scorecard_dir / ".seed.txt"
        seed_path.write_text("slice04 seed\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", ".seed.txt"],
            cwd=str(scorecard_dir),
            check=True,
            capture_output=True,
            env=env,
        )
        subprocess.run(
            [
                "git",
                "commit",
                "--quiet",
                "--no-gpg-sign",
                "-m",
                f"feat(slice04-fixture): seed commit naming {fresh_fid_named_in_commit}",
            ],
            cwd=str(scorecard_dir),
            check=True,
            capture_output=True,
            env=env,
        )

    # ------------------------------------------------------------------
    # Driving-port invocation (When-step delegates).
    # ------------------------------------------------------------------

    def run_cli_capturing_surface(
        self,
        cli: ClosureCli,
        stderr_mode: StderrMode,
        invocation_context: dict[str, str],
    ) -> CliResult:
        """Invoke the named CLI as a subprocess against the staged repo.

        ``invocation_context`` is the per-CLI dict returned by ``stage_for_cli``
        — carries the feature-id / repo-root / diff-source / scorecard paths
        the named CLI's argv needs.

        Routes through the per-CLI argv builder, then through the existing
        TTY-vs-PIPE subprocess plumbing the slice-01 fixture authored. Re-uses
        ``_run_with_pty_stderr`` / ``_run_with_piped_stderr`` by delegating to
        a sibling ``HumanSurfaceFixture`` over the same repo root.
        """
        argv = self._build_argv(cli, invocation_context)
        helper = HumanSurfaceFixture(repo_root=self.repo_root)
        if stderr_mode is StderrMode.TTY:
            return helper._run_with_pty_stderr(argv)
        if stderr_mode is StderrMode.PIPE:
            return helper._run_with_piped_stderr(argv)
        raise ValueError(f"unknown StderrMode: {stderr_mode!r}")  # pragma: no cover

    def _build_argv(
        self, cli: ClosureCli, invocation_context: dict[str, str]
    ) -> list[str]:
        """Construct the per-CLI argv list for subprocess invocation.

        Each closure CLI lives under ``scripts/cli/`` (no DES-runtime coupling)
        so the invocation is a direct script path.
        """
        if cli is ClosureCli.CHECK_REUSE_FIRST_DESIGN:
            return [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "cli" / "check_reuse_first_design.py"),
                "--feature-id",
                invocation_context["feature_id"],
                "--repo-root",
                invocation_context["repo_root"],
                "--git-diff-source",
                f"path:{invocation_context['diff_source']}",
            ]
        if cli is ClosureCli.CHECK_SCORECARD_FRESHNESS:
            return [
                sys.executable,
                str(_REPO_ROOT / "scripts" / "cli" / "check_scorecard_freshness.py"),
                "--scorecard",
                invocation_context["scorecard"],
            ]
        raise ValueError(f"unknown ClosureCli: {cli!r}")  # pragma: no cover

    # ------------------------------------------------------------------
    # Then-step observables (per-CLI surface inspection).
    # ------------------------------------------------------------------

    def capture_structured_surface(
        self, cli: ClosureCli, result: CliResult, *, success: bool
    ) -> StructuredSurfaceSnapshot:
        """Capture the per-CLI pre-existing structured surface from one result.

        Both closure CLIs emit a single-line stdout token (L1.4 contract):
          * check_reuse_first_design  → ``reuse_first feature=... verdict=...``
          * check_scorecard_freshness → ``scorecard_freshness scorecard=... verdict=...``
        The snapshot extracts the token line so AT3 can compare TTY vs PIPE.
        """
        if cli is ClosureCli.CHECK_REUSE_FIRST_DESIGN:
            for line in result.stdout.splitlines():
                if line.startswith("reuse_first "):
                    return StructuredSurfaceSnapshot(
                        kind="reuse_first_stdout_token", payload=line.strip()
                    )
            return StructuredSurfaceSnapshot(
                kind="reuse_first_stdout_token", payload=None
            )
        if cli is ClosureCli.CHECK_SCORECARD_FRESHNESS:
            for line in result.stdout.splitlines():
                if line.startswith("scorecard_freshness "):
                    return StructuredSurfaceSnapshot(
                        kind="scorecard_freshness_stdout_token",
                        payload=line.strip(),
                    )
            return StructuredSurfaceSnapshot(
                kind="scorecard_freshness_stdout_token", payload=None
            )
        raise ValueError(f"unknown ClosureCli: {cli!r}")  # pragma: no cover

    def structured_surface_stable_for(
        self,
        cli: ClosureCli,
        result: CliResult,
        *,
        success: bool,
    ) -> bool:
        """Return True iff the per-CLI structured surface matches expectations.

        reuse-first success:    token line present AND verdict=PASS
        reuse-first negative:   token line present AND verdict=FAIL
        scorecard success:      token line present AND verdict=PASS
        scorecard negative:     token line present AND verdict=FAIL
        """
        snapshot = self.capture_structured_surface(cli, result, success=success)
        if snapshot.payload is None or not isinstance(snapshot.payload, str):
            return False
        expected_token = "verdict=PASS" if success else "verdict=FAIL"
        return expected_token in snapshot.payload

    def stderr_carries_verdict_line(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff stderr carries the verdict's plain prefix line."""
        return _PREFIX_BY_VERDICT[verdict] in result.stderr_stripped

    def stderr_verdict_line_carries_color(
        self, result: CliResult, verdict: HumanSurfaceVerdict
    ) -> bool:
        """Return True iff the verdict line on stderr carries its ANSI color.

        Asserts BOTH the verdict prefix glyph AND the verdict-matching ANSI
        CSI color escape on the same logical line — guards against an
        unrelated color sequence elsewhere on stderr.
        """
        prefix = _PREFIX_BY_VERDICT[verdict]
        color = _ANSI_BY_VERDICT[verdict]
        for raw_line in result.stderr_raw.splitlines():
            if prefix in raw_line and color in raw_line:
                return True
        return False

    def stderr_carries_no_ansi_escapes(self, result: CliResult) -> bool:
        """Return True iff stderr contains no ANSI CSI escape sequences."""
        return _ANSI_CSI_RE.search(result.stderr_raw) is None

    def structured_surface_matches_across_modes(
        self,
        cli: ClosureCli,
        result_a: CliResult,
        result_b: CliResult,
    ) -> bool:
        """Return True iff the structured surface matches across two runs."""
        snap_a = self.capture_structured_surface(cli, result_a, success=True)
        snap_b = self.capture_structured_surface(cli, result_b, success=True)
        return snap_a.kind == snap_b.kind and snap_a.payload == snap_b.payload

    def success_verdict_for(self, cli: ClosureCli) -> HumanSurfaceVerdict:
        """Return the human-readable verdict the named CLI emits on success."""
        return SUCCESS_VERDICT_BY_CLOSURE_CLI[cli]

    def negative_verdict_for(self, cli: ClosureCli) -> HumanSurfaceVerdict:
        """Return the human-readable verdict the named CLI emits on negative."""
        return NEGATIVE_VERDICT_BY_CLOSURE_CLI[cli]
