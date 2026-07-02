"""slice-05 acceptance: the dead per-feature mutation knob is removed (JOB-002).

REMOVAL slice (DD-D2, @infrastructure) -- proves the absence of a surface that
still exists today, so each scenario is active-RED until DELIVER deletes it:

Driving surfaces (real, in-process, hermetic -- no interpreter fork, no
``~/.claude`` path):
  (a) a REAL ``DESConfig`` over a real ``tmp_path/.nwave/des-config.json`` --
      the SAME in-process config-adapter surface slices 01-04 drive --
      asserting the knob accessor ``rigor_mutation_enabled`` is ABSENT.
  (b) a REAL file read of the shipped ``nWave/skills/nw-rigor/SKILL.md``
      (repo-relative via ``parents[5]``; not a personal-hook path, so the
      acceptance hermeticity guard is satisfied) asserting the literal token
      ``mutation_enabled`` is ABSENT.

Active-RED topology (nw-distill-red-scaffolding P1-P4):
  P1  module-top imports ONLY the stable shipped ``DESConfig`` entry (present
      at HEAD); no not-yet-implemented module is imported -> collection
      cannot ImportError -> RED, not BROKEN. (This slice is REMOVAL: nothing
      new is built, so there is nothing absent to import -- the absence is
      observed at runtime.)
  P2  scenario (a) drives ``DESConfig`` in-process; ``hasattr`` triggers the
      property getter (which returns ``False`` without raising) -> ``hasattr``
      is True TODAY.
  P3  the to-be-absent surface is reached at RUNTIME inside the ``Then``
      (``hasattr`` / file-token membership), never at collection.
  P4  the failure is a semantic ``AssertionError`` -- "knob still present,
      must be removed" with DELIVER guidance -- NOT an import/collection/
      AttributeError. DELIVER deletes the property (a) and the guide rows (b)
      -> both ``Then``s pass.

RED strategy (explicit, per the slice-05 task):
  (a) RED because ``@property rigor_mutation_enabled`` still exists on
      ``DESConfig`` (``des_config.py`` ~L415) -> ``hasattr(config,
      "rigor_mutation_enabled")`` is True -> ``assert not hasattr(...)``
      fails with a semantic AssertionError.
  (b) RED because the literal token ``mutation_enabled`` appears 5x in the
      shipped guide (``nw-rigor/SKILL.md`` L31/220/240/274/391) -> ``assert
      "mutation_enabled" not in text`` fails with a semantic AssertionError.
  No schema scenario: no config schema lists the token (confirmed ZERO in
  ``step-tdd-cycle-schema.json`` + ``atdd-pure-phase-sequence.schema.json``)
  -> an absence-assertion there would be a vacuous green, not active-RED, so
  it is intentionally omitted.

Resolution/observation is a pure read (config/file in -> presence out,
nothing mutated): @contract-shape:pure-function. No observable state mutates
-> Mandate-8 state-delta does not apply; example-based assertions per
Mandate-9 (layer-3 example-only).

The real-DESConfig construction shape mirrors the slice-01..04 binding
inline. The ``ctx`` fixture and ``_write_project_config`` helper were
consolidated into ``steps/conftest.py`` at feature-end (whole-feature L1-L6
batch refactor).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pytest_bdd import given, scenarios, then, when

from des.adapters.driven.config.des_config import DESConfig

from .conftest import _write_project_config


scenarios("../slice-05-remove-dead-mutation-knob.feature")


# ---------------------------------------------------------------------------
# Scenario (a): the real config-reader surface, in-process
# ---------------------------------------------------------------------------


@given("a project rigor configuration surface backed by a real DESConfig")
def given_project_under_rigor(ctx: dict[str, Any], tmp_path: Path) -> None:
    config_path = _write_project_config(tmp_path, {"mutation_enabled": False})
    ctx["config"] = DESConfig(
        config_path=config_path,
        global_config_path=tmp_path / "home" / ".nwave" / "global-config.json",
    )


@when("the rigor configuration surface is inspected for the mutation knob")
def when_inspect_config_surface(ctx: dict[str, Any]) -> None:
    # Pure inspection -- no mutation of the surface under test.
    ctx["config"] = ctx["config"]


@then("the config reader exposes no rigor_mutation_enabled accessor")
def then_no_mutation_knob_on_config(ctx: dict[str, Any]) -> None:
    assert not hasattr(ctx["config"], "rigor_mutation_enabled"), (
        "DESConfig.rigor_mutation_enabled must be REMOVED (DD-D2) -- mutation "
        "is CI-nightly-only (project strategy nightly-delta) with ZERO "
        "production readers of this per-feature knob; delete the @property "
        "at src/des/adapters/driven/config/des_config.py (~L414-417)"
    )


# ---------------------------------------------------------------------------
# Scenario (b): the shipped nw-rigor guide, real file read
# ---------------------------------------------------------------------------


def _nw_rigor_skill_path() -> Path:
    # tests/des/acceptance/rigor_review_step_toggles/steps/this_file.py
    #   parents[0]=steps  [1]=rigor_review_step_toggles  [2]=acceptance
    #   [3]=des  [4]=tests  [5]=repo root
    repo_root = Path(__file__).resolve().parents[5]
    return repo_root / "nWave" / "skills" / "nw-rigor" / "SKILL.md"


@given("the shipped nw-rigor quality-profile guide")
def given_rigor_guide(ctx: dict[str, Any]) -> None:
    guide_path = _nw_rigor_skill_path()
    assert guide_path.is_file(), f"shipped guide not found at {guide_path}"
    ctx["guide_path"] = guide_path
    ctx["guide_text"] = guide_path.read_text(encoding="utf-8")


@when("the rigor guide is inspected for the mutation knob token")
def when_inspect_guide(ctx: dict[str, Any]) -> None:
    # Pure inspection -- no mutation of the shipped guide under test.
    ctx["guide_text"] = ctx["guide_text"]


@then("the rigor guide contains no mutation_enabled token")
def then_no_mutation_knob_in_guide(ctx: dict[str, Any]) -> None:
    occurrences = ctx["guide_text"].count("mutation_enabled")
    assert occurrences == 0, (
        f"{ctx['guide_path']} still contains {occurrences} occurrence(s) of "
        "'mutation_enabled' -- DD-D2 requires dropping the profile-table row, "
        "the Mode-3 Step-7 settings list, the comparison table row, and the "
        "detail-view rows from nWave/skills/nw-rigor/SKILL.md"
    )
