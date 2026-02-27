"""Backward-compatible re-export of JsonExecutionLogReader.

This module exists for backward compatibility. New code should import from
des.adapters.driven.hooks.json_execution_log_reader instead.
"""

from des.adapters.driven.hooks.json_execution_log_reader import (
    JsonExecutionLogReader,
)
from des.adapters.driven.hooks.json_execution_log_reader import (
    JsonExecutionLogReader as YamlExecutionLogReader,
)


__all__ = ["JsonExecutionLogReader", "YamlExecutionLogReader"]
