"""Shared test fixture: a FILLED expectation charter body.

Tests that need the commit-time examine gate ARMED write a charter under
``docs/product/expectations/{delivery_id}/*.md``. Since the gate decides on the
FILLED *property* rather than on the file's existence (GDP-8 --
``commit_slice._hollow_charter_refusal``, delegating to
``des verify-charter-filled``), a one-line stub like ``"# Charter\\n"`` no
longer arms anything: it is a hollow scaffold and is refused LOUDLY.

`filled_charter` renders the minimum body that genuinely satisfies the FILLED
contract -- a real ``## Preconditions`` start recipe plus an
``## Expected observations (oracle)`` section carrying >=1 ``Negative:`` line
-- so an arming fixture stays a one-liner at the call site.
"""

from __future__ import annotations


def filled_charter(intent: str) -> str:
    """A charter body that `des verify-charter-filled` judges FILLED.

    `intent` is the human sentence the fixture was already passing as its
    throwaway body (e.g. "Walk the checkout flow."); it becomes the charter's
    Intent, and the remaining judgment sections are filled with generic but
    REAL content -- no template placeholder tokens survive.
    """
    return (
        f"# {intent}\n"
        "ID: fixture-delivery · Persona: operator\n"
        "\n"
        "## Intent\n"
        f"{intent}\n"
        "\n"
        "## Preconditions\n"
        "cd into the tree under test and start the system from a clean "
        "checkout with no staged changes.\n"
        "\n"
        "## Charter\n"
        f"Explore the surface under test via the CLI to verify: {intent}\n"
        "\n"
        "## Expected observations (oracle)\n"
        "- The described outcome is observable on the real surface.\n"
        "- Negative: no error or refusal is emitted while walking it.\n"
        "\n"
        "## Session log (append-only)\n"
        "| date | examiner | verdict | observations |\n"
        "|------|----------|---------|--------------|\n"
    )
