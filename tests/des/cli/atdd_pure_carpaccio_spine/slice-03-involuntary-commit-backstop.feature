@feature-simplify-atdd-pure-carpaccio-spine
Feature: A skipped exit gate cannot ship an unverified slice

  Relocating the spine's logic into CLIs the orchestrator invokes makes
  non-vacuity rest on a fallible operator reliably running the right CLI -- a
  memory rule, not a control. This slice restores involuntariness: one cheap
  commit-time check that fires whether or not the orchestrator wants it to, plus
  a feature-end reconciliation that catches what the commit-time check missed.

  The commit-time backstop refuses any commit carrying a slice-id trailer unless
  a matching SliceCommitVerified record exists. The feature-end reconciliation
  walks every slice-id commit and fails the feature if any lacks a record. Two
  backstops -- one early warning at commit time, one authoritative sweep at
  feature close.

  Read in sequence after slice-02: slice-02 made the exit gate produce a ledger
  record atomically; this slice makes a SKIPPED exit gate fail closed -- the
  commit is refused, and even an amended or wrong-commit skip is caught when the
  feature is reconciled.

  # Driving ports: the M-2 pre-commit hook (verify_slice_ledger_record.py) and
  # the verify_deliver_integrity CLI (python -m). Layer 3 (subprocess / FS
  # acceptance) -- example-only sad paths (Mandate 11). @coupled per the slice
  # plan: the backstop and the reconciliation are one involuntariness change.
  #
  # Each driving port is exercised as one decision-table Scenario Outline
  # (max-PBT/parametrize-density standing rule): the M-2 hook is the
  # allow/refuse/abstain table, the reconciliation is the reconciled/unreconciled
  # table. The abstain row is the hook's DOMINANT path -- the hook fires on every
  # commit repo-wide, and a commit with no slice-id trailer must be waved through
  # cleanly, or every developer's every commit is rejected.

  Background:
    Given a feature project with a multi-slice plan
    And a slice commit exists for the entering slice

  @slice-03 @coupled @driving_port @contract-shape:pure-function
  Scenario Outline: The commit-time backstop decides each commit by its ledger record
    Given the commit under inspection is <commit>
    When the commit-time backstop inspects the commit
    Then the commit-time backstop reaches the verdict "<verdict>"

    Examples:
      | commit                                                       | verdict             |
      | a slice commit whose exit gate produced a ledger record      | commit-allowed      |
      | a slice commit whose exit gate was skipped                   | commit-refused      |
      | an ordinary commit carrying no slice-id trailer              | not-a-slice-commit  |

  @slice-03 @coupled @driving_port @contract-shape:bounded-change @red_scaffold_reconciliation
  Scenario Outline: The feature-end reconciliation sweeps every slice commit against the ledger
    Given a feature where <ledger_state>
    When the orchestrator runs the feature-end reconciliation
    Then the feature-end reconciliation reaches the outcome "<outcome>"
    And the system filesystem is otherwise unchanged

    Examples:
      | ledger_state                                                          | outcome                      |
      | every slice commit has a ledger record                                | reconciled                   |
      | a slice commit has no ledger record                                   | unreconciled                 |
      | every slice commit is recorded but the feature-end cycle never ran    | feature-end-cycle-incomplete |
