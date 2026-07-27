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

import hashlib
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


# The gradlew binary name resolved at the head of the declared command.
_GRADLEW_NAME = "gradlew"

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

    ``scoped_node_ids`` carries the feature's declared ``test_command`` tokens
    (the per-runner scope, NOT node-ids). The leading token is the gradlew
    binary resolved via the shared discovery scale; the rest is the subcommand
    shelled as-is. Returns PASS/FAIL or raises ``RunnerAdapterUnavailable`` for
    the single INDETERMINATE row (gradlew-absent). Unlike cargo there is NO
    exit-4 empty-scope row.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else _GRADLEW_NAME
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool(binary, GRADLE_KNOWN_LOCATIONS, base_dir=target_root)
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
                f"the gradlew command did not complete within "
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
                f"the gradlew run was killed by the OS ({kill_reason}), not a "
                "test failure -- INDETERMINATE, retry once memory/load recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


# ---------------------------------------------------------------------------
# Kotlin at-discovery facet (fix-rust-regression-at-kind-wiring pattern) --
# mirrors ``cargo_runner.discover_cargo_ats`` for ``@Test``-annotated Kotlin
# ``fun`` identities.
# ---------------------------------------------------------------------------

_KOTLIN_TEST_FN_RE = re.compile(
    r"@Test\b\s*(?:@[\w.]+(?:\([^)]*\))?\s*)*"
    r"(?:public\s+|private\s+|internal\s+|protected\s+)?fun\s+(\w+)"
)


def _strip_kotlin_line_comments(source: str) -> str:
    """Strip ``//``-to-EOL line comments before annotation matching.

    Minimal robust line-scan (no Kotlin parser, no block-comment / string-
    literal awareness -- deliberately out of scope): an ``@Test`` occurring
    only inside a ``//`` line comment is text, never a real Kotlin annotation,
    and must never satisfy ``_KOTLIN_TEST_FN_RE``. Newlines are preserved so
    multi-line annotation-then-``fun`` matching is unaffected.
    """
    return "\n".join(line.split("//", 1)[0] for line in source.splitlines())


def discover_kotlin_ats(
    adapter: RunnerAdapter,
    target_root: Path,
    regression_test_file: Path,
) -> AtDiscoveryResult:
    """Discover the ``@Test``-attributed AT identities a ``.kt`` regression
    file carries.

    Line/regex scan (no Kotlin parser, no Python ``ast`` on ``.kt`` source) for
    ``@Test``-attributed function names. Degrade-LOUD
    (``RunnerAdapterUnavailable``, never a silently-empty discovery) when the
    file cannot be read/decoded or has zero ``@Test`` functions.
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
    at_ids = _KOTLIN_TEST_FN_RE.findall(_strip_kotlin_line_comments(text))
    if not at_ids:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"zero @Test functions found in {regression_test_file} "
                "(malformed regression file)"
            ),
        )
    return AtDiscoveryResult(
        at_ids=tuple(at_ids), content_hash=hashlib.sha256(source).hexdigest()
    )


__all__ = [
    "GRADLE_KNOWN_LOCATIONS",
    "discover_kotlin_ats",
    "run_kotlin_scope",
]
