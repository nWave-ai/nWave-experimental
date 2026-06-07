"""GOLDEN FIXTURE (clean corpus) — M8 universe-bound-assertion gate.

This file is NOT a real test. It is the precision-half corpus the slice-03 gate
scans: a well-formed test suite the M8 rule MUST NOT flag
(``detect(...).flagged is False``). It contains the near-miss shapes a naive
scanner would over-fire on:

  1. A state-mutating test (``@mutates_state``) that DOES guard its mutation with
     ``assert_state_delta`` over PORT-OBSERVABLE names only (no ``_`` prefix) —
     the compliant shape; the gate must pass it.
  2. A READ-ONLY test (NO ``@mutates_state`` marker) with no guard — out of audit
     scope; a query test needs no universe guard, so the absence of
     ``assert_state_delta`` here is legal and must NOT be flagged.

The gate must approach 100% precision: a false-positive here would block a commit.
The ``mutates_state`` / ``assert_state_delta`` symbols below are stand-in domain
helpers so the corpus parses; the gate reads structure, not behaviour.
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

    def email_of(self, customer):
        return None


# (1) COMPLIANT: a state-mutating test guarded over port-observable names only.
@mutates_state
def test_operator_changes_email_guarded_over_observables():
    board = _AuditBoard()
    before = {"email": "old@x.it"}
    board.change_customer_email(customer=42, new_email="new@x.it")
    after = {"email": "new@x.it"}
    assert_state_delta(
        before=before,
        after=after,
        universe={"email", "audit_log.event_count"},
        expected={"email": "new@x.it"},
    )


# (2) READ-ONLY near-miss: no @mutates_state marker, so out of audit scope — the
# missing guard here is legal (a query test needs no universe guard).
def test_operator_reads_email_without_mutation():
    board = _AuditBoard()
    assert board.email_of(42) is None
