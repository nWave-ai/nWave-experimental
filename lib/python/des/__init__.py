"""DES runtime package.

The supported executable entry point is ``des.cli.__main__.main``.  The root
package keeps a small set of lazy compatibility exports for still-supported
domain, port, and adapter types; it no longer exposes the retired prompt
validator/orchestrator facade.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any


#: Public name -> the module that defines it. The ONE place a re-export is declared;
#: ``__all__`` below is derived from it plus the aliases, so a name can never be
#: exported without a home or given a home without being exported.
_EXPORTS: dict[str, str] = {
    # Driven adapters
    "ClaudeCodeTaskAdapter": "des.adapters.driven",
    "EnvironmentConfigAdapter": "des.adapters.driven",
    "InMemoryConfigAdapter": "des.adapters.driven",
    "MockedTaskAdapter": "des.adapters.driven",
    "RealFileSystem": "des.adapters.driven",
    "SilentLogger": "des.adapters.driven",
    "StructuredLogger": "des.adapters.driven",
    "SystemTimeProvider": "des.adapters.driven",
    # Application
    "ConfigLoader": "des.application.config_loader",
    "InvocationLimitsResult": "des.application.invocation_limits_validator",
    "InvocationLimitsValidator": "des.application.invocation_limits_validator",
    # Driven ports
    "ConfigPort": "des.ports.driven_ports",
    "FileSystemPort": "des.ports.driven_ports",
    "LoggingPort": "des.ports.driven_ports",
    "TaskInvocationPort": "des.ports.driven_ports",
    "TimeProvider": "des.ports.driven_ports",
    "HookPort": "des.ports.driven_ports.hook_port",
    # Driver ports
    "ValidatorPort": "des.ports.driver_ports",
}

#: Backward-compatibility aliases: old public name -> current export name. Resolved
#: through ``_EXPORTS`` too, so an alias cannot outlive the thing it aliases.
_ALIASES: dict[str, str] = {
    "RealFilesystem": "RealFileSystem",
    "SystemTime": "SystemTimeProvider",
}

__all__: list[str] = sorted([*_EXPORTS, *_ALIASES])

if TYPE_CHECKING:  # pragma: no cover - import-time cost is the whole point at runtime
    from des.adapters.driven import (
        ClaudeCodeTaskAdapter,
        EnvironmentConfigAdapter,
        InMemoryConfigAdapter,
        MockedTaskAdapter,
        RealFileSystem,
        SilentLogger,
        StructuredLogger,
        SystemTimeProvider,
    )
    from des.ports.driven_ports import (
        ConfigPort,
        FileSystemPort,
        LoggingPort,
        TaskInvocationPort,
        TimeProvider,
    )
    from des.ports.driven_ports.hook_port import HookPort
    from des.ports.driver_ports import ValidatorPort


def __getattr__(name: str) -> Any:
    """Resolve a re-exported name on first use (PEP 562).

    The AttributeError names what was asked for and where to look, because a lazy
    package that fails with a bare "module has no attribute" is harder to debug than
    the eager one it replaced.
    """
    target = _ALIASES.get(name, name)
    module_path = _EXPORTS.get(target)
    if module_path is None:
        raise AttributeError(
            f"module 'des' has no attribute {name!r}. The re-exported names are "
            f"{', '.join(__all__)}; anything else lives in its layer package "
            f"(des.domain / des.application / des.ports / des.adapters)."
        )
    value = getattr(importlib.import_module(module_path), target)
    globals()[name] = value  # resolve once, not on every attribute access
    return value


def __dir__() -> list[str]:
    """Keep tab-completion and ``dir(des)`` honest under lazy resolution."""
    return sorted([*globals().keys(), *__all__])
