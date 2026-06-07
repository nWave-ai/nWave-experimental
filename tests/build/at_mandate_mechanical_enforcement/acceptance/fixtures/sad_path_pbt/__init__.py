# Golden-fixture corpora for the M11 integration-sad-path gate (slice-07).
# These files are scanned-as-data by the gate; they are NOT collected as tests
# themselves (filenames are violation_*/clean_*/adversarial_*, not test_*.py).
#
# The PBT-half fixtures (*.py) carry sad-path tests; the gate reads each file's
# STRUCTURE (PBT decorators + stateful imports), and its intended LAYER is
# supplied by the composition service via a synthetic representative path
# (slice-03/04 pattern) so the fixture content stays layer-agnostic data.
#
# The coverage-half fixtures (*.yaml) are component manifests carrying
# ``failure_modes`` entries; the gate cross-checks each entry against the named
# tests the composition supplies.
#
# The adversarial_* fixture is the dormant check_robustness_density R6
# self-dogfood case — an unclassifiable parser shape the gate must survive
# without crashing (the gate's own parser is the SUT).
