"""Tests for lazy, typed install_nwave product-version resolution."""

from unittest.mock import patch

import pytest

from scripts.install.install_nwave import _get_version
from scripts.shared.version import ProductVersion, VersionResolutionError


class TestInstallerVersionResolution:
    """_get_version() returns a real identity or propagates typed refusal."""

    def test_unresolved_identity_is_never_replaced_by_a_sentinel(self):
        unresolved = VersionResolutionError(
            "WHAT: product identity could not be resolved\n"
            "WHY: no installed or source owner exists\n"
            "HOW: restore owning metadata"
        )

        with patch(
            "scripts.install.install_nwave.resolve_product_version",
            side_effect=unresolved,
        ):
            with pytest.raises(VersionResolutionError) as captured:
                _get_version()

        assert captured.value is unresolved

    def test_returns_resolved_product_version_without_changing_its_text(self):
        with patch(
            "scripts.install.install_nwave.resolve_product_version",
            return_value=ProductVersion.from_text("2.2.0"),
        ):
            assert _get_version() == "2.2.0"
