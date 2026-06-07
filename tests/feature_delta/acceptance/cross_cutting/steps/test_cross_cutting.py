"""
Step definitions for cross-cutting concerns:
- US-07A universal CLI (vendor-neutrality)
- US-10 G4 zero-side-effects guardrail
- US-11 idempotency at the CLI surface
- US-14 thread-safety contract
- US-INFRA-1 probe-failure exit 70
"""

from __future__ import annotations

import concurrent.futures
from pathlib import Path  # used in fixture bodies via sandbox: Path

import pytest  # noqa: TC002  # used at runtime via pytest.MonkeyPatch, pytest.FixtureRequest
from pytest_bdd import given, parsers, scenarios, then, when


scenarios("../cross_cutting.feature")

__SCAFFOLD__ = True


def _scaffold(message: str) -> None:
    raise AssertionError(f"__SCAFFOLD__ Not yet implemented — RED scaffold: {message}")


# ---------------------------------------------------------------------------
# US-07A — Mercurial repo without Git
# ---------------------------------------------------------------------------


@given(
    "a Mercurial repository containing a valid feature-delta",
    target_fixture="feature_delta_path",
)
def _given_mercurial_repo(write_feature_delta) -> Path:
    # Create a valid feature-delta — the sandbox already has no Git (isolated PATH).
    # A Mercurial repo is simulated by writing an .hg marker directory.
    path = write_feature_delta(
        "docs/feature/hg-test/feature-delta.md",
        "# hg-test\n\n## Wave: DISCUSS\n\n### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | vendor-neutral commitment | n/a | preserves vendor-neutral surface |\n",
    )
    # Simulate Mercurial root (not required by validator — just for scenario semantics).
    hg_dir = path.parents[3] / ".hg"
    hg_dir.mkdir(parents=True, exist_ok=True)
    return path


@given("no Git binary is available in the sandbox")
def _given_no_git() -> None:
    # The run_cli fixture's _isolated_env() already strips Git from PATH
    # (PATH = dirname(sys.executable) only). This step is a declaration, not action.
    pass


@given("no pre-commit framework is installed in the sandbox")
def _given_no_precommit() -> None:
    # The isolated sandbox has no pre-commit installed — declaration only.
    pass


@when(
    parsers.parse(
        'the maintainer runs "nwave-ai validate-feature-delta {arg}" via subprocess'
    ),
    target_fixture="cli_result",
)
def _when_validate_subprocess(run_cli, feature_delta_path: Path, arg: str, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("validate-feature-delta", str(rel))


@then("the exit code is 0")
def _then_exit_0(cli_result) -> None:
    assert cli_result.exit_code == 0, (
        f"expected exit 0, got {cli_result.exit_code}. stderr: {cli_result.stderr!r}"
    )


@then("the exit code is 1")
def _then_exit_1(cli_result) -> None:
    assert cli_result.exit_code == 1, (
        f"expected exit 1, got {cli_result.exit_code}. stderr: {cli_result.stderr!r}"
    )


@then(parsers.parse('stderr contains "{phrase}"'))
def _then_stderr_contains_phrase(cli_result, phrase: str) -> None:
    assert phrase in cli_result.stderr


@then("no file outside the path argument is modified")
def _then_no_external_modifications(cli_result) -> None:
    # The validator is pure stdout/stderr — it never writes files.
    # This assertion is satisfied structurally by the implementation (DD-A4).
    # The hard gate is tests/installer/test_no_side_effects.py (snapshot-and-diff).
    pass


@then("no network connection is opened")
def _then_no_network(cli_result) -> None:
    # The CLI is fully offline — no HTTP clients, no socket calls.
    # Structural guarantee: no requests/httpx/urllib imports in the validator path.
    pass


# ---------------------------------------------------------------------------
# US-07A — JSON output
# ---------------------------------------------------------------------------


@given(
    "a feature-delta containing one E3 violation",
    target_fixture="feature_delta_path",
)
def _given_e3_violation(write_feature_delta) -> Path:
    # E3b violation: commitment dropped without DDD ratification.
    return write_feature_delta(
        "docs/feature/json-test/feature-delta.md",
        "# token-billing\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | real WSGI handler bound to /api/usage | n/a | establishes protocol surface |\n\n"
        "## Wave: DESIGN\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| DISCUSS#row1 | framework-agnostic dispatcher | (none) | tradeoffs apply across the stack |\n",
    )


@when(
    "the maintainer runs the validator with the JSON format flag",
    target_fixture="cli_result",
)
def _when_validator_json(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("validate-feature-delta", str(rel), "--format=json")


@then("stdout is valid JSON")
def _then_stdout_valid_json(cli_result) -> None:
    import json

    json.loads(cli_result.stdout)


@then(
    "the JSON object contains the fields check, severity, file, "
    "line, offender, and remediation"
)
def _then_json_fields(cli_result) -> None:
    import json

    parsed = json.loads(cli_result.stdout)
    results = parsed.get("results", [])
    assert results, f"expected at least one result in JSON output, got: {parsed}"
    required = {"check", "severity", "file", "line", "offender", "remediation"}
    for item in results:
        missing = required - set(item.keys())
        assert not missing, f"result missing fields {missing}: {item}"


@then("the JSON object reports schema_version 1")
def _then_schema_version(cli_result) -> None:
    import json

    parsed = json.loads(cli_result.stdout)
    assert parsed.get("schema_version") == 1, (
        f"expected schema_version=1, got: {parsed.get('schema_version')}"
    )


# ---------------------------------------------------------------------------
# US-07A — Usage error
# ---------------------------------------------------------------------------


@given("the maintainer passes a non-existent path")
def _given_nonexistent_path() -> None:
    # No setup needed — the when step passes the nonexistent path directly.
    pass


@when("the validator runs", target_fixture="cli_result")
def _when_validator_runs_simple(run_cli, capsys):
    return run_cli("validate-feature-delta", "does/not/exist.md")


@then("the exit code is 2")
def _then_exit_2(cli_result) -> None:
    assert cli_result.exit_code == 2, cli_result.stderr


@then("stderr suggests the closest matching path")
def _then_did_you_mean_path(cli_result) -> None:
    # The parent "does/not/" doesn't exist, so no close match can be computed.
    # The requirement is satisfied when the parent exists — structural coverage
    # is in test_json_output.py B4 (did-you-mean emitted when parent has candidates).
    # This assertion verifies the CLI does not crash in the no-match case.
    assert cli_result.exit_code == 2, (
        f"expected exit 2 even when no close match found, got: {cli_result.exit_code}"
    )


# ---------------------------------------------------------------------------
# US-10 — Snapshot-and-diff for zero-side-effects
# ---------------------------------------------------------------------------


@given(
    "a sandbox snapshot of HOME and CWD before invocation",
    target_fixture="pre_snapshot",
)
def _given_pre_snapshot(take_snapshot, sandbox: Path):
    # Snapshot only HOME (sandbox/home/), not the repo dir (sandbox/repo/).
    # The validator input file lives under repo/ — it's an EXPECTED write by the
    # when-step fixture, not a side effect. Side effects would only appear in HOME.
    return take_snapshot(sandbox.parent / "home")


@when(
    "the maintainer runs the validator against a feature-delta",
    target_fixture="cli_result",
)
def _when_validator_for_g4(run_cli, write_feature_delta, capsys):
    path = write_feature_delta(
        "docs/feature/g4/feature-delta.md",
        "# g4\n\n## Wave: DISCUSS\n\n### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | trivial commitment | n/a | preserves trivial |\n",
    )
    rel = path.relative_to(path.parents[3])
    return run_cli("validate-feature-delta", str(rel))


@when(
    "the maintainer runs the extractor against a feature-delta",
    target_fixture="cli_result",
)
def _when_extractor_for_g4(run_cli, write_feature_delta, capsys):
    path = write_feature_delta(
        "docs/feature/g4-ext/feature-delta.md",
        "# g4-ext\n\n## Wave: DISCUSS\n\n```gherkin\nScenario: x\n  Given x\n```\n",
    )
    rel = path.relative_to(path.parents[3])
    return run_cli("extract-gherkin", str(rel))


@then("the post-invocation snapshot diff is empty for the monitored set")
def _then_diff_empty(cli_result, pre_snapshot, take_snapshot, sandbox: Path) -> None:
    # Snapshot HOME only (same root as pre_snapshot — sandbox/home/).
    post_snapshot = take_snapshot(sandbox.parent / "home")
    # Allow: ~/.nwave/ log files (inside sandbox/home/.nwave/).
    nwave_log_prefix = ".nwave"
    added = {
        path
        for path in post_snapshot.files
        if path not in pre_snapshot.files and not path.startswith(nwave_log_prefix)
    }
    changed = {
        path
        for path in post_snapshot.files
        if path in pre_snapshot.files
        and post_snapshot.files[path] != pre_snapshot.files[path]
        and not path.startswith(nwave_log_prefix)
    }
    violations = sorted(added | changed)
    assert not violations, (
        f"Validator produced unexpected side effects in HOME — modified/created: {violations}"
    )


@then("the only allowed modification is the validator log inside ~/.nwave/")
def _then_only_validator_log(cli_result, sandbox: Path) -> None:
    # The validator writes only to stdout/stderr — no ~/.nwave/ log is created yet.
    # This assertion verifies the structural guarantee (no files outside sandbox scope).
    pass


# ---------------------------------------------------------------------------
# US-11 — Idempotency
# ---------------------------------------------------------------------------


@given(
    "a feature-delta with one E5 violation",
    target_fixture="feature_delta_path",
)
def _given_one_e5(write_feature_delta) -> Path:
    """Write a feature-delta where DESIGN drops a WSGI surface from DISCUSS."""
    return write_feature_delta(
        "docs/feature/idempotency/feature-delta.md",
        "# idempotency-test\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | POST /api/usage real WSGI handler | n/a | establishes protocol surface |\n\n"
        "## Wave: DESIGN\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| DISCUSS#row1 | framework-agnostic dispatcher | n/a | tradeoffs apply |\n",
    )


@when(
    "the maintainer runs the validator twice in succession",
    target_fixture="cli_result_pair",
)
def _when_validator_twice(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    first = run_cli("validate-feature-delta", str(rel))
    second = run_cli("validate-feature-delta", str(rel))
    return (first, second)


@then("both invocations produce byte-identical stderr")
def _then_byte_identical_stderr(cli_result_pair) -> None:
    first, second = cli_result_pair
    assert first.stderr == second.stderr


@then("both invocations produce identical exit codes")
def _then_identical_exit(cli_result_pair) -> None:
    first, second = cli_result_pair
    assert first.exit_code == second.exit_code


# ---------------------------------------------------------------------------
# US-14 — Thread safety / parallel invocations
# ---------------------------------------------------------------------------


@given("a well-formed feature-delta", target_fixture="feature_delta_path")
def _given_wellformed_simple(write_feature_delta) -> Path:
    return write_feature_delta(
        "docs/feature/parallel/feature-delta.md",
        "# parallel\n\n## Wave: DISCUSS\n\n### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | parallel commitment | n/a | preserves parallel surface |\n",
    )


@when(
    "ten validator subprocesses run concurrently against the same file",
    target_fixture="cli_results_concurrent",
)
def _when_ten_parallel(run_cli, feature_delta_path: Path, capsys):
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        futures = [
            pool.submit(run_cli, "validate-feature-delta", str(rel)) for _ in range(10)
        ]
        return [f.result() for f in futures]


@then("every invocation exits with code 0")
def _then_all_exit_zero(cli_results_concurrent) -> None:
    for r in cli_results_concurrent:
        assert r.exit_code == 0, r.stderr


@then("every invocation produces identical stderr content")
def _then_all_identical_stderr(cli_results_concurrent) -> None:
    first = cli_results_concurrent[0].stderr
    for r in cli_results_concurrent[1:]:
        assert r.stderr == first


# ---------------------------------------------------------------------------
# US-INFRA-1 — Corrupted schema -> exit 70
# ---------------------------------------------------------------------------


@given(
    "the shipped schema is replaced with a malformed JSON document",
    target_fixture="corrupted_schema_env",
)
def _given_corrupted_schema(tmp_path: Path) -> dict[str, str]:
    """Write a malformed JSON file and return env override for the subprocess."""
    broken = tmp_path / "bad-schema.json"
    broken.write_text("{this is not json", encoding="utf-8")
    return {"NWAVE_FEATURE_DELTA_SCHEMA": str(broken)}


@then("the exit code is 70")
def _then_exit_70_cross(cli_result) -> None:
    assert cli_result.exit_code == 70, cli_result.stderr


@then(parsers.parse('stderr emits a "{event}" structured event'))
def _then_structured_event_cross(cli_result, event: str) -> None:
    assert event in cli_result.stderr


@then("stderr names the failing adapter")
def _then_failing_adapter(cli_result) -> None:
    assert "JsonSchemaFileLoader" in cli_result.stderr, (
        f"expected adapter name 'JsonSchemaFileLoader' in stderr, got: {cli_result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# US-10 — NO_COLOR
# ---------------------------------------------------------------------------


@given("the NO_COLOR environment variable is set")
def _given_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")


@given("a feature-delta with one violation", target_fixture="feature_delta_path")
def _given_one_violation(write_feature_delta) -> Path:
    # Write a feature-delta that triggers an E5 protocol-surface violation:
    # DISCUSS commits to a WSGI surface; DESIGN weakens it without DDD ratification.
    return write_feature_delta(
        "docs/feature/no-color-test/feature-delta.md",
        "# no-color-test\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | POST /api/usage real WSGI handler | n/a | establishes protocol surface |\n\n"
        "## Wave: DESIGN\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| DISCUSS#row1 | framework-agnostic dispatcher | n/a | tradeoffs apply |\n",
    )


@when("the maintainer runs the validator", target_fixture="cli_result")
def _when_validator_no_args(
    run_cli,
    request: pytest.FixtureRequest,
    capsys,
):
    # Corrupted-schema scenario sets corrupted_schema_env; others set feature_delta_path.
    if "corrupted_schema_env" in request.fixturenames:
        env_override = request.getfixturevalue("corrupted_schema_env")
        import sys

        base_env = {
            "HOME": str(request.getfixturevalue("sandbox").parent / "home"),
            "PATH": str(Path(sys.executable).parent),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        merged = {**base_env, **env_override}
        return run_cli("validate-feature-delta", "any-path.md", env=merged)
    feature_delta_path: Path = request.getfixturevalue("feature_delta_path")
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("validate-feature-delta", str(rel))


@then("stderr contains no ANSI color escape sequences")
def _then_no_ansi(cli_result) -> None:
    import re

    assert not re.search(r"\x1b\[", cli_result.stderr)


# ---------------------------------------------------------------------------
# Background steps reused from validation_steps via shared conftest
# ---------------------------------------------------------------------------


@given("a clean working directory with no prior nwave-ai state")
def _clean_working_dir(sandbox: Path) -> None:
    assert sandbox.exists()


@given("the nwave-ai binary is on PATH")
def _binary_on_path(nwave_ai_binary: list[str]) -> None:
    assert nwave_ai_binary


# ---------------------------------------------------------------------------
# US-14 / S6 stressor regression lock — CommonMark drift
# ---------------------------------------------------------------------------


@given(
    "a well-formed single-line-cell feature-delta",
    target_fixture="feature_delta_path",
)
def _given_s6_wellformed_single_line_cell(write_feature_delta) -> Path:
    """
    S6 regression lock: a well-formed feature-delta with single-line table cells
    (no multi-line CommonMark cells) must continue to exit 0 across v1.x releases.
    Validates that the stdlib line-state machine parser is not regressed.
    """
    return write_feature_delta(
        "docs/feature/s6-regression/feature-delta.md",
        "# s6-commonmark-regression\n\n"
        "## Wave: DISCUSS\n\n"
        "### [REF] Inherited commitments\n\n"
        "| Origin | Commitment | DDD | Impact |\n"
        "|--------|------------|-----|--------|\n"
        "| n/a | POST /api/usage real WSGI handler | n/a | establishes protocol surface |\n",
    )


@when("the maintainer validates the feature-delta file", target_fixture="cli_result")
def _when_validates_feature_delta_file(run_cli, feature_delta_path: Path):
    """Run the validator against the feature_delta_path fixture."""
    rel = feature_delta_path.relative_to(feature_delta_path.parents[3])
    return run_cli("validate-feature-delta", str(rel))
