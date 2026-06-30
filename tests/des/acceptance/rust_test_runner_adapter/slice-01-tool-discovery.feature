@feature-f-rust-test-runner-adapter @slice-01
Feature: A tool a language-adapter needs is DISCOVERED, never assumed at a fixed position
  As an operator running the nWave spine against any target machine
  I want the shared resolve_tool discovery scale to FIND a tool wherever it is installed
  So that a present toolchain off the hook PATH (WSL2 ~/.cargo/bin) is USED, and a
    genuinely absent tool yields a LOUD INDETERMINATE that names the exact remediation

  # slice-01 of f-rust-test-runner-adapter (atdd_pure; walking skeleton).
  # The SHARED resolve_tool(name, known_locations) 3-rung discovery scale (§V.C) --
  # the genericità primitive every language adapter (TestRunner now; Build/Coverage/
  # AST/Mutation later) and every LanguageAdapterPlugin.probe() inherits. At HEAD
  # src/des/adapters/driven/runner/tool_discovery.py does NOT exist (Tsunami
  # callers-of: 0; grep tree-wide: 0).
  #
  # DRIVING SURFACE (Mandate-13, Layer 3 subprocess): the REAL production
  # resolve_tool imported + invoked in a CHILD interpreter over a GENUINE controlled
  # filesystem + PATH/HOME env (real executable files chmod +x in a tmp dir; PATH/HOME
  # scrubbed and rebuilt). NO mocks -- the genuine discovery behaviour. observables =
  # the RUNG that resolved the tool + the remediation string the INDETERMINATE result
  # names. An absent module is a captured child-probe observable (rc != 0, no marker),
  # never a collection error in the test process.
  #
  # DORMANT-SEAM RECONCILIATION (D11): the net-new DESIGN seam this slice declares is
  # the shared resolve_tool(name, known_locations) helper (the §V.C primitive). All
  # three scenarios drive THAT exact seam through the real entry point (a child
  # interpreter calling resolve_tool) and assert its observable outcome -- the rung
  # resolved / the named remediation. No indirect seam in slice-01: resolve_tool IS
  # the entry point.
  #
  # RED-for-right-reason (active-RED scaffold, atdd_pure -- NOT @skip): at HEAD the
  # tool_discovery module is absent, so the child import raises ModuleNotFoundError
  # (rc != 0, no RESOLVED:/INDETERMINATE: marker). Each Then turns a captured
  # observable into a semantic AssertionError. GREEN once DELIVER ships
  # tool_discovery.py with the 3-rung scale. No @skip, no import / collection error.

  @slice-01 @walking_skeleton @driving_port @real-io @us-discover-don-t-assume @contract-shape:pure-function
  Scenario: A tool present on PATH is discovered on the PATH rung
    Given the tool is on the search PATH
    When the adapter resolves the tool through the discovery scale
    Then the tool is used from the on-path rung

  @slice-01 @driving_port @real-io @us-wsl2-gotcha @contract-shape:pure-function
  Scenario: A tool off PATH but in a known install location is discovered, not falsely indeterminate
    Given the tool is absent from PATH but installed in a known location
    When the adapter resolves the tool through the discovery scale
    Then the tool is used from the known-location rung

  @slice-01 @driving_port @real-io @us-loud-indeterminate @error @contract-shape:pure-function
  Scenario: A tool absent everywhere yields a loud indeterminate naming the remediation
    Given the tool is absent from PATH and every known location
    When the adapter resolves the tool through the discovery scale
    Then the discovery yields an indeterminate result naming the remediation
