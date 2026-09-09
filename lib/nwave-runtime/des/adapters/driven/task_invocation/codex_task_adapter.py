"""Codex-local adapter for one governed model turn.

Semantic model output is read only from Codex's provider-enforced terminal
file. JSONL stdout is retained as provenance; it is never parsed as an answer.
"""

from __future__ import annotations

import json
import shutil
import stat
import tempfile
import time
from pathlib import Path
from typing import Any

from des.adapters.driven.task_invocation.model_envelope import (
    _schema_for,
    decode_model_run,
)
from des.adapters.driven.task_invocation.turn_recorder import TurnRecorder
from des.domain.agent_capability import ClaimRegister, resolve_declared_capability
from des.ports.driven_ports.task_invocation_port import (
    MalformedModelEnvelope,
    ModelOutcome,
    ModelRun,
    TaskInvocationPort,
)
from des.runtime.spawn import AGENT_TIMEOUT_ENV, SpawnTimeout, agent_timeout_seconds


_LAUNCHER_NAME = "codex"
_WRITE_CAPABILITIES = frozenset({"Edit", "Write"})
_SUPPORTED_CAPABILITIES = frozenset({"Read", "Glob", "Grep", "Bash", "Edit", "Write"})
# The local Codex protocol exposes these feature names. A role that declares
# no tools is admitted only with every tool-producing feature explicitly off;
# an unsupported flag then fails under ``--strict-config`` before a semantic
# answer is accepted.
_TOOL_FREE_FEATURES = (
    "apps",
    "browser_use",
    "browser_use_external",
    "browser_use_full_cdp_access",
    "shell_tool",
    "unified_exec",
    "code_mode",
    "code_mode_host",
    "code_mode_only",
    "computer_use",
    "multi_agent",
    "multi_agent_v2",
    "image_generation",
    "js_repl",
    "js_repl_tools_only",
    "plugins",
    "request_permissions_tool",
    "skill_search",
    "sleep_tool",
    "standalone_web_search",
    "view_image",
)
_TOOL_FREE_CLI_VERSION = "codex-cli 0.153.4"


def resolve_launcher() -> Path | None:
    """Return one admitted absolute Codex executable, or ``None``.

    Admission happens before the provider is issued; a caller can then refuse
    an unavailable selected provider without changing to Claude.
    """
    found = shutil.which(_LAUNCHER_NAME)
    if not found:
        return None
    launcher = Path(found)
    try:
        mode = launcher.lstat().st_mode
        if launcher.is_symlink():
            launcher = launcher.resolve(strict=True)
            mode = launcher.lstat().st_mode
    except OSError:
        return None
    return launcher if stat.S_ISREG(mode) else None


def _sandbox_for(declared_tools: tuple[str, ...]) -> str | None:
    """Project an admitted capability set to the strictest Codex sandbox.

    Codex's sandbox preserves the read/write boundary. An empty declared set
    is separately projected into every known tool feature set to false.
    """
    if not set(declared_tools).issubset(_SUPPORTED_CAPABILITIES):
        return None
    return (
        "workspace-write" if set(declared_tools) & _WRITE_CAPABILITIES else "read-only"
    )


def _tool_free_profile_is_current(launcher: Path, cwd: Path) -> bool:
    """Refuse an empty-tool role when the audited CLI profile has drifted."""
    from des.runtime.spawn import spawn

    try:
        version = spawn(
            [str(launcher), "--version"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=agent_timeout_seconds(),
            timeout_env=AGENT_TIMEOUT_ENV,
            reap_process_group=True,
        )
    except (OSError, SpawnTimeout):
        return False
    if version.returncode or version.stdout.strip() != _TOOL_FREE_CLI_VERSION:
        return False
    try:
        features = spawn(
            [str(launcher), "features", "list"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=agent_timeout_seconds(),
            timeout_env=AGENT_TIMEOUT_ENV,
            reap_process_group=True,
        )
    except (OSError, SpawnTimeout):
        return False
    if features.returncode:
        return False
    observed = {
        line.split(maxsplit=1)[0] for line in features.stdout.splitlines() if line
    }
    return set(_TOOL_FREE_FEATURES).issubset(observed)


def codex_schema_for(
    role_id: str,
    max_product_values: int | None = None,
    defect_values: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Project the semantic law into Codex strict nested-branch grammar.

    The semantic schema's top-level conditionals are not dropped: Codex gets a
    required ``answer`` object whose nested ``anyOf`` spells the accepting and
    non-accepting payload shapes. The adapter unwraps that software-owned
    projection before the shared decoder repeats the law for replayed bytes.
    """
    schema = json.loads(_schema_for(role_id, max_product_values, defect_values))

    def strictify(value: Any) -> Any:
        if isinstance(value, list):
            return [strictify(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {
            key: strictify(item)
            for key, item in value.items()
            # Codex strict schemas reject `uniqueItems`. The shared decoder
            # keeps the support-set law below this provider transport layer;
            # dropping the unsupported producer keyword must never turn a
            # duplicate into an accepted DesignFacts value.
            if key not in {"if", "then", "else", "uniqueItems"}
        }
        properties = result.get("properties")
        kind = result.get("type")
        is_object = kind == "object" or (isinstance(kind, list) and "object" in kind)
        if is_object and isinstance(properties, dict):
            result["required"] = list(properties)
            result["additionalProperties"] = False
        return result

    def merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
        merged = dict(base)
        for key, value in patch.items():
            current = merged.get(key)
            if isinstance(current, dict) and isinstance(value, dict):
                merged_value = merge(current, value)
                # A semantic conditional may narrow a union to null (for an
                # accepted crafter/reviewer). Its base enum contains the
                # non-accepting words and Codex rejects that incompatible
                # type/enum pair, so the narrowed branch must own its enum.
                if "type" in value and "enum" in current and "enum" not in value:
                    merged_value.pop("enum", None)
                merged[key] = merged_value
            else:
                merged[key] = value
        return merged

    condition = schema.pop("if")
    then = schema.pop("then")
    otherwise = schema.pop("else", {})
    rule = condition["properties"]["outcome"]
    true_outcomes = (rule["const"],) if "const" in rule else tuple(rule["enum"])
    false_outcomes = tuple(
        outcome.value for outcome in ModelOutcome if outcome.value not in true_outcomes
    )

    def branch(
        outcomes: tuple[str, ...], constraints: dict[str, Any]
    ) -> dict[str, Any]:
        result = merge(schema, constraints)
        properties = result["properties"]
        properties["outcome"] = (
            {"type": "string", "const": outcomes[0]}
            if len(outcomes) == 1
            else {"type": "string", "enum": list(outcomes)}
        )
        return strictify(result)

    return {
        "type": "object",
        "properties": {
            "answer": {
                "anyOf": [
                    *(branch((outcome,), then) for outcome in true_outcomes),
                    *(branch((outcome,), otherwise) for outcome in false_outcomes),
                ]
            }
        },
        "required": ["answer"],
        "additionalProperties": False,
    }


class CodexTaskAdapter(TaskInvocationPort):
    """Spawn one configured Codex role without a Claude compatibility layer."""

    def __init__(
        self,
        launcher: Path | None = None,
        *,
        model: str | None = None,
        recorder: TurnRecorder | None = None,
        record_root: Path | None = None,
        framework_root: Path | None = None,
    ) -> None:
        resolved = launcher if launcher is not None else resolve_launcher()
        if resolved is None:
            raise ValueError(
                f"no {_LAUNCHER_NAME} model launcher is resolvable on PATH"
            )
        self._launcher = Path(resolved)
        self._model = model
        self._framework_root = framework_root
        self._recorder = (
            recorder if recorder is not None else TurnRecorder(root=record_root)
        )

    @property
    def launcher(self) -> Path:
        return self._launcher

    @property
    def run_id(self) -> str:
        return self._recorder.run_id

    def argv_for(
        self,
        *,
        role_id: str,
        model: str,
        developer_instruction: str,
        sandbox: str,
        tool_free: bool,
        schema_path: Path,
        terminal_path: Path,
        cwd: Path,
    ) -> list[str]:
        """Build the complete admitted Codex argv; prompt travels on stdin."""
        argv = [
            str(self._launcher),
            "exec",
            "--strict-config",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            sandbox,
            "--model",
            model,
            "-c",
            "developer_instructions=" + json.dumps(developer_instruction),
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(terminal_path),
            "--json",
            "-C",
            str(cwd),
        ]
        if tool_free:
            # The source-blind workspace is deliberately a fresh private
            # directory rather than a repository.  Codex otherwise rejects
            # it before the sandbox/profile can be applied.
            argv.append("--skip-git-repo-check")
            # ``--ignore-user-config`` removes user MCP declarations. Keep an
            # explicit empty map as well so no configured server can widen a
            # declared empty capability set.
            argv.extend(("-c", "mcp_servers={}"))
            # ``web_search_request`` is deprecated and no longer turns the
            # default web surface off. This top-level control is the admitted
            # current Codex mechanism.
            argv.extend(("-c", 'web_search="disabled"'))
            # Verified config key: an empty-tool role is source blind, so no
            # ancestor AGENTS/project-doc bytes may enter its model context.
            argv.extend(("-c", "project_doc_max_bytes=0"))
            # Host-provided skill and orchestration surfaces are independent
            # of project documents and MCP. Disable them explicitly.
            argv.extend(("-c", "skills.include_instructions=false"))
            argv.extend(("-c", "orchestrator.skills.enabled=false"))
            argv.extend(("-c", "orchestrator.mcp.enabled=false"))
            argv.extend(("--disable", "memories"))
            argv.extend(("--enable", "skip_host_skill_discovery"))
            for feature in _TOOL_FREE_FEATURES:
                argv.extend(("--disable", feature))
        return argv

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        started_at = time.time()
        captured: dict[str, Any] = {"argv": None, "stdout": None, "stderr": None}
        try:
            run = self._run_turn(
                role_id=role_id,
                prompt=prompt,
                cwd=cwd,
                max_product_values=max_product_values,
                defect_values=defect_values,
                captured=captured,
            )
        except (MalformedModelEnvelope, OSError) as error:
            self._recorder.record(
                root=cwd,
                role_id=role_id,
                prompt=prompt,
                argv=captured["argv"],
                outcome=ModelOutcome.Indeterminate.value,
                diagnostic=f"{type(error).__name__}: {error}",
                exit_status=-1,
                retry_safe=False,
                provider_stdout=captured["stdout"],
                provider_stderr=captured["stderr"],
                started_at=started_at,
                ended_at=time.time(),
                raised=type(error).__name__,
            )
            raise
        self._recorder.record(
            root=cwd,
            role_id=role_id,
            prompt=prompt,
            argv=captured["argv"],
            outcome=run.outcome.value,
            diagnostic=run.diagnostic,
            exit_status=run.exit_status,
            retry_safe=run.retry_safe,
            provider_stdout=captured["stdout"],
            provider_stderr=captured["stderr"],
            started_at=started_at,
            ended_at=time.time(),
        )
        return run

    def _run_turn(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None,
        defect_values: tuple[str, ...],
        captured: dict[str, Any],
    ) -> ModelRun:
        from des.runtime.spawn import spawn

        capability = resolve_declared_capability(
            role_id, repo_root=cwd, framework_root=self._framework_root
        )
        if (
            capability.register is ClaimRegister.UNKNOWN
            or capability.spec_path is None
            or capability.declared_tools is None
        ):
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is missing, unreadable, or has no explicit tools",
                0,
                False,
                issued=False,
            )
        sandbox = _sandbox_for(capability.declared_tools)
        if sandbox is None:
            return ModelRun(
                ModelOutcome.Indeterminate,
                "selected Codex adapter cannot enforce this role's declared tools",
                0,
                True,
                issued=False,
            )
        if not capability.declared_tools and not _tool_free_profile_is_current(
            self._launcher, cwd
        ):
            return ModelRun(
                ModelOutcome.Indeterminate,
                "selected Codex tool-free profile differs from the audited CLI census",
                0,
                True,
                issued=False,
            )
        # A role's frontmatter still carries the historical Claude selection.
        # Codex may run only a runtime-selected Codex model; inheriting that
        # field would silently issue the wrong provider/model pair.
        model = self._model
        if not isinstance(model, str) or not model.strip():
            return ModelRun(
                ModelOutcome.Indeterminate,
                "selected Codex runtime has no declared model",
                0,
                True,
                issued=False,
            )
        try:
            developer_instruction = capability.spec_path.read_text(encoding="utf-8")
        except OSError:
            return ModelRun(
                ModelOutcome.Indeterminate,
                "agent specification is unreadable",
                0,
                False,
                issued=False,
            )
        # Resolve the role spec from the owning repository, but never make a
        # source-blind role inherit its AGENTS.md or other project context.
        # Its TurnRecorder remains anchored by ``invoke`` to that repository.
        private_dir = None if not capability.declared_tools else cwd
        with tempfile.TemporaryDirectory(
            prefix=".nwave-codex-", dir=private_dir
        ) as private:
            private_root = Path(private)
            execution_cwd = cwd
            if not capability.declared_tools:
                execution_cwd = private_root / "workspace"
                execution_cwd.mkdir()
            schema_path = private_root / "terminal-schema.json"
            terminal_path = private_root / "terminal.json"
            schema_path.write_text(
                json.dumps(
                    codex_schema_for(role_id, max_product_values, defect_values),
                    separators=(",", ":"),
                ),
                encoding="utf-8",
            )
            argv = self.argv_for(
                role_id=role_id,
                model=model,
                developer_instruction=developer_instruction,
                sandbox=sandbox,
                tool_free=not capability.declared_tools,
                schema_path=schema_path,
                terminal_path=terminal_path,
                cwd=execution_cwd,
            )
            captured["argv"] = argv
            try:
                completed = spawn(
                    argv,
                    input=prompt,
                    cwd=str(execution_cwd),
                    capture_output=True,
                    text=True,
                    timeout=agent_timeout_seconds(),
                    timeout_env=AGENT_TIMEOUT_ENV,
                    reap_process_group=True,
                )
            except SpawnTimeout as expired:
                captured["stdout"] = expired.captured_text
                return ModelRun(
                    ModelOutcome.Indeterminate,
                    f"provider bound fired: {expired.captured_text}",
                    -1,
                    False,
                )
            captured["stdout"] = completed.stdout
            captured["stderr"] = completed.stderr
            if completed.returncode:
                return ModelRun(
                    ModelOutcome.Indeterminate,
                    _provider_error_diagnostic(completed.stdout, completed.stderr),
                    int(completed.returncode),
                    False,
                )
            try:
                terminal = json.loads(terminal_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as error:
                raise MalformedModelEnvelope(
                    f"ModelEnvelopeTerminalFileMalformed: {error}"
                ) from None
            if not isinstance(terminal, dict):
                raise MalformedModelEnvelope(
                    "ModelEnvelopeTerminalFileNotObject: Codex terminal output is not an object"
                )
            structured = terminal.get("answer")
            if not isinstance(structured, dict) or set(terminal) != {"answer"}:
                raise MalformedModelEnvelope(
                    "ModelEnvelopeTerminalProjectionMalformed: Codex terminal output "
                    "does not carry exactly one answer object"
                )
            return decode_model_run(
                structured,
                role_id=role_id,
                max_product_values=max_product_values,
                defect_values=defect_values,
            )


def _provider_error_diagnostic(stdout: str, stderr: str) -> str:
    """Prefer Codex's native JSONL failure over generic process stderr.

    The selected string is preserved only as opaque terminal evidence; it never
    drives continuation or provider selection.
    """
    for line in reversed(stdout.splitlines()):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        message = event.get("message")
        if event.get("type") == "error" and isinstance(message, str):
            return message
        error = event.get("error")
        if (
            event.get("type") == "turn.failed"
            and isinstance(error, dict)
            and isinstance(error.get("message"), str)
        ):
            return error["message"]
    return stderr or stdout or "Codex exited without diagnostics"


__all__ = ["CodexTaskAdapter", "codex_schema_for", "resolve_launcher"]
