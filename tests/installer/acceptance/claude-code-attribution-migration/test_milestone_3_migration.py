"""Binder — legacy-hook migration (AC6)."""

from pytest_bdd import scenario


@scenario(
    "milestone-3-migration.feature",
    "Installing over a legacy hook retires it and enables the credit",
)
def test_migration_retires_legacy_hook():
    """AC6 — migration dismantles the legacy hook and records the enabled preference."""
