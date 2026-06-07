r"""Composition root for slice-04 -- the APPLICABILITY-AWARE feature-end done-gate.

slice-04 of fix-feature-end-ws-gate-applicability (env-e2e + coverage-map legs,
Atlas-APPROVED 2026-06-06): the feature-end cycle's env-e2e leg (leg 2) and
coverage-map leg (leg 3) become applicability-aware, mirroring the WS-floor delta
cross-check slices 01-03 established for leg 1.

Mandate-13 (driving-port-only, Layer 3 subprocess) + Pillar 3: the SUT is
exercised through the PRODUCTION single entry points -- the real
``des feature-end run`` command (the cycle) and the real ``des verify-integrity``
command (the downstream done-gate), invoked end-to-end over the
``des.cli.__main__`` dispatcher as subprocesses, exactly as an operator runs them.
This module imports ZERO production code from ``des.{domain,application,adapters}``
(the S2 driving-port-only boundary holds: ``grep '^from des\.'`` returns nothing
here). The ledger records the cycle mints are read back from the raw JSONL the
cycle wrote -- a PURE filesystem read of the audit SUBSTRATE the done-gate
consumes, NOT a ``des.*`` import and NOT the SUT. The un-gameable assertions come
from (a) the real ``des feature-end run`` exit code + reported reason, (b) the
NA-marker event names the cycle minted in its own ledger (M7-valid by the cycle's
production writer), and (c) the real ``des verify-integrity`` verdict JSON.

There are no test doubles: the staged feature directory, the real git work-trees
(for the env-e2e pair, whose WS-NA piggybacks the slice-03 delta cross-check), the
repo-level ``.nwave/des-config.json`` adoption switch, the ``distill/coverage-map.md``
artifacts, and the ``des`` subprocesses are all real I/O -- a layer-3 ``@real-io``
surface (Mandate 9/11: example only, no PBT machinery). The honest dev-checkout
marker (``.git/`` adjacency at the repo root) makes the runtime freshness gate
AUTOSKIP rather than the customer-install REFUSAL (exit 78) -- under freshness
ACTIVE, not a ``NWAVE_FRESHNESS=skip`` mask (env-parity, RCA-#68; see
``tests/env_parity.py``).

Staging shape per leg:

  * env-e2e pair (A1/A2): a REAL git work-tree (master baseline carrying a root
    ``pyproject.toml``, exactly like nwave-dev, + a feature commit). A1's commit
    ADDS no new build-system file -> WS-NA -> the cycle must propagate NA to the
    env-e2e leg. A2's commit ADDS ``new_pkg/pyproject.toml`` -> WS-FAIL -> the
    cycle refuses at leg 1 and never reaches the env-e2e NA branch. The ONLY
    difference is a tracked file in the git delta -- the un-gameable signal.
  * coverage pair (B1-B6): a non-installable git work-tree (so the WS + env-e2e
    legs grant NA and the cycle REACHES the coverage leg) PLUS a repo-level
    adoption switch + an optional ``distill/coverage-map.md``. The divergence keys
    on the REPO switch (read from ``repo_root``, a path no feature can shadow) and
    the genuine presence/absence of the map.
  * reconciliation pair (C1/C2): drive ``des feature-end run`` then the real
    ``des verify-integrity``; C1 asserts the NA markers reconcile the applicable
    legs; C2 asserts a leg with neither record is still caught.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_04 import (
    CycleOutcome,
    FeatureShape,
)


# THIS file lives at
# tests/des/acceptance/fix_feature_end_ws_gate_applicability/steps/composition_slice_04.py
# -> 5 parents up is the repo root; repo-`src/` is the absolute import root the
# `des` subprocess needs (its cwd is the per-test workspace, so a cwd-relative
# PYTHONPATH would resolve under the tmp tree and fail to import `des`).
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_MANIFEST_NAME = "walking-skeleton.json"
_FEATURE_DELTA_NAME = "feature-delta.md"
_FEATURE_ID = "fix-feature-end-ws-gate-applicability-demo"

# The reviewer signing key the cycle's deep-review SIGN leg needs
# (`feature_end_sign_service.py:88,108` -> `load_signing_key(repo_root)` reads
# `NWAVE_REVIEWER_SIGNING_KEY`). A1/B1 are the first slice-04 scenarios that drive
# a FULLY-NA feature all the way THROUGH the sign leg (the NA markers mint BEFORE
# it; the dodge-catch scenarios refuse earlier and never reach it). The signing
# key is a legitimate production input the operator provides -- staging it in the
# subprocess env makes A1/B1 self-contained + deterministic with no ambient key,
# changes no scenario body or assertion, and is harmless to the dodge-catch
# scenarios (they refuse before the sign leg). Mirrors the established
# self-contained pattern in oss_feature_end_emit_cli/steps/composition_slice_04.py:110.
_SIGNING_KEY = "test-reviewer-signing-key-slice-04"

# The baseline branch the WS-floor delta is computed against (slice-03 DDD-2
# default `--delta-base-ref master`). The staged work-tree is initialised on it.
_BASE_REF = "master"

# A NEW installable root the A2 feature commit ADDS -- a build-system file at a
# NEW directory absent on the baseline (the slice-03 `new_pkg` signature the
# WS-floor diagnostic names).
_ADDED_PACKAGE_REL = "new_pkg/pyproject.toml"

# The justified WS-floor declaration the env-e2e pair shares; only the git delta
# differs between A1 and A2, so the cycle's verdict turns on the MECHANICAL delta
# probe, never on the declaration.
_SHARED_RATIONALE = (
    "monorepo-internal hook-only src/des change; ships no new installable package"
)

# The per-feature ledger JSONL the cycle appends to (legacy per-feature shape:
# `AtCompletionLedger(feature_id, repo_root)` writes here -- see
# at_completion_ledger.py:284). Read back as a PURE filesystem read.
_LEDGER_REL = Path(".nwave") / "telemetry" / "atdd-pure" / f"{_FEATURE_ID}.jsonl"

# The repo-level adoption switch the coverage leg reads (DDD-3 LOAD-BEARING
# INVARIANT: read from `repo_root`, never `feature_dir`).
_DES_CONFIG_REL = Path(".nwave") / "des-config.json"


@dataclass
class CycleObserved:
    """The operator-observable result of one `des feature-end run` invocation.

    Universe entries are port-exposed only (Mandate 8): the cycle outcome
    (proceeds-past-leg / refuses, derived from the exit code + which leg's refusal
    fired), the reported refusal reason read back from the command's printed JSON,
    the exit code, and the ledger event-name set the cycle minted (read from the
    raw JSONL audit substrate) -- never an internal struct of the cycle.
    """

    outcome: CycleOutcome
    reported_reason: str
    exit_code: int
    ledger_events: frozenset[str] = field(default_factory=frozenset)


@dataclass
class IntegrityObserved:
    """The operator-observable result of one `des verify-integrity` invocation.

    Universe entries are port-exposed only: the verdict event the done-gate
    printed (`FeatureReconciled` / `FeatureEndCycleIncomplete` / ...), the
    `missing_records` set it named, and the exit code -- read back from the
    command output, NOT the SUT.
    """

    verdict_event: str
    missing_records: frozenset[str]
    exit_code: int


class ApplicabilityAwareCycleComposition:
    """Production-wired composition root for the applicability-aware done-gate slice.

    The driving ports are the real `des feature-end run` (the cycle) and
    `des verify-integrity` (the done-gate) commands invoked over the `des`
    dispatcher as subprocesses; the observable surface is each command's exit
    code + printed JSON, plus the ledger records the cycle minted (raw JSONL
    read-back of the audit substrate, not the SUT).
    """

    def __init__(self, workspace_root: Path) -> None:
        # Every staged feature lives under a per-shape repo so the repo-level
        # adoption switch + the per-feature ledger are isolated between scenarios.
        self._workspace_root = workspace_root

    # --- staging (PRECONDITION setup only -- never the expected output) -------

    def stage_feature(self, shape: FeatureShape) -> _StagedFeature:
        """Stage the repo + feature + (where applicable) git delta / adoption switch.

        Each shape produces a feature whose feature-end cycle reaches a DISTINCT
        verdict THROUGH the cycle's own legs. This sets up the INPUT state only;
        it never writes the verdict, the reason, or the ledger records the test
        asserts on -- the cycle computes all of them itself.
        """
        repo_root = self._fresh_repo()
        feature_dir = repo_root / "docs" / "feature" / _FEATURE_ID
        feature_dir.mkdir(parents=True, exist_ok=True)
        (feature_dir / _FEATURE_DELTA_NAME).write_text(
            "# Feature Delta: demo\n", encoding="utf-8"
        )

        if shape in _ENV_E2E_SHAPES:
            self._stage_env_e2e(repo_root, feature_dir, shape)
        else:
            self._stage_coverage(repo_root, feature_dir, shape)

        return _StagedFeature(repo_root=repo_root, feature_dir=feature_dir)

    # --- env-e2e pair staging (A1/A2) ----------------------------------------

    def _stage_env_e2e(
        self, repo_root: Path, feature_dir: Path, shape: FeatureShape
    ) -> None:
        """Stage a REAL git work-tree whose WS-floor delta drives the env-e2e leg.

        A1 (HONEST_NON_INSTALLABLE): the feature commit adds no new build-system
        file -> WS-NA -> the cycle must propagate NA to the env-e2e leg. A2
        (DODGE_ADDS_INSTALLABLE): the commit ADDS `new_pkg/pyproject.toml` ->
        WS-FAIL -> the cycle refuses at leg 1, never reaching the env-e2e NA
        branch. The manifest declaration is IDENTICAL; only the git delta differs.
        """
        adds_new_package = shape is FeatureShape.DODGE_ADDS_INSTALLABLE
        self._git_init_baseline(repo_root)
        self._git(repo_root, "checkout", "-q", "-b", "feature/topic")
        (repo_root / "src" / "des" / "edited.py").write_text(
            "CHANGED = True\n", encoding="utf-8"
        )
        if adds_new_package:
            added = repo_root / _ADDED_PACKAGE_REL
            added.parent.mkdir(parents=True, exist_ok=True)
            added.write_text(
                '[project]\nname = "added-pkg"\nversion = "0.0.0"\n',
                encoding="utf-8",
            )
        self._git(repo_root, "add", "-A")
        self._git(repo_root, "commit", "-qm", "feat: the feature under gate")
        # feature_root == repo root (the monorepo-internal shape: the ambient root
        # carries pyproject on the baseline). The WS gate keys NA on the DELTA, not
        # the ambient tree.
        self._write_manifest(feature_dir, repo_root, rationale=_SHARED_RATIONALE)

    # --- coverage pair staging (B1-B6) ---------------------------------------

    def _stage_coverage(
        self, repo_root: Path, feature_dir: Path, shape: FeatureShape
    ) -> None:
        """Stage a non-installable feature + repo adoption switch + optional map.

        The feature is a non-installable monorepo-internal git work-tree (so the
        WS + env-e2e legs grant NA and the cycle REACHES the coverage leg). The
        divergence keys on the REPO-level `coverage_map_adoption` switch and the
        genuine presence/absence of `distill/coverage-map.md`.
        """
        self._git_init_baseline(repo_root)
        self._git(repo_root, "checkout", "-q", "-b", "feature/topic")
        (repo_root / "src" / "des" / "edited.py").write_text(
            "CHANGED = True\n", encoding="utf-8"
        )
        self._git(repo_root, "add", "-A")
        self._git(repo_root, "commit", "-qm", "feat: the feature under gate")
        self._write_manifest(feature_dir, repo_root, rationale=_SHARED_RATIONALE)

        self._stage_repo_adoption_switch(repo_root, shape)
        self._stage_coverage_map(feature_dir, shape)
        if shape is FeatureShape.SELF_GRANTED_NA_DODGE:
            # The feature self-ships its OWN des-config declaring inactive,
            # attempting to self-grant NA. The cycle MUST read the repo switch and
            # IGNORE this one (B5 -- the un-per-feature-gameability hinge).
            self._write_des_config(feature_dir, '{"coverage_map_adoption": "inactive"}')

    def _stage_repo_adoption_switch(self, repo_root: Path, shape: FeatureShape) -> None:
        """Write (or omit) the repo-level `coverage_map_adoption` switch per shape."""
        active_shapes = {
            FeatureShape.DODGE_ACTIVE_NO_MAP,
            FeatureShape.PRESENT_INCOMPLETE_MAP_ACTIVE,
            FeatureShape.SELF_GRANTED_NA_DODGE,
            # C2 silent-skip: active adoption + no map so the coverage leg mints
            # NEITHER the verified record NOR the NA marker (it hard-refuses), and
            # `des verify-integrity` must still name the coverage records missing.
            FeatureShape.SILENT_SKIP_LEG,
        }
        if shape in active_shapes:
            self._write_des_config(repo_root, '{"coverage_map_adoption": "active"}')
        elif shape is FeatureShape.DEGRADE_ABSENT_KEY:
            # Present + parseable but NO coverage_map_adoption key -> absent-key ⇒
            # inactive (permissive NA -- B6a).
            self._write_des_config(repo_root, '{"some_other_key": true}')
        elif shape is FeatureShape.DEGRADE_MALFORMED_FILE:
            # Malformed / unreadable JSON -> active (degrade toward rigour -- B6b).
            self._write_des_config(repo_root, "{ this is not valid json ")
        # B1/B2 (HONEST_NO_COVERAGE_INACTIVE / DODGE_HALF_BAKED_MAP): no repo
        # des-config at all -> absent file ⇒ inactive (the designed 0/74 default).

    def _stage_coverage_map(self, feature_dir: Path, shape: FeatureShape) -> None:
        """Write (or omit) the feature's `distill/coverage-map.md` per shape.

        B2 (DODGE_HALF_BAKED_MAP) and B4 (PRESENT_INCOMPLETE_MAP_ACTIVE) both stage
        a PRESENT-but-structurally-incomplete map (a lone heading, no mandatory L1
        sections). The real §5.3 verify holds BOTH to the real check and refuses
        with `StructuralIncomplete` (`coverage_map_verify_service.py:341-346`) -- a
        present map is ALWAYS verified, never NA. The `StructuralIncomplete` token
        in the refusal POSITIVELY witnesses the coverage leg was REACHED.
        """
        present_incomplete_shapes = {
            FeatureShape.DODGE_HALF_BAKED_MAP,
            FeatureShape.PRESENT_INCOMPLETE_MAP_ACTIVE,
        }
        if shape in present_incomplete_shapes:
            distill = feature_dir / "distill"
            distill.mkdir(parents=True, exist_ok=True)
            # A lone heading with NO mandatory section -> the real verify reports
            # StructuralIncomplete (verified-from-source: _check_structural_
            # completeness fails on a body missing the mandatory L1 sections).
            (distill / "coverage-map.md").write_text(
                "# Coverage Map (structurally incomplete -- no mandatory sections)\n",
                encoding="utf-8",
            )
        # B1/B3/B5/B6: NO coverage-map.md -> genuine absence (the only path to NA,
        # and only while adoption is inactive repo-wide).

    # --- manifest + config + git helpers (PRECONDITION I/O only) -------------

    def _write_manifest(
        self, feature_dir: Path, feature_root: Path, *, rationale: str
    ) -> None:
        manifest: dict[str, object] = {
            "feature_id": _FEATURE_ID,
            "feature_root": str(feature_root),
            "walking_skeleton_applicable": False,
            "not_applicable_rationale": rationale,
        }
        (feature_dir / _MANIFEST_NAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    @staticmethod
    def _write_des_config(root: Path, raw_json: str) -> None:
        config_path = root / _DES_CONFIG_REL
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(raw_json, encoding="utf-8")

    def _fresh_repo(self) -> Path:
        """A fresh per-scenario repo root, marked a dev checkout for env-parity."""
        repo_root = self._workspace_root / "repo"
        repo_root.mkdir(parents=True, exist_ok=True)
        # Freshness autoskip (env-parity, RCA-#68): the `des` subprocesses run with
        # cwd=repo_root; the `.git/` adjacency seeded below ALSO marks the dev
        # checkout, so the freshness gate AUTOSKIPS instead of the exit-78 refusal.
        seed_dev_checkout_marker(repo_root)
        return repo_root

    def _git_init_baseline(self, repo_root: Path) -> None:
        """Initialise a repo on `master` whose ROOT carries `pyproject.toml`.

        Mirrors the nwave-dev shape: an installable root present on the BASELINE.
        The feature's delta is measured against this baseline; the root
        `pyproject.toml` predates the feature so it is NOT in the delta -- only an
        ADDED build-system file makes the feature "ship a new installable".
        """
        self._git(repo_root, "init", "-q", "-b", _BASE_REF)
        self._git(repo_root, "config", "user.email", "distill@nwave.test")
        self._git(repo_root, "config", "user.name", "distill")
        (repo_root / "pyproject.toml").write_text(
            '[project]\nname = "ambient-repo"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        src_des = repo_root / "src" / "des"
        src_des.mkdir(parents=True, exist_ok=True)
        (src_des / "baseline.py").write_text("BASELINE = True\n", encoding="utf-8")
        self._git(repo_root, "add", "-A")
        self._git(repo_root, "commit", "-qm", "baseline: the ambient repo on master")

    @staticmethod
    def _git(cwd: Path, *args: str) -> None:
        """Run a staging `git` command, raising on failure (setup must succeed)."""
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"git {' '.join(args)} failed in staging (exit "
                f"{completed.returncode}): {completed.stderr.strip()[:200]}"
            )

    # --- driving-port invocation ---------------------------------------------

    def run_cycle(self, staged: _StagedFeature) -> CycleObserved:
        """Invoke the REAL `des feature-end run` command over the dispatcher.

        Mirrors the cycle CLI's own argument shape (`cli/feature_end.py:119-143`).
        The observable is the printed JSON's `error` field (reported refusal
        reason), the exit code, and the ledger event-names the cycle minted (read
        from the raw JSONL audit substrate). A non-zero exit is a refusal; exit 0
        proceeds past every leg.
        """
        argv = [
            "feature-end",
            "run",
            "--repo",
            str(staged.repo_root),
            "--feature-id",
            _FEATURE_ID,
            "--feature-dir",
            str(staged.feature_dir),
            "--reviewer-agent-id",
            "nw-acceptance-designer-reviewer",
            "--verdict",
            "APPROVED",
        ]
        completed = self._dispatch(staged.repo_root, argv)
        outcome = (
            CycleOutcome.PROCEEDS_PAST_LEG
            if completed.returncode == 0
            else CycleOutcome.REFUSES
        )
        return CycleObserved(
            outcome=outcome,
            reported_reason=self._reported_error(completed.stdout),
            exit_code=completed.returncode,
            ledger_events=self._ledger_events(staged.repo_root),
        )

    def run_integrity(self, staged: _StagedFeature) -> IntegrityObserved:
        """Invoke the REAL `des verify-integrity` done-gate over the dispatcher.

        The done-gate reconciles the cycle's ledger against the required-record
        set. The observable is the verdict event it prints
        (`FeatureReconciled` / `FeatureEndCycleIncomplete`), the `missing_records`
        it names, and the exit code -- read back from the command output.
        """
        argv = [
            "verify-integrity",
            "--repo",
            str(staged.repo_root),
            "--feature-id",
            _FEATURE_ID,
        ]
        completed = self._dispatch(staged.repo_root, argv)
        payload = self._last_json_object(completed.stdout)
        verdict_event = ""
        missing: frozenset[str] = frozenset()
        if payload is not None:
            event = payload.get("event")
            verdict_event = str(event) if isinstance(event, str) else ""
            raw_missing = payload.get("missing_records")
            if isinstance(raw_missing, list):
                missing = frozenset(str(item) for item in raw_missing)
        return IntegrityObserved(
            verdict_event=verdict_event,
            missing_records=missing,
            exit_code=completed.returncode,
        )

    # --- observable read-back (printed JSON + raw ledger, NOT the SUT) --------

    def _ledger_events(self, repo_root: Path) -> frozenset[str]:
        """The set of event names in the cycle's per-feature ledger JSONL.

        A PURE filesystem read of the audit SUBSTRATE the cycle wrote (the same
        records `des verify-integrity` consumes) -- never a `des.*` import (S2
        boundary) and never the SUT. An absent ledger means the cycle minted no
        records (it refused before any append).
        """
        ledger_path = repo_root / _LEDGER_REL
        if not ledger_path.is_file():
            return frozenset()
        events: set[str] = set()
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = record.get("event") if isinstance(record, dict) else None
            if isinstance(event, str):
                events.add(event)
        return frozenset(events)

    @staticmethod
    def _reported_error(stdout: str) -> str:
        """The `error` reason a refusal JSON reports (empty when none present)."""
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "error" in payload:
                return str(payload["error"])
        return ""

    @staticmethod
    def _last_json_object(stdout: str) -> dict[str, object] | None:
        """The last single-line JSON object the command printed, or None."""
        for line in reversed(stdout.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
        return None

    def _dispatch(
        self, repo_root: Path, argv: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=self._subprocess_env(),
        )

    def _subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        # ABSOLUTE repo-`src/` path (derived from __file__, not cwd-relative): the
        # subprocess cwd is the per-test workspace, so a `Path("src")` would
        # resolve under it and fail to import `des`.
        env["PYTHONPATH"] = str(_REPO_SRC)
        # The reviewer signing key the cycle's deep-review SIGN leg needs (A1/B1
        # drive a fully-NA feature THROUGH the sign leg). Set unconditionally: the
        # dodge-catch scenarios refuse before the sign leg, so the key is harmless
        # there; self-contained, no ambient NWAVE_REVIEWER_SIGNING_KEY required.
        env["NWAVE_REVIEWER_SIGNING_KEY"] = _SIGNING_KEY
        return env


@dataclass(frozen=True)
class _StagedFeature:
    """A staged feature: the repo root the cycle runs in + the feature directory."""

    repo_root: Path
    feature_dir: Path


_ENV_E2E_SHAPES = frozenset(
    {
        FeatureShape.HONEST_NON_INSTALLABLE,
        FeatureShape.DODGE_ADDS_INSTALLABLE,
    }
)


__all__ = [
    "ApplicabilityAwareCycleComposition",
    "CycleObserved",
    "IntegrityObserved",
]
