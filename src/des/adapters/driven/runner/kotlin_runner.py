"""The Kotlin/Gradle concrete run-adapter -- shells the target's gradlew, maps
exit codes, and discovers the @Test-annotated ATs a Kotlin regression file
carries.

Slice-01 of kotlin-test-runner-adapter (ADR-RTR-001 C1 + the pytest/cargo
AT-discovery facet pair, fix-rust-regression-at-kind-wiring). Mirrors
``go_runner.run_go_scope`` -- shells the TARGET's own ``gradlew`` over the
feature's declared ``gradlew test`` command and maps the exit code to a
pass/fail/indeterminate verdict. ``gradlew`` is the TARGET's tool (subprocess),
NEVER a nWave dependency (D3) -- stdlib + the resolved gradlew binary only.

``run_kotlin_scope(adapter, target_root, scoped_node_ids) -> RunVerdict``:

1. Resolve the leading gradlew binary via the SHARED ``resolve_tool`` discovery
   scale (a project-local ``<target_root>/gradlew`` wrapper off the hook PATH is
   USED via the known-location rung, never a false INDETERMINATE). Unresolvable
   after the full scale -> raise ``RunnerAdapterUnavailable`` naming the
   remediation (the LOUD INDETERMINATE channel, never a silent pass).
2. The per-runner "scope" IS the feature's declared ``test_command`` tokens
   (``scoped_node_ids`` -- e.g. ``("gradlew", "test")``), NOT a node-id list.
   The leading token is the binary resolved in step 1; the rest is the
   subcommand shelled as-is (the adapter does NOT choose the subcommand -- the
   feature declares it, D5).
3. Shell the resolved gradlew + the declared subcommand with ``cwd=target_root``.
4. Map the exit code:

   * exit 0       -> ``RunVerdict(passed=True)``   (PASS)
   * any non-zero -> ``RunVerdict(passed=False)``  (FAIL -- PROPAGATED, never
     swallowed into INDETERMINATE)

GRADLE-vs-cargo (like go/vitest): there is NO cargo-style exit-4 NO_MATCH
empty-scope row. So Kotlin has only 0 -> PASS / non-zero -> FAIL; INDETERMINATE
is reached ONLY by an unresolvable gradlew. NEVER a pytest fallback, NEVER a
silent pass.

``discover_kotlin_ats(adapter, target_root, regression_test_file) ->
AtDiscoveryResult``: mirrors ``discover_cargo_ats`` -- a line/regex scan (no
Kotlin parser) for ``@Test``-annotated ``fun`` identities, degrading LOUD
(``RunnerAdapterUnavailable``, never a silently-empty discovery) when the file
cannot be read/decoded or declares zero ``@Test`` functions.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from des.adapters.driven.runner.at_discovery import discover_ats_by_regex
from des.adapters.driven.runner.scope_run import run_declared_scope
from des.adapters.driven.runner.tool_discovery import resolve_tool


if TYPE_CHECKING:
    from des.ports.test_runner_port import AtDiscoveryResult, RunnerAdapter, RunVerdict


# The gradlew binary name resolved at the head of the declared command.
_GRADLEW_NAME = "gradlew"

# The Kotlin/Gradle-specific remediation passed to `resolve_tool` -- NOT the
# shared cargo-flavoured default (SOSTITUZIONE fix: a Rust hint told a Kotlin
# target to run `cargo install gradlew`, which does not exist).
GRADLE_INSTALL_HINT = (
    "./gradlew is a per-project wrapper script that is GENERATED, not "
    "installed: run `gradle wrapper` inside the target repo, bootstrapping "
    "from a system Gradle (https://gradle.org/install)"
)

# The known install locations gradlew lives in off the hook PATH: the
# project-local wrapper script (``.`` resolved against ``target_root`` via
# ``base_dir``, the standard Gradle-wrapper convention) and the common Gradle
# distribution/toolchain dirs. A gradlew present here but absent from PATH is
# USED via the known-location rung, never a false INDETERMINATE.
GRADLE_KNOWN_LOCATIONS: tuple[str, ...] = (
    ".",
    str(Path.home() / ".gradle" / "wrapper" / "dists"),
    "/usr/local/bin",
)


def run_kotlin_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
) -> RunVerdict:
    """Shell the declared gradlew command in ``target_root``; map the exit code.

    Thin delegator (fix-runner-scope-discover-dedup slice-03): supplies only
    gradlew's own default binary / known locations / install hint / tool
    label to the SHARED ``scope_run.run_declared_scope`` (no env builder --
    kotlin never builds one, mirroring its current behaviour byte-for-byte).
    ``resolve_tool`` and ``subprocess`` are passed through BY REFERENCE (never
    called here) so a monkeypatch of ``kotlin_runner.resolve_tool`` /
    ``kotlin_runner.subprocess`` (pre-existing pinned regressions) still takes
    effect: Python resolves those free variables from this module's own
    globals at call time.
    """
    return run_declared_scope(
        adapter,
        target_root,
        scoped_node_ids,
        base_dir=target_root,
        default_binary=_GRADLEW_NAME,
        known_locations=GRADLE_KNOWN_LOCATIONS,
        install_hint=GRADLE_INSTALL_HINT,
        tool_label="gradlew",
        resolve_tool_fn=resolve_tool,
        subprocess_module=subprocess,
    )


# ---------------------------------------------------------------------------
# Kotlin at-discovery facet (fix-rust-regression-at-kind-wiring pattern) --
# mirrors ``cargo_runner.discover_cargo_ats`` for ``@Test``-annotated Kotlin
# ``fun`` identities.
# ---------------------------------------------------------------------------

_KOTLIN_TEST_FN_RE = re.compile(
    r"@Test\b\s*(?:@[\w.]+(?:\([^)]*\))?\s*)*"
    r"(?:public\s+|private\s+|internal\s+|protected\s+)?fun\s+(\w+)"
)


def discover_kotlin_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``@Test``-attributed AT identities a ``.kt`` regression
    file carries.

    Line/regex scan (no Kotlin parser, no Python ``ast`` on ``.kt`` source) for
    ``@Test``-attributed function names. Delegates to the SHARED
    ``at_discovery.discover_ats_by_regex`` (fix-runner-scope-discover-dedup),
    supplying only ``_KOTLIN_TEST_FN_RE`` and this language's own zero-found
    noun. Degrade-LOUD (``RunnerAdapterUnavailable``, never a silently-empty
    discovery) when the file cannot be read/decoded or has zero ``@Test``
    functions.
    """
    del target_root  # unused: AT-discovery scopes to the ONE declared file
    return discover_ats_by_regex(
        adapter, regression_test_file, _KOTLIN_TEST_FN_RE, "@Test functions"
    )


__all__ = [
    "GRADLE_KNOWN_LOCATIONS",
    "discover_kotlin_ats",
    "run_kotlin_scope",
]
