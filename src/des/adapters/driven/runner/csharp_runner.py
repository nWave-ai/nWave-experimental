"""The C# concrete run-adapter -- shells the target's dotnet, maps exit codes.

ADR-RTR-001 C1. The C#/.NET half of the run/read split (Principle 12): mirrors
``run_go_scope`` / ``run_vitest_scope`` -- shells the TARGET's own ``dotnet``
over the feature's declared ``dotnet test`` command and maps the dotnet exit
code to a pass/fail/indeterminate verdict. ``dotnet`` is the TARGET's tool
(subprocess), NEVER a nWave dependency (D3) -- stdlib + the resolved dotnet
binary only.

``run_csharp_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading dotnet binary via the SHARED ``resolve_tool`` discovery
   scale (a dotnet in ``$DOTNET_ROOT`` / ``~/.dotnet`` / the common system
   install dirs off the hook PATH is USED via the known-location rung, never a
   false INDETERMINATE). Unresolvable after the full scale -> raise
   ``RunnerAdapterUnavailable`` naming the remediation (the LOUD INDETERMINATE
   channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("dotnet", "test")``), NOT a node-id list.
   The leading token is the binary resolved in step 1; the rest is the
   subcommand shelled as-is (the adapter does NOT choose the subcommand -- the
   feature declares its driver, D5).
3. Shell the resolved dotnet + the declared subcommand with ``cwd=target_root``
   and the resolved dotnet's directory prepended to a copied ``PATH``.
4. Map the exit code:

   * exit 0       -> ``RunVerdict(passed=True)``   (PASS)
   * any non-zero -> ``RunVerdict(passed=False)``  (FAIL -- PROPAGATED, never
     swallowed into INDETERMINATE)

C#-vs-cargo (like go/vitest): there is NO cargo-style exit-4 NO_MATCH
empty-scope row. So C# has only 0 -> PASS / non-zero -> FAIL; INDETERMINATE is
reached ONLY by an unresolvable dotnet. NEVER a pytest fallback, NEVER a
silent pass.

``discover_csharp_ats(adapter, target_root, regression_test_file) ->
AtDiscoveryResult``: the 4th facet-slot-pair (fix-rust-regression-at-kind-
wiring), mirroring ``discover_pytest_ats`` / ``discover_cargo_ats`` -- a
line/regex scan (no C# parser) for ``[Fact]``-attributed ``public void``
methods, degrading LOUD (``RunnerAdapterUnavailable``, never a silently-empty
discovery) on an unreadable/undecodable file or zero discovered [Fact]
methods.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.runner.at_discovery import discover_ats_by_regex
from des.adapters.driven.runner.scope_run import run_declared_scope
from des.adapters.driven.runner.tool_discovery import env_with_tool_dir, resolve_tool


if TYPE_CHECKING:
    from des.ports.test_runner_port import AtDiscoveryResult, RunnerAdapter, RunVerdict


# The dotnet binary name resolved at the head of the declared command.
_DOTNET_NAME = "dotnet"

# The .NET-specific remediation passed to `resolve_tool` -- NOT the shared
# cargo-flavoured default (SOSTITUZIONE fix: a Go/Rust hint told a C# target
# to run `cargo install dotnet`, which does not exist).
DOTNET_INSTALL_HINT = "install the .NET SDK via https://dotnet.microsoft.com/download"

# The known install locations dotnet lives in off the hook PATH: the env-derived
# ``$DOTNET_ROOT`` and the common system/user install dirs. A dotnet present here
# but absent from PATH is USED via the known-location rung, never a false
# INDETERMINATE.
_DOTNET_ROOT = os.environ.get("DOTNET_ROOT")
DOTNET_KNOWN_LOCATIONS: tuple[str, ...] = (
    *((_DOTNET_ROOT,) if _DOTNET_ROOT else ()),
    str(Path.home() / ".dotnet"),
    "/usr/share/dotnet",
    "/usr/local/share/dotnet",
)


def run_csharp_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared dotnet command in ``target_root``; map the exit code.

    Thin delegator (fix-runner-scope-discover-dedup slice-03): supplies only
    dotnet's own default binary / known locations / install hint / tool
    label / env builder to the SHARED ``scope_run.run_declared_scope``.
    ``resolve_tool`` and ``subprocess`` are passed through BY REFERENCE (never
    called here) so a monkeypatch of ``csharp_runner.resolve_tool`` /
    ``csharp_runner.subprocess`` (pre-existing pinned regressions) still takes
    effect: Python resolves those free variables from this module's own
    globals at call time.
    """
    return run_declared_scope(
        adapter,
        target_root,
        scoped_node_ids,
        base_dir=target_root,
        default_binary=_DOTNET_NAME,
        known_locations=DOTNET_KNOWN_LOCATIONS,
        install_hint=DOTNET_INSTALL_HINT,
        tool_label="dotnet",
        env_builder=env_with_tool_dir,
        resolve_tool_fn=resolve_tool,
        subprocess_module=subprocess,
    )


# ---------------------------------------------------------------------------
# C# at-discovery facet (fix-rust-regression-at-kind-wiring) -- mirrors
# ``discover_pytest_ats`` / ``discover_cargo_ats``: a line/regex scan (no C#
# parser) for ``[Fact]``-attributed ``public void`` method names.
# ---------------------------------------------------------------------------

_CSHARP_FACT_METHOD_RE = re.compile(
    r"\[Fact(?:\([^)]*\))?\]\s*"
    r"(?:\[[^\]]*\]\s*)*"
    r"public\s+(?:static\s+)?(?:async\s+)?void\s+(\w+)\s*\("
)


def discover_csharp_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``[Fact]``-attributed AT identities a C# regression file
    carries.

    Line/regex scan (no C# parser, no Python ``ast`` on ``.cs`` source) for
    ``[Fact]``-attributed ``public void`` method names. Delegates to the
    SHARED ``at_discovery.discover_ats_by_regex``
    (fix-runner-scope-discover-dedup), supplying only
    ``_CSHARP_FACT_METHOD_RE`` and this language's own zero-found noun.
    Degrade-LOUD (``RunnerAdapterUnavailable``, never a silently-empty
    discovery) when the file cannot be read/decoded or has zero ``[Fact]``
    methods.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    return discover_ats_by_regex(
        adapter, regression_test_file, _CSHARP_FACT_METHOD_RE, "[Fact] methods"
    )


__all__ = [
    "DOTNET_KNOWN_LOCATIONS",
    "discover_csharp_ats",
    "run_csharp_scope",
]
