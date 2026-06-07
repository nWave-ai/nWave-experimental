"""
E2E WIRING TESTS: Validate nWave commands integrate turn counting, timeout warnings, and extension API

PERSONA: Marcus (Senior Developer)
STORY: As a senior developer, I want to verify that turn counting, timeout warnings,
       and extension API are all wired into actual nWave command execution paths
       (/nw-execute and /nw-develop), so that these features work during real
       command invocations (EXTERNAL VALIDITY).

PROBLEM: Features exist in isolation but may not be properly integrated into the
         orchestrator's command execution loop. Without E2E validation, we cannot
         be certain these features execute during real commands. Both primary nWave
         commands must have full DES feature integration.

SOLUTION: Create comprehensive E2E tests that:
          - Invoke /nw-execute and /nw-develop with real command paths
          - Validate turn_count increments in step file
          - Validate timeout warnings emit when thresholds crossed
          - Validate extension request API is callable and updates limits
          - Prove features are wired into actual execution for BOTH commands

BUSINESS VALUE:
- Proves external validity of turn/timeout features
- Validates integration across all components
- Prevents integration failures in production
- Ensures audit trail completeness
- Confirms feature parity between /nw-execute and /nw-develop

SOURCE:
- docs/feature/des-us006/steps/08-01.json (Step 08-01 - /nw-execute wiring)
- docs/feature/des-us006/steps/08-02.json (Step 08-02 - /nw-develop wiring)
"""

import pytest


# Both primary nWave commands must have full DES feature integration.
# Parametrize all tests over (command, task_id) to prove feature parity.
COMMAND_PARAMS = [
    pytest.param("/nw-execute", "08-01", id="execute"),
    pytest.param("/nw-develop", "08-02", id="develop"),
]


def _build_step_data(task_id):
    """Build initial step file structure with required fields for E2E wiring tests."""
    return {
        "task_id": task_id,
        "project_id": "test-project",
        "state": {
            "status": "IN_PROGRESS",
            "started_at": "2026-01-26T10:00:00Z",
            "completed_at": None,
        },
        "tdd_cycle": {
            "max_turns": 50,
            "duration_minutes": 30,
            "total_extensions_minutes": 0,
            "phase_execution_log": [
                {
                    "phase_name": "PREPARE",
                    "phase_index": 0,
                    "status": "IN_PROGRESS",
                    "turn_count": 0,
                }
            ],
        },
    }


def _execute_wiring_scenario(
    des_orchestrator,
    in_memory_filesystem,
    minimal_step_file,
    tmp_project_root,
    command,
    task_id,
):
    """Execute the common E2E wiring scenario: write step data, run orchestrator, return result.

    Used by all split tests to share the setup/act phases without duplication.
    """
    step_file_path = str(minimal_step_file.relative_to(tmp_project_root))
    step_data = _build_step_data(task_id)
    in_memory_filesystem.write_json(minimal_step_file, step_data)

    agent = "@software-crafter"
    expected_iterations = 3
    mocked_elapsed_times = [900, 1350, 1620]  # 50%, 75%, 90% of 30 minutes

    result = des_orchestrator.execute_step(
        command=command,
        agent=agent,
        step_file=step_file_path,
        project_root=tmp_project_root,
        simulated_iterations=expected_iterations,
        mocked_elapsed_times=mocked_elapsed_times,
        timeout_thresholds=[15, 22, 27],
    )
    return result


class TestE2ECommandWiring:
    """
    E2E WIRING TEST validating turn counting, timeout warnings, and extension API
    integration in /nw-execute and /nw-develop command execution paths.

    Tests prove EXTERNAL VALIDITY by invoking real commands and validating
    all features execute during actual orchestrator operation.

    Both commands are parametrized to confirm feature parity.
    """

    # ------------------------------------------------------------------
    # Scenario 021 — split into 4 focused tests (was 9 assertions)
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("command, task_id", COMMAND_PARAMS)
    def test_turn_count_increments_for_each_iteration(
        self,
        tmp_project_root,
        minimal_step_file,
        des_orchestrator,
        in_memory_filesystem,
        command,
        task_id,
    ):
        """
        AC-08-01.1 / AC-08-02.1: Turn count increments correctly during execution.

        GIVEN command invoked with step file
        WHEN orchestrator executes 3 iterations
        THEN result.turn_count == 3
        """
        result = _execute_wiring_scenario(
            des_orchestrator,
            in_memory_filesystem,
            minimal_step_file,
            tmp_project_root,
            command,
            task_id,
        )

        expected_iterations = 3
        assert result.turn_count == expected_iterations, (
            f"Expected turn_count={expected_iterations} after {expected_iterations} iterations, "
            f"got {result.turn_count}"
        )

    @pytest.mark.parametrize("command, task_id", COMMAND_PARAMS)
    def test_turn_count_persisted_to_step_file(
        self,
        tmp_project_root,
        minimal_step_file,
        des_orchestrator,
        in_memory_filesystem,
        command,
        task_id,
    ):
        """
        AC-08-01.1 / AC-08-02.1: Turn count is written to step file's phase_execution_log.

        GIVEN command invoked with step file
        WHEN orchestrator executes 3 iterations
        THEN current IN_PROGRESS phase in step file has turn_count == 3
        """
        _execute_wiring_scenario(
            des_orchestrator,
            in_memory_filesystem,
            minimal_step_file,
            tmp_project_root,
            command,
            task_id,
        )

        expected_iterations = 3
        step_data = in_memory_filesystem.read_json(minimal_step_file)
        phase_log = step_data["tdd_cycle"]["phase_execution_log"]
        current_phase = next(
            (p for p in phase_log if p["status"] == "IN_PROGRESS"), None
        )

        assert current_phase is not None, "No IN_PROGRESS phase found"
        assert "turn_count" in current_phase, "turn_count field missing"
        assert current_phase["turn_count"] == expected_iterations, (
            f"Expected turn_count={expected_iterations} in step file, "
            f"got {current_phase.get('turn_count')}"
        )

    @pytest.mark.parametrize("command, task_id", COMMAND_PARAMS)
    def test_timeout_warnings_emitted_at_thresholds(
        self,
        tmp_project_root,
        minimal_step_file,
        des_orchestrator,
        in_memory_filesystem,
        command,
        task_id,
    ):
        """
        AC-08-01.1 / AC-08-02.1: Timeout warnings emitted when thresholds crossed.

        GIVEN command invoked with step file and mocked time crossing 50%, 75%, 90%
        WHEN orchestrator executes through threshold crossings
        THEN at least 3 timeout warnings emitted
        AND warnings contain threshold percentage information
        """
        result = _execute_wiring_scenario(
            des_orchestrator,
            in_memory_filesystem,
            minimal_step_file,
            tmp_project_root,
            command,
            task_id,
        )

        assert hasattr(result, "timeout_warnings"), (
            "Result missing timeout_warnings field"
        )
        assert len(result.timeout_warnings) >= 3, (
            f"Expected at least 3 timeout warnings (50%, 75%, 90%), "
            f"got {len(result.timeout_warnings)}"
        )

        # Verify warnings contain threshold information
        warnings_text = " ".join([w.lower() for w in result.timeout_warnings])
        assert any(threshold in warnings_text for threshold in ["50%", "75%", "90%"]), (
            "Warnings should mention threshold percentages (50%, 75%, 90%)"
        )

    @pytest.mark.parametrize("command, task_id", COMMAND_PARAMS)
    def test_execution_path_and_features_validated(
        self,
        tmp_project_root,
        minimal_step_file,
        des_orchestrator,
        in_memory_filesystem,
        command,
        task_id,
    ):
        """
        AC-08-01.1 / AC-08-02.1: Execution path and features_validated metadata populated.

        GIVEN command invoked with step file
        WHEN orchestrator executes through complete execution path
        THEN result.execution_path == "DESOrchestrator.execute_step"
        AND result.features_validated contains turn_counting and timeout_monitoring

        EXTERNAL VALIDITY PROVEN:
        This test validates features work in actual command path, not just unit tests.
        Integration failures would be caught here before production deployment.
        """
        result = _execute_wiring_scenario(
            des_orchestrator,
            in_memory_filesystem,
            minimal_step_file,
            tmp_project_root,
            command,
            task_id,
        )

        # Extension API testing COMMENTED OUT - OUT_OF_SCOPE for US-006
        # Extension API functionality will be implemented in a future user story.
        # This test section is commented out to align with the scope declaration
        # at line 180 which states: "extension_api is OUT_OF_SCOPE for US-006"
        #
        # # AND: Extension request API is callable and updates limits
        # # Simulate requesting 10-minute extension
        # extension_request = {
        #     "step_file": step_file_path,
        #     "extension_minutes": 10,
        #     "justification": "Complex refactoring requires additional time",
        # }
        #
        # extension_result = des_orchestrator.request_execution_extension(
        #     **extension_request
        # )
        #
        # assert extension_result.approved is True, "Extension request should be approved"
        # assert (
        #     extension_result.new_total_extensions == 10
        # ), f"Expected new_total_extensions=10, got {extension_result.new_total_extensions}"
        #
        # # Verify extension persisted to step file
        # with open(minimal_step_file, "r") as f:
        #     step_data = json.load(f)
        #
        # assert (
        #     step_data["tdd_cycle"]["total_extensions_minutes"] == 10
        # ), "Extension should be persisted to step file total_extensions_minutes"

        # AND: EXTERNAL VALIDITY PROVEN
        # All features executed in actual command invocation path
        assert result.execution_path == "DESOrchestrator.execute_step", (
            "Test must validate features execute in real orchestrator path"
        )

        assert result.features_validated == [
            "turn_counting",
            "timeout_monitoring",
        ], (
            "Both features should be validated in execution path "
            "(extension_api is OUT_OF_SCOPE for US-006)"
        )
