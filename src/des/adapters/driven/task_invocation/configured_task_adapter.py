"""Config-selected provider dispatcher behind the unchanged invocation port."""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.driven.task_invocation.turn_recorder import TurnRecorder
from des.domain.model_runtime import ModelProvider, ModelRuntimeConfigError
from des.ports.driven_ports.task_invocation_port import ModelRun, TaskInvocationPort
from des.runtime.packaged_asset import installed_package_root


if TYPE_CHECKING:
    from pathlib import Path


class ModelRuntimeUnavailable(RuntimeError):
    """The chosen provider cannot be admitted before a model turn is spent."""


class ConfiguredTaskAdapter(TaskInvocationPort):
    """Resolve each role once and delegate to its configured provider adapter."""

    def __init__(self, root: Path, config: DESConfig | None = None) -> None:
        self._root = root
        self._framework_root = installed_package_root()
        self._config = config if config is not None else DESConfig(cwd=root)
        self._recorder = TurnRecorder(root=root)
        self._delegates: dict[tuple[ModelProvider, str], TaskInvocationPort] = {}

    def _delegate(self, role_id: str) -> TaskInvocationPort:
        runtime = self._config.role_runtime(
            role_id, framework_root=self._framework_root
        )
        key = (runtime.provider, runtime.model)
        if key in self._delegates:
            return self._delegates[key]
        if runtime.provider is ModelProvider.CLAUDE:
            from des.adapters.driven.task_invocation.claude_code_task_adapter import (
                ClaudeCodeTaskAdapter,
                resolve_launcher,
            )

            launcher = resolve_launcher()
            if launcher is None:
                raise ModelRuntimeUnavailable(
                    "configured claude launcher is unavailable"
                )
            delegate = ClaudeCodeTaskAdapter(
                launcher,
                model=runtime.model,
                recorder=self._recorder,
                record_root=self._root,
                framework_root=self._framework_root,
            )
        elif runtime.provider is ModelProvider.CODEX:
            from des.adapters.driven.task_invocation.codex_task_adapter import (
                CodexTaskAdapter,
                resolve_launcher,
            )

            launcher = resolve_launcher()
            if launcher is None:
                raise ModelRuntimeUnavailable(
                    "configured codex launcher is unavailable"
                )
            delegate = CodexTaskAdapter(
                launcher,
                model=runtime.model,
                recorder=self._recorder,
                record_root=self._root,
                framework_root=self._framework_root,
            )
        else:  # Enum makes this unreachable; retain a loud guard for future members.
            raise ModelRuntimeConfigError(
                f"unsupported configured provider {runtime.provider!r}"
            )
        self._delegates[key] = delegate
        return delegate

    def invoke(
        self,
        *,
        role_id: str,
        prompt: str,
        cwd: Path,
        max_product_values: int | None = None,
        defect_values: tuple[str, ...] = (),
    ) -> ModelRun:
        return self._delegate(role_id).invoke(
            role_id=role_id,
            prompt=prompt,
            cwd=cwd,
            max_product_values=max_product_values,
            defect_values=defect_values,
        )
