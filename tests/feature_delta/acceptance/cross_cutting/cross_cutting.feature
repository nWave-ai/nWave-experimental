Feature: Universal CLI surface across triggers, environments, and concurrency
  As any maintainer using any version-control system, any CI provider,
  or no automation at all
  I want a single CLI binary that runs validator, extractor, and migrator
  with predictable exit codes, machine-parseable output, zero side effects,
  and safe parallel execution
  So that the tool integrates with my chosen workflow without coupling me
  to any vendor, hook framework, or orchestration substrate

  Background:
    Given a clean working directory with no prior nwave-ai state
    And the nwave-ai binary is on PATH

  # ------------------------------------------------------------------
  # US-07A — Vendor-neutral universal CLI
  # ------------------------------------------------------------------

  @US-07A @AC-1 @driving_adapter @vendor_neutral
  Scenario: CLI runs standalone in a Mercurial repository without Git
    Given a Mercurial repository containing a valid feature-delta
    And no Git binary is available in the sandbox
    And no pre-commit framework is installed in the sandbox
    When the maintainer runs "nwave-ai validate-feature-delta <path>" via subprocess
    Then the exit code is 0
    And stderr contains "[PASS] all checks"
    And no file outside the path argument is modified
    And no network connection is opened

  @US-07A @AC-2 @driving_adapter
  Scenario: Machine-parseable JSON output for trigger integration
    Given a feature-delta containing one E3 violation
    When the maintainer runs the validator with the JSON format flag
    Then the exit code is 1
    And stdout is valid JSON
    And the JSON object contains the fields check, severity, file, line, offender, and remediation
    And the JSON object reports schema_version 1

  @US-07A @AC-3 @error
  Scenario: Usage error returns exit code 2 with did-you-mean
    Given the maintainer passes a non-existent path
    When the validator runs
    Then the exit code is 2
    And stderr contains "file not found"
    And stderr suggests the closest matching path

  # ------------------------------------------------------------------
  # US-10 — G4 zero-side-effects guardrail (cross-cutting)
  # ------------------------------------------------------------------

  @US-10 @AC-1 @real-io @adapter-integration
  Scenario: Validator invocation produces no diff outside the path argument
    Given a sandbox snapshot of HOME and CWD before invocation
    When the maintainer runs the validator against a feature-delta
    Then the post-invocation snapshot diff is empty for the monitored set
    And the only allowed modification is the validator log inside ~/.nwave/

  @US-10 @AC-2 @real-io
  Scenario: Extractor invocation produces no diff outside stdout
    Given a sandbox snapshot of HOME and CWD before invocation
    When the maintainer runs the extractor against a feature-delta
    Then the post-invocation snapshot diff is empty for the monitored set

  # ------------------------------------------------------------------
  # US-11 idempotency (DD-A7b) at the CLI surface
  # ------------------------------------------------------------------

  @US-11 @AC-3
  Scenario: Repeated validator invocation produces identical output
    Given a feature-delta with one E5 violation
    When the maintainer runs the validator twice in succession
    Then both invocations produce byte-identical stderr
    And both invocations produce identical exit codes

  # ------------------------------------------------------------------
  # US-14 — Thread-safety contract (DD-A7a)
  # ------------------------------------------------------------------

  @US-14 @AC-1 @real-io
  Scenario: Ten parallel validator invocations on the same file all succeed
    Given a well-formed feature-delta
    When ten validator subprocesses run concurrently against the same file
    Then every invocation exits with code 0
    And every invocation produces identical stderr content

  # ------------------------------------------------------------------
  # Probe failure surfaces as exit 70 (DD-A7d composition root)
  # ------------------------------------------------------------------

  @US-INFRA-1 @AC-2 @error
  Scenario: Corrupted schema file causes startup probe failure
    Given the shipped schema is replaced with a malformed JSON document
    When the maintainer runs the validator
    Then the exit code is 70
    And stderr emits a "health.startup.refused" structured event
    And stderr names the failing adapter

  # ------------------------------------------------------------------
  # NO_COLOR honored across all CLI subcommands
  # ------------------------------------------------------------------

  @US-10 @AC-3
  Scenario: NO_COLOR environment variable suppresses ANSI codes
    Given the NO_COLOR environment variable is set
    And a feature-delta with one violation
    When the maintainer runs the validator
    Then stderr contains no ANSI color escape sequences

  # ------------------------------------------------------------------
  # US-14 / S6 stressor regression lock — CommonMark drift (permanent FAIL)
  # The validator uses a stdlib line-state machine (ADR-01). Multi-line
  # table cells produced by CommonMark renderers bypass E3 row detection.
  # This is an accepted out-of-scope stressor (Layer 1 permanent FAIL).
  # Regression lock: verify the validator still exits 0 on a well-formed
  # single-line-cell file (no regression from v1.0 baseline behavior).
  # ------------------------------------------------------------------

  @US-14 @stressor-regression @S6
  Scenario: Stressor matrix S6 — pre-existing solved case regression
    Given a well-formed single-line-cell feature-delta
    When the maintainer validates the feature-delta file
    Then the exit code is 0
    And stderr contains "[PASS] all checks"
