@feature-evidence-locus-and-absence-detection
Feature: A committed slice with no reachable examine verdict is named, counted and dated
  As Maya Okafor, an nWave OSS maintainer running a multi-lane swarm
  I want a committed slice whose examine verdict is unreachable to be NAMED,
    COUNTED and DATED by the oldest affected commit
  So that eight silent days of evidence loss can never repeat -- a run that
    cannot vouch for a slice says so LOUDLY instead of printing a reassuring
    zero

  # slice-01 of evidence-locus-and-absence-detection -- THE WALKING SKELETON
  # (DISCUSS Locked Decisions WD-1 + DESIGN Design -> Slice Mapping slice-01).
  # The thinnest end-to-end vertical that makes the defect class VISIBLE: real
  # git commit history through CommitTrailerReadPort (reused) + the NEW
  # CommitDateReadPort, a real examine-ledger scan through the NEW
  # ExamineLedgerScanPort, classified by the NEW pure domain decision table
  # `evidence_locus.classify_slice_evidence`, reported by the NEW CLI
  # `des verify-examine-attestation`.
  #
  # SCOPE (per dispatch + DESIGN Design -> Slice Mapping): this slice exercises
  # ONLY the `UNATTESTED, join_confidence: heuristic` branch (a bare slice-id
  # with ZERO ledger entries anywhere, authored on/after the ledger's earliest
  # record) plus a non-vacuity control (a committed slice whose bare id IS
  # somewhere in the ledger -> NOT counted/named as unattested). The
  # COULD_NOT_VERIFY / INDETERMINATE / EmptyLedgerAmbiguous branches
  # (temporal-boundary pre-mechanism commits, unreadable git/canonical-root,
  # and the empty-ledger refusal) are deliberately OUT of scope here --
  # slice-02 authors them.
  #
  # HONEST CONTROL (review-corrected 2026-07-29): the control scenario's
  # fixture carries NO `Feature-Id:` trailer (slice-03 is out of scope), so
  # per Decisions Table Revision 1 row 4 its classification is
  # `COULD_NOT_VERIFY`, NEVER `ATTESTED` -- `ATTESTED` is definitionally
  # unreachable by any slice-01 fixture. The control therefore asserts ONLY
  # what slice-01 can honestly claim (not counted/named as UNATTESTED),
  # carrying NO exit-code claim: D-6 assigns a COULD_NOT_VERIFY-only run its
  # own non-zero exit (2), a distinction `Design -> Slice Mapping` names
  # slice-02 scope.
  #
  # DRIVING PORT (Mandate-13 driving-port-only, Layer 3 in-process composition,
  # nw-distill-red-scaffolding P1-P4): the REAL `des` CLI dispatcher
  # (`des.cli.__main__.main`) driven IN-PROCESS via `run_cli_in_process` --
  # NEVER a `subprocess.run([sys.executable, ...])` fork, and NEVER a direct
  # import of `des.cli.verify_examine_attestation` (absent at HEAD -- that
  # would be a collection-time ImportError, the escalation trap). The absent
  # `verify-examine-attestation` subcommand surfaces as a RUNTIME
  # `SystemExit(2)` (argparse "invalid choice") raised INSIDE the stable
  # dispatcher's own call -- collection succeeds, and every current-slice
  # scenario RED-fails with a NAMED semantic AssertionError (the report is
  # unparseable / the exit code is not the expected one), never an import
  # traceback. See steps/composition.py's module docstring for the full P1-P4
  # trace and the DELIVER-pinned observable schema (A1-A4).
  #
  # NON-VACUITY (perturbation-bound, KPI #2 guardrail): the walking skeleton +
  # depth scenario are paired with a CONTROL -- a committed slice whose bare
  # id IS somewhere in the ledger is neither counted nor named as
  # unattested -- proving the UNATTESTED classification is bound to genuine
  # bare-id absence, not vacuously always-on.
  #
  # WD-2 (the disease this feature exists to close): a dedicated negative pins
  # that the detector's verdict is UNCHANGED by touching an unrelated file
  # under `.nwave/telemetry/` -- the exact directory-activity-vs-evidence
  # confusion the RCA measured (trunk's atdd-pure directory kept receiving
  # writes for eight days while the examine family was silently dead).
  #
  # 3 Pillars: business language only (Pillar 1); each scenario's Given reuses
  # the prior scenario's substrate-building vocabulary (Pillar 2, chained
  # narrative); the composition drives the REAL des dispatcher + a REAL git
  # work-tree + the REAL record_examine_verdict production writer (Pillar 3).
  #
  # Mandate 8 (state-delta): the When-step snapshots git HEAD + the ledger
  # family's total byte-size before/after and asserts both unchanged -- the
  # detector is a pure observer (DESIGN: "Pure read -- no filesystem
  # mutation"), never a mutator.

  @slice-01 @walking_skeleton @driving_port @real-io @contract-shape:unbounded-preservation @covers-R1 @covers-R2 @covers-R3 @covers-R4
  Scenario: A committed slice with no reachable examine verdict is named, counted and dated
    Given a committed slice whose examine verdict is unreachable
    When the operator runs the evidence-attestation detector
    Then the report names the unattested slice
    And the report names the commit the unattested slice came from
    And the report states the count as 1
    And the report states the oldest unattested date as "2026-02-01T09:00:00+00:00"
    And the command exits non-zero

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R2 @covers-R3
  Scenario: Two unattested slices are counted and the oldest of the two commit dates is reported
    Given two committed slices whose examine verdicts are unreachable, authored on different dates
    When the operator runs the evidence-attestation detector
    Then the report names the unattested slice
    And the report states the count as 2
    And the report states the oldest unattested date as "2026-02-01T09:00:00+00:00"
    And the command exits non-zero

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R5
  Scenario: A report listing a problem never exits zero as a green success summary
    Given a committed slice whose examine verdict is unreachable
    When the operator runs the evidence-attestation detector
    Then the report does not read as a success summary

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R6
  Scenario: Touching an unrelated telemetry file without a verdict record does not change the report
    Given a committed slice whose examine verdict is unreachable
    And the operator has already run the evidence-attestation detector once
    When an unrelated file is touched under the telemetry directory and the detector is run again
    Then the report is unchanged from the first run

  @slice-01 @driving_port @real-io @contract-shape:unbounded-preservation @covers-R7
  Scenario: A committed slice reachable in the ledger is never counted or named as unattested
    Given every committed slice's bare identifier is present somewhere in the examine ledger
    When the operator runs the evidence-attestation detector
    Then the report names no unattested slice
