"""Typed domain vocabulary for the runtime-asset-tier fail-loud acceptance test.

SSOT-via-Types-Services-DSL mandate (criterion 1, canonical:
``nw-test-design-mandates``): the one domain noun the Gherkin of
``runtime-asset-tier-fail-loud.feature`` names explicitly is expressed here
once.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


AssetFamilyName = NewType("AssetFamilyName", str)

#: The asset family the scenarios exercise. Chosen because it is the family
#: the retracted `_install_des_data` duplicated to a second, reader-less
#: destination -- the concrete case that proves the shipping already worked.
DATA_FAMILY = AssetFamilyName("data")


class ShippingOutcome(Enum):
    """The three outcomes the contract must keep DISTINCT.

    The defect being guarded is precisely the collapse of ``NOT_APPLICABLE``
    and ``REFUSED`` onto one silent result, so they are separate members here
    rather than a bool plus a message.
    """

    SHIPPED = "shipped"
    NOT_APPLICABLE = "not-applicable"
    REFUSED = "refused"
