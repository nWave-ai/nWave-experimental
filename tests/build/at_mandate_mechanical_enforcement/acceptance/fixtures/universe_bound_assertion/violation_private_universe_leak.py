"""GOLDEN FIXTURE (planted violation — private leak) — M8 universe gate.

This file is NOT a real test. It is the recall-half corpus the slice-03 gate
scans: a state-mutating layer-1-3 test that DOES call ``assert_state_delta`` but
passes a private (``_``-prefixed) name into the ``universe=`` argument. The
private name ``_audit_rows`` couples the test to an internal mutation field — a
refactor rename would red the test for no functional reason. The M8 rule MUST
flag it (``detect(...).flagged is True``), naming the offending test
``test_operator_changes_email_leaking_private_field`` and the leaked field
``_audit_rows`` as a ``private_universe_leak`` breach.

The ``mutates_state`` / ``assert_state_delta`` symbols below are stand-in domain
helpers so the corpus parses; the gate reads structure (the ``universe=`` literal
names), not behaviour.
"""


def mutates_state(fn):
    """Stand-in marker decorator — designates a state-mutating test."""
    return fn


def assert_state_delta(before, after, universe, expected):
    """Stand-in universe-guard helper (signature only; the gate reads its call)."""
    return None


class _AuditBoard:
    def change_customer_email(self, customer, new_email):
        return None


@mutates_state
def test_operator_changes_email_leaking_private_field():
    board = _AuditBoard()
    before = {"email": "old@x.it"}
    board.change_customer_email(customer=42, new_email="new@x.it")
    after = {"email": "new@x.it"}
    # VIOLATION: the universe names a private (_-prefixed) internal field.
    assert_state_delta(
        before=before,
        after=after,
        universe={"email", "_audit_rows"},
        expected={"email": "new@x.it"},
    )
