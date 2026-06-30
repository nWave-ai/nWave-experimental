r"""Composition root for slice-01 -- the MANIFEST-OPTIONAL WS-floor.

feature-end-ws-gate-manifest-optional (ADR-098, ratified 2026-06-24): the
walking-skeleton floor, when NO ``walking-skeleton.json`` manifest is present,
COMPUTES applicability from the feature's git DELTA rather than fail-closing
(usage exit 2). This EXTENDS the delta-compute path the gate already runs for the
empty-``entry_points`` case to the no-manifest case.

Mandate-13 (driving-port-only, Layer 3 subprocess) + Pillar 3: the SUT -- the
walking-skeleton floor -- is exercised through the PRODUCTION single entry point,
the real ``des walking-skeleton-gate --feature-dir ... --repo-root ...
--delta-base-ref master`` command, invoked end-to-end over the
``des.cli.__main__`` dispatcher as a subprocess exactly as the feature-end cycle
runs it. The composition NEVER imports the gate domain service, the delta port, or
the git adapter and calls it at the step boundary: the only entry is the real
subprocess through the dispatcher. So this module imports ZERO production code from
``des.{domain,application,adapters}`` -- the S2 driving-port-only boundary holds
(grep ``^from des\.`` returns nothing here).

The observable surface is the gate's printed single-line JSON verdict
(``WalkingSkeletonGateVerdict`` / ``WalkingSkeletonGateUsageError``) plus its exit
code -- read back from the command output, NOT the SUT.

Staging: each manifest-less scenario stages a REAL git work-tree -- an initial
``master`` baseline commit (the repo carrying a root ``pyproject.toml``, exactly
as nwave-dev does) plus a feature-branch commit that either ADDS a new
``pyproject.toml`` at a NEW root (AC-2) or ADDS no new build-system file (AC-1).
The gate's delta probe runs ``git diff --diff-filter=A --name-only
master...HEAD`` against this work-tree. Crucially NO ``walking-skeleton.json`` is
written into the feature dir -- the absent manifest is the whole point. AC-3
stages a NON-git feature dir (no ``.git/`` history) so the delta is undecidable.
AC-4 is the only scenario that writes a manifest (the preservation guard).

Env-parity (RCA-#68): the ``des`` subprocess pays an import-time freshness probe.
The manifest-less work-trees' own ``.git/`` already classifies the cwd as a
developer checkout, so freshness AUTOSKIPS. For the non-git AC-3 case the feature
dir is a plain subdir of a workspace root that DOES carry a ``.git/`` dev-checkout
marker (``seed_dev_checkout_marker``): the freshness cwd-marker and the feature's
tracked-history probe are independent surfaces.

RED-for-right-reason (pre-DELIVER gate): at HEAD ``_load_manifest`` raises a
``ValueError`` (mapped to usage exit 2) the moment the manifest file is absent
(``walking_skeleton_gate.py:108-110``). So AC-1/2/3 RED-fail because the observed
verdict is the usage FAIL_CLOSED (exit 2) rather than NOT_APPLICABLE / FAIL /
INDETERMINATE -- a semantic AssertionError, never a collection/import/setup error
(this module imports zero ``des.*``). AC-4 (manifest present) is already green.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process
from tests.env_parity import seed_dev_checkout_marker

from .domain_types_manifest_optional import FeatureShape, FloorVerdict


# THIS file lives at
# tests/des/acceptance/ws_gate_manifest_optional/steps/composition_manifest_optional.py
# -> 5 parents up is the repo root; repo-`src/` is the absolute import root the
# `des` subprocess needs (its cwd is the per-test workspace, so a cwd-relative
# PYTHONPATH would resolve under the tmp tree and fail to import `des`).
_REPO_SRC = Path(__file__).resolve().parents[5] / "src"

_MANIFEST_NAME = "walking-skeleton.json"

# The baseline branch the delta is computed against (the gate's default
# `--delta-base-ref master`). The staged work-tree is initialised on this branch.
_BASE_REF = "master"

# A NEW installable root the feature commit ADDS in AC-2 -- a build-system file at
# a NEW directory absent on the baseline.
_ADDED_PACKAGE_REL = "new_pkg/pyproject.toml"

# The justified rationale the AC-4 manifest carries (the preservation guard's only
# manifest). The manifest-less scenarios write NO manifest at all.
_SHARED_RATIONALE = (
    "monorepo-internal gate-logic src/des change; ships no new installable package"
)


@dataclass
class FloorVerdictObserved:
    """The operator-observable result of one `des walking-skeleton-gate` run.

    Universe entries are port-exposed only (Mandate 8): the floor verdict (derived
    from the gate's exit code -- the parity its CLI contract fixes:
    PASS/NOT_APPLICABLE=0, FAIL=1, usage fail-close=2, UNVERIFIED=3,
    INDETERMINATE=4), the verdict token the gate prints in its JSON, the
    reason/diagnostic it prints, and the raw stdout (so the "does not fail-close"
    assertion can key on the ABSENCE of the usage-error event token) -- never an
    internal struct of the gate.
    """

    verdict: FloorVerdict
    reported_verdict_token: str
    reported_reason: str
    exit_code: int
    raw_stdout: str


class ManifestOptionalFloorComposition:
    """Production-wired composition root for the manifest-optional WS-floor slice.

    The driving port is the real `des walking-skeleton-gate` command invoked over
    the `des` dispatcher as a subprocess; the observable surface is the command
    exit code and the verdict + reason the command reports in its printed JSON.
    """

    def __init__(self, workspace_root: Path) -> None:
        self._workspace_root = workspace_root

    # --- staging (PRECONDITION setup only -- never the expected output) -------

    def stage_feature(self, shape: FeatureShape) -> Path:
        """Stage the feature directory + a real (or absent) tracked change-history.

        Each shape produces a feature directory whose floor reaches a DISTINCT
        verdict THROUGH the gate's own delta probe. This sets up the INPUT state
        only; it never writes the verdict or the reason the test asserts on -- the
        gate computes both itself. The manifest-less shapes write NO
        ``walking-skeleton.json``; only the manifest-present shape writes one.
        """
        if shape is FeatureShape.MANIFEST_LESS_NO_TRACKED_HISTORY:
            return self._stage_non_git_manifest_less_feature()
        if shape is FeatureShape.MANIFEST_PRESENT_NOT_APPLICABLE:
            return self._stage_git_feature(adds_new_package=False, write_manifest=True)
        adds_new_package = shape is FeatureShape.MANIFEST_LESS_ADDS_NEW_INSTALLABLE_ROOT
        return self._stage_git_feature(
            adds_new_package=adds_new_package, write_manifest=False
        )

    def _stage_git_feature(
        self, *, adds_new_package: bool, write_manifest: bool
    ) -> Path:
        """Stage a REAL git work-tree: master baseline + feature-branch commit.

        The baseline is a repo whose ROOT carries `pyproject.toml` (exactly like
        nwave-dev). The feature commit always touches an existing tracked source
        file so the delta is non-empty; it ADDS a new build-system file only when
        `adds_new_package`. A `walking-skeleton.json` is written ONLY when
        `write_manifest` (the AC-4 preservation guard) -- the manifest-less
        scenarios leave the feature dir manifest-free, which is the whole point.
        """
        workspace = self._workspace_root
        feature_root = workspace  # root carries pyproject on the baseline.

        self._git_init_baseline(workspace)
        self._git(workspace, "checkout", "-q", "-b", "feature/topic")

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

        if write_manifest:
            self._write_manifest(workspace, feature_root, rationale=_SHARED_RATIONALE)
        return workspace

    def _stage_non_git_manifest_less_feature(self) -> Path:
        """Stage a manifest-less feature dir with NO tracked change-history.

        The feature dir is a plain subdir (no `.git/` history) and carries NO
        manifest, so the gate's delta probe cannot compute an added-paths set ->
        the floor must refuse-to-decide LOUD. The workspace ROOT still carries a
        `.git/` dev-checkout marker so the import-time freshness probe AUTOSKIPS
        (env-parity, not a `NWAVE_FRESHNESS=skip` mask) -- the freshness cwd-marker
        and the feature's tracked-history are independent surfaces.
        """
        seed_dev_checkout_marker(self._workspace_root)
        feature_workspace = self._workspace_root / "ungit_feature"
        feature_workspace.mkdir(parents=True, exist_ok=True)
        # No manifest written -- absent manifest + no tracked history.
        return feature_workspace

    def _write_manifest(
        self, feature_dir: Path, feature_root: Path, *, rationale: str
    ) -> None:
        manifest: dict[str, object] = {
            "feature_id": "ws-gate-manifest-optional-demo",
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
        feature dir itself (its own work-tree, or non-git for AC-3) so the gate's
        delta probe runs against the staged history; the delta baseline defaults to
        `master`. The observable is the printed JSON's `verdict`/`reason` fields,
        the exit code, and the raw stdout.
        """
        argv = [
            "walking-skeleton-gate",
            "--feature-dir",
            str(feature_dir),
            "--repo-root",
            str(feature_dir),
        ]
        exit_code, out, _err = self._run_des_in_process(argv, cwd=feature_dir)
        return FloorVerdictObserved(
            verdict=self._verdict_from_exit(exit_code),
            reported_verdict_token=self._reported_token(out),
            reported_reason=self._reported_reason(out),
            exit_code=exit_code,
            raw_stdout=out,
        )

    # --- observable read-back (printed JSON, NOT the SUT) --------------------

    @staticmethod
    def _verdict_from_exit(exit_code: int) -> FloorVerdict:
        """The floor verdict the gate's exit code declares (gate CLI contract).

        Per `gate_outcome.py:67-74`: exit 0 = PASS/NOT_APPLICABLE, exit 1 = FAIL,
        exit 2 = usage fail-close (the HEAD behaviour on absent manifest the
        no-manifest branch must REPLACE), exit 3 = UNVERIFIED, exit 4 =
        INDETERMINATE.

        NOTE (DISTILL clarification surfaced to DESIGN/Ale): the feature-delta
        AC-3 names the LOUD refuse-to-decide as "INDETERMINATE (UNVERIFIED exit
        3)", but the EXISTING delta-compute path DDD-2 mandates reusing verbatim
        routes a git-undecidable delta to `GateOutcome.indeterminate()` ->
        `GateVerdict.INDETERMINATE` -> exit 4 (`walking_skeleton_gate.py:222-229`
        + `gate_outcome.py:73`). Both exit 3 and exit 4 are mapped to the same
        observable `FloorVerdict.INDETERMINATE` here so the AC-3 assertion is
        robust to whichever the ratified resolution chooses -- the LOUD
        refuse-to-decide is what the contract guarantees; the precise 3-vs-4 code
        is the open clarification. (The Then assertion checks the verdict is
        INDETERMINATE AND that the floor did NOT fail-close on absence.)
        """
        if exit_code == 0:
            return FloorVerdict.NOT_APPLICABLE
        if exit_code == 1:
            return FloorVerdict.FAIL
        if exit_code == 2:
            return FloorVerdict.FAIL_CLOSED
        if exit_code in (3, 4):
            return FloorVerdict.INDETERMINATE
        return FloorVerdict.OTHER

    @staticmethod
    def _reported_token(stdout: str) -> str:
        """The `verdict` token the gate prints in its single-line JSON."""
        payload = ManifestOptionalFloorComposition._last_json_object(stdout)
        verdict = payload.get("verdict") if payload is not None else None
        return str(verdict) if isinstance(verdict, str) else ""

    @staticmethod
    def _reported_reason(stdout: str) -> str:
        """The `reason`/`diagnostic` text the gate prints in its JSON.

        Returns whichever of `diagnostic`/`reason` is present so a single
        observable names the floor's stated cause. Empty when neither is present
        (never a swallowed parse).
        """
        payload = ManifestOptionalFloorComposition._last_json_object(stdout)
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

    @staticmethod
    def _run_des_in_process(argv: list[str], *, cwd: Path) -> tuple[int, str, str]:
        """In-process analogue of ``python -m des.cli.__main__ <argv...>``.

        Calls the production dispatcher EDGE directly. ABSOLUTE repo-`src/` is set
        on os.environ (NOT cwd-relative -- the gate's cwd is the per-test
        workspace) so any subprocess the gate forks resolves `des`; restored after.
        """
        prior_pythonpath = os.environ.get("PYTHONPATH")
        os.environ["PYTHONPATH"] = str(_REPO_SRC)
        try:
            return run_cli_in_process(argv, cwd=str(cwd))
        finally:
            if prior_pythonpath is None:
                os.environ.pop("PYTHONPATH", None)
            else:
                os.environ["PYTHONPATH"] = prior_pythonpath


__all__ = [
    "FloorVerdictObserved",
    "ManifestOptionalFloorComposition",
]
