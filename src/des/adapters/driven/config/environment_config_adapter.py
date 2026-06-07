"""
EnvironmentConfigAdapter - production configuration implementation.

Reads configuration values from environment variables, with sensible
defaults for production environments.
"""

import os

from des.ports.driven_ports.config_port import ConfigPort


class EnvironmentConfigAdapter(ConfigPort):
    """
    Production configuration adapter that reads from environment variables.

    Provides fallback defaults when environment variables are not set,
    ensuring the system can operate even without explicit configuration.
    """

    def get_timeout_threshold_default(self) -> int:
        """
        Get timeout threshold default from environment or use fallback.

        Reads from DES_TIMEOUT_THRESHOLD_DEFAULT environment variable.

        Returns:
            int: Timeout threshold in seconds (from env or fallback of 600)
        """
        return int(os.environ.get("DES_TIMEOUT_THRESHOLD_DEFAULT", "600"))
