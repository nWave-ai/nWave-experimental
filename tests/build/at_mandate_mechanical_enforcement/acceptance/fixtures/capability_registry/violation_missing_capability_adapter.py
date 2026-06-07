"""GOLDEN FIXTURE (planted gap / non-conformant adapter) — capability-registry.

This is NOT a real adapter the gates use; it is the recall-half corpus for the
slice-02 conformance check. It deliberately OMITS exactly one required
capability — ``imports_in_function`` (``PLANTED_MISSING_CAPABILITY`` in
``domain_types``) — while implementing every other required capability.

The registry MUST flag it as non-conformant (``check_conformance(...).conformant
is False``) and MUST name the single missing capability so a new-language
implementer sees exactly what is left to build. A registry that cannot detect
this planted gap is itself testing-theater (ADR-TEST-002 D-E) — the very disease
it exists to detect one level down.
"""

from __future__ import annotations


class MissingCapabilityFixtureAdapter:
    """Implements every required capability EXCEPT ``imports_in_function``."""

    def functions_with_decorator(self, *args, **kwargs):
        return []

    # GAP: ``imports_in_function`` deliberately absent — the planted recall case.

    def imports_in_module(self, *args, **kwargs):
        return []

    def calls_in_function(self, *args, **kwargs):
        return []

    def marker_decorators(self, *args, **kwargs):
        return []

    def spawn_shape_in_body(self, *args, **kwargs):
        return None

    def keyword_arg_names(self, *args, **kwargs):
        return []

    def assignments_constructing_type(self, *args, **kwargs):
        return []

    def layer_of_file(self, *args, **kwargs):
        return None
