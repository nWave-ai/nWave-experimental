"""The Java (Maven) concrete run-adapter -- shells the target's mvn, maps exit codes.

ADR-RTR-001 C1. The Java half of the run/read split (Principle 12): mirrors
``run_go_scope`` -- shells the TARGET's own ``mvn`` over the feature's declared
``mvn test`` command and maps the mvn exit code to a pass/fail/indeterminate
verdict. ``mvn`` is the TARGET's tool (subprocess), NEVER a nWave dependency
(D3) -- stdlib + the resolved mvn binary only.

``run_java_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading mvn binary via the SHARED ``resolve_tool`` discovery
   scale (an mvn in ``$MAVEN_HOME/bin`` / ``$M2_HOME/bin`` off the hook PATH is
   USED via the known-location rung, never a false INDETERMINATE). Unresolvable
   after the full scale -> raise ``RunnerAdapterUnavailable`` naming the
   remediation (the LOUD INDETERMINATE channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("mvn", "test")``), NOT a node-id list. The
   leading token is the binary resolved in step 1; the rest is the subcommand
   shelled as-is (the adapter does NOT choose the subcommand -- the feature
   declares its driver, D5).
3. Shell the resolved mvn + the declared subcommand with ``cwd=target_root``
   and the resolved mvn's directory prepended to a copied ``PATH``.
4. Map the exit code:

   * exit 0       -> ``RunVerdict(passed=True)``   (PASS)
   * any non-zero -> ``RunVerdict(passed=False)``  (FAIL -- PROPAGATED, never
     swallowed into INDETERMINATE)

JAVA-vs-cargo (like go): ``mvn test`` exits 0 even with NO test files -- there
is NO cargo-style exit-4 NO_MATCH empty-scope row. So Java has only 0 -> PASS /
non-zero -> FAIL; INDETERMINATE is reached ONLY by an unresolvable mvn. NEVER
a pytest fallback, NEVER a silent pass.

``discover_java_ats(adapter, target_root, regression_test_file) ->
AtDiscoveryResult``:

Mirrors ``discover_pytest_ats``/``discover_cargo_ats``: a line/regex scan (no
Java parser) for ``@Test``-attributed method names, tolerating an intervening
annotation (e.g. ``@DisplayName(...)``) between ``@Test`` and the method
declaration. Degrade-LOUD (``RunnerAdapterUnavailable``, never a silently-empty
discovery) on an unreadable/undecodable file or zero discovered ``@Test``
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


# The mvn binary name resolved at the head of the declared command.
_MVN_NAME = "mvn"

# The known install locations mvn lives in off the hook PATH: the env-derived
# ``$MAVEN_HOME/bin`` / ``$M2_HOME/bin`` and the common system toolchain dirs.
# An mvn present here but absent from PATH is USED via the known-location
# rung, never a false INDETERMINATE.
_MAVEN_HOME = os.environ.get("MAVEN_HOME")
_M2_HOME = os.environ.get("M2_HOME")
JAVA_KNOWN_LOCATIONS: tuple[str, ...] = (
    *((str(Path(_MAVEN_HOME) / "bin"),) if _MAVEN_HOME else ()),
    *((str(Path(_M2_HOME) / "bin"),) if _M2_HOME else ()),
    "/usr/share/maven/bin",
    "/opt/maven/bin",
    "/usr/local/maven/bin",
)


def run_java_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared mvn command in ``target_root``; map the exit code.

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the mvn binary
    resolved via the shared discovery scale; the rest is the subcommand
    shelled as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for
    the single INDETERMINATE row (mvn-absent). Unlike cargo there is NO exit-4
    empty-scope row.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _MVN_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(binary, JAVA_KNOWN_LOCATIONS, base_dir=target_root)
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    try:
        completed = subprocess.run(
            [resolution.path, *subcommand],
            capture_output=True,
            text=True,
            cwd=target_root,
            env=_env_with_mvn_dir(resolution.path),
            timeout=run_timeout_seconds(),
        )
    except subprocess.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the mvn command did not complete within "
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
                f"the mvn run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


def _env_with_mvn_dir(mvn_path: str) -> dict[str, str]:
    """A copied env with the resolved mvn's dir prepended to ``PATH``.

    So the shelled mvn finds its own toolchain siblings even when the resolved
    mvn was found off PATH (the known-location rung).
    """
    env = dict(os.environ)
    mvn_dir = str(Path(mvn_path).parent)
    existing = env.get("PATH", "")
    env["PATH"] = mvn_dir + os.pathsep + existing if existing else mvn_dir
    return env


# ---------------------------------------------------------------------------
# Java AT-discovery facet -- mirrors discover_pytest_ats/discover_cargo_ats:
# scans a regression file's raw bytes for @Test-attributed method names and
# seals them with a sha256 content hash.
# ---------------------------------------------------------------------------

_JAVA_TEST_METHOD_RE = re.compile(
    r"@Test\b"
    r"(?:\s+@[A-Za-z_][\w.]*(?:\([^)]*\))?)*"
    r"\s+(?:(?:public|private|protected|static|final)\s+)*"
    r"\w+\s+(\w+)\s*\("
)


def _strip_java_line_comments(source: str) -> str:
    """Strip ``//``-to-EOL line comments before annotation matching.

    Minimal robust line-scan (no Java parser, no block-comment / string-
    literal awareness -- deliberately out of scope): an ``@Test`` occurring
    only inside a ``//`` line comment is text, never a real Java annotation,
    and must never satisfy ``_JAVA_TEST_METHOD_RE``. Newlines are preserved so
    multi-line annotation-then-method matching is unaffected.
    """
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def discover_java_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``@Test``-attributed AT identities a Java regression file
    carries.

    Line/regex scan (no Java parser) for ``@Test``-attributed method names,
    tolerating an intervening annotation (e.g. ``@DisplayName(...)``) between
    ``@Test`` and the method declaration. Degrade-LOUD
    (``RunnerAdapterUnavailable``, never a silently-empty discovery) when the
    file cannot be read/decoded or has zero ``@Test`` methods.
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
    at_ids = _JAVA_TEST_METHOD_RE.findall(_strip_java_line_comments(text))
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero @Test methods found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = [
    "JAVA_KNOWN_LOCATIONS",
    "discover_java_ats",
    "run_java_scope",
]
