"""Test adapters (mocked implementations) for DES ports.

These are test-only mocked implementations for unit and integration testing,
and this package is their single canonical home. Doubles do not live under
src/des/adapters/ -- production code there implements ports for real.
"""

from tests.des.adapters.in_memory_filesystem import InMemoryFileSystem
from tests.des.adapters.mocked_time import MockedTimeProvider


__all__ = [
    "InMemoryFileSystem",
    "MockedTimeProvider",
]
