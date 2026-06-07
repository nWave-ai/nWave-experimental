r"""Composition root for slice-03 -- the DELTA-AWARE WS-floor installability path.

slice-03 of fix-feature-end-ws-gate-applicability (Ale-ratified option B-port,
2026-06-05): the WS-floor installability cross-check becomes DELTA-AWARE. The
gate keys its verdict on whether THIS feature's git DELTA adds a NEW installable
root, NOT on whether the ambient tree is installable.

Mandate-13 (driving-port-only, Layer 3 subprocess) + Pillar 3: the SUT -- the
walking-skeleton floor -- is exercised through the PRODUCTION single entry point,
the real ``des walking-skeleton-gate --feature-dir ... --repo-root ...
--delta-base-ref master`` command, invoked end-to-end over the
``des.cli.__main__`` dispatcher as a subprocess exactly as the feature-end cycle
runs it. The composition NEVER imports the gate domain service, the delta port,
or the git adapter and calls it at the step boundary: the only entry is the real
subprocess through the dispatcher. So this module imports ZERO production code
from ``des.{domain,application,adapters}`` -- the S2 driving-port-only boundary
holds (grep ``^from des\.`` returns nothing here).

The observable surface is the gate's printed single-line JSON verdict
(``WalkingSkeletonGateVerdict`` / ``WalkingSkeletonGateUsageError``) plus its exit
code -- read back from the command output, NOT the SUT.

Staging difference vs slice-02 (harder): slice-02 keyed the divergence on a real
``pyproject.toml`` under a declared ``feature_root`` in a plain tmp tree. slice-03
keys it on the feature's git DELTA, so each scenario stages a REAL git work-tree:
an initial ``master`` baseline commit (the repo carrying a root ``pyproject.toml``,
exactly as nwave-dev does) plus a feature-branch commit that either ADDS a new
``pyproject.toml`` at a NEW root (case a) or ADDS no new build-system file (case
b). The gate's delta probe runs ``git diff --diff-filter=A --name-only
master...HEAD`` against this work-tree. Case (c) stages a NON-git feature dir (no
``.git/`` history) so the delta is undecidable.

Env-parity (RCA-#68): the ``des`` subprocess pays an import-time freshness probe.
For cases (a)/(b) the staged work-tree's own ``.git/`` already classifies the cwd
as a developer checkout, so freshness AUTOSKIPS (not the customer-install refusal,
exit 78) -- no ``NWAVE_FRESHNESS=skip`` mask. For case (c) the feature dir must NOT
be a git work-tree, so the feature dir is a plain subdir of a workspace root that
DOES carry a ``.git/`` dev-checkout marker (``seed_dev_checkout_marker``): the
freshness cwd-marker and the feature's tracked-history probe are independent
surfaces -- the cwd is a dev checkout (freshness autoskips) while the feature dir
genuinely has no tracked history (the delta is INDETERMINATE).

The divergence pair (case a vs case b) carries the SAME manifest declaration
(``walking_skeleton_applicable: false`` + the SAME non-empty rationale) and the
SAME ambient repo root ``pyproject.toml`` on the baseline. The ONLY difference is
whether the feature commit ADDS a new build-system file in the delta -- so the
gate's verdict turns on the MECHANICAL delta probe, never on the declaration.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from tests.env_parity import seed_dev_checkout_marker

from .domain_types_slice_03 import DeltaShape, FloorVerdict


# THIS file lives at
# tests/des/acceptance/fix_feature_end_ws_gate_applicability/steps/composition_slice_03.py
# -> 5 parents up is the repo root; repo-`src/` is the absolute import root the
# `des` subprocess needs (its cwd is the per-test workspace, so a cwd-relative
# PYTHONPATH would resolve under the tmp tree and fail to import `des`).
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_MANIFEST_NAME = "walking-skeleton.json"

# The baseline branch the delta is computed against (DESIGN DDD-2 default
# `--delta-base-ref master`). The staged work-tree is initialised on this branch.
_BASE_REF = "master"

# A NEW installable root the feature commit ADDS in case (a) -- a build-system
# file at a NEW directory absent on the baseline (DESIGN _INSTALLABLE_SIGNATURES).
_ADDED_PACKAGE_REL = "new_pkg/pyproject.toml"

# The SAME justified rationale carried by BOTH halves of the divergence pair --
# only the feature's git delta differs between the two staged work-trees, so the
# gate's verdict turns on its MECHANICAL delta probe, never on the declaration.
_SHARED_RATIONALE = (
    "monorepo-internal hook-only src/des change; ships no new installable package"
)


@dataclass
class FloorVerdictObserved:
    """The operator-observable result of one `des walking-skeleton-gate` run.

    Universe entries are port-exposed only (Mandate 8): the floor verdict
    (derived from the gate's exit code -- the parity the gate CLI contract fixes:
    NOT_APPLICABLE/PASS=0, FAIL=1, usage=2, INDETERMINATE=4), the verdict token
    the gate prints in its JSON, and the reason/diagnostic the gate prints --
    never an internal struct of the gate.
    """

    verdict: FloorVerdict
    reported_verdict_token: str
    reported_reason: str
    exit_code: int


class DeltaAwareFloorComposition:
    """Production-wired composition root for the delta-aware WS-floor slice.

    The driving port is the real `des walking-skeleton-gate` command invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the verdict + reason the command reports in its printed JSON.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    # --- staging (PRECONDITION setup only -- never the expected output) -------

    def stage_feature(self, shape: DeltaShape) -> Path:
        """Stage the feature directory + a real (or absent) tracked change-history.

        Each shape produces a feature directory whose floor reaches a DISTINCT
        verdict THROUGH the gate's own delta probe. This sets up the INPUT state
        only; it never writes the verdict or the reason the test asserts on -- the
        gate computes both itself from the staged git delta (the manifest carries
        only the declaration; the gate decides NOT_APPLICABLE / FAIL /
        INDETERMINATE).
        """
        if shape is DeltaShape.NOT_A_GIT_WORK_TREE:
            return self._stage_non_git_feature()
        return self._stage_git_feature(adds_new_package=_adds_new_package(shape))

    def _stage_git_feature(self, *, adds_new_package: bool) -> Path:
        """Stage a REAL git work-tree: master baseline + feature-branch commit.

        Both halves of the divergence pair share the SAME baseline (a repo whose
        ROOT carries `pyproject.toml`, exactly like nwave-dev) and the SAME
        manifest declaration. They differ ONLY in whether the feature commit ADDS
        a new build-system file at a NEW root -- the delta the gate keys on.

        The manifest `feature_root` is the REPO ROOT itself (the monorepo-internal
        shape DDD-4 specifies: the ambient repo root HAS `pyproject.toml` on the
        baseline). This is load-bearing for an honest RED: under the CURRENT
        ambient probe the root-pyproject makes BOTH halves read installable -> the
        gate FAILs BOTH today (verified). The honest monorepo NA (case b) only
        becomes reachable once the producer is delta-keyed -- so case (b)'s
        NOT_APPLICABLE assertion RED-fails now for the right reason, and is not a
        vacuous pass against a non-installable subdir.
        """
        workspace = self._workspace_root
        # feature_root == repo root: root carries pyproject on the baseline.
        feature_root = workspace

        self._git_init_baseline(workspace)
        self._git(workspace, "checkout", "-q", "-b", "feature/topic")

        # The feature commit always touches an existing tracked source file so the
        # delta is non-empty regardless of the build-system file. Case (a)
        # additionally ADDS a new installable root; case (b) adds none.
        (workspace / "src" / "des" / "edited.py").write_text(
            "CHANGED = True\n", encoding="utf-8"
        )
        if adds_new_package:
            added = workspace / _ADDED_PACKAGE_REL
            added.parent.mkdir(parents=True, exist_ok=True)
            added.write_text(
                '[project]\nname = "added-pkg"\nversion = "0.0.0"\n',
                encoding="utf-8",
            )
        self._git(workspace, "add", "-A")
        self._git(workspace, "commit", "-qm", "feat: the feature under gate")

        # The justified declaration -- IDENTICAL across both halves of the pair.
        self._write_manifest(workspace, feature_root, rationale=_SHARED_RATIONALE)
        return workspace

    def _stage_non_git_feature(self) -> Path:
        """Stage a feature dir with NO tracked change-history (not a work-tree).

        The feature dir is a plain subdir; the gate's delta probe cannot compute
        an added-paths set -> INDETERMINATE. The workspace ROOT still carries a
        `.git/` dev-checkout marker so the import-time freshness probe AUTOSKIPS
        (env-parity, not a `NWAVE_FRESHNESS=skip` mask) -- the freshness cwd-marker
        and the feature's tracked-history are independent surfaces. The feature dir
        itself is deliberately not a work-tree (it sits OUTSIDE the marker's
        history: a sibling whose `--repo-root` is itself, carrying no `.git/`).
        """
        # Freshness autoskip: mark the cwd (workspace root) a developer checkout.
        seed_dev_checkout_marker(self._workspace_root)

        # The feature itself lives in a NON-git directory used as its own
        # --repo-root, so the gate's delta probe finds no tracked history there.
        # feature_root == that non-git dir (carries no pyproject either), so the
        # ONLY honest verdict is INDETERMINATE: the delta cannot be computed.
        feature_workspace = self._workspace_root / "ungit_feature"
        feature_workspace.mkdir(parents=True, exist_ok=True)
        self._write_manifest(
            feature_workspace, feature_workspace, rationale=_SHARED_RATIONALE
        )
        return feature_workspace

    def _write_manifest(
        self, feature_dir: Path, feature_root: Path, *, rationale: str
    ) -> None:
        manifest: dict[str, object] = {
            "feature_id": "fix-feature-end-ws-gate-applicability-demo",
            "feature_root": str(feature_root),
            "walking_skeleton_applicable": False,
            "not_applicable_rationale": rationale,
        }
        (feature_dir / _MANIFEST_NAME).write_text(
            json.dumps(manifest), encoding="utf-8"
        )

    # --- git staging helpers (PRECONDITION I/O only) -------------------------

    def _git_init_baseline(self, workspace: Path) -> None:
        """Initialise a repo on `master` whose ROOT carries `pyproject.toml`.

        Mirrors the nwave-dev shape: an installable root present on the BASELINE.
        The feature's delta is measured against this baseline; the root
        `pyproject.toml` is NOT in the delta (it predates the feature), so it does
        not by itself make the feature "ship a new installable" -- only an ADDED
        build-system file does.
        """
        self._git(workspace, "init", "-q", "-b", _BASE_REF)
        self._git(workspace, "config", "user.email", "distill@nwave.test")
        self._git(workspace, "config", "user.name", "distill")
        (workspace / "pyproject.toml").write_text(
            '[project]\nname = "ambient-repo"\nversion = "0.0.0"\n', encoding="utf-8"
        )
        src_des = workspace / "src" / "des"
        src_des.mkdir(parents=True, exist_ok=True)
        (src_des / "baseline.py").write_text("BASELINE = True\n", encoding="utf-8")
        self._git(workspace, "add", "-A")
        self._git(workspace, "commit", "-qm", "baseline: the ambient repo on master")

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

    def run_floor(self, feature_dir: Path) -> FloorVerdictObserved:
        """Invoke the REAL `des walking-skeleton-gate` command over the dispatcher.

        Mirrors the feature-end cycle's own invocation shape. `--repo-root` is the
        feature dir itself (its own work-tree, or non-git for case c) so the gate's
        delta probe runs against the staged history; the delta baseline defaults to
        `master` (DDD-2 default `--delta-base-ref master`, exercised here via the
        default rather than the explicit flag so the RED keys on the missing
        delta-detection behaviour, not on argparse rejecting an unknown flag). The
        observable is the printed JSON's `verdict`/`reason` fields and the exit code.
        """
        argv = [
            "walking-skeleton-gate",
            "--feature-dir",
            str(feature_dir),
            "--repo-root",
            str(feature_dir),
        ]
        completed = subprocess.run(
            [sys.executable, "-m", "des.cli.__main__", *argv],
            capture_output=True,
            text=True,
            cwd=str(feature_dir),
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

        Per DESIGN DDD-3 + `gate_outcome.py:64`: exit 0 = PASS/NOT_APPLICABLE,
        exit 1 = FAIL, exit 4 = INDETERMINATE (the NEW distinct verdict). This
        slice's only exit-0 producer in scope is the honest monorepo-internal NA
        (case b), so exit 0 maps to NOT_APPLICABLE here; exit 1 to FAIL; exit 4 to
        INDETERMINATE.
        """
        if exit_code == 0:
            return FloorVerdict.NOT_APPLICABLE
        if exit_code == 1:
            return FloorVerdict.FAIL
        if exit_code == 4:
            return FloorVerdict.INDETERMINATE
        # Any other exit code (e.g. usage 2, or freshness 78) is NOT a verdict the
        # slice-03 contract produces; surface it distinctly so a RED never masks a
        # setup failure as a verdict.
        return FloorVerdict.INDETERMINATE

    @staticmethod
    def _reported_token(stdout: str) -> str:
        """The `verdict` token the gate prints in its single-line JSON."""
        payload = DeltaAwareFloorComposition._last_json_object(stdout)
        verdict = payload.get("verdict") if payload is not None else None
        return str(verdict) if isinstance(verdict, str) else ""

    @staticmethod
    def _reported_reason(stdout: str) -> str:
        """The `reason`/`diagnostic` text the gate prints in its JSON.

        Returns whichever of `diagnostic`/`reason` is present so a single
        observable names the floor's stated cause. Empty when neither is present
        (never a swallowed parse).
        """
        payload = DeltaAwareFloorComposition._last_json_object(stdout)
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
        # ABSOLUTE repo-`src/` path (derived from __file__, not cwd-relative): the
        # subprocess cwd is the per-test workspace, so a `Path("src")` would
        # resolve under it and fail to import `des`.
        env["PYTHONPATH"] = str(_REPO_SRC)
        return env


def _adds_new_package(shape: DeltaShape) -> bool:
    """Whether the staged feature commit ADDS a new installable root."""
    return shape is DeltaShape.DELTA_ADDS_NEW_INSTALLABLE_ROOT


__all__ = [
    "DeltaAwareFloorComposition",
    "FloorVerdictObserved",
]
