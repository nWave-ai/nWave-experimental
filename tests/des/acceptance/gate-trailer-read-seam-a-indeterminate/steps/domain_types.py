"""Domain types for the gate-trailer-read-seam-a-indeterminate slice-01 ATs.

Mandate-12 criterion 1: every domain noun used in the Gherkin is expressed once
here as a typed enum or NewType. Step bodies and the composition service consume
these typed parameters -- no raw `str` where a domain enum exists.

Bounded context: the commit-trailer HMAC verifier's seam-A git-read path
(DESIGN Driving Surface table). The verifier either CANNOT-EVALUATE the commit
body (git absent / SHA unresolvable -> LOUD INDETERMINATE, exit 7) or VERIFIES
the HMAC trailers (history readable, HMAC matches -> exit 0) or reports one of
the existing post-read conditions (tampering exit 4, missing key exit 5,
malformed exit 6).

EXIT-CODE LOCKED DECISION (DESIGN authority, feature-delta.md §Exit-Code
Collision): exit 7 is the NEW INDETERMINATE (cannot-evaluate / git-absence
class) in verify_commit_trailers. Exit 4 remains HMAC mismatch (tampering).
Exit 6 remains malformed-trailer or --strict+no-trailers. All three are
STRUCTURALLY DISTINCT; the non-conflation AT asserts this explicitly.
"""

from __future__ import annotations

from enum import Enum
from typing import NewType


class CommitEnvironment(str, Enum):
    """The git readability environment in which the verifier is invoked.

    The seam-A re-point (_get_commit_message -> port.commit_message) must
    degrade LOUD on every cannot-evaluate condition. Each enum value exercises
    one materially-distinct decision-table row (DESIGN SUT verdict model C6).

    GIT_BINARY_ABSENT -- the git binary is masked off PATH. subprocess.run
                         raises FileNotFoundError before any git process starts.
                         Today this propagates as an uncaught raw stack-trace.
                         Post-GREEN: LOUD INDETERMINATE, exit 7.

    SHA_UNRESOLVABLE  -- git binary present, directory is a git work-tree, but
                         the requested SHA does not exist in the repo history.
                         git show returns a non-zero exit code. Today caught as
                         RuntimeError -> exit 6 (malformed-trailer code, WRONG).
                         Post-GREEN: LOUD INDETERMINATE, exit 7.

    REAL_WORK_TREE_SIGNED -- a real git work-tree with a commit carrying a
                         correctly signed Reviewed-by trailer. The seam-A re-
                         point must not regress this path. Post-GREEN: exit 0.
                         The non-vacuity control (KPI #2 guardrail).
    """

    GIT_BINARY_ABSENT = "git_binary_absent"
    SHA_UNRESOLVABLE = "sha_unresolvable"
    REAL_WORK_TREE_SIGNED = "real_work_tree_signed"


class VerifierVerdict(str, Enum):
    """The user-observable verdict of one des verify-commit-trailers invocation.

    Maps onto the CLI exit-code contract (DESIGN §Exit-Code Collision).
    The CANNOT_EVALUATE verdict is NEW (exit 7); all others are pre-existing.

    CANNOT_EVALUATE -- exit 7 + LOUD structured INDETERMINATE reason on stderr.
                       The commit body could not be READ (git absent / SHA
                       unresolvable). Distinct from both TAMPERING and MALFORMED.
    TAMPERING       -- exit 4 + HMAC mismatch. HMAC comparison ran (git WAS
                       readable) but the digest did not match. Integrity failure.
    MISSING_KEY     -- exit 5 + key env unset and key file absent.
    MALFORMED       -- exit 6 + malformed Reviewed-by trailer or --strict+no-trailers.
                       A post-read condition (git WAS readable). Distinct from
                       CANNOT_EVALUATE.
    VERIFIED        -- exit 0 + all trailers verified (or no trailers, non-strict).
    OTHER           -- any other exit code (e.g. Python unhandled exception exit 1
                       from today's uncaught FileNotFoundError). Captured so the
                       raw-stack-trace RED is observable as a distinct, non-
                       CANNOT_EVALUATE verdict.
    """

    CANNOT_EVALUATE = "cannot_evaluate"  # exit 7 (NEW)
    TAMPERING = "tampering"  # exit 4 (UNCHANGED)
    MISSING_KEY = "missing_key"  # exit 5 (UNCHANGED)
    MALFORMED = "malformed"  # exit 6 (UNCHANGED)
    VERIFIED = "verified"  # exit 0 (UNCHANGED)
    OTHER = "other"  # raw stack-trace / unexpected


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

# A signing key (HMAC-SHA256 secret bytes encoded as UTF-8).
SigningKey = NewType("SigningKey", bytes)
