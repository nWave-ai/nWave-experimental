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

**Stale-but-passing-shadowing gap (2026-07-20, see
`docs/product/expectations/bugfix-shutil-which-des-fragility/`):** the
original ``--help``-probes-cleanly check (``_shim_runs``) does NOT catch a
stale global that still runs — e.g. an older nWave install missing only a
*newer* subcommand, not `des` itself. Its ``--help`` exits 0 and never prints
``ModuleNotFoundError``, so it PASSES the probe and silently shadows the
correct, currently-active venv build whenever it is first on PATH. Confirmed
independently in ``WorktreeCleanupFixture.run_sweep_subprocess`` (commit
``1e05a7bda``/``c2d7f5e44``): a PATH-first resolution order cannot distinguish
"runs" from "is the RIGHT build".

The robust contract: resolve the ACTIVE venv's OWN console-script first —
``Path(sys.executable).parent / shim_name`` — never consulting PATH at all.
This is immune to shadowing by *any* other ``shim_name`` reachable earlier on
PATH, stale-but-running or outright broken, because PATH is never even
queried when the running venv itself built the shim. Only when the active
venv does NOT build this shim (e.g. no console-script entry for it) does
resolution fall back to the previous ``shutil.which`` + ``_shim_runs`` probe —
preserving the legitimate no-venv / global-only case. The final fallback
remains the in-interpreter ``python -m`` form, which runs against whatever
interpreter (project ``.venv``) is executing the tests.
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
from pathlib import Path


def resolve_des_cli_cmd(shim_name: str, module: str) -> list[str]:
    """Resolve a ``des*`` driving-port command robustly.

    Resolution order:

    1. The ACTIVE venv's own ``shim_name`` console-script, resolved from
       ``sys.executable``'s own ``bin``/``Scripts`` directory — never PATH.
       Preferred whenever it exists AND a ``--help`` probe proves it runs.
       PATH is not even consulted in this branch, so a stale-but-running
       global shim earlier on PATH can never shadow it.
    2. The PATH-resolved ``shim_name`` (``shutil.which``) — ONLY reached when
       the active venv does not build this shim at all — preferred when a
       ``--help`` probe proves it runs. Preserves the legitimate no-venv /
       global-only case.
    3. ``[sys.executable, "-m", module]``.

    Args:
        shim_name: console-script name on PATH (e.g. ``"des-verify-integrity"``).
        module: dotted module path for the ``python -m`` fallback
            (e.g. ``"des.cli.verify_deliver_integrity"``).
    """
    venv_shim = Path(sys.executable).parent / shim_name
    if venv_shim.exists() and _shim_runs(str(venv_shim)):
        return [str(venv_shim)]
    bin_path = shutil.which(shim_name)
    if bin_path and _shim_runs(bin_path):
        return [bin_path]
    return [sys.executable, "-m", module]


def _shim_runs(bin_path: str) -> bool:
    """True iff the resolved shim executes ``--help`` cleanly.

    A stale/broken shim (wrong interpreter, cannot ``import des``) fails this
    probe — returncode != 0 or ``ModuleNotFoundError`` in stderr — and the
    caller falls back to its next resolution step.

    Note: this probe alone cannot distinguish a stale-but-partially-working
    build (passes ``--help``, missing only a newer subcommand) from a
    genuinely correct one — that distinction is ``resolve_des_cli_cmd``'s job
    (the venv-first resolution order above), not this probe's.
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
