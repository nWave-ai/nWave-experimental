"""Milestone 3 bindings — restore preservation (S5)."""

from pytest_bdd import scenario


@scenario(
    "milestone-3-restore-preservation.feature",
    "After 11 successful installs, restore picks the most recent surviving backup",
)
def test_s5_restore_after_retention():
    pass
