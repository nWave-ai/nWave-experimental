"""Resolve the one shipped DeliveryContract schema across supported layouts."""

from __future__ import annotations

from pathlib import Path


_SCHEMA_NAME = "thin-delivery-contract.schema.json"


def resolve_delivery_contract_schema_path() -> Path:
    """Resolve the schema in checkout, Claude-install, or wheel layout.

    The returned fallback preserves a deterministic diagnostic path when a
    broken distribution omitted the schema; callers still fail closed before
    trusting it.
    """
    here = Path(__file__).resolve()
    candidates = (
        here.parents[3] / "nWave" / "schemas" / _SCHEMA_NAME,
        here.parents[2] / "nWave" / "nWave" / "schemas" / _SCHEMA_NAME,
    )
    return next((path for path in candidates if path.is_file()), candidates[0])
