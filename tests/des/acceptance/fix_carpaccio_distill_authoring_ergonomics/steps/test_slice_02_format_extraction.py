"""slice-02: the gate's format checks live in one shared place the pre-check reuses.

ADR-001. Layer 3 (subprocess / FS acceptance) -- the real `des
carpaccio-slice-gate` CLI is the driving port (Mandate-13). Example-only, no PBT
(Mandate 9/11).

RED on master: `des.cli.carpaccio_format` does not exist, so the
"shared format checks are available" Given records absence; the gate behaviour
is correct today (the existing untouched gate AT suite is the byte-identity
regression net), but these ATs additionally witness the shared module ships and
the gate draws on it. The AT reds on the shared-module-presence assertion.
"""

from __future__ import annotations

from pytest_bdd import scenarios, then

from .composition import CarpaccioErgonomicsComposition  # noqa: F401
from .steps_shared import *


scenarios("../slice-02-format-predicate-extraction.feature")


# slice-02-only Then: the shared format-checks module must actually ship. This
# step literal is declared ONCE (here) and used only by slice-02's two
# scenarios, so it does not collide with any slice-01/03 step (S1 PASS).
@then("the shared format checks resolve from a single reusable module")
def then_shared_format_checks_resolve(result_box: dict[str, object]) -> None:
    assert result_box.get("shared_format_available") is True, (
        "expected des.cli.carpaccio_format to ship as the shared format-checks "
        "module the gate and pre-check both reuse (ADR-001); it is absent"
    )
