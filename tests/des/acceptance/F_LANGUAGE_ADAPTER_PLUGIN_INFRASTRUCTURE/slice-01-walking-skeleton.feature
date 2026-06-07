@feature-F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE
Feature: The language-adapter plugin infrastructure exposes its walking-skeleton floor
  As an nWave OSS operator working with a non-Python target codebase
  I want the SSOT port catalog, the dry-run discovery CLI, and the
    plugin-registry substrate to be in place from the first slice
  So that subsequent slices have a stable substrate to extend
    (per `feedback_recursive_workflow_self_improvement_2026_05_25`):
    each new slice adds rows to the catalog, plugin coverage to the
    registry, or gap-report details to the doctor CLI -- the floor
    never moves under their feet

  # carpaccio slice-01 (walking-skeleton, T1 installed-artifact tier per
  # feature-delta §Slice Plan). Layer 3 (subprocess / FS acceptance against
  # the real `des` CLI + the real validator + the real Python entry-points
  # mechanism) -- example-only, no PBT (Mandate 9/11).
  #
  # CONTRACT SOURCES (per DESIGN feature-delta §Reuse Analysis):
  # - SSOT port catalog: `nWave/data/language-adapter-ports.yaml` (CREATE)
  # - Catalog JSON schema: `nWave/schemas/language-adapter-ports.schema.json` (CREATE)
  # - Validator CLI: `scripts/cli/validate_language_adapter_catalog.py` (CREATE,
  #   pattern reused from `scripts/cli/validate_component_manifest.py`)
  # - Dry-run CLI: `des doctor --target-language=<lang>` routed via
  #   `src/des/cli/doctor.py` (CREATE) + new row in `_REGISTRY` at
  #   `src/des/cli/__main__.py:42-75` (EXTEND)
  # - Plugin discovery substrate: PyPI entry-points group `nwave.lang.adapter`
  #   per ADR-031 Option C (existing `importlib.metadata` stdlib)
  #
  # The atdd_pure spine ships ALL FOUR in this single carpaccio slice. RED
  # cadence: every AT fails at DISTILL time because the artifacts above are
  # absent (empirical reads at DISTILL: catalog yaml absent, schema absent,
  # validator absent, doctor.py absent, doctor not in _REGISTRY). DELIVER's
  # GREEN phase creates them all + appends the SSOT rows for the three
  # slice-01 LANGUAGE_BOUND gate CLIs (run_contract_gate, verify_
  # environmental_e2e, check_robustness_density).
  #
  # Driving ports (Mandate 1, hexagonal boundary): all three ATs invoke
  # through subprocess against the as-installed `des` CLI / Python runtime
  # -- never direct domain-module import. This is the
  # F-ATDD-PURE-AT-DIRECT-DOMAIN-TESTING-ANTI-PATTERN avoidance.

  # AT-1: the port catalog SSOT exists, schema-validates, and enumerates
  # the three slice-01 LANGUAGE_BOUND gate CLIs as the walking-skeleton
  # floor (run_contract_gate, verify_environmental_e2e,
  # check_robustness_density). The catalog YAML is the substrate every
  # subsequent slice (slice-02..slice-07) appends rows to.
  @slice-01 @driving_port @real-io @walking_skeleton @contract-shape:pure-function
  Scenario: The port catalog SSOT validates and enumerates the slice-01 floor
    Given the port catalog SSOT is present and well-formed
    When the port catalog validator runs
    Then the catalog validator reports the catalog as valid
    And the validator output names the three slice-01 LANGUAGE_BOUND gate CLIs

  # AT-2: the dry-run discovery CLI emits a structured JSON gap report for
  # a target language. Slice-01 floor: any target language reports GAPS
  # shape with non-empty missing_ports (no per-language plugins are
  # registered until slice-02 ships the ABC + slice-05a ships the first
  # plugin). Parametrize-collapse over the three first-class target
  # languages from the Nova-audit catalog (python, typescript, go).
  @slice-01 @driving_port @real-io @walking_skeleton @parametrize-collapse @contract-shape:unbounded-preservation
  Scenario Outline: The des doctor CLI reports GAPS for a "<language>" target with no plugins registered
    Given the operator targets the "<language>" language
    When the des doctor CLI runs
    Then the doctor report shape is gaps
    And the doctor report enumerates the language-bound ports missing for the target language

    Examples:
      | language   |
      | python     |
      | typescript |
      | go         |

  # AT-3: the plugin-discovery substrate (PyPI entry-points group
  # `nwave.lang.adapter` per ADR-031 Option C) is queryable as the
  # canonical discovery mechanism. Slice-01 floor: the group resolves
  # (Python stdlib `importlib.metadata.entry_points` succeeds), the
  # returned list is parseable JSON, and the minimum-count floor is 0
  # (zero plugins registered yet -- slice-02 introduces the
  # LanguageAdapterPlugin ABC, slice-05a registers the Python reference).
  # This AT pins the substrate's shape so slice-02..07 can rely on it.
  @slice-01 @driving_port @real-io @walking_skeleton @contract-shape:pure-function
  Scenario: The language-adapter entry-point discovery substrate is queryable
    Given the port catalog SSOT is present and well-formed
    When the language-adapter entry-point discovery runs
    Then the entry-point discovery substrate is queryable
    And the entry-point discovery lists at least 0 registered plugin
