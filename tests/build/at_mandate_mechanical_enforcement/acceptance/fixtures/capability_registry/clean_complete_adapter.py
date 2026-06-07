"""GOLDEN FIXTURE (clean / complete adapter) — capability-registry conformance.

This is NOT a real adapter the gates use; it is the precision-half corpus for
the slice-02 conformance check. It exposes a callable method for EVERY one of
the 9 required capabilities (ADR-TEST-002 D-C), so the registry MUST judge it
conformant against the full contract (``check_conformance(...).conformant is
True``, zero missing).

A registry that flags this complete adapter as non-conformant is over-firing —
the precision failure the clean fixture exists to catch. The method bodies are
irrelevant: conformance is structural (the method NAME is present + callable),
never behavioural.
"""

from __future__ import annotations


class CompleteFixtureAdapter:
    """Exposes every required capability by name — the conformant reference shape."""

    def functions_with_decorator(self, *args, **kwargs):
        return []

    def imports_in_function(self, *args, **kwargs):
        return []

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
