"""The go concrete run-adapter -- shells the target's go, maps exit codes.

ADR-RTR-001 C1. The go half of the run/read split (Principle 12): mirrors
``run_cargo_scope`` -- shells the TARGET's own ``go`` over the feature's declared
``go test`` command and maps the go exit code to a pass/fail/indeterminate
verdict. ``go`` is the TARGET's tool (subprocess), NEVER a nWave dependency (D3)
-- stdlib + the resolved go binary only.

``run_go_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading go binary via the SHARED ``resolve_tool`` discovery scale
   (a go in ``~/go/bin`` / ``$GOROOT/bin`` off the hook PATH is USED via the
   known-location rung, never a false INDETERMINATE). Unresolvable after the full
   scale -> raise ``RunnerAdapterUnavailable`` naming the remediation (the LOUD
   INDETERMINATE channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("go", "test", "./...")``), NOT a node-id list.
   The leading token is the binary resolved in step 1; the rest are the subcommand
   shelled as-is (the adapter does NOT choose the subcommand -- the feature
   declares its driver, D5).
3. Shell the resolved go + the declared subcommand with ``cwd=target_root`` and
   the resolved go's directory prepended to a copied ``PATH``.
4. Map the exit code:

   * exit 0                -> ``RunVerdict(passed=True)``   (PASS)
   * any non-zero          -> ``RunVerdict(passed=False)``  (FAIL -- PROPAGATED,
     never swallowed into INDETERMINATE)

GO-vs-cargo: ``go test`` exits 0 even with NO tests ("no test files") -- there is
NO cargo-style exit-4 NO_MATCH empty-scope row. So go has only 0 -> PASS /
non-zero -> FAIL; INDETERMINATE is reached ONLY by an unresolvable go. NEVER a
pytest fallback, NEVER a silent pass.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.runner.pytest_runner import _signal_kill_reason
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.test_runner_port import RunnerAdapterUnavailable, RunVerdict


if TYPE_CHECKING:
    from des.ports.test_runner_port import RunnerAdapter


# The go binary name resolved at the head of the declared command.
_GO_NAME = "go"

# The known install locations go lives in off the hook PATH: the env-derived
# ``$GOROOT/bin`` and ``$GOPATH/bin``, the rustup-analogue default ``~/go/bin``,
# and the common system toolchain dirs. A go present here but absent from PATH is
# USED via the known-location rung, never a false INDETERMINATE.
_GOROOT = os.environ.get("GOROOT")
_GOPATH = os.environ.get("GOPATH")
GO_KNOWN_LOCATIONS: tuple[str, ...] = (
    *((str(Path(_GOROOT) / "bin"),) if _GOROOT else ()),
    *((str(Path(_GOPATH) / "bin"),) if _GOPATH else ()),
    str(Path.home() / "go" / "bin"),
    "/usr/local/go/bin",
    "/usr/lib/go/bin",
)


def run_go_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared go command in ``target_root``; map the exit code.

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the go binary
    resolved via the shared discovery scale; the rest is the subcommand shelled
    as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for the single
    INDETERMINATE row (go-absent). Unlike cargo there is NO exit-4 empty-scope row.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _GO_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(binary, GO_KNOWN_LOCATIONS, base_dir=target_root)
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    completed = subprocess.run(
        [resolution.path, *subcommand],
        capture_output=True,
        text=True,
        cwd=target_root,
        env=_env_with_go_dir(resolution.path),
    )

    kill_reason = _signal_kill_reason(completed.returncode)
    if kill_reason is not None:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the go run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


def _env_with_go_dir(go_path: str) -> dict[str, str]:
    """A copied env with the resolved go's dir prepended to ``PATH``.

    So the shelled go finds its own toolchain siblings even when the resolved go
    was found off PATH (the known-location rung).
    """
    env = dict(os.environ)
    go_dir = str(Path(go_path).parent)
    existing = env.get("PATH", "")
    env["PATH"] = go_dir + os.pathsep + existing if existing else go_dir
    return env


__all__ = ["GO_KNOWN_LOCATIONS", "run_go_scope"]
