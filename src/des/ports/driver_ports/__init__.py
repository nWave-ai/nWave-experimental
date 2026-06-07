"""
DES Driver Ports - Inbound/Primary port abstractions.

Exports all driver port interfaces (ports that DES exposes to callers).
"""

from des.ports.driven_ports.hook_port import HookPort
from des.ports.driver_ports.validator_port import ValidatorPort


# Note: HookPort is re-exported here for backward compatibility but
# canonically lives in des.ports.driven_ports.hook_port (it's a driven port).
__all__ = [
    "HookPort",
    "ValidatorPort",
]
