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


# The mvn binary name resolved at the head of the declared command.
_MVN_NAME = "mvn"

# The Java/Maven-specific remediation passed to `resolve_tool` -- NOT the
# shared cargo-flavoured default (SOSTITUZIONE fix: a Rust hint told a Java
# target to run `cargo install mvn`, which does not exist).
MAVEN_INSTALL_HINT = (
    "install a JDK plus Maven (e.g. via your OS package manager or "
    "https://maven.apache.org/install.html) and ensure mvn is on PATH"
)

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

    Thin delegator (fix-runner-scope-discover-dedup slice-03): supplies only
    mvn's own default binary / known locations / install hint / tool label /
    env builder to the SHARED ``scope_run.run_declared_scope``. ``resolve_tool``
    and ``subprocess`` are passed through BY REFERENCE (never called here) so
    a monkeypatch of ``java_runner.resolve_tool`` / ``java_runner.subprocess``
    (pre-existing pinned regressions) still takes effect: Python resolves
    those free variables from this module's own globals at call time.
    """
    return run_declared_scope(
        adapter,
        target_root,
        scoped_node_ids,
        base_dir=target_root,
        default_binary=_MVN_NAME,
        known_locations=JAVA_KNOWN_LOCATIONS,
        install_hint=MAVEN_INSTALL_HINT,
        tool_label="mvn",
        env_builder=env_with_tool_dir,
        resolve_tool_fn=resolve_tool,
        subprocess_module=subprocess,
    )


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


def discover_java_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``@Test``-attributed AT identities a Java regression file
    carries.

    Line/regex scan (no Java parser) for ``@Test``-attributed method names,
    tolerating an intervening annotation (e.g. ``@DisplayName(...)``) between
    ``@Test`` and the method declaration. Delegates to the SHARED
    ``at_discovery.discover_ats_by_regex`` (fix-runner-scope-discover-dedup),
    supplying only ``_JAVA_TEST_METHOD_RE`` and this language's own
    zero-found noun. Degrade-LOUD (``RunnerAdapterUnavailable``, never a
    silently-empty discovery) when the file cannot be read/decoded or has
    zero ``@Test`` methods.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    return discover_ats_by_regex(
        adapter, regression_test_file, _JAVA_TEST_METHOD_RE, "@Test methods"
    )


__all__ = [
    "JAVA_KNOWN_LOCATIONS",
    "discover_java_ats",
    "run_java_scope",
]
