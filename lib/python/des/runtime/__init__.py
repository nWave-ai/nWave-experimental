"""des.runtime — cross-cutting runtime utilities for the des package.

A plain utility package (peer to domain/, application/, ports/, adapters/),
NOT a hexagonal layer. Domain and application code MUST NOT import it; only
adapters/ and cli/ may. See
docs/feature/fix-des-runtime-interpreter-boundary/feature-delta.md §1.
"""
