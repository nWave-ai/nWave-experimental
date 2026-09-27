from __future__ import annotations

import pytest

from des.domain.invocation_reference import InvocationReference


def test_formula_contains_only_sealed_identity_and_location() -> None:
    reference = InvocationReference(
        role_id="nw-acceptance-designer",
        artifact_path=".nwave/des/logs/roles/value-1-input.json",
        artifact_sha256="a" * 64,
    )

    assert reference.formula() == (
        "DES-TASK-REFERENCE role=nw-acceptance-designer "
        "path=.nwave/des/logs/roles/value-1-input.json sha256=" + "a" * 64
    )


@pytest.mark.parametrize(
    ("artifact_path", "digest"),
    [
        ("/absolute/input.json", "a" * 64),
        (".nwave/../input.json", "a" * 64),
        (".nwave/input.json", "A" * 64),
    ],
)
def test_invalid_reference_is_refused_before_provider_launch(
    artifact_path: str, digest: str
) -> None:
    with pytest.raises(ValueError):
        InvocationReference("nw-role", artifact_path, digest)
