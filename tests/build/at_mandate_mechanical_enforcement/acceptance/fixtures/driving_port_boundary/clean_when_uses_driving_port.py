"""GOLDEN FIXTURE (clean corpus) — M1 driving-port-boundary gate.

This file is NOT a real test. It is the precision-half corpus the slice-01 gate
scans: a well-formed step file that the M1 rule MUST NOT flag
(``detect(...).flagged is False``). It contains the two near-miss shapes that a
naive scanner would over-fire on:

  1. A driven-adapter import at MODULE level (outside any ``@when`` body) — the
     rule is scoped to ``@when`` bodies ONLY, so this is legal.
  2. A driven-adapter import inside a ``@given`` body (a non-``@when`` step) —
     again out of scope; fixtures and Given-setup may touch adapters.

The ``@when`` step itself enters through the driving port (a composition-root
service), with no driven-adapter import in its body. The gate must approach
100% precision: a false-positive here would block a commit.
"""

# (1) MODULE-LEVEL driven-adapter import — legal, out of @when scope.
from pytest_bdd import given, when

from des.adapters.driven.logging.jsonl_audit_log_writer import (  # noqa: F401
    JsonlAuditLogWriter,
)


@given("a fresh installation environment")
def given_fresh_environment(run_state):
    # (2) driven-adapter import inside a @given body — legal, non-@when step.
    from des.adapters.driven.filesystem.real_filesystem import (  # noqa: F401
        RealFileSystem,
    )

    run_state["env"] = "fresh"


@when("the operator runs the install")
def when_operator_runs_the_install(run_state, composition):
    # Enters through the driving port (composition-root service) — no driven
    # adapter import in the body. The clean shape the gate must pass.
    run_state["result"] = composition.installer.install(run_state["env"])
