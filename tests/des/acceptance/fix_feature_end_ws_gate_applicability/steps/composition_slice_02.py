r"""Composition root for slice-02 -- the WS-floor NOT_APPLICABLE applicability path.

slice-02 of fix-feature-end-ws-gate-applicability (the un-gameable divergence
pair + the usage guard).

Mandate-13 (driving-port-only, Layer 3 subprocess) + Pillar 3: the SUT -- the
walking-skeleton floor -- is exercised through the PRODUCTION single entry point,
the real ``des walking-skeleton-gate --feature-dir ... --repo-root ...`` command,
invoked end-to-end over the ``des.cli.__main__`` dispatcher as a subprocess
exactly as the feature-end cycle runs it (``feature_end_cycle_service.py:176``).
The composition NEVER imports the gate domain service (or its CLI internals) and
calls it at the step boundary: the only entry is the real subprocess through the
dispatcher. So this module imports ZERO production code from
``des.{domain,application,adapters}`` -- the S2 driving-port-only boundary holds
(grep ``^from des\.`` returns nothing).

The WS floor IS the gate this feature fixes; driving it directly isolates the
divergence pair cleanly to the floor verdict (the feature-delta DDD-6 explicitly
authorises driving ``des walking-skeleton-gate`` as the slice-02 driving port).
The observable surface is the gate's printed single-line JSON verdict
(``WalkingSkeletonGateVerdict`` / ``WalkingSkeletonGateUsageError``,
``cli/walking_skeleton_gate.py:143``/``:148``) plus its exit code -- read back
from the command output, NOT the SUT.

There are no test doubles: the staged feature directory, its manifest, and the
``des`` subprocess are real I/O -- a layer-3 ``@real-io`` surface (Mandate 9/11:
example only, no PBT machinery). The honest dev-checkout marker (``.git/``
adjacency) makes the runtime freshness gate AUTOSKIP rather than the
customer-install REFUSAL (exit 78) on the manifest-less tmp tree, under freshness
ACTIVE -- not a ``NWAVE_FRESHNESS=skip`` mask (env-parity, RCA-#68; see
``tests/env_parity.py``).

The divergence pair (NON_INSTALLABLE vs INSTALLABLE) carries the SAME manifest
declaration (``walking_skeleton_applicable: false`` + the SAME non-empty
rationale). The ONLY difference between the two staged trees is a real
``pyproject.toml`` on disk under ``feature_root`` -- exactly the on-disk signature
the gate keys its mechanical installability cross-check on (DESIGN DDD-3/DDD-6).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_02 import FeatureShape, FloorVerdict


# THIS file lives at
# tests/des/acceptance/fix_feature_end_ws_gate_applicability/steps/composition_slice_02.py
# -> 5 parents up is the repo root; repo-`src/` is the absolute import root the
# `des` subprocess needs (its cwd is the per-test tmp workspace, so a cwd-relative
# PYTHONPATH would resolve under the tmp tree and fail to import `des`).
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_MANIFEST_NAME = "walking-skeleton.json"


@dataclass
class FloorVerdictObserved:
    """The operator-observable result of one `des walking-skeleton-gate` run.

    Universe entries are port-exposed only (Mandate 8): the floor verdict
    (derived from the gate's exit code, the parity the gate CLI contract fixes --
    NOT_APPLICABLE/PASS=0, FAIL=1, usage=2), the verdict token the gate prints in
    its JSON, and the reason/diagnostic the gate prints -- never an internal
    struct of the gate.
    """

    verdict: FloorVerdict
    reported_verdict_token: str
    reported_reason: str
    exit_code: int


class WalkingSkeletonFloorComposition:
    """Production-wired composition root for the WS-floor applicability slice.

    The driving port is the real `des walking-skeleton-gate` command invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the verdict + reason the command reports in its printed JSON.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root
        # Env-parity (RCA-#68): the `des walking-skeleton-gate` subprocess runs
        # with cwd=workspace_root. Mark it a developer checkout so the runtime
        # freshness gate AUTOSKIPS instead of the customer-install REFUSAL (exit
        # 78) on the manifest-less tmp tree. The gate stays ACTIVE -- the honest
        # fix, NOT a NWAVE_FRESHNESS=skip mask. See tests/env_parity.py.
        seed_dev_checkout_marker(self._workspace_root)

    # --- staging (PRECONDITION setup only -- never the expected output) -------

    def stage_feature(self, shape: FeatureShape) -> Path:
        """Stage the feature directory + manifest the WS floor checks.

        Each shape produces a feature directory whose floor reaches a DISTINCT
        verdict THROUGH the gate's own logic. This sets up the INPUT state only;
        it never writes the verdict or the reason the test asserts on -- the gate
        computes both itself (the manifest carries only the declaration + the
        on-disk tree; the gate decides NOT_APPLICABLE / FAIL / USAGE).
        """
        feature_dir = self._workspace_root / "feature"
        feature_dir.mkdir(parents=True, exist_ok=True)
        feature_root = feature_dir / "root"
        feature_root.mkdir(parents=True, exist_ok=True)

        # slice-03 supersession: the NON_INSTALLABLE_DECLARED_NOT_APPLICABLE and
        # INSTALLABLE_DECLARED_NOT_APPLICABLE staging shapes were RETIRED with the
        # two divergence-pair scenarios they fed -- the delta-aware installability
        # cross-check is now specified by slice-03-delta-aware-installability.feature
        # on real git work-trees. Only the orthogonal justification guard remains.
        if shape is FeatureShape.DECLARED_NOT_APPLICABLE_NO_RATIONALE:
            # Declared not-applicable but with an EMPTY rationale -> unjustified.
            # The gate must refuse the declaration as a USAGE error, not pass.
            self._write_manifest(
                feature_dir,
                feature_root,
                applicable=False,
                rationale="",
            )
            return feature_dir

        raise AssertionError(f"unhandled feature shape: {shape!r}")

    def _write_manifest(
        self,
        feature_dir: Path,
        feature_root: Path,
        *,
        applicable: bool,
        rationale: str,
    ) -> None:
        manifest: dict[str, object] = {
            "feature_id": "fix-feature-end-ws-gate-applicability-demo",
            "feature_root": str(feature_root),
            "walking_skeleton_applicable": applicable,
            "not_applicable_rationale": rationale,
        }
        (feature_dir / _MANIFEST_NAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    # --- driving-port invocation ---------------------------------------------

    def run_floor(self, feature_dir: Path) -> FloorVerdictObserved:
        """Invoke the REAL `des walking-skeleton-gate` command over the dispatcher.

        Mirrors the feature-end cycle's own invocation shape
        (`feature_end_cycle_service.py:176-185`). The observable is the printed
        JSON's `verdict`/`reason` fields and the exit code.
        """
        argv = [
            "walking-skeleton-gate",
            "--feature-dir",
            str(feature_dir),
            "--repo-root",
            str(self._workspace_root),
        ]
        completed = subprocess.run(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
            cwd=str(self._workspace_root),
            env=self._subprocess_env(),
        )
        return FloorVerdictObserved(
            verdict=self._verdict_from_exit(completed.returncode),
            reported_verdict_token=self._reported_token(completed.stdout),
            reported_reason=self._reported_reason(completed.stdout),
            exit_code=completed.returncode,
        )

    # --- observable read-back (printed JSON, NOT the SUT) --------------------

    @staticmethod
    def _verdict_from_exit(exit_code: int) -> FloorVerdict:
        """The floor verdict the gate's exit code declares (gate CLI contract).

        Per `cli/walking_skeleton_gate.py` + `gate_outcome.py:64`: exit 0 =
        PASS/NOT_APPLICABLE, exit 1 = FAIL, exit 2 = usage. This slice's positive
        half is the only exit-0 producer in scope (a non-installable declared-NA
        feature), so exit 0 maps to NOT_APPLICABLE here; exit 1 to FAIL; exit 2 to
        USAGE_ERROR.
        """
        if exit_code == 0:
            return FloorVerdict.NOT_APPLICABLE
        if exit_code == 1:
            return FloorVerdict.FAIL
        return FloorVerdict.USAGE_ERROR

    @staticmethod
    def _reported_token(stdout: str) -> str:
        """The `verdict` token the gate prints in its single-line JSON.

        The gate prints exactly one single-line JSON object per run
        (`cli/walking_skeleton_gate.py:143`/`:148`). A verdict line carries
        `{"event": "WalkingSkeletonGateVerdict", "verdict": <token>, ...}`; a
        usage line carries `{"event": "WalkingSkeletonGateUsageError", ...}` with
        no `verdict` key. Reads the last JSON line and returns its `verdict` token
        (empty when none -- a usage line or a genuinely absent verdict, never a
        swallowed parse).
        """
        payload = WalkingSkeletonFloorComposition._last_json_object(stdout)
        verdict = payload.get("verdict") if payload is not None else None
        return str(verdict) if isinstance(verdict, str) else ""

    @staticmethod
    def _reported_reason(stdout: str) -> str:
        """The `reason`/`diagnostic` text the gate prints in its JSON.

        A verdict line carries `diagnostic` (the FAIL contradiction text); a usage
        line carries `reason` (the malformed-declaration text). Returns whichever
        is present so a single observable names the floor's stated cause. Empty
        when neither is present (never a swallowed parse).
        """
        payload = WalkingSkeletonFloorComposition._last_json_object(stdout)
        if payload is None:
            return ""
        for key in ("diagnostic", "reason"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
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

    def _subprocess_env(self) -> dict[str, str]:
        env = dict(os.environ)
        # ABSOLUTE repo-`src/` path (derived from __file__, not cwd-relative):
        # the subprocess cwd is the per-test tmp workspace, so a `Path("src")`
        # would resolve under the tmp tree and fail to import `des`.
        env["PYTHONPATH"] = str(_REPO_SRC)
        return env


__all__ = [
    "FloorVerdictObserved",
    "WalkingSkeletonFloorComposition",
]
