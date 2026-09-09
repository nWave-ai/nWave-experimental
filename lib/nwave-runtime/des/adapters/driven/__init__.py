"""
DES Driven Adapters - Secondary/Outbound adapter implementations.

Exports all driven adapter implementations for configuration, filesystem,
logging, task invocation, and time provision.
"""

from des.adapters.driven.config.environment_config_adapter import (
    EnvironmentConfigAdapter,
)
from des.adapters.driven.config.in_memory_config_adapter import (
    InMemoryConfigAdapter,
)
from des.adapters.driven.filesystem.real_filesystem import RealFileSystem
from des.adapters.driven.logging.silent_logger import SilentLogger
from des.adapters.driven.logging.structured_logger import StructuredLogger
from des.adapters.driven.task_invocation.claude_code_task_adapter import (
    ClaudeCodeTaskAdapter,
)
from des.adapters.driven.task_invocation.mocked_task_adapter import (
    MockedTaskAdapter,
)
from des.adapters.driven.time.system_time import SystemTimeProvider


# Backward compatibility aliases
RealFilesystem = RealFileSystem
SystemTime = SystemTimeProvider

__all__ = [
    # Task invocation adapters
    "ClaudeCodeTaskAdapter",
    # Config adapters
    "EnvironmentConfigAdapter",
    "InMemoryConfigAdapter",
    "MockedTaskAdapter",
    # Filesystem adapters
    "RealFileSystem",
    "RealFilesystem",  # Backward compatibility
    # Logging adapters
    "SilentLogger",
    "StructuredLogger",
    "SystemTime",  # Backward compatibility
    # Time adapters
    "SystemTimeProvider",
]
