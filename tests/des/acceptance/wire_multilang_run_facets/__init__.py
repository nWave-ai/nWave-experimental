"""Acceptance package: wire-multilang-run-facets (epic consolidation-for-wider-beta-testing).

Closes C13 + C14 (demoted by the adversarial swarm 2026-06-24 as catalogued != wired):
the Go run-facet ``run_go_scope`` and the JS/TS run-facet ``run_vitest_scope`` EXIST and
are correct, but ``seed_runner_registry`` registers ONLY ``pytest`` + ``cargo-test`` -- so
the PRODUCTION dispatch ``RunnerAdapter("go-test").run()`` / ``RunnerAdapter("vitest").run()``
looks the token up in ``GLOBAL_REGISTRY``, finds None, and raises ``RunnerAdapterUnavailable``
WITHOUT ever reaching the run-facet.

These ATs drive the PRODUCTION REGISTRY DISPATCH (``seed_runner_registry()`` +
``GLOBAL_REGISTRY.lookup(token)`` + ``RunnerAdapter(token).run(...)``), NOT a direct
child-interpreter import of the run-facet (that bypass is exactly the theater the swarm
flagged). The wiring is proven, not just the isolated function.
"""
