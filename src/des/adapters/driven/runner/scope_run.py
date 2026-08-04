"""Shared declared-scope-run primitive (fix-runner-scope-discover-dedup, slice-03).

The ONE ``run_declared_scope`` shared primitive every per-language
``run_*_scope`` wrapper delegates to, matching the package convention set by
``at_discovery.py`` / ``tool_discovery.py`` / ``runner_json.py`` -- each one
narrow shared concern.

Consolidates the resolve-tool + shell + exit-code-mapping body previously
duplicated byte-identically (modulo the default binary name, the
``*_KNOWN_LOCATIONS`` tuple, the ``*_INSTALL_HINT`` string, the tool label in
the timeout/kill messages, and whether an ``env=`` kwarg is built) across
``go_runner.run_go_scope``, ``csharp_runner.run_csharp_scope``,
``java_runner.run_java_scope``, ``kotlin_runner.run_kotlin_scope``, and
``vitest_runner.run_vitest_scope``. ``cargo_runner.run_cargo_scope`` is
DELIBERATELY EXCLUDED: it carries its own exit-4/exit-94 empty-scope rows the
other five lack.

``base_dir`` is a REQUIRED keyword-only parameter (no default): kotlin's
``GRADLE_KNOWN_LOCATIONS`` carries the relative entry ``"."`` resolved
against ``target_root`` via ``resolve_tool``'s own ``base_dir`` argument -- a
shared helper defaulting ``base_dir`` to ``None`` would silently revert
gradlew discovery to CWD-relative and produce a false INDETERMINATE.

``env_builder`` is OPTIONAL (default ``None``): when supplied, the resolved
binary's own path is passed to it and the returned dict becomes
``subprocess.run``'s ``env=`` (go/java/csharp supply
``tool_discovery.env_with_tool_dir``); when omitted, ``env=None`` is passed,
which is ``subprocess.run``'s own default and therefore behaviourally
identical to omitting the kwarg entirely (kotlin/vitest's current shape).

``resolve_tool_fn`` / ``subprocess_module`` are OPTIONAL capability-injection
seams (default to the real ``tool_discovery.resolve_tool`` / stdlib
``subprocess``): each per-language wrapper passes its OWN module-level
``resolve_tool`` / ``subprocess`` bindings through explicitly (a REFERENCE,
never a call, so the wrapper's own source stays free of the shelling
primitives per the slice-03 no-duplication AT). This preserves two
PRE-EXISTING pinned regressions (``test_runner_env_with_tool_dir_helper_dedup``,
``test_polyglot_runners_timeout_bound``) that monkeypatch
``<language>_runner.resolve_tool`` / ``<language>_runner.subprocess`` directly
-- a patch on the WRAPPER module's own attribute must still take effect, which
requires the wrapper to look the name up from its own module globals at call
time (Python's free-variable resolution) rather than the delegate hard-binding
its own private copy.
"""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

from des.adapters.driven.runner.pytest_runner import (
    _signal_kill_reason,
    run_timeout_seconds,
)
from des.adapters.driven.runner.tool_discovery import resolve_tool
from des.ports.test_runner_port import RunnerAdapterUnavailable, RunVerdict


if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from pathlib import Path
    from types import ModuleType

    from des.adapters.driven.runner.tool_discovery import ToolResolution
    from des.ports.test_runner_port import RunnerAdapter


def run_declared_scope(
    adapter: RunnerAdapter,
    target_root: Path,
    scoped_node_ids: tuple[str, ...],
    *,
    base_dir: Path,
    default_binary: str,
    known_locations: Sequence[str],
    install_hint: str,
    tool_label: str,
    env_builder: Callable[[str], dict[str, str]] | None = None,
    resolve_tool_fn: Callable[..., ToolResolution] = resolve_tool,
    subprocess_module: ModuleType = subprocess,
) -> RunVerdict:
    """Shell the declared command in ``target_root``; map the exit code.

    ``scoped_node_ids`` carries the feature's declared ``test_command``
    tokens (the per-runner scope, NOT node-ids). The leading token is the
    binary resolved via the shared discovery scale (falling back to
    ``default_binary`` when ``scoped_node_ids`` is empty); the rest is the
    subcommand shelled as-is. Returns PASS/FAIL or raises
    ``RunnerAdapterUnavailable`` for the INDETERMINATE rows (tool-absent /
    timeout / OS-killed) -- naming ``tool_label`` and the caller's own
    ``install_hint``, never another language's.
    """
    binary = scoped_node_ids[0] if scoped_node_ids else default_binary
    subcommand = scoped_node_ids[1:]

    resolution = resolve_tool_fn(
        binary,
        known_locations,
        base_dir=base_dir,
        install_hint=install_hint,
    )
    if resolution.path is None:
        raise RunnerAdapterUnavailable(adapter.name, reason=resolution.remediation)

    env = env_builder(resolution.path) if env_builder is not None else None

    try:
        completed = subprocess_module.run(
            [resolution.path, *subcommand],
            capture_output=True,
            text=True,
            cwd=target_root,
            env=env,
            timeout=run_timeout_seconds(),
        )
    except subprocess_module.TimeoutExpired as exc:
        raise RunnerAdapterUnavailable(
            adapter.name,
            reason=(
                f"the {tool_label} command did not complete within "
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
                f"the {tool_label} run was killed by the OS ({kill_reason}), "
                "not a test failure -- INDETERMINATE, retry once memory/load "
                "recover"
            ),
        )

    return RunVerdict(passed=completed.returncode == 0, runner=adapter.name)


__all__ = ["run_declared_scope"]
