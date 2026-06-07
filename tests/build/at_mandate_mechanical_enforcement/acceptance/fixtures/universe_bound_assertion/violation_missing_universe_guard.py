"""GOLDEN FIXTURE (planted violation — missing guard) — M8 universe gate.

This file is NOT a real test. It is the recall-half corpus the slice-03 gate
scans: a state-mutating layer-1-3 test (carrying the ``@mutates_state`` marker)
that mutates observable state but NEVER calls ``assert_state_delta`` to guard it.
The M8 rule MUST flag it (``detect(...).flagged is True``), naming the offending
test ``test_operator_changes_email_without_guard`` as a ``missing_assert`` breach.

A gate that cannot flag this planted violation is itself testing-theater
(ADR-TEST-002 D-E). The unguarded mutation can silently pass against a
wired-but-broken seam — exactly the assertion-free-test smell the mandate exists
to catch.

The ``mutates_state`` / ``change_customer_email`` symbols below are stand-in
domain helpers so the corpus parses; the gate reads structure, not behaviour.
"""


def mutates_state(fn):
    """Stand-in marker decorator — designates a state-mutating test."""
    return fn


class _AuditBoard:
    def change_customer_email(self, customer, new_email):
        return None

    def email_of(self, customer):
        return None


@mutates_state
def test_operator_changes_email_without_guard():
    # VIOLATION: a state-mutating test with NO assert_state_delta universe guard.
    board = _AuditBoard()
    board.change_customer_email(customer=42, new_email="new@x.it")
    assert board.email_of(42) == "new@x.it"
