"""The vitest concrete run-adapter -- shells the target's vitest, maps exit codes.

ADR-RTR-001 (the run/read split, Principle 12). The JS/TS half of the run-facet
family: mirrors ``run_go_scope`` / ``run_cargo_scope`` -- shells the TARGET's own
``vitest`` over the feature's declared ``vitest run`` command and maps the vitest
exit code to a pass/fail/indeterminate verdict. ``vitest`` is the TARGET's tool
(subprocess), NEVER a nWave dependency -- stdlib + the resolved vitest binary
only.

``run_vitest_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading vitest binary via the SHARED ``resolve_tool`` discovery
   scale (a vitest in a project ``node_modules/.bin`` or a global npm bin off the
   hook PATH is USED via the known-location rung, never a false INDETERMINATE).
   Unresolvable after the full scale -> raise ``RunnerAdapterUnavailable`` naming
   the remediation (the LOUD INDETERMINATE channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("vitest", "run")``), NOT a node-id list. The
   leading token is the binary resolved in step 1; the rest is the subcommand
   shelled as-is (the adapter does NOT choose the subcommand -- the feature
   declares its driver, D5).
3. Shell the resolved vitest + the declared subcommand with ``cwd=target_root``.
4. Map the exit code:

   * exit 0       -> ``RunVerdict(passed=True)``   (PASS)
   * any non-zero -> ``RunVerdict(passed=False)``  (FAIL -- PROPAGATED, never
     swallowed into INDETERMINATE)

VITEST-vs-cargo (like go): there is NO cargo-style exit-4 NO_MATCH empty-scope
row. So vitest has only 0 -> PASS / non-zero -> FAIL; INDETERMINATE is reached
ONLY by an unresolvable vitest. NEVER a pytest fallback, NEVER a silent pass.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.runner.pytest_runner import (
    _signal_kill_reason,
    run_timeout_seconds,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.test_runner_port import RunnerAdapterUnavailable, RunVerdict


if TYPE_CHECKING:
    from des.ports.test_runner_port import RunnerAdapter


# The vitest binary name resolved at the head of the declared command.
_VITEST_NAME = "vitest"

# The known install locations vitest lives in off the hook PATH: the project's
# own ``node_modules/.bin``, the npm global bins, and the common system Node
# toolchain dirs. A vitest present here but absent from PATH is USED via the
# known-location rung, never a false INDETERMINATE.
VITEST_KNOWN_LOCATIONS: tuple[str, ...] = (
    "node_modules/.bin",
    str(Path.home() / ".npm-global" / "bin"),
    "/usr/local/bin",
    "/usr/lib/node_modules/.bin",
)

# The Node/vitest-specific remediations passed to `resolve_tool` -- NOT the
# shared cargo-flavoured default (SOSTITUZIONE fix: a Rust hint told a
# TypeScript target to run `cargo install vitest`, which does not exist).
# Public (not `_`-prefixed): reused by every caller sharing
# ``VITEST_KNOWN_LOCATIONS`` (the e2e runner, the contract-gate adapter, and
# the npm install/pack adapters resolving `npm` itself).
VITEST_INSTALL_HINT = (
    "install it via 'npm install' in the project (vitest is a devDependency) "
    "or 'npm install -g vitest'"
)
NPM_INSTALL_HINT = (
    "install Node.js (npm ships with it) via https://nodejs.org or your OS "
    "package manager"
)


def run_vitest_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared vitest command in ``target_root``; map the exit code.

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the vitest binary
    resolved via the shared discovery scale; the rest is the subcommand shelled
    as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for the single
    INDETERMINATE row (vitest-absent). Unlike cargo there is NO exit-4
    empty-scope row.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _VITEST_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(
        binary,
        VITEST_KNOWN_LOCATIONS,
        base_dir=target_root,
        install_hint=VITEST_INSTALL_HINT,
    )
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    try:
        completed = subprocess.run(
            [resolution.path, *subcommand],
            capture_output=True,
            text=True,
            cwd=target_root,
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the vitest command did not complete within "
                f"{run_timeout_seconds():.0f}s (a hanging/deadlocking run) -- "
                "INDETERMINATE, never a silent unbounded hang; raise "
                "NWAVE_GATE_RUN_TIMEOUT if this is a legitimate long run"
            ),
        ) from exc

    kill_reason = _signal_kill_reason(completed.returncode)
    if kill_reason is not None:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the vitest run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


__all__ = ["VITEST_KNOWN_LOCATIONS", "run_vitest_scope"]
