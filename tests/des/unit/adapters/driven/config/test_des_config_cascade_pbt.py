"""
Property-based tests for DESConfig rigor cascade resolution.

Verifies that DESConfig always produces valid, well-typed rigor settings
regardless of the config state it receives -- missing files, corrupt JSON,
empty dicts, partial rigor blocks, or any combination thereof.

Uses Hypothesis to generate random config states and assert type invariants.

Property types used:
- Invariant: rigor_* properties always return correct types with valid values
- Idempotency: loading the same config twice produces the same result
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from des.adapters.driven.config.des_config import DESConfig


# ---------------------------------------------------------------------------
# Strategies: building blocks for random config states
# ---------------------------------------------------------------------------

# Rigor field strategies -- values that could appear in config
rigor_profile_values = st.sampled_from(
    ["standard", "lean", "thorough", "custom", "exhaustive"]
)
agent_model_values = st.sampled_from(["sonnet", "haiku", "opus", "gpt-4o"])
reviewer_model_values = st.sampled_from(["haiku", "sonnet", "opus"])
tdd_phase_values = st.lists(
    st.sampled_from(["PREPARE", "RED_ACCEPTANCE", "RED_UNIT", "GREEN", "COMMIT"]),
    min_size=1,
    max_size=5,
    unique=True,
)


def rigor_block_strategy() -> st.SearchStrategy[dict[str, Any]]:
    """Generate a rigor block with random subsets of valid fields."""
    return st.fixed_dictionaries(
        {},
        optional={
            "profile": rigor_profile_values,
            "agent_model": agent_model_values,
            "reviewer_model": reviewer_model_values,
            "tdd_phases": tdd_phase_values,
            "review_enabled": st.booleans(),
            "double_review": st.booleans(),
            "mutation_enabled": st.booleans(),
            "refactor_pass": st.booleans(),
        },
    )


def valid_config_strategy() -> st.SearchStrategy[dict[str, Any]]:
    """Generate a valid JSON-serializable config dict (may or may not have rigor)."""
    return st.one_of(
        # No rigor key at all
        st.just({}),
        st.just({"audit_logging_enabled": True}),
        # Empty rigor block
        st.just({"rigor": {}}),
        # Partial or full rigor block
        st.fixed_dictionaries({"rigor": rigor_block_strategy()}),
    )


# Config file states: the file can be missing, corrupt, empty, or valid JSON
@st.composite
def config_file_state(draw: st.DrawFn) -> str:
    """Generate a config file content state.

    Returns one of:
    - "MISSING" -- file should not exist
    - "CORRUPT" -- file contains invalid JSON
    - "EMPTY" -- file contains empty string
    - A valid JSON string
    """
    state = draw(st.sampled_from(["MISSING", "CORRUPT", "EMPTY", "VALID"]))
    if state == "VALID":
        data = draw(valid_config_strategy())
        return json.dumps(data)
    return state


def _write_config_file(path: Path, state: str) -> None:
    """Write a config file according to the generated state."""
    if state == "MISSING":
        if path.exists():
            path.unlink()
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    if state == "CORRUPT":
        path.write_text("{{not valid json!!!]]", encoding="utf-8")
    elif state == "EMPTY":
        path.write_text("", encoding="utf-8")
    else:
        # state is a valid JSON string
        path.write_text(state, encoding="utf-8")


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    project_state=config_file_state(),
    global_state=config_file_state(),
)
@settings(max_examples=200, deadline=None)
def test_cascade_always_produces_valid_rigor_types(
    project_state: str,
    global_state: str,
) -> None:
    """Invariant: rigor_* properties always return correct types.

    For ANY combination of project config state and global config state,
    DESConfig must never raise an exception and must always return
    well-typed values from all rigor properties.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        project_config = base / ".nwave" / "des-config.json"
        global_config = base / "global" / ".nwave" / "global-config.json"

        _write_config_file(project_config, project_state)
        _write_config_file(global_config, global_state)

        # Construction must never raise
        config = DESConfig(
            config_path=project_config,
            global_config_path=global_config,
        )

        # All rigor properties must return correct types
        assert isinstance(config.rigor_profile, str)
        assert len(config.rigor_profile) > 0

        assert isinstance(config.rigor_agent_model, str)
        assert len(config.rigor_agent_model) > 0

        assert isinstance(config.rigor_reviewer_model, str)
        assert len(config.rigor_reviewer_model) > 0

        assert isinstance(config.rigor_tdd_phases, tuple)
        assert len(config.rigor_tdd_phases) > 0
        assert all(isinstance(phase, str) for phase in config.rigor_tdd_phases)

        assert isinstance(config.rigor_review_enabled, bool)
        assert isinstance(config.rigor_double_review, bool)
        assert isinstance(config.rigor_mutation_enabled, bool)
        assert isinstance(config.rigor_refactor_pass, bool)


@given(
    project_state=config_file_state(),
    global_state=config_file_state(),
)
@settings(max_examples=100, deadline=None)
def test_cascade_resolution_is_idempotent(
    project_state: str,
    global_state: str,
) -> None:
    """Idempotency: loading the same config twice produces identical results.

    Two DESConfig instances created from the same files must return
    the same rigor values.
    """
    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        project_config = base / ".nwave" / "des-config.json"
        global_config = base / "global" / ".nwave" / "global-config.json"

        _write_config_file(project_config, project_state)
        _write_config_file(global_config, global_state)

        config_a = DESConfig(
            config_path=project_config,
            global_config_path=global_config,
        )
        config_b = DESConfig(
            config_path=project_config,
            global_config_path=global_config,
        )

        assert config_a.rigor_profile == config_b.rigor_profile
        assert config_a.rigor_agent_model == config_b.rigor_agent_model
        assert config_a.rigor_reviewer_model == config_b.rigor_reviewer_model
        assert config_a.rigor_tdd_phases == config_b.rigor_tdd_phases
        assert config_a.rigor_review_enabled == config_b.rigor_review_enabled
        assert config_a.rigor_double_review == config_b.rigor_double_review
        assert config_a.rigor_mutation_enabled == config_b.rigor_mutation_enabled
        assert config_a.rigor_refactor_pass == config_b.rigor_refactor_pass


@given(config_data=valid_config_strategy())
@settings(max_examples=100, deadline=None)
def test_project_rigor_key_blocks_global_cascade(
    config_data: dict[str, Any],
) -> None:
    """Invariant: when project has "rigor" key, global rigor is ignored.

    If the project config contains a "rigor" key (even empty dict),
    global config rigor must have zero influence on the result.
    """
    assume("rigor" in config_data)

    with tempfile.TemporaryDirectory() as tmp:
        base = Path(tmp)
        project_config = base / ".nwave" / "des-config.json"
        global_config = base / "global" / ".nwave" / "global-config.json"

        # Write project config with rigor key
        _write_config_file(project_config, json.dumps(config_data))

        # Write global config with completely different rigor
        different_rigor = {
            "rigor": {
                "profile": "SHOULD_NOT_APPEAR",
                "agent_model": "SHOULD_NOT_APPEAR",
                "reviewer_model": "SHOULD_NOT_APPEAR",
            }
        }
        _write_config_file(global_config, json.dumps(different_rigor))

        config = DESConfig(
            config_path=project_config,
            global_config_path=global_config,
        )

        # Global values must never leak through
        assert config.rigor_profile != "SHOULD_NOT_APPEAR"
        assert config.rigor_agent_model != "SHOULD_NOT_APPEAR"
        assert config.rigor_reviewer_model != "SHOULD_NOT_APPEAR"
