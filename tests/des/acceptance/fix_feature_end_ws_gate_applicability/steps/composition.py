r"""Composition root for slice-01 -- the feature-end gate's truthful refusal.

slice-01 of fix-feature-end-ws-gate-applicability (the walking-skeleton slice).

Mandate-13 (driving-port-only, Layer 3 subprocess) + Pillar 3: the SUT is
exercised through the PRODUCTION single entry point -- the real
``des feature-end run`` command, invoked end-to-end over the ``des.cli.__main__``
dispatcher as a subprocess, exactly as an operator runs it. The composition
NEVER imports the cycle use-case (or its module-private ``_gate_diagnostic``) and
calls it at the step boundary: the only entry is the real subprocess through the
dispatcher. So this module imports ZERO production code from
``des.{domain,application,adapters}`` -- the S2 driving-port-only boundary holds
(grep ``^from des\.`` returns nothing).

The garbling under test is observable end-to-end through the subprocess: when the
cycle runs the walking-skeleton-gate as an inner subprocess on this dev checkout,
that inner gate prints a ``des.runtime.freshness.autoskipped`` notice to standard
error (the dev-checkout autoskip) AND its real refusal reason to standard output;
the cycle's ``_gate_diagnostic`` then selects the reason. The cycle reports the
selected reason as the ``error`` field of the ``FeatureEndCycleRefused`` JSON it
prints to standard output. This composition reads that reported reason back -- it
is the operator-observable surface, NOT the SUT.

There are no test doubles: the staged feature directory and the ``des``
subprocess are real I/O -- a layer-3 ``@real-io`` surface (Mandate 9/11: example
only, no PBT machinery). The honest dev-checkout marker (``.git/`` adjacency)
makes the freshness gate AUTOSKIP -- the real signal that fires the
``des.runtime.freshness.autoskipped`` notice this slice must filter out -- rather
than a ``NWAVE_FRESHNESS=skip`` mask (env-parity, RCA-#68; see
``tests/env_parity.py``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tests.env_parity import seed_dev_checkout_marker

from .domain_types import CycleOutcome, FeatureId, StagedFeature


# THIS file lives at
# tests/des/acceptance/fix_feature_end_ws_gate_applicability/steps/composition.py
# -> 5 parents up is the repo root; repo-`src/` is the absolute import root the
# `des` subprocess needs (its cwd is the per-test tmp workspace, so a cwd-relative
# PYTHONPATH would resolve under the tmp tree and fail to import `des`).
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_FEATURE_ID = FeatureId("fix-feature-end-ws-gate-applicability-demo")

_MANIFEST_NAME = "walking-skeleton.json"


@dataclass
class CycleRefusalObserved:
    """The operator-observable result of one `des feature-end run` invocation.

    Universe entries are port-exposed only (Mandate 8): the cycle outcome
    (certified / refused, derived from the exit code) and the reported refusal
    reason read back from the command's printed JSON -- never an internal struct
    of the cycle.
    """

    outcome: CycleOutcome
    reported_reason: str
    exit_code: int


class FeatureEndGateRefusalComposition:
    """Production-wired composition root for the feature-end-refusal slice.

    The driving port is the real `des feature-end run` command invoked over the
    `des` dispatcher as a subprocess; the observable surface is the command exit
    code and the refusal reason the command reports in its printed JSON.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        self._feature_id = _FEATURE_ID
        # Env-parity (RCA-#68): the `des feature-end run` subprocess -- and the
        # inner `des walking-skeleton-gate` subprocess it spawns -- run with
        # cwd=workspace_root. Mark it a developer checkout so the runtime
        # freshness gate AUTOSKIPS (emitting `des.runtime.freshness.autoskipped`
        # to stderr -- the exact notice this slice must filter out of the
        # reported reason) instead of the customer-install REFUSAL (exit 78) on
        # the manifest-less tmp tree. The gate stays ACTIVE -- a test fixture IS
        # a synthetic dev workspace; the honest fix, NOT a NWAVE_FRESHNESS=skip
        # mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._workspace_root)

    # --- staging (PRECONDITION setup only -- never the expected output) -------

    def stage_feature(self, shape: StagedFeature) -> Path:
        """Stage the feature directory the cycle's walking-skeleton floor checks.

        Each shape produces a feature directory whose floor refuses for a
        DISTINCT real reason. This sets up the INPUT state only; it never writes
        the reason the test asserts on -- the gate computes that reason itself.
        """
        feature_dir = self._workspace_root / "feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        if shape is StagedFeature.NO_MANIFEST:
            # No walking-skeleton.json at all -> the floor's real reason names
            # the missing manifest.
            return feature_dir
        if shape is StagedFeature.MANIFEST_NO_ROOT:
            # A manifest that is present but omits its `feature_root` -> the
            # floor's real reason names the missing feature root. A DIFFERENT
            # real reason than NO_MANIFEST, so a filter that surfaces the real
            # reason is proven to surface different real reasons.
            manifest = {"entry_points": []}
            (feature_dir / _MANIFEST_NAME).write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            return feature_dir
        raise AssertionError(f"unhandled staged-feature shape: {shape!r}")

    # --- driving-port invocation ---------------------------------------------

    def run_cycle(self, feature_dir: Path) -> CycleRefusalObserved:
        """Invoke the REAL `des feature-end run` command over the dispatcher.

        Mirrors the cycle CLI's own argument shape
        (`cli/feature_end.py:119-143`). The observable is the printed JSON's
        `error` field (the reported refusal reason) and the exit code.
        """
        argv = [
            "feature-end",
            "run",
            "--repo",
            str(self._workspace_root),
            "--feature-id",
            str(self._feature_id),
            "--feature-dir",
            str(feature_dir),
        ]
        completed = subprocess.run(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
            cwd=str(self._workspace_root),
            env=self._subprocess_env(),
        )
        outcome = (
            CycleOutcome.CERTIFIED
            if completed.returncode == 0
            else CycleOutcome.REFUSED
        )
        return CycleRefusalObserved(
            outcome=outcome,
            reported_reason=self._reported_reason(completed.stdout),
            exit_code=completed.returncode,
        )

    # --- observable read-back (printed JSON, NOT the SUT) --------------------

    @staticmethod
    def _reported_reason(stdout: str) -> str:
        """The `error` reason the cycle reports in its printed refusal JSON.

        The cycle prints exactly one single-line JSON object per run
        (`cli/feature_end.py:52` `_emit`). On a refusal it carries
        `{"event": "FeatureEndCycleRefused", "error": <reported reason>}`. Reads
        the last JSON line so the reported reason is observed straight from the
        command's output surface. Returns the empty string when no refusal JSON
        is present (a genuinely absent reason -- never a swallowed parse).
        """
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

    def _subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        # ABSOLUTE repo-`src/` path (derived from __file__, not cwd-relative):
        # the subprocess cwd is the per-test tmp workspace, so a `Path("src")`
        # would resolve under the tmp tree and fail to import `des`.
        env["PYTHONPATH"] = str(_REPO_SRC)
        return env


__all__ = [
    "CycleRefusalObserved",
    "FeatureEndGateRefusalComposition",
]
