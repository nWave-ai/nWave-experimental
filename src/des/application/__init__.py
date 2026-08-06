"""DES application services.

Application modules are imported at their concrete module path.  This package
intentionally performs no eager re-exports, so importing a sibling service
does not revive retired facade dependencies.
"""

__all__: list[str] = []
