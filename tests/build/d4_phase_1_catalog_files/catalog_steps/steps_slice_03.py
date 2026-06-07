"""Step bindings for D4 Phase 1 slice-03 (flavor + log + host-bridge defaults)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, then, when

from ..conftest import REPO_ROOT


FLAVOR_SCHEMA = REPO_ROOT / "nWave" / "flavors" / "_schema.yaml"
LOG_DEFAULTS = REPO_ROOT / "nWave" / "data" / "log-persistence-defaults.yaml"
HOST_BRIDGE_EVENTS = REPO_ROOT / "nWave" / "data" / "host-bridge-events.yaml"


class S3Composition:
    def __init__(self) -> None:
        self._parsed: dict = {}

    def parse(self, path: Path, key: str) -> None:
        import yaml

        self._parsed[key] = yaml.safe_load(path.read_text())

    def get(self, key: str) -> dict:
        return self._parsed[key]


@pytest.fixture
def s3_comp() -> S3Composition:
    return S3Composition()


@given(parsers.parse('the flavor schema file at "{path}"'))
def given_flavor_schema(s3_comp, path: str) -> None:
    s3_comp.parse(FLAVOR_SCHEMA, "flavor_schema")


@given(parsers.parse('the log defaults file at "{path}"'))
def given_log_defaults(s3_comp, path: str) -> None:
    s3_comp.parse(LOG_DEFAULTS, "log_defaults")


@given(parsers.parse('the host-bridge events file at "{path}"'))
def given_host_bridge(s3_comp, path: str) -> None:
    s3_comp.parse(HOST_BRIDGE_EVENTS, "host_bridge")


@when("the schema is parsed")
def when_parse_schema(s3_comp) -> None:
    pass  # already parsed in @given


@when("the defaults are parsed")
def when_parse_defaults(s3_comp) -> None:
    pass


@when("the events vocabulary is parsed")
def when_parse_events(s3_comp) -> None:
    pass


@then("the schema has a top-level $schema declaring draft/2020-12")
def then_schema_draft(s3_comp) -> None:
    schema = s3_comp.get("flavor_schema")
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


@then("the schema requires flavor_id, description, lifecycle_events fields")
def then_schema_required(s3_comp) -> None:
    schema = s3_comp.get("flavor_schema")
    required = set(schema["required"])
    assert required == {"flavor_id", "description", "lifecycle_events"}, (
        f"required={required}"
    )


@then("the schema defines a GateInvocation $def with gate_id + on_failure")
def then_schema_gateinvocation(s3_comp) -> None:
    schema = s3_comp.get("flavor_schema")
    gi = schema["$defs"]["GateInvocation"]
    required = set(gi["required"])
    assert "gate_id" in required and "on_failure" in required, (
        f"GateInvocation required={required}"
    )


@then(parsers.parse('the active_adapter equals "{expected}"'))
def then_active_adapter(s3_comp, expected: str) -> None:
    defaults = s3_comp.get("log_defaults")
    assert defaults["active_adapter"] == expected


@then(parsers.parse('the adapters dict contains keys "{a}", "{b}", "{c}"'))
def then_adapters_keys(s3_comp, a: str, b: str, c: str) -> None:
    defaults = s3_comp.get("log_defaults")
    keys = set(defaults["adapters"].keys())
    expected = {a, b, c}
    assert expected.issubset(keys), (
        f"adapters keys={keys}, expected superset of {expected}"
    )


@then("the jsonl adapter declares per_feature_path AND common_log_path AND fanout")
def then_jsonl_fields(s3_comp) -> None:
    defaults = s3_comp.get("log_defaults")
    jsonl = defaults["adapters"]["jsonl"]
    assert "per_feature_path" in jsonl
    assert "common_log_path" in jsonl
    assert "fanout" in jsonl


@then(parsers.parse("at least {n:d} abstract events are declared"))
def then_min_events(s3_comp, n: int) -> None:
    events = s3_comp.get("host_bridge")["events"]
    assert len(events) >= n, f"event count={len(events)}, expected ≥{n}"


@then("every event lists hosts dict with keys claude-code, codex, opencode, git-hook")
def then_events_hosts(s3_comp) -> None:
    events = s3_comp.get("host_bridge")["events"]
    required_hosts = {"claude-code", "codex", "opencode", "git-hook"}
    missing = []
    for e in events:
        host_keys = set(e["hosts"].keys())
        if not required_hosts.issubset(host_keys):
            missing.append(f"{e['id']}: hosts={host_keys}")
    assert not missing, f"Events missing host keys: {missing}"


@then(parsers.parse('the events include "{e1}", "{e2}", "{e3}", "{e4}"'))
def then_events_include(s3_comp, e1: str, e2: str, e3: str, e4: str) -> None:
    event_ids = {e["id"] for e in s3_comp.get("host_bridge")["events"]}
    expected = {e1, e2, e3, e4}
    missing = expected - event_ids
    assert not missing, f"Missing event ids: {missing}"
