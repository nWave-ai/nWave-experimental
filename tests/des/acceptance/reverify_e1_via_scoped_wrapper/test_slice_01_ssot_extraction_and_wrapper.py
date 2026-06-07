"""slice-01 binder: SSOT extraction + thin wrapper CLI.

Walking-skeleton / wiring_e2e: drives the real ``check_slice_at_completeness``
CLI port end-to-end via subprocess against a real temp-git repo (the F3
bootstrap-blind residuality probe).

RED scaffold: ``des.application.slice_at_completeness`` + ``des.cli.
check_slice_at_completeness`` raise ``AssertionError("Not yet implemented --
RED scaffold")`` on every public surface, so the three scenarios fail for the
right reason (semantic AssertionError surfacing as exit 1 with a Python
traceback on stderr, classified MALFORMED by the wrapper outcome).
DELIVER's A_GREEN_ATS turns them green.
"""

from pytest_bdd import scenarios

from .steps.steps_reverify_e1 import *  # noqa: F403


scenarios("slice_01_ssot_extraction_and_wrapper.feature")
