"""Regression: attest-bundled-slice A2.c must scan Gherkin TAG lines only.

Found by dogfooding the F-ATTEST-BUNDLED-SLICE primitive on its first real use
(f-deliver-wave-migration slice-02, 2026-06-20): the slice's
``slice_02_divergence_bump_seam.feature`` carries an explanatory COMMENT
``# Active-RED (atdd_pure / ADR-025, NOT @skip)`` -- no actual ``@skip`` tag on
any scenario (the run reports 0 skipped). The original A2.c did a whole-content
``_DEFERRED_TAG_RE.search`` and false-refused on the ``@skip`` substring inside
the comment.

The honest contract: A2.c refuses a slice whose @slice-NN scenario is GENUINELY
deferred (a ``@skip``/``@xfail``/``@wip`` TAG), never one whose comment/prose
merely mentions the string. ``_has_deferred_tag`` scans only tag lines
(stripped line starting with ``@``).
"""

from __future__ import annotations

import importlib


_mod = importlib.import_module("des.cli.attest_bundled_slice")
_has_deferred_tag = _mod._has_deferred_tag


def test_comment_mentioning_skip_is_not_a_deferred_scenario() -> None:
    content = (
        "  # Active-RED (atdd_pure / ADR-025, NOT @skip)\n@slice-02\nScenario: x\n"
    )
    assert _has_deferred_tag(content) is False


def test_deferred_tag_in_step_prose_is_not_a_deferred_scenario() -> None:
    content = "@slice-02\nScenario: x\n  When the @wip subsystem is exercised\n"
    assert _has_deferred_tag(content) is False


def test_real_xfail_tag_on_a_scenario_is_a_deferred_scenario() -> None:
    content = "@slice-02 @xfail\nScenario: x\n"
    assert _has_deferred_tag(content) is True


def test_real_skip_tag_alone_on_a_tag_line_is_a_deferred_scenario() -> None:
    content = "@skip @slice-03\nScenario: y\n"
    assert _has_deferred_tag(content) is True
