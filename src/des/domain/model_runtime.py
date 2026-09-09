"""Typed provider/model selection for one DES role invocation.

The selected pair is deliberately atomic: a configuration tier either owns
both provider and model for a role/default, or it is invalid.  Selecting a
provider from one tier and a model from another would manufacture a runtime no
operator declared.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from des.domain.agent_capability import resolve_declared_capability


if TYPE_CHECKING:
    from pathlib import Path


class ModelProvider(str, Enum):
    CLAUDE = "claude"
    CODEX = "codex"


@dataclass(frozen=True, slots=True)
class RoleRuntime:
    provider: ModelProvider
    model: str


class ModelRuntimeConfigError(ValueError):
    """A present model-runtime declaration cannot safely select a provider."""


def _runtime(value: object, *, source: str) -> RoleRuntime:
    if not isinstance(value, dict):
        raise ModelRuntimeConfigError(
            f"{source} must be an object with provider and model"
        )
    if set(value) != {"provider", "model"}:
        raise ModelRuntimeConfigError(
            f"{source} must declare exactly provider and model as one atomic pair"
        )
    provider = value["provider"]
    model = value["model"]
    if not isinstance(provider, str):
        raise ModelRuntimeConfigError(f"{source}.provider must be claude or codex")
    try:
        selected_provider = ModelProvider(provider)
    except ValueError as exc:
        raise ModelRuntimeConfigError(
            f"{source}.provider must be claude or codex, got {provider!r}"
        ) from exc
    if not isinstance(model, str) or not model.strip():
        raise ModelRuntimeConfigError(f"{source}.model must be a non-empty string")
    return RoleRuntime(selected_provider, model)


def _declared(tier: dict[str, Any], *, role_id: str, source: str) -> RoleRuntime | None:
    if "model_runtime" not in tier:
        return None
    runtime = tier["model_runtime"]
    if not isinstance(runtime, dict):
        raise ModelRuntimeConfigError(f"{source}.model_runtime must be an object")
    unknown = set(runtime) - {"default", "roles"}
    if unknown:
        raise ModelRuntimeConfigError(
            f"{source}.model_runtime has unsupported keys {sorted(unknown)!r}"
        )
    roles = runtime.get("roles")
    if roles is not None and not isinstance(roles, dict):
        raise ModelRuntimeConfigError(f"{source}.model_runtime.roles must be an object")
    if isinstance(roles, dict) and role_id in roles:
        return _runtime(
            roles[role_id], source=f"{source}.model_runtime.roles[{role_id!r}]"
        )
    if "default" in runtime:
        return _runtime(runtime["default"], source=f"{source}.model_runtime.default")
    # A tier that declares only roles for other roles has no opinion here.
    return None


def resolve_role_runtime(
    role_id: str,
    *,
    global_tier: dict[str, Any],
    repo_tier: dict[str, Any],
    repo_root: Path,
    framework_root: Path | None = None,
) -> RoleRuntime:
    """Resolve one role with repo -> global -> declared-Claude precedence."""
    for tier, source in ((repo_tier, "repo config"), (global_tier, "global config")):
        selected = _declared(tier, role_id=role_id, source=source)
        if selected is not None:
            return selected
    declared = resolve_declared_capability(
        role_id, repo_root=repo_root, framework_root=framework_root
    ).declared_model
    if declared is None:
        raise ModelRuntimeConfigError(
            f"no model_runtime declaration and {role_id!r} declares no legacy Claude model"
        )
    return RoleRuntime(ModelProvider.CLAUDE, declared)
