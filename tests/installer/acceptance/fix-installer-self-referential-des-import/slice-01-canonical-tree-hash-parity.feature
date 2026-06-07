@feature-fix-installer-self-referential-des-import
Feature: installer plugin breaks self-referential import on canonical_tree_hash

  As the installer plugin author
  I want `scripts/install/plugins/des_plugin.py` to NOT import `des.runtime.tree_hash.canonical_tree_hash`
  So that PyPI-time install does not fail with `ModuleNotFoundError: No module named 'des'`
  Because `des` lives at `site-packages/nWave/lib/python/des/` which is NOT on `sys.path` at install time.

  Background:
    Given the installer plugin currently depends on `des.runtime.tree_hash.canonical_tree_hash`
    And the `des` module is shipped to `site-packages/nWave/lib/python/des/` at PyPI install
    And that location is NOT on `sys.path` during `nwave-ai install`

  @slice-01 @walking_skeleton @driving_port @real-io @e2e_smoke @contract-shape:installer-subprocess
  Scenario: nwave-ai install runs to completion on a clean target machine
    Given a clean virtualenv with `nwave-ai` installed from the wheel
    When the operator runs `nwave-ai install`
    Then the install completes with exit code 0
    And the existing e2e test `tests/e2e/test_pypi_shape_install_chain.py` reports all checks passing
    And no `DES module install failed: No module named 'des'` error appears in the install log

  @slice-01 @driving_port @contract-shape:byte-identical-parity
  Scenario Outline: inline canonical_tree_hash byte-matches the SSOT module-level function
    Given the inline `_canonical_tree_hash` function in `scripts/install/plugins/des_plugin.py`
    And the SSOT `canonical_tree_hash` function in `src/des/runtime/tree_hash.py`
    And a fixture tree of shape "<tree_shape>"
    When both functions hash the same fixture tree
    Then they return byte-identical output

    Examples:
      | tree_shape    |
      | single_file   |
      | nested_dirs   |
      | unicode_names |
