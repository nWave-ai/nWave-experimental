"""The native child environment identity binds toolchain selectors, never credentials."""

from __future__ import annotations

import pytest

from des.application.delivery_continuation import DeliveryContinuationRunner


def _digest(env: dict[str, str]) -> str:
    return DeliveryContinuationRunner._child_environment_digest(env)


BASE = {"PATH": "/a", "CC": "c" * 40, "DOTNET_ROOT": "/sdk-a"}


@pytest.mark.parametrize(
    "changed",
    [
        {"PATH": "/b"},
        {"CC": "d" * 40},
        {"DOTNET_ROOT": "/sdk-b"},
        {"NODE_OPTIONS": "-r x"},
    ],
)
def test_a_toolchain_selector_change_changes_the_identity(
    changed: dict[str, str],
) -> None:
    assert _digest(BASE) != _digest({**BASE, **changed})


@pytest.mark.parametrize(
    "name",
    ["AZURE_DEVOPS_EXT_PAT", "GH_PAT", "PAT", "DEPLOY_TOKEN", "REGISTRY_PASSWORD"],
)
def test_a_rotated_credential_never_changes_the_identity(name: str) -> None:
    first = {**BASE, name: "a" * 52}
    assert _digest(first) == _digest({**BASE, name: "b" * 52})
