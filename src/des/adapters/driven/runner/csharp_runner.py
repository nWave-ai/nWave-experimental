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

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.runner.pytest_runner import (
    _signal_kill_reason,
    run_timeout_seconds,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.test_runner_port import (
    AtDiscoveryResult,
    RunnerAdapterUnavailable,
    RunVerdict,
)


if TYPE_CHECKING:
    from des.ports.test_runner_port import RunnerAdapter


# The dotnet binary name resolved at the head of the declared command.
_DOTNET_NAME = "dotnet"

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

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the dotnet
    binary resolved via the shared discovery scale; the rest is the subcommand
    shelled as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for
    the single INDETERMINATE row (dotnet-absent). Unlike cargo there is NO
    exit-4 empty-scope row.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _DOTNET_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(binary, DOTNET_KNOWN_LOCATIONS, base_dir=target_root)
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    try:
        completed = subprocess.run(
            [resolution.path, *subcommand],
            capture_output=True,
            text=True,
            cwd=target_root,
            env=_env_with_dotnet_dir(resolution.path),
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the dotnet command did not complete within "
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
                f"the dotnet run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


def _env_with_dotnet_dir(dotnet_path: str) -> dict[str, str]:
    """A copied env with the resolved dotnet's dir prepended to ``PATH``.

    So the shelled dotnet finds its own toolchain siblings even when the
    resolved dotnet was found off PATH (the known-location rung).
    """
    env = dict(os.environ)
    dotnet_dir = str(Path(dotnet_path).parent)
    existing = env.get("PATH", "")
    env["PATH"] = dotnet_dir + os.pathsep + existing if existing else dotnet_dir
    return env


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


def _strip_csharp_line_comments(source: str) -> str:
    """Strip ``//``-to-EOL line comments before attribute matching.

    Minimal robust line-scan (no C# parser, no block-comment / string-literal
    awareness -- deliberately out of scope): a ``[Fact]`` occurring only
    inside a ``//`` line comment is text, never a real C# attribute, and must
    never satisfy ``_CSHARP_FACT_METHOD_RE``. Newlines are preserved so
    multi-line attribute-then-method matching is unaffected.
    """
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def discover_csharp_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``[Fact]``-attributed AT identities a C# regression file
    carries.

    Line/regex scan (no C# parser, no Python ``ast`` on ``.cs`` source) for
    ``[Fact]``-attributed ``public void`` method names. Degrade-LOUD
    (``RunnerAdapterUnavailable``, never a silently-empty discovery) when the
    file cannot be read/decoded or has zero ``[Fact]`` methods.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    try:
        source = regression_test_file.read_bytes()
    except OSError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name, reason=f"cannot read {regression_test_file}: {exc}"
        ) from exc
    try:
        text = source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"cannot read/decode {regression_test_file}: malformed "
                f"(not valid UTF-8): {exc}"
            ),
        ) from exc
    at_ids = _CSHARP_FACT_METHOD_RE.findall(_strip_csharp_line_comments(text))
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero [Fact] methods found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = [
    "DOTNET_KNOWN_LOCATIONS",
    "discover_csharp_ats",
    "run_csharp_scope",
]
