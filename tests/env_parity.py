"""Shared env-parity test helper — honest dev-checkout marker for CLI subprocesses.

Why this exists (F21 / RCA-#68 environment-coupling class):
``docs/analysis/rca-f21-environment-coupling-class-2026-05-21.md``.

Acceptance tests that drive a ``des*`` CLI **via subprocess** stage a synthetic
project workspace under ``tempfile.mkdtemp()`` / ``tmp_path`` and run the
subprocess with ``cwd`` pointed at that workspace. The unified ``des`` console
script pays an import-time runtime-freshness probe
(``src/des/runtime/freshness.py``). On the CLI path that probe is fail-closed by
design: with no install manifest beside the loaded ``des`` package it REFUSES
with ``exit 78`` (``EX_CONFIG``) BEFORE the CLI's own logic runs.

Under the repo ``.env`` (``NWAVE_FRESHNESS=skip``) the probe is disabled and the
subprocess runs — but that is the masked-green path the env-parity contract
forbids (commit only what passes under ``NWAVE_FRESHNESS=""``). The probe is
correct; the test environment is incomplete: the synthetic workspace is not a
real customer install, so the fail-closed customer-install refusal does not
apply to it.

The honest, non-masking fix is to make the workspace look like what it actually
is — a **developer checkout**. The freshness gate already has a first-class,
intentional signal for that: the ``.git/``-adjacency autoskip
(``freshness.py`` §"Developer-checkout auto-skip"), which emits a distinct
``des.runtime.freshness.autoskipped`` event (NOT the operator ``skipped`` event)
and lets the CLI proceed. Seeding an empty ``.git/`` directory in the workspace
the subprocess uses as ``cwd`` makes the probe correctly classify the workspace
as a dev checkout — exactly what a test fixture is — without disabling the gate,
without ``NWAVE_FRESHNESS=skip``, and without touching any assertion.

This is environment SETUP, not assertion-weakening: the subprocess now reaches
the CLI logic the test actually asserts on, under freshness ACTIVE.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


__all__ = ["seed_dev_checkout_marker", "seed_feature_delta_git_repo"]


def seed_feature_delta_git_repo(
    workspace_root: Path, *, ships_new_installable: bool
) -> Path:
    """Make ``workspace_root`` a REAL git repo whose ``master...HEAD`` delta is shaped.

    ``seed_dev_checkout_marker`` seeds only an empty ``.git/`` for the freshness
    autoskip — NOT a valid repo. The walking-skeleton gate computes its applicability
    from ``git diff --diff-filter=A --name-only master...HEAD`` (GitFeatureDeltaAdapter,
    base_ref defaults to ``master``): per ADR-098
    (``fix-feature-end-ws-gate-applicability``) a delta that adds a NEW installable
    (a ``pyproject.toml`` / ``setup.py`` root) with no walking-skeleton AT is a domain
    FAIL ("a no-AT installer feature cannot dodge"), while a delta that adds NO new
    installable is NOT_APPLICABLE (proceeds=True). Over an empty ``.git/`` the
    ``git diff`` fails (exit 129) → INDETERMINATE → the cycle REFUSES.

    A test that drives the cycle must therefore stage a repo where ``master...HEAD``
    has the ADR-098-correct shape for its scenario:

    - ``ships_new_installable=False`` (the gate-RUN / NA-pass path): commit every
      staged file (including any installable already present) on the ``master``
      baseline, then a single non-installable marker on the ``work`` branch →
      ``master...HEAD`` adds NO new installable → NOT_APPLICABLE → the cycle proceeds
      to the env-e2e / coverage-map legs (the SUT of slice-03 AT-1 / slice-04).
    - ``ships_new_installable=True`` (the fail-closed path, slice-03 AT-3): commit
      every staged file on ``master``, then ADD a new ``pyproject.toml`` root on
      ``work`` → ``master...HEAD`` adds a new installable with no WS AT → domain FAIL
      → the cycle reads the REAL gate FAIL and refuses (the anti-laundering SUT,
      now exercised through the ADR-098 invariant instead of the pre-ADR-098
      build-leg failure).

    Call AFTER all staging, immediately before driving ``des feature-end run``.
    Environment SETUP (a developer checkout IS a git repo with a delta), never
    assertion-weakening. Returns the root for chaining.
    """

    def _git(*args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=workspace_root,
            capture_output=True,
            text=True,
            check=False,
        )

    _git("init")
    _git("config", "user.email", "env-parity@nwave.test")
    _git("config", "user.name", "nWave Env Parity")
    # Baseline: every already-staged file (an ambient installable lands HERE, so it
    # is NOT a new addition in the delta). Then the delta on a `work` branch.
    _git("checkout", "-b", "master")
    _git("add", "-A")
    _git("commit", "--allow-empty", "--no-verify", "-m", "env-parity baseline")
    _git("checkout", "-b", "work")
    if ships_new_installable:
        # A NEW installable root in the delta → ships_installer_artifact + no WS AT
        # → domain FAIL (the ADR-098 "cannot dodge" invariant the AT-3 SUT pins).
        (workspace_root / "pyproject.toml").write_text(
            '[project]\nname = "env-parity-delta-installable"\nversion = "0.0.0"\n',
            encoding="utf-8",
        )
    else:
        # A non-installable marker → delta adds no new installable → NOT_APPLICABLE.
        (workspace_root / ".env-parity-delta").write_text("delta\n", encoding="utf-8")
    _git("add", "-A")
    _git("commit", "--no-verify", "-m", "env-parity feature delta")
    return workspace_root


def seed_dev_checkout_marker(workspace_root: Path) -> Path:
    """Seed an empty ``.git/`` in ``workspace_root`` to trigger the freshness autoskip.

    ``workspace_root`` MUST be the directory a ``des*`` CLI subprocess uses as
    its ``cwd`` (or an ancestor of it) — the freshness autoskip walks ``cwd``
    and its parents looking for ``.git/`` adjacency. Idempotent: a no-op when the
    marker already exists.

    Returns the workspace root for call-site chaining.
    """
    (workspace_root / ".git").mkdir(parents=True, exist_ok=True)
    return workspace_root
