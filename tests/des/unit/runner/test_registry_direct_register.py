"""Regression: BUG C -- in-tree run-facets are DIRECT-registered, not entry-point-only.

`seed_runner_registry` registered `pytest` directly but `cargo-test` ONLY via
`nwave.lang.adapter` entry-point discovery. The shared `~/.claude/lib` install is
a sys.path INSERT, not a pip package -> no entry-points -> the discovery returns
empty -> `cargo-test` was never registered -> the gate degraded to
"no production-ready run-adapter for 'cargo-test'" on a Rust target (sister
tsunami's BUG C). Same class as BUG A (path-insert vs pip-package). Fix: the
in-tree run-facets (pytest + cargo) are direct-registered; entry-point discovery
stays ADDITIVE for external/paid plugins.
"""

from __future__ import annotations

from des.adapters.driven.runner import runner_registry as rr


def test_cargo_test_registered_without_entrypoints(monkeypatch):
    """BUG C: cargo-test must resolve after seed even when entry-points are EMPTY
    (the path-insert install scenario)."""
    rr.GLOBAL_REGISTRY._facets.clear()
    monkeypatch.setattr(rr.metadata, "entry_points", lambda **kw: [])  # no pip plugins
    rr.seed_runner_registry()
    assert rr.GLOBAL_REGISTRY.lookup("cargo-test") is not None, (
        "cargo-test must be DIRECT-registered (BUG C: not entry-point-only)"
    )
    assert rr.GLOBAL_REGISTRY.lookup("pytest") is not None


def test_entrypoint_discovery_stays_additive(monkeypatch):
    """A pip-installed plugin's register_adapters is STILL honored (additive)."""
    rr.GLOBAL_REGISTRY._facets.clear()

    class _FakePlugin:
        def register_adapters(self, registry) -> None:
            registry.register("fake-lang", lambda *a, **k: None)

    class _EP:
        def load(self):
            return _FakePlugin

    monkeypatch.setattr(rr.metadata, "entry_points", lambda **kw: [_EP()])
    rr.seed_runner_registry()
    assert rr.GLOBAL_REGISTRY.lookup("fake-lang") is not None  # plugin honored
    assert rr.GLOBAL_REGISTRY.lookup("cargo-test") is not None  # built-in still there
