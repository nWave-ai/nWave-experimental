"""Per-runner concrete adapters behind ``TestRunnerPort.run`` (the run facet).

The port (``des.ports.test_runner_port``) resolves WHICH runner a target uses by
filesystem lockfile inspection and exposes the abstract ``RunnerAdapter.run``
contract. The concrete adapters here SHELL the target's own runner over a scoped
node-id set and map the exit code to a pass/fail verdict -- the only effect in
the run facet (effect-isolation, Principle 12).

Only the ``pytest`` dogfood adapter is production-ready in
``f-spine-runs-tests-not-git-hooks`` (DDD-7); other recognized runners
resolve-and-degrade-LOUD (``RunnerAdapterUnavailable`` -> INDETERMINATE), never a
silent pass and never a pytest fallback on a non-Python target.
"""
