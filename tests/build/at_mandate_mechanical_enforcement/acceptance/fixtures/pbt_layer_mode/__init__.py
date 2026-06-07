# Golden-fixture corpora for the M9/9-v2 PBT-layer-mode gate (slice-04).
# These files are scanned-as-data by the gate; they are NOT collected as tests
# themselves (filenames are violation_*/clean_*, not test_*.py). The gate reads
# each file's STRUCTURE (PBT decorators + stateful imports); the file's intended
# LAYER is supplied by the composition service via a synthetic representative
# path (slice-03 pattern), so the fixture content stays layer-agnostic data.
