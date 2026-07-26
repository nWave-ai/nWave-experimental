"""
DES (Deterministic Execution System) - Post-execution validation and phase tracking.

This package provides deterministic validation hooks that fire when sub-agents complete
execution, ensuring phase progression is tracked accurately and deviations are detected.

Follows hexagonal architecture with:
  - Domain: Core business logic and entities
  - Application: Use cases and orchestration
  - Ports: Abstract interfaces (driver and driven)
  - Adapters: Concrete implementations (drivers and driven)

Core Components:
  - DESOrchestrator: Main DES coordination engine
  - TimeoutMonitor: Domain entity for timeout management
  - ConfigPort: Configuration abstractions
  - HookPort/ValidatorPort: Driver port abstractions
  - TemplateValidator: Driver implementations
  - EnvironmentConfigAdapter/InMemoryConfigAdapter: Driven implementations

For backward compatibility, this module re-exports all key classes and interfaces --
LAZILY (PEP 562). Importing ``des`` itself pulls in nothing but this module: a name is
resolved, and its layer imported, only when someone actually asks for it.

Why lazy matters here, measured 2026-07-25: the eager form cost 111ms on every
``import des.cli.dispatch`` (45ms of it the DRIVEN ADAPTERS, dragged in by the root
package alone) against a 30-40ms bare interpreter. Every ``des`` command paid it before
doing any work, and so did every test touching the package -- with a 55ms median test,
three CLI invocations were enough to push a test over one second. Re-exports written
"for backward compatibility" are a convenience; charging the whole system's import cost
to every caller of any part of it is not the price that convenience is worth.

It also restored the declared layering in the only way that matters at runtime: touching
the root package no longer loads filesystem/git/logging drivers, so the domain can be
used without dragging the edge in behind it.

New code should import from the specific layer packages:
  - from des.domain import TimeoutMonitor, TurnCounter
  - from des.application import DESOrchestrator, TemplateValidator
  - from des.ports.driver_ports import HookPort, ValidatorPort
  - from des.ports.driven_ports import ConfigPort, FileSystemPort, TimeProvider
  - from des.adapters.driven import EnvironmentConfigAdapter
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
    "DESOrchestrator": "des.application.orchestrator",
    "TDDPhaseValidator": "des.application.validator",
    "TemplateValidator": "des.application.validator",
    # Domain
    "TimeoutMonitor": "des.domain",
    "TurnCounter": "des.domain",
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
    "RealValidator": "TemplateValidator",
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
    from des.application.config_loader import ConfigLoader
    from des.application.invocation_limits_validator import (
        InvocationLimitsResult,
        InvocationLimitsValidator,
    )
    from des.application.orchestrator import DESOrchestrator
    from des.application.validator import TDDPhaseValidator, TemplateValidator
    from des.domain import TimeoutMonitor, TurnCounter
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
