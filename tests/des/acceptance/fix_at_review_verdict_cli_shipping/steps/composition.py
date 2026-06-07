"""Composition root for the fix-at-review-verdict-cli-shipping suite.

Mandate-12 (Pillar 3 / SSOT): the SUT is driven exclusively through
PRODUCTION composition-root driving ports — NO direct domain / application /
adapter import (Mandate-13 / S2). All business logic lives in this module's
service methods; the step bodies in steps/*.py delegate here and never inline
logic (Mandate-12 criterion 3).

Driving ports used (Mandate-13 Layer 3/4):
  slice-01:
    - the install discovery helper ``des_plugin._discover_shims`` run against
      the REAL source tree the installer ships from (the install plugin's own
      production helper — the same call the install performs; allowed under
      S2 tolerable-variant: production install helper, NOT a des.domain/
      application/adapters import).
    - ``des_plugin.DES_SHIMS_FLOOR`` — the production frozen ship-floor set.
    - ``python -c "import des.cli.at_review_verdict"`` — Layer-3 subprocess
      import-clean probe against the installed recorder namespace.
  slice-02:
    - ``python -m des.cli.at_review_verdict`` — Layer-3 subprocess recorder,
      run from a working directory with NO enclosing repository, pointed at
      the working repository only via the NWAVE_REPO_ROOT environment pointer.
    - ``python -m des.cli.carpaccio_slice_gate`` — Layer-3 subprocess gate.

RED scaffold note (ADR-028): on current master the recorder lives at
``scripts/cli/at_review_verdict.py`` (outside the source tree the installer
ships from) and is absent from ``DES_SHIMS_FLOOR``. Therefore:
  - ``_discover_shims`` against the source tree does NOT contain
    ``at_review_verdict`` -> slice-01 R1 reds (MISSING_FUNCTIONALITY).
  - ``DES_SHIMS_FLOOR`` does NOT contain ``at_review_verdict`` -> R3 reds.
  - ``import des.cli.at_review_verdict`` raises ModuleNotFoundError in a
    subprocess where only the shipped namespace is importable -> R2 reds via
    a non-zero subprocess exit (the composition asserts exit 0).
  - the slice-02 recorder subprocess (``-m des.cli.at_review_verdict``) fails
    because the module is not under des.cli yet -> no ledger line is written
    and the gate never clears (R4/R5 red); R6 reds because the gate-blocked
    assertion is reached only after a successful no-op record path that does
    not yet exist.
All RED for the RIGHT reason: the recorder is not yet relocated, not an
import error in the TEST infrastructure (this composition imports only the
production install plugin + stdlib).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

# Production install driving surface — the install plugin's own discovery
# helper + frozen ship-floor. NOT a des.domain/application/adapters import
# (Mandate-13 / S2 tolerable variant: production install plugin helper).
from scripts.install.plugins import des_plugin

from .domain_types import (
    FeatureId,
    GateDecision,
    RecorderModule,
    ReviewOutcome,
    SliceId,
)


# Repo-root pointer + signing-key precedence the production recorder + gate
# honour (mirrors src/des/cli/carpaccio_slice_gate.py and the recorder).
_REPO_ROOT_ENV = "NWAVE_REPO_ROOT"
_SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"
_FRESHNESS_ENV = "NWAVE_FRESHNESS"
_SIGNING_KEY_FILE = ".nwave/secrets/reviewer-signing.key"
_FIXTURE_SIGNING_KEY = b"shipping-slice-acceptance-fixture-signing-key"

# Canonical source tree the installer ships canonical recorder modules from.
_CANONICAL_RECORDER_SOURCE = Path("src/des/cli")

# The seven HMAC-signed fields of a verdict record (mirrors the producer +
# consumer). Used to recompute the signature for the verifies-against-key
# observation without importing production code.
_SIGNED_FIELDS = (
    "schema_version",
    "slice_id",
    "verdict",
    "reviewer_agent_id",
    "at_ids",
    "at_content_hash",
    "timestamp",
)

# A minimal feature-delta + one-scenario .feature the recorder + gate parse to
# derive at_ids / at_content_hash for the entering slice. The single scenario
# carries the entering slice tag so the gate's expected_ids = {AT-1}.
_ENTERING_SLICE = "slice-01"
_FIXTURE_FEATURE_ID = "shipping-demo-feature"

_FEATURE_DELTA = """# Feature Delta — shipping-demo-feature

## Wave: DISCUSS / [REF] Slice Plan

| slice_id | value_statement | status | annotation | justification |
|----------|-----------------|--------|------------|---------------|
| slice-01 | Demo slice for the installed-operator gate-clear keystone. ATs (1). | pending | demo | demo |
"""

_FEATURE_FILE = """@feature-shipping-demo-feature
Feature: Demo slice for the installed-operator keystone

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: The demo behaviour holds
    Given a demo precondition
    When the demo action occurs
    Then the demo outcome holds
"""


@dataclass(frozen=True)
class ShimSet:
    """The set of recorder-module stems the install will ship."""

    stems: frozenset[str]


@dataclass(frozen=True)
class SubprocessResult:
    """Observable result of one Layer-3 subprocess driving-port invocation."""

    exit_code: int
    stdout: str
    stderr: str


class ShippingComposition:
    """Production-wired composition root for the recorder-shipping feature.

    slice-01 state is repo-relative (the real source tree + frozen floor).
    slice-02 state is an installed-shape layout under ``installed_root`` with a
    separate ``working_repo`` that has NO enclosing repository above it — the
    recorder is pointed at ``working_repo`` only via the env pointer.
    """

    def __init__(self, repo_dir: Path, installed_root: Path) -> None:
        self._repo_dir = repo_dir
        self._installed_root = installed_root
        # slice-02 working repository — the directory the operator names. It is
        # NOT a parent of any recorder file (the installed layout lies about
        # file-relative roots), so the recorder MUST use the env pointer.
        self._working_repo = installed_root / "operator-workspace"
        self._feature_id: FeatureId = FeatureId(_FIXTURE_FEATURE_ID)
        self._entering_slice: SliceId = SliceId(_ENTERING_SLICE)

    # --- slice-01: shipped-set + floor + import-clean -----------------------

    def discover_shipped_recorders(self) -> ShimSet:
        """Run the production install discovery helper on the real source tree.

        This is the exact invocation the install performs to decide which
        recorder modules ship. On master the recorder is NOT under the source
        tree, so its stem is absent from the result (R1 reds).
        """
        source = self._repo_dir / _CANONICAL_RECORDER_SOURCE
        return ShimSet(stems=des_plugin._discover_shims(source))

    def frozen_ship_floor(self) -> frozenset[str]:
        """The production frozen ship-floor set (R3 source of truth)."""
        return frozenset(des_plugin.DES_SHIMS_FLOOR)

    def load_recorder_from_installed_namespace(self) -> SubprocessResult:
        """Import the recorder from the canonical recorder namespace.

        Layer-3 subprocess: ``python -c "import des.cli.at_review_verdict"``.
        Exit 0 iff the relocated recorder is importable from ``des.cli`` (R2).
        """
        return self._run([sys.executable, "-c", "import des.cli.at_review_verdict"])

    # --- slice-02: installed-operator end-to-end ----------------------------

    def provision_installed_instance_with_empty_ledger(self) -> None:
        """Create the installed-shape layout + an empty working-repo ledger.

        The working repository has the feature-delta + one-scenario .feature
        the recorder + gate parse, an empty AT-completion ledger, and the
        reviewer signing key — but NO ``.git`` and NO enclosing repository
        above it, so file-relative root deduction would fail.
        """
        delta = (
            self._working_repo
            / "docs"
            / "feature"
            / str(self._feature_id)
            / "feature-delta.md"
        )
        delta.parent.mkdir(parents=True, exist_ok=True)
        delta.write_text(_FEATURE_DELTA, encoding="utf-8")
        # The gate resolves a feature's scenarios from ``.feature`` files under
        # the working repo's ``tests/`` tree (carpaccio_slice_gate
        # ``_feature_tag_files``), bound either by a file-level
        # ``@feature-{id}`` tag or the legacy
        # ``tests/scripts/cli/{id}/acceptance`` directory. Stage the fixture
        # scenario there (tag + legacy dir) so the producer's at-derivation and
        # the gate's expected_ids agree on the entering slice's AT set.
        feature = (
            self._working_repo
            / "tests"
            / "scripts"
            / "cli"
            / str(self._feature_id)
            / "acceptance"
            / "slice-01-demo.feature"
        )
        feature.parent.mkdir(parents=True, exist_ok=True)
        feature.write_text(_FEATURE_FILE, encoding="utf-8")
        self._ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._ledger_path.write_text("", encoding="utf-8")
        key_file = self._working_repo / _SIGNING_KEY_FILE
        key_file.parent.mkdir(parents=True, exist_ok=True)
        key_file.write_bytes(_FIXTURE_SIGNING_KEY)

    def record_verdict_from_installed_instance(
        self, outcome: ReviewOutcome
    ) -> SubprocessResult:
        """Record a verdict via the installed recorder subprocess.

        Driving port: ``python -m des.cli.at_review_verdict`` run from a
        directory with no enclosing repository, pointed at the working repo via
        the NWAVE_REPO_ROOT env pointer ONLY (no --repo-root flag, no cwd
        inside the repo) — the no-enclosing-repo environment the design
        assumes. On master the module is not under des.cli, so the subprocess
        exits non-zero and writes no ledger line (R4/R6 red for right reason).
        """
        env = self._installed_env()
        run_from = self._installed_root  # no enclosing repository here
        return self._run(
            [
                sys.executable,
                "-m",
                "des.cli.at_review_verdict",
                "--feature-id",
                str(self._feature_id),
                "--slice-id",
                str(self._entering_slice),
                "--verdict",
                outcome.value,
                "--reviewer-agent-id",
                "nw-acceptance-designer-reviewer",
            ],
            env=env,
            cwd=run_from,
        )

    def record_verdict_from_working_repo_cwd(
        self, outcome: ReviewOutcome
    ) -> SubprocessResult:
        """Record a verdict relying ONLY on the working-repo as the run cwd.

        The PRR keystone witness (reviewer iteration 1 blocker): the recorder is
        run with NO ``--repo-root`` flag AND NO ``NWAVE_REPO_ROOT`` env pointer,
        from ``cwd=self._working_repo`` -- a directory with no enclosing
        repository above it. Repo-root resolution MUST therefore fall through to
        ``Path.cwd()`` (the F-11 final branch). If the recorder instead used the
        ``__file__``-relative branch the feature dropped, it would resolve into
        the installed ``des.cli`` package (which has no working-repo ledger), so
        the at-derivation + signed write would NOT land in this working repo --
        no ledger line appears. The signed line appears ONLY when ``Path.cwd()``
        resolution worked.
        """
        return self._run(
            [
                sys.executable,
                "-m",
                "des.cli.at_review_verdict",
                "--feature-id",
                str(self._feature_id),
                "--slice-id",
                str(self._entering_slice),
                "--verdict",
                outcome.value,
                "--reviewer-agent-id",
                "nw-acceptance-designer-reviewer",
            ],
            env=self._installed_env_without_pointer(),
            cwd=self._working_repo,
        )

    def run_carpaccio_gate_from_installed_instance(self) -> GateDecision:
        """Run the installed carpaccio gate subprocess for the entering slice.

        Driving port: ``python -m des.cli.carpaccio_slice_gate``. Exit 0 ==
        cleared; any non-zero (45 AT-review-not-approved, etc.) == refused.
        """
        result = self._run(
            [
                sys.executable,
                "-m",
                "des.cli.carpaccio_slice_gate",
                "--feature-id",
                str(self._feature_id),
                "--entering-slice",
                str(self._entering_slice),
                "--repo-root",
                str(self._working_repo),
            ],
            env=self._installed_env(),
            cwd=self._installed_root,
        )
        return GateDecision.CLEARED if result.exit_code == 0 else GateDecision.REFUSED

    # --- Then: observe the working-repo ledger ------------------------------

    def verdicts_for_entering_slice(self) -> list[dict[str, object]]:
        """All ATReviewVerdict records in the working-repo ledger for the slice."""
        records: list[dict[str, object]] = []
        if not self._ledger_path.is_file():
            return records
        for line in self._ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("event") == "ATReviewVerdict" and record.get(
                "slice_id"
            ) == str(self._entering_slice):
                records.append(record)
        return records

    def recorded_verdict_verifies(self) -> bool:
        """True iff the latest recorded verdict's HMAC verifies against the key."""
        verdicts = self.verdicts_for_entering_slice()
        if not verdicts:
            return False
        record = verdicts[-1]
        payload = {field: record[field] for field in _SIGNED_FIELDS if field in record}
        signed_bytes = json.dumps(
            payload, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        recomputed = hmac.new(
            _FIXTURE_SIGNING_KEY, signed_bytes, hashlib.sha256
        ).hexdigest()
        signature = record.get("hmac_sha256")
        return isinstance(signature, str) and hmac.compare_digest(recomputed, signature)

    # --- Internals ----------------------------------------------------------

    @property
    def _ledger_path(self) -> Path:
        return (
            self._working_repo
            / ".nwave"
            / "telemetry"
            / "atdd-pure"
            / f"{self._feature_id}.jsonl"
        )

    def _installed_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env[_REPO_ROOT_ENV] = str(self._working_repo)
        env[_SIGNING_KEY_ENV] = _FIXTURE_SIGNING_KEY.decode("utf-8")
        # The relocated recorder now lives under ``des.cli`` whose package
        # ``__init__`` fires the runtime freshness gate at import time. The
        # installed-shape sandbox is a tmp_path tree with no install manifest,
        # so the gate would DEGRADE and refuse. ``skip`` is the audit-bearing
        # dev-tree contract (fix-des-self-hosted-gate-sync §6) -- the same
        # contract the spine wiring-e2e curated env uses for ``des.cli.*``
        # subprocesses launched from a non-installed tmp project.
        env[_FRESHNESS_ENV] = "skip"
        # Ensure the source tree is importable so the relocated des.cli.*
        # recorder resolves from the installed-shape sandbox.
        existing = env.get("PYTHONPATH", "")
        src = str(self._repo_dir / "src")
        env["PYTHONPATH"] = f"{src}{os.pathsep}{existing}" if existing else src
        return env

    def _installed_env_without_pointer(self) -> dict[str, str]:
        """``_installed_env`` with the NWAVE_REPO_ROOT pointer REMOVED.

        Keeps the freshness-skip + signing-key + PYTHONPATH the crafter wired,
        but drops the repo-root env pointer so resolution cannot short-circuit
        at the env branch -- it must reach ``Path.cwd()``. Used only by the
        cwd-only PRR keystone witness.
        """
        env = self._installed_env()
        env.pop(_REPO_ROOT_ENV, None)
        return env

    def _run(
        self,
        argv: list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> SubprocessResult:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            env=env if env is not None else self._installed_env(),
            cwd=str(cwd) if cwd is not None else str(self._repo_dir),
        )
        return SubprocessResult(
            exit_code=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
        )


def recorder_stem(module: RecorderModule) -> str:
    """The canonical recorder-module stem for ``module`` (typed-parameter coercer)."""
    return module.value
