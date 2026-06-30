"""Shared test helper — robust ``des*`` driving-port command resolution.

Why this exists (stale-global-shim fragility class):

Acceptance tests that drive a ``des*`` CLI via ``subprocess.run`` resolve the
command with ``shutil.which("<shim>")`` and fall back to ``python -m
des.cli.<module>`` only when ``which`` returns ``None``. That logic silently
PREFERS a ``which``-resolved console-script **without checking it works**.

On a machine with a STALE global install (e.g. an old ``uv tool install
nwave-ai`` whose interpreter cannot ``import des``), ``which`` finds the shim,
the helper prefers it, and every subprocess raises
``ModuleNotFoundError: No module named 'des'`` — failing a test of the DES
integrity LOGIC for an entirely unrelated environment reason.

The robust contract: prefer the ``which``-resolved shim ONLY after probing that
it actually runs (``--help`` returns 0 AND no ``ModuleNotFoundError`` in
stderr); otherwise fall back to the in-interpreter ``python -m`` form, which
runs against whatever interpreter (project ``.venv``) is executing the tests.
The fallback is the same one the helpers always had — this only stops a broken
shim from shadowing it.
"""

from __future__ import annotations

# des:allow-module-form: this helper IS the legacy-shim driving-port resolver;
# the `des-{shim}` / `python -m des.cli.<X>` tokens here are its OWN parameter
# domain (docstring examples + the fallback it constructs), not migratable
# callsites -- P3-sanctioned per the rescoped single-entry-point migration gate
# (docs/feature/single-entry-point/feature-delta.md slice-04, AT-07/AT-08).
import shutil
import subprocess
import sys


def resolve_des_cli_cmd(shim_name: str, module: str) -> list[str]:
    """Resolve a ``des*`` driving-port command robustly.

    Prefer the installed console-script ``shim_name`` ONLY when a ``--help``
    probe proves it runs; otherwise fall back to
    ``[sys.executable, "-m", module]``.

    Args:
        shim_name: console-script name on PATH (e.g. ``"des-verify-integrity"``).
        module: dotted module path for the ``python -m`` fallback
            (e.g. ``"des.cli.verify_deliver_integrity"``).
    """
    bin_path = shutil.which(shim_name)
    if bin_path and _shim_runs(bin_path):
        return [bin_path]
    return [sys.executable, "-m", module]


def _shim_runs(bin_path: str) -> bool:
    """True iff the resolved shim executes ``--help`` cleanly.

    A stale/broken global shim (wrong interpreter, cannot ``import des``) fails
    this probe — returncode != 0 or ``ModuleNotFoundError`` in stderr — and the
    caller falls back to the ``python -m`` form.
    """
    try:
        probe = subprocess.run(
            [bin_path, "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0 and "ModuleNotFoundError" not in probe.stderr
