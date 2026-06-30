@feature-gate-trailer-read-seam-a-indeterminate @slice-01
Feature: The commit-trailer verifier refuses LOUD with a uniform cannot-evaluate verdict when git is absent or the SHA is unresolvable
  As an nWave operator running des verify-commit-trailers on a target machine
  I want the verifier to refuse with a LOUD cannot-evaluate verdict (exit 7)
    whenever git is absent or the commit SHA cannot be resolved
  So that a git-less environment can never be silently mistaken for a tampered
    or malformed-trailer condition -- the genericita / target-machine-agnosticism
    guarantee (a git-absence is exit 7, never exit 4 tampering, never exit 6
    malformed, never a raw Python stack-trace)

  # slice-01 of gate-trailer-read-seam-a-indeterminate -- THE WALKING SKELETON
  # (DISCUSS Slice Plan slice-01 + DESIGN Per-Slice Companion slice-01). The
  # thinnest honest end-to-end vertical: a target where the git binary is absent
  # from PATH -> the verifier cannot read the commit body -> it emits a LOUD
  # structured INDETERMINATE reason to stderr and refuses with the distinct
  # cannot-evaluate exit code 7. NOT a raw Python stack-trace (today's bug --
  # FileNotFoundError propagates uncaught from subprocess.run at line 132).
  # NOT exit 6 (the malformed-trailer code -- a post-read condition). NOT exit 4
  # (the HMAC-mismatch/tampering code -- a completely different severity class).
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 subprocess): the REAL
  # `des verify-commit-trailers` CLI, invoked as a subprocess black box
  # (`python -m des.cli.verify_commit_trailers --commit <sha>`). The
  # `_get_commit_message` seam and the (future) CommitTrailerReadPort are NEVER
  # imported-and-called at the step boundary -- that is a Layer-1 unit test
  # masquerading as an AT (Mandate-13 HARD invariant). The observable surface is
  # the process exit code and the structured INDETERMINATE payload on stderr --
  # nothing else. The composition root default-wires the real
  # GitCommitTrailerReadAdapter (post-GREEN), so the genuine git-absence degrade
  # is exercised end-to-end, not via an in-memory fake.
  #
  # EXIT-CODE LOCKED DECISION (DESIGN authority, feature-delta.md §Exit-Code
  # Collision): exit 7 is INDETERMINATE (cannot-evaluate / git-absence class)
  # in verify_commit_trailers. Exit 4 in this CLI remains HMAC mismatch
  # (tampering) -- a different severity class. Exit 6 remains malformed-trailer
  # or --strict+no-trailers (a post-read condition). These three codes are
  # STRUCTURALLY DISTINCT; the ATs assert non-conflation explicitly.
  #
  # RED-for-right-reason (ADR-025 + ADR-028, pre-DELIVER fail-for-right-reason
  # gate): on master _get_commit_message (line 132) has no try/except around
  # subprocess.run(["git","show",...]).  A missing git binary raises
  # FileNotFoundError before `result` is assigned -- fully unhandled, raw Python
  # stack-trace to stderr, process exits with Python's unhandled-exception code
  # (typically 1).  An unresolvable SHA raises RuntimeError caught at line 181
  # -> exit 6.  The Then-steps assert exit 7 + a structured INDETERMINATE reason
  # on stderr and therefore fail with a semantic AssertionError -- never a
  # collection/import/setup error in the test process (step modules import only
  # test-local types). The ATs PASS once DELIVER lands the new
  # CommitTrailerReadPort.commit_message method + GitCommitTrailerReadAdapter
  # extension + the seam-A re-point in verify_commit_trailers.
  #
  # NON-VACUITY (perturbation-bound, KPI #2 guardrail): the two cannot-evaluate
  # scenarios are paired with a CONTROL -- a REAL git work-tree with a valid
  # commit carrying a correctly signed Reviewed-by trailer verifies cleanly
  # (exit 0). The refusal is therefore bound to git-unreadability / SHA
  # unresolvability, not vacuously always-on.
  #
  # S3 CROSS-TABLE RECONCILIATION (DESIGN Driving Surface table, each seam
  # driven by at least one scenario from the real CLI):
  #   seam: CommitTrailerReadPort.commit_message (port method)     -> scenario 1+2
  #   seam: GitCommitTrailerReadAdapter.commit_message (adapter)   -> scenario 1+2
  #   seam: seam-A re-point (_get_commit_message in CLI)           -> scenario 1+2+3
  #
  # TAG SCHEME: scenario @tags convert to dynamic pytest marks via pytest-bdd's
  # tag pipeline; the project's filterwarnings (pyproject.toml) suppresses
  # PytestUnknownMarkWarning so --strict-markers does not reject them. Binding
  # goes through pytest-bdd's scenario machinery via the RELATIVE `scenarios(...)`
  # call from the steps/ module (the proven-collecting form).

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation
  Scenario: A commit-trailer verifier run with the git binary absent produces a loud cannot-evaluate refusal not a stack-trace
    Given a target directory without the git binary available
    When the operator runs des verify-commit-trailers on a commit in that directory
    Then the verifier refuses with a loud cannot-evaluate verdict
    And the cannot-evaluate verdict names a reason on standard error
    And the verifier does not emit a raw Python stack-trace
    And the verifier does not mutate the target directory

  @slice-01 @driving_port @real-io @contract-shape:bounded-change
  Scenario: The cannot-evaluate verdict from an unresolvable commit SHA is distinct from both tampering and malformed-trailer verdicts
    Given a git work-tree where the requested commit SHA does not exist
    When the operator runs des verify-commit-trailers on that unresolvable SHA
    Then the verifier refuses with a loud cannot-evaluate verdict
    And the cannot-evaluate verdict is distinct from the tampering verdict
    And the cannot-evaluate verdict is distinct from the malformed-trailer verdict

