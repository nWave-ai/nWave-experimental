"""Milestone 2 bindings — config overrides + validation (S4, S9)."""

from pytest_bdd import scenario


@scenario(
    "milestone-2-config-overrides.feature",
    "Marco sets the cap to 5 and the install enforces it",
)
def test_s4_cap_5():
    pass


@scenario(
    "milestone-2-config-overrides.feature",
    "Marco sets the cap to 1 and only the newest backup survives",
)
def test_s4_cap_1():
    pass


@scenario(
    "milestone-2-config-overrides.feature",
    "Marco sets the cap to 0 and every backup is removed after this install",
)
def test_s4_cap_0():
    pass


@scenario(
    "milestone-2-config-overrides.feature",
    "Negative cap value is rejected with a clear error before any backup is touched",
)
def test_s9_negative_cap_rejected():
    pass


@scenario(
    "milestone-2-config-overrides.feature",
    "Non-integer cap value is rejected with a clear error",
)
def test_s9_non_integer_cap_rejected():
    pass


@scenario(
    "milestone-2-config-overrides.feature",
    "Missing cap key falls back to the default of 10 silently",
)
def test_s9_missing_key_default():
    pass
