"""Domain types for the gate-trailer-read-seam-a-indeterminate slice-01 ATs.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw `str` where a domain enum exists.

Bounded context: the repurposed verify-commit-trailers CLI's seam-A git-read
path (DESIGN Driving Surface table). The verifier either CANNOT-EVALUATE the
commit body (git absent / SHA unresolvable -> LOUD INDETERMINATE, exit 7) or
audits the ledger record via the carpaccio gate logic (exit 0 approved /
exit 45 rejected). Post-read conditions: exit 4 (legacy tampering slot),
exit 6 (malformed).

EXIT-CODE LOCKED DECISION (DESIGN authority, feature-delta.md §Exit-Code
Collision): exit 7 is INDETERMINATE (cannot-evaluate / git-absence class).
Exit 4 is the legacy tampering slot (distinct from exit 7, used only for the
non-conflation assertion). Exit 6 remains malformed-trailer (post-read
condition, distinct from exit 7). All three are STRUCTURALLY DISTINCT; the
non-conflation AT asserts this explicitly.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class CommitEnvironment(str, Enum):
    """The git readability environment in which the verifier is invoked.

    The seam-A port degrade must fire LOUD on every cannot-evaluate condition.
    Each enum value exercises one materially-distinct decision-table row.

    GIT_BINARY_ABSENT -- the git binary is masked off PATH. subprocess.run
                         raises FileNotFoundError before any git process starts.
                         LOUD INDETERMINATE, exit 7.

    SHA_UNRESOLVABLE  -- git binary present, directory is a git work-tree, but
                         the requested SHA does not exist in the repo history.
                         git show returns a non-zero exit code. LOUD
                         INDETERMINATE, exit 7.
    """

    GIT_BINARY_ABSENT = "git_binary_absent"
    SHA_UNRESOLVABLE = "sha_unresolvable"


class VerifierVerdict(str, Enum):
    """The user-observable verdict of one des verify-commit-trailers invocation.

    Maps onto the CLI exit-code contract (DESIGN §Exit-Code Collision).

    CANNOT_EVALUATE -- exit 7 + LOUD structured INDETERMINATE reason on stderr.
                       The commit body could not be READ (git absent / SHA
                       unresolvable). Distinct from both TAMPERING and MALFORMED.
    TAMPERING       -- exit 4 (legacy tampering slot, used for non-conflation
                       assertion only; no longer emitted by the repurposed CLI).
    MALFORMED       -- exit 6 + malformed or --strict+no-trailers (post-read).
                       Distinct from CANNOT_EVALUATE.
    OTHER           -- any other exit code (e.g. Python unhandled exception exit 1
                       from an uncaught error). Captured so the RED is observable
                       as a distinct, non-CANNOT_EVALUATE verdict.
    """

    CANNOT_EVALUATE = "cannot_evaluate"  # exit 7
    TAMPERING = "tampering"  # exit 4 (non-conflation assertion)
    MALFORMED = "malformed"  # exit 6
    OTHER = "other"  # unexpected exit code


# Exit code for INDETERMINATE (git-absent / unresolvable-SHA) in
# verify_commit_trailers. DISTINCT from exit 4 (tampering), exit 5 (key), exit 6
# (malformed). Locked decision per DESIGN §Exit-Code Collision.
CANNOT_EVALUATE_EXIT = 7

# Exit code for HMAC mismatch / tampering in verify_commit_trailers (UNCHANGED).
# The non-conflation AT asserts CANNOT_EVALUATE_EXIT != TAMPERING_EXIT.
TAMPERING_EXIT = 4

# Exit code for malformed-trailer or --strict+no-trailers (UNCHANGED, post-read).
# The non-conflation AT asserts CANNOT_EVALUATE_EXIT != MALFORMED_EXIT.
MALFORMED_EXIT = 6

# A commit SHA (arbitrary hex string from the caller's perspective).
CommitSha = NewType("CommitSha", str)
