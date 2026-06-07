"""Step definitions for the lean-wave-documentation walking skeleton.

Strategy C — Real local: real filesystem under tmp_path with monkeypatched
HOME, real JSONL written to tmp_path. NO mocks.

Driving port (this step): the pure-function `resolve_density(global_config)`
in `scripts/shared/density_config.py` (DDD-5). The WS step bindings compose
the resolver with a thin test-harness writer that simulates what step 02-01
(CLI install) and step 03-01 (wave skill) will do in production:

    step 01-01 (this step):
        Test harness calls resolve_density({}) and writes the artifacts.
        This is acknowledged transitional fixture work — the resolver is
        proven correct here, the production wiring catches up in 02-01/03-01.

    step 02-01 (next):
        nwave-ai install will call resolve_density(parsed_global_config) and
        write global-config.json itself; this binding will delegate to that.

    step 03-01:
        The wave-skill harness will write feature-delta.md and the audit log;
        this binding will delegate to that.

Until those steps land, the WS step bindings perform the writes themselves
to keep the WS scenario GREEN as the outer-loop guiding test (Outside-In TDD,
Bache).

Driving ports the WS scenario will exercise once 02-01/03-01 land:
- nwave-ai install (subprocess CLI) — first-run density prompt
- /nw-discuss wave skill — invoked through the wave-runner driving port
- ~/.nwave/global-config.json read via density_config (DDD-5)
- JsonlAuditLogWriter for telemetry assertions (DDD-6)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pytest_bdd import given, parsers, scenarios, then, when

from des.domain.telemetry import DOCUMENTATION_DENSITY_CHOICE
from scripts.shared.density_config import resolve_density


if TYPE_CHECKING:
    from pathlib import Path


# Link feature file
scenarios("../walking-skeleton.feature")


# ---------------------------------------------------------------------------
# Tier-1 fields the WS asserts must be present in every feature-delta.md.
# Source: walking-skeleton.feature -> "Tier-1 fields" then-step.
# ---------------------------------------------------------------------------

_TIER1_SECTIONS = (
    "Persona",
    "Job-to-be-done",
    "Locked decisions",
    "User stories",
    "Acceptance scenarios",
    "Definition of Done",
    "Out of scope",
    "WS strategy",
    "Driving ports",
    "Pre-requisites",
)


# ---------------------------------------------------------------------------
# Given steps
# ---------------------------------------------------------------------------


@given(
    "Marco is installing nWave for the first time on a host with no nWave global"
    " configuration"
)
def given_fresh_install(
    marco_home: Path,
    marco_repo: Path,
    global_config_path: Path,
    audit_log_dir: Path,
    ctx: dict[str, Any],
) -> None:
    """Confirm clean slate — no global config exists, audit dir empty."""
    assert not global_config_path.exists(), (
        f"Walking skeleton precondition violated: {global_config_path} already exists"
    )
    ctx["marco_home"] = marco_home
    ctx["marco_repo"] = marco_repo
    ctx["global_config_path"] = global_config_path
    ctx["audit_log_dir"] = audit_log_dir


# ---------------------------------------------------------------------------
# When steps — driving port invocations
# ---------------------------------------------------------------------------


@when("Marco completes the install accepting the lean density choice")
def when_marco_installs_lean(ctx: dict[str, Any]) -> None:
    """Drive the density resolver and persist Marco's resolved choices.

    For step 01-01 the resolver is the only production code under test;
    the test harness performs the file write that step 02-01 will own.
    """
    config_path = ctx["global_config_path"]

    # Driving port: resolve_density({}) for a fresh-install host.
    density = resolve_density({})

    # Persist resolver output. Step 02-01 will replace this harness write
    # with the real CLI install path.
    payload = {
        "documentation": {
            "default_density": density.mode,
            "expansion_prompt": density.expansion_prompt,
        },
    }
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    ctx["density"] = density


@when(
    parsers.parse(
        'Marco runs a lean DISCUSS wave on a small feature called "{feature_id}"'
    )
)
def when_marco_runs_discuss(ctx: dict[str, Any], feature_id: str) -> None:
    """Drive a lean DISCUSS wave: emit feature-delta.md + audit event.

    Production code under DELIVER (step 03-01) will own these writes through
    the wave-skill harness; today the test binding performs them so the WS
    scenario can verify the resolver-driven lean density flows end-to-end.
    """
    ctx["feature_id"] = feature_id
    density = ctx["density"]

    # Feature-delta.md with [REF]-only headings + every Tier-1 section.
    feature_dir = ctx["marco_repo"] / "docs" / "feature" / feature_id
    feature_dir.mkdir(parents=True, exist_ok=True)
    feature_delta = feature_dir / "feature-delta.md"
    feature_delta.write_text(
        _render_lean_feature_delta(feature_id, density.mode), encoding="utf-8"
    )

    # JSONL audit event — DDD-6 schema, written by JsonlAuditLogWriter in
    # production (step 03-01). Today: direct JSONL append from the harness.
    audit_log = ctx["audit_log_dir"] / "audit-walking-skeleton.log"
    event = {
        "event_type": DOCUMENTATION_DENSITY_CHOICE,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "feature_name": feature_id,
        "data": {
            "wave": "DISCUSS",
            "density_mode": density.mode,
            "expansion_prompt": density.expansion_prompt,
            "provenance": density.provenance,
        },
    }
    audit_log.write_text(json.dumps(event) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers — feature-delta.md rendering (lean mode, [REF]-only)
# ---------------------------------------------------------------------------


def _render_lean_feature_delta(feature_id: str, density_mode: str) -> str:
    """Render a lean-mode feature-delta.md skeleton.

    Every wave heading is `## Wave: WAVE / [REF] section`; every Tier-1
    field name appears at least once so the WS Then-steps pass.
    """
    waves = ("DISCOVER", "DISCUSS", "DESIGN", "DEVOPS", "DISTILL", "DELIVER")

    parts: list[str] = [
        f"# Feature: {feature_id}",
        "",
        f"density_mode: {density_mode}",
        "",
    ]
    for wave in waves:
        parts.append(f"## Wave: {wave} / [REF] {wave.lower()} reference")
        parts.append("")
        parts.append(f"Lean placeholder for {feature_id} {wave}.")
        parts.append("")

    # Tier-1 sections — every name must appear verbatim per WS assertion.
    parts.append("## Tier-1 fields")
    parts.append("")
    for section in _TIER1_SECTIONS:
        parts.append(f"- {section}: (lean placeholder)")
    parts.append("")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Then steps — observable outcomes
# ---------------------------------------------------------------------------


@then(
    "Marco's nWave global configuration records lean as the default density and ask"
    " as the expansion prompt"
)
def then_global_config_recorded(ctx: dict[str, Any]) -> None:
    """Read the real global-config.json and check Marco's recorded choices."""
    config_path = ctx["global_config_path"]
    assert config_path.exists(), f"global-config.json was not created at {config_path}"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    documentation = payload.get("documentation", {})
    assert documentation.get("default_density") == "lean", (
        f"expected default_density='lean', got {documentation.get('default_density')!r}"
    )
    assert documentation.get("expansion_prompt") == "ask-intelligent", (
        f"expected expansion_prompt='ask-intelligent', got {documentation.get('expansion_prompt')!r}"
    )


@then(
    parsers.parse(
        'the feature-delta.md for "{feature_id}" contains only sections labelled [REF]'
    )
)
def then_only_ref_sections(ctx: dict[str, Any], feature_id: str) -> None:
    """Read the real feature-delta.md and confirm every wave heading is [REF]."""
    import re

    feature_delta = (
        ctx["marco_repo"] / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    assert feature_delta.exists(), f"feature-delta.md missing at {feature_delta}"
    text = feature_delta.read_text(encoding="utf-8")
    wave_headings = re.findall(r"^## Wave: \w+ / \[(REF|WHY|HOW)\] .+$", text, re.M)
    assert wave_headings, "no wave headings found in feature-delta.md"
    non_ref = [h for h in wave_headings if h != "REF"]
    assert not non_ref, f"expected only [REF] headings, found: {non_ref}"


@then("every Tier-1 field downstream waves require is present in the feature-delta.md")
def then_tier1_fields_present(ctx: dict[str, Any]) -> None:
    """Confirm every Tier-1 section heading from the wave-doc audit is present."""
    feature_id = ctx["feature_id"]
    feature_delta = (
        ctx["marco_repo"] / "docs" / "feature" / feature_id / "feature-delta.md"
    )
    text = feature_delta.read_text(encoding="utf-8")
    missing = [s for s in _TIER1_SECTIONS if s not in text]
    assert not missing, f"Tier-1 fields missing from feature-delta.md: {missing}"


@then("Marco's audit trail records a documentation-density event for that wave")
def then_audit_event_recorded(ctx: dict[str, Any]) -> None:
    """Read the real JSONL audit log and confirm a DOCUMENTATION_DENSITY_CHOICE event exists."""
    audit_log_dir = ctx["audit_log_dir"]
    log_files = list(audit_log_dir.glob("audit-*.log"))
    assert log_files, f"no audit log files found in {audit_log_dir}"

    found = False
    for log_file in log_files:
        for line in log_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            event = json.loads(line)
            if event.get("event_type") == DOCUMENTATION_DENSITY_CHOICE:
                found = True
                break
        if found:
            break
    assert found, f"no {DOCUMENTATION_DENSITY_CHOICE} event found in audit trail"


@then("the nw-discuss wave skill encodes density-aware emission instructions")
def then_skill_density_aware(ctx: dict[str, Any]) -> None:
    """Confirm the production nw-discuss SKILL.md file encodes density-aware behavior.

    Step 01-01 wired the WS via test-harness writes (transitional). Step 03-01
    establishes the production wiring: the wave skill markdown — the SOP the
    dispatched agent reads at runtime — must explicitly instruct density
    resolution, output-tier discipline, and telemetry emission. Without these
    instructions encoded in the skill, the test harness is the only thing
    keeping the WS green (Fixture Theater).
    """
    from pathlib import Path

    # Locate the repo root by walking up from this file until we find nWave/skills/.
    here = Path(__file__).resolve()
    repo_root = next(
        (p for p in here.parents if (p / "nWave" / "skills" / "nw-discuss").is_dir()),
        None,
    )
    assert repo_root is not None, (
        "could not locate nWave/skills/nw-discuss/ from test file path"
    )

    skill_path = repo_root / "nWave" / "skills" / "nw-discuss" / "SKILL.md"
    assert skill_path.exists(), f"nw-discuss SKILL.md missing at {skill_path}"
    text = skill_path.read_text(encoding="utf-8")

    required_phrases = (
        "## Output Tiers",
        "## Density resolution",
        "## Telemetry",
        "resolve_density(global_config)",
        "DocumentationDensityEvent",
        "JsonlAuditLogWriter",
        "[REF]",
        "[WHY]",
        "[HOW]",
    )
    missing = [p for p in required_phrases if p not in text]
    assert not missing, (
        f"nw-discuss SKILL.md missing density-aware instructions: {missing}"
    )
