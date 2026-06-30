"""pytest-bdd binding for slice-01-feature-end-u4-wiring (distill-signoff-feature-end-wiring).

Thin binding (Mandate-12 / Mandate 10 shared-vocabulary contract): registers
the slice's scenarios and re-exports the shared step vocabulary. No business
logic here.

Sibling: walking_skeleton_feature_end_wiring/steps/test_slice_01_*.py shares
the same .feature pattern under a different feature scope; this docstring
carries the feature-specific scope tag to keep the byte-identical-guard at
tests/meta/test_collection_guard.py satisfied while preserving both bindings.
"""

from __future__ import annotations

from pytest_bdd import scenarios

from .common_steps import *


scenarios("../slice-01-feature-end-u4-wiring.feature")
