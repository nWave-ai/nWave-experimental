"""pytest-bdd binding for slice-02-language-adapter-plugin-abc.

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and imports the slice-02 step vocabulary. No business
logic here.

Mandate-13 (driving-port-only, CRITICAL P0): the imports are vocabulary-only
(pytest-bdd scenarios + slice-02 common step decorators). ZERO direct
production-module imports.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .slice02_common_steps import *


scenarios("../slice-02-language-adapter-plugin-abc.feature")
