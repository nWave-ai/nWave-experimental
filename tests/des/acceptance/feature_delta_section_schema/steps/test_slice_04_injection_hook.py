"""pytest-bdd binding — slice-04 (wave-injection from the hooks-only surface).

Driving port: `des feature-delta-schema inject --wave <w>` subprocess -- the same
pure projection a PreToolUse hook composes in-process (Invariant 4: Python +
filesystem only, no sequencer/engine). Mandate-13, Layer 3. Each step body is a
single delegation (Mandate-12).

Active-RED: at HEAD the scaffold raises, so inject exits non-zero.
"""

from __future__ import annotations

import pytest
from pytest_bdd import scenarios, then, when

from .composition import InjectComposition
from .domain_types import Wave


scenarios("../slice-04-wave-injection-hook.feature")


@pytest.fixture
def inject() -> InjectComposition:
    return InjectComposition()


# --- When --------------------------------------------------------------------


@when("the schema injects sections for the design wave")
def when_inject_design(inject: InjectComposition) -> None:
    inject.when_injected(Wave.DESIGN)


@when("the schema injects sections for the discover wave")
def when_inject_discover(inject: InjectComposition) -> None:
    inject.when_injected(Wave.DISCOVER)


# --- Then --------------------------------------------------------------------


@then("the projected rows include the section the design wave consumes")
def then_design_rows(inject: InjectComposition) -> None:
    inject.then_rows_all_consume_wave()


@then("the injection runs with Python and the filesystem only")
def then_no_engine(inject: InjectComposition) -> None:
    inject.then_no_engine_imported()


@then("the projection for a non-consuming wave is empty")
def then_empty_projection(inject: InjectComposition) -> None:
    inject.then_projection_is_empty()
