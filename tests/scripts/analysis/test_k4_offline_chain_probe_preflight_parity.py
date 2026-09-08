"""The offline probe may only name preflight symbols preflight still defines.

The defect this pins, measured 2026-09-05: `stage_shims` read
`k4_preflight._PERMISSION_CANARY_RESULT`, a constant `fd905f4cc`
("fix(k4): require real DES treatment evidence", 2026-09-04) deleted along
with `probe_delivery_permissions` and the whole `--settings` sandbox
rendering, which moved to `seed_auth._sandbox_settings()`. The probe was not
updated, so `offline_chain_probe --pairs 1` crashed at stage 1 of 8 with an
`AttributeError` -- and stage 1 is the gate that is supposed to run GREEN
before any paid campaign starts.

An import-time check cannot catch this: Python resolves a module attribute
at ACCESS time, so a dead name sits silent in the source until the branch
that reads it executes -- here, only inside a full probe run. Reading the
names statically out of the probe's own AST and resolving every one against
the live module moves the failure to a cheap test, and makes the NEXT
preflight deletion fail here instead of mid-campaign.

The AST is the source of truth deliberately: a runtime `dir()` diff would
only cover the names an executed path happened to touch.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.analysis.k4 import offline_chain_probe as probe
from scripts.analysis.k4 import preflight as k4_preflight


def _preflight_attributes_named_by_the_probe() -> set[str]:
    """Every `k4_preflight.<attr>` the probe's source reads."""
    tree = ast.parse(Path(probe.__file__).read_text(encoding="utf-8"))
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "k4_preflight"
    }


def test_the_probe_names_at_least_one_preflight_symbol():
    """Guards the guard: an empty set would make the parity test vacuous."""
    assert _preflight_attributes_named_by_the_probe()


def test_every_preflight_symbol_the_probe_names_exists():
    named = _preflight_attributes_named_by_the_probe()
    missing = sorted(name for name in named if not hasattr(k4_preflight, name))
    assert not missing, (
        f"the offline probe reads preflight attribute(s) {missing} that "
        "preflight no longer defines; the probe will die with AttributeError "
        "when the stage reading them runs"
    )
