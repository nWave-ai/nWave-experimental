"""Turn limit configuration by task type.

Business Value: Enables fine-grained control over execution duration per task complexity.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TurnLimitConfig:
    """Typed SSOT value object for task type-specific turn limits.

    Provides turn limits tailored to task complexity:
    - quick: Short-running tasks (e.g., schema validation)
    - standard: Normal development tasks (e.g., feature implementation)
    - complex: Long-running tasks (e.g., architectural refactoring)

    Loaded and validated by ``des.application.config_loader.ConfigLoader``,
    which is the single configuration loader for DES turn limits and sources
    its canonical defaults from ``src/des/config/des_defaults.yaml``.
    """

    quick: int
    standard: int
    complex: int

    def get_limit_for_type(self, task_type: str) -> int:
        """Retrieve turn limit for specified task type.

        Args:
            task_type: Task complexity classification (quick, standard, complex)

        Returns:
            Turn limit for task type. Defaults to standard if type unknown.
        """
        limit_map = {
            "quick": self.quick,
            "standard": self.standard,
            "complex": self.complex,
        }
        return limit_map.get(task_type, self.standard)
