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

from des.adapters.driven.runner.scope_run import run_declared_scope
from des.adapters.driven.runner.tool_discovery import env_with_tool_dir, resolve_tool


if TYPE_CHECKING:
    from des.ports.test_runner_port import RunnerAdapter, RunVerdict


# The go binary name resolved at the head of the declared command.
_GO_NAME = "go"

# The Go-specific remediation passed to `resolve_tool` -- NOT the shared
# cargo-flavoured default (SOSTITUZIONE fix: a Rust hint told a Go target to
# run `cargo install go`, which does not exist).
GO_INSTALL_HINT = "install Go via https://go.dev/dl or your OS package manager"

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

    Thin delegator (fix-runner-scope-discover-dedup slice-03): supplies only
    go's own default binary / known locations / install hint / tool label /
    env builder to the SHARED ``scope_run.run_declared_scope``. ``resolve_tool``
    and ``subprocess`` are passed through BY REFERENCE (never called here) so
    a monkeypatch of ``go_runner.resolve_tool`` / ``go_runner.subprocess``
    (pre-existing pinned regressions) still takes effect: Python resolves
    those free variables from this module's own globals at call time.
    """
    return run_declared_scope(
        adapter,
        target_root,
        scoped_node_ids,
        base_dir=target_root,
        default_binary=_GO_NAME,
        known_locations=GO_KNOWN_LOCATIONS,
        install_hint=GO_INSTALL_HINT,
        tool_label="go",
        env_builder=env_with_tool_dir,
        resolve_tool_fn=resolve_tool,
        subprocess_module=subprocess,
    )


__all__ = ["GO_KNOWN_LOCATIONS", "run_go_scope"]
