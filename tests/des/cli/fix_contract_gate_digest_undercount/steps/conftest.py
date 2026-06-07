"""Shared fixtures for the contract-gate digest-undercount slice-01 ATs."""

from __future__ import annotations

import pytest

from .composition import ContractGateDigestComposition


@pytest.fixture
def composition(tmp_path):
    return ContractGateDigestComposition(tmp_path)
