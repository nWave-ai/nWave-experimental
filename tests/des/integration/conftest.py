"""pytest configuration and fixtures for DES integration tests."""

from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def _silence_probe_integration(request):
    """Silence substrate probe in integration tests that don't test probe behavior.

    Prevents real run_probe() from emitting advisory output that would
    corrupt stdout assertions in session_start_handler integration tests.

    Tests marked with @pytest.mark.probe_test opt out and patch run_probe
    themselves to verify probe advisory output.
    """
    if request.node.get_closest_marker("probe_test"):
        yield
        return
    with patch(
        "des.adapters.drivers.hooks.session_start_handler.run_probe",
        return_value="",
    ):
        yield
