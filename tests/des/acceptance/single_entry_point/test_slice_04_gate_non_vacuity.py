"""slice-04 binder: the rescoped migration gate still bites (AT-10).

Layer 3 (filesystem scan). ONE class-level negative control collapses the
non-vacuity obligation of the slice-04 AT-07/08 rescope into a single
assertion:

  AT-10: the rescoped P1∧P2∧P3 migration-violation predicate STILL reports an
         unmarked, concrete, registered-subcommand module-form invocation in a
         non-test authoring file (mutation-checkable; remove the planted hit
         and the scan goes empty → GREEN, prove it is not vacuously green).

RED posture today: the rescoped predicate
(`scan_directory_for_unmarked_registered_module_form`) is a RED scaffold; it
raises AssertionError until slice-04 DELIVER implements P1∧P2∧P3. AT-07/AT-08
(slice-03 file) are the rescoped GREEN-path witnesses — they go green when
DELIVER teaches the real scan the P2 (no-subcommand) + P3 (sanctioned-SUT)
exclusions.
"""

from pytest_bdd import scenarios

from .steps.steps_slice_01 import *
from .steps.steps_slice_04 import *


scenarios("slice_04_gate_non_vacuity.feature")
