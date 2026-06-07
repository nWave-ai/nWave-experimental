"""GOLDEN FIXTURE (unresolvable registry source) -- slice-03 loud-INDETERMINATE corpus.

language-adapter-registry-self-enforcement, slice-03 (DISTILL, per-slice JIT). An injected
``entry_points`` source carrying a single registered entry point whose target module/class
CANNOT be imported. When the conformance gate resolve-and-probes this source, the entry
point's ``.load()`` raises ``ModuleNotFoundError`` -- a GENUINE, real resolution failure (no
mock, no stub): the import is really attempted and really fails.

Per DDD-D5 the gate MUST degrade LOUDLY: emit the exit-3 INDETERMINATE lane with a distinct
loud message, NEVER a silent green and NEVER a fabricated empty discovery set. This corpus
is the falsifiable witness for that contract -- a gate that swallowed the resolution failure
and reported CONFORMANT (or an empty discovery -> vacuously conformant) would fail this
scenario.

The entry point points at a deliberately non-existent module (``nonexistent.module``) so the
resolution failure can never accidentally coincide with a real plugin.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint


# The unresolvable entry-point name the gate names in its loud INDETERMINATE signal.
UNRESOLVABLE_PLUGIN_ID = "ghost_unresolvable_plugin"


def unresolvable_entry_points() -> tuple[EntryPoint, ...]:
    """An injected ``entry_points`` source whose single member cannot be resolved.

    The member's value points at a non-existent module:class, so ``.load()`` raises
    ``ModuleNotFoundError`` -- the real resolution failure that drives the gate's exit-3
    loud INDETERMINATE lane.
    """
    return (
        EntryPoint(
            name=UNRESOLVABLE_PLUGIN_ID,
            value="nonexistent.module:GhostUnresolvableAdapter",
            group="nwave.lang.adapter",
        ),
    )
