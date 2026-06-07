"""GOLDEN FIXTURE (planted violation) — M1 driving-port-boundary gate.

This file is NOT a real test. It is the recall-half corpus the slice-01 gate
scans: a ``@when`` step function that imports a driven adapter inside its body.
The M1 rule MUST flag it (``detect(...).flagged is True``), naming the offending
function ``when_operator_runs_the_install`` and module
``des.adapters.driven.logging.jsonl_audit_log_writer``.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). Mirrors the dormant gate's own known-violation shape.
"""

from pytest_bdd import when


@when("the operator runs the install")
def when_operator_runs_the_install(run_state):
    # VIOLATION: a driving-port action reaching for a driven adapter directly.
    from des.adapters.driven.logging.jsonl_audit_log_writer import (
        JsonlAuditLogWriter,
    )

    run_state["writer"] = JsonlAuditLogWriter
