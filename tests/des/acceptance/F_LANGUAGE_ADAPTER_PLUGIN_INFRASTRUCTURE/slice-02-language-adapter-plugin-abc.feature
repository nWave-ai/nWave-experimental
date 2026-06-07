@feature-F-LANGUAGE-ADAPTER-PLUGIN-INFRASTRUCTURE
Feature: The LanguageAdapterPlugin ABC formalizes the per-language plugin discovery contract
  As an nWave OSS operator working with a non-Python target codebase
  I want every per-language plugin to inherit a shared abstract base class
    that declares the target-language identifier, the adapter-registration
    method, and the Earned-Trust probe contract
  So that future language plugins (slice-05a Python, slice-07 TypeScript,
    future Go/Rust/Java) conform to a single substrate the doctor CLI,
    install pipeline, and registry can rely on uniformly
    (per `feedback_recursive_workflow_self_improvement_2026_05_25`):
    the ABC becomes the mechanical contract every successor must satisfy --
    the floor never moves under their feet

  # carpaccio slice-02 (walking-skeleton, T1 installed-artifact tier per
  # feature-delta §Slice Plan). Layer 3 (subprocess / FS acceptance against
  # the real installed package + the real Python entry-points mechanism) --
  # example-only, no PBT (Mandate 9/11). 3 ATs cap; max parametrize density.
  #
  # CONTRACT SOURCES (per DESIGN feature-delta §Reuse Analysis):
  # - LanguageAdapterPlugin ABC: `src/des/ports/language_adapter_plugin.py`
  #   (CREATE) -- subclasses `scripts.install.plugins.base.InstallationPlugin`
  #   per DESIGN §Reuse Analysis "EXTEND" row. Declares:
  #     * `target_language: str` -- the kebab-case language identifier
  #     * `register_adapters(registry) -> None` -- per-port adapter wiring
  #     * `probe() -> ProbeResult` -- Earned-Trust environment probe (slice-01
  #        ships the contract; slice-05a ships the first concrete probe + lies)
  #     * `port_coverage: dict[str, AdapterStatus]` -- per-port coverage matrix
  #     * `metadata: PluginMetadata` -- maintainer/SLA/semver (slice-06 hardens)
  # - ProbeResult dataclass: `src/des/ports/language_adapter_plugin.py`
  #   (CREATE) -- frozen, fields `{ok: bool, missing_ports: list[str],
  #   probed_at: datetime}` per DESIGN §Earned Trust probes required.
  # - PyPI entry-points discovery substrate: existing group
  #   `nwave.lang.adapter` (slice-01 floor) -- slice-02 adds the conformance
  #   check: when ANY plugin IS registered, the loaded class IS-A
  #   LanguageAdapterPlugin subclass. Discovery still via stdlib
  #   `importlib.metadata.entry_points`.
  #
  # The atdd_pure spine ships the ABC + ProbeResult in this carpaccio slice.
  # RED cadence: every AT fails at DISTILL time because the ABC module is
  # absent (empirical reads at DISTILL: `src/des/ports/language_adapter_plugin.py`
  # absent, `LanguageAdapterPlugin` import resolves to ImportError, the
  # in-tree probe-conformance fixture-plugin module does not yet exist).
  # DELIVER's GREEN phase creates the ABC + ProbeResult + the in-tree
  # conformance-fixture plugin registered in the local installable wheel's
  # entry-points so the discovery substrate has a witness.
  #
  # Driving ports (Mandate 1, hexagonal boundary): all three ATs invoke
  # through subprocess against the as-installed Python runtime --
  # `python -c "..."` interrogating `importlib.metadata` + checking
  # `issubclass()` / `inspect` on the loaded class. NEVER direct domain-module
  # import in step composition (per Mandate-13 driving-port-only invariant,
  # CRITICAL P0 -- friction #34 F-ATDD-PURE-AT-DIRECT-DOMAIN-TESTING-ANTI-PATTERN
  # avoidance). The Python subprocess IS the driving port; the import happens
  # in the SUT (subprocess), the assertion observes the subprocess exit code +
  # stdout JSON shape.

  # AT-1: the LanguageAdapterPlugin ABC exists at its SSOT location and is an
  # abstract class (instantiation raises TypeError on missing abstractmethods).
  # This pins the SUBSTRATE every slice-05a/07/future per-language plugin
  # inherits. Subprocess introspection via `inspect` + `abc.ABC` membership
  # check exercised through the as-installed package boundary.
  #
  # M52 ATD AMENDMENT (2026-05-25, friction #43 closure): the original AT-1
  # second And-step `And the language-adapter ABC introspection reports the
  # class as an InstallationPlugin subclass` was DROPPED. M44 architect
  # Option (a) explicitly DECOUPLES `LanguageAdapterPlugin` from
  # `InstallationPlugin` at the ABC level (per F-D-09 closure: pure ABC, ZERO
  # `scripts.*` imports). The dual-base contract now lives ONLY on the
  # CONCRETE fixture (`ConformanceFixtureLanguageAdapter` multi-inherits both
  # bases) and is mechanically asserted by AT-3's dual `issubclass(cls,
  # LanguageAdapterPlugin) AND issubclass(cls, InstallationPlugin)` check at
  # the entry-point load site. Coverage of the dimension is preserved at the
  # correct architectural layer.
  @slice-02 @driving_port @real-io @walking_skeleton @contract-shape:pure-function
  Scenario: The LanguageAdapterPlugin ABC is loadable and abstract from the installed package
    Given the language-adapter ABC substrate is queried via the installed package
    When the language-adapter ABC introspection runs
    Then the language-adapter ABC introspection reports the class as abstract

  # AT-2: the LanguageAdapterPlugin ABC declares the four contract members
  # the doctor CLI + registry + install pipeline rely on. Parametrize-collapse
  # over the four mandatory members per DESIGN §Reuse Analysis:
  #   target_language (str attr), register_adapters (callable), probe
  #   (callable returning ProbeResult), port_coverage (dict attr).
  # The substrate guarantees these are PRESENT on the ABC; slice-05a's
  # concrete Python plugin (and slice-07's TS plugin) implement them.
  # AT-2 pins the contract shape every future subclass must satisfy.
  @slice-02 @driving_port @real-io @walking_skeleton @parametrize-collapse @contract-shape:pure-function
  Scenario Outline: The LanguageAdapterPlugin ABC declares the "<contract_member>" contract member
    Given the language-adapter ABC substrate is queried via the installed package
    When the language-adapter ABC introspection runs
    Then the language-adapter ABC introspection reports the "<contract_member>" contract member as declared

    Examples:
      | contract_member    |
      | target_language    |
      | register_adapters  |
      | probe              |
      | port_coverage      |

  # AT-3: the PyPI entry-points discovery substrate, when it discovers a
  # plugin in the `nwave.lang.adapter` group, loads a class that IS-A
  # LanguageAdapterPlugin subclass. Slice-02 ships an in-tree conformance
  # fixture plugin registered in the local installable wheel's entry-points
  # so the substrate has a witness without depending on slice-05a's Python
  # plugin (which lands later in the slice plan).
  #
  # Universe (port-exposed observables): subprocess exit code + stdout JSON
  # envelope `{registered: [...], all_conform: bool, non_conforming: [...]}`.
  # Slice-02 floor pins: when registered list is non-empty, all_conform is
  # true and non_conforming is empty. Slice-05a/07 add language-specific
  # plugin entries; the same conformance gate applies uniformly.
  @slice-02 @driving_port @real-io @walking_skeleton @contract-shape:unbounded-preservation
  Scenario: The entry-points discovery loads only LanguageAdapterPlugin subclasses
    Given the language-adapter entry-point discovery is exercised against the conformance fixture
    When the language-adapter entry-point conformance check runs
    Then the language-adapter entry-point conformance reports every discovered plugin as conformant
    And the language-adapter entry-point conformance reports no non-conforming class
