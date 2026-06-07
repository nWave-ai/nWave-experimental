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

from pathlib import Path


__all__ = ["seed_dev_checkout_marker"]


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
