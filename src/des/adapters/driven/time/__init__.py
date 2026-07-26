"""Time provider driven adapters."""

from des.adapters.driven.time.system_time import SystemTimeProvider


# Backward compatibility alias
SystemTime = SystemTimeProvider

__all__ = ["SystemTime", "SystemTimeProvider"]
