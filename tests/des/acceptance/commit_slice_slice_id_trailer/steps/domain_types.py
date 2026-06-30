"""Domain types for the commit-slice-slice-id-trailer slice (C9).

Every domain noun used in the Gherkin is expressed once here as a typed NewType
or frozen value object (Mandate-15 / SSOT-via-types). Step bodies and the
composition root consume these typed parameters -- no raw ``str`` where a domain
type exists.

The two domain nouns this slice governs:

  * ``SliceId`` -- the carpaccio slice identity (``slice-NN``) that must reach the
    committed slice commit as a ``Slice-Id:`` trailer. It arrives either via the
    new ``--slice-id`` argument (AC-1 / AC-4) or already inlined in the message
    body (AC-2). Absent from both -> the commit is refused (AC-3).
  * ``CommitMessageBody`` -- the conventional-commit subject + body the caller
    hands ``des commit-slice --message``. It may or may not already carry a
    ``Slice-Id:`` trailer; the mechanical stamp is idempotent against one that
    does (AC-2).
"""

from __future__ import annotations

from typing import NewType


# A carpaccio slice identity (``slice-NN``) -- the value the Slice-Id: trailer
# must carry on the committed slice commit.
SliceId = NewType("SliceId", str)

# The commit message BODY handed to ``des commit-slice --message`` (subject +
# body, no Gate-Scope: trailer -- that is appended mechanically).
CommitMessageBody = NewType("CommitMessageBody", str)
