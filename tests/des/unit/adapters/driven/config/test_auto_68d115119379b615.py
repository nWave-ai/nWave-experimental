"""Acceptance oracle for delivery auto-68d115119379b615 (ADR-CFG-001 Slice 2
amendment): wire the already-delivered pure ``merge_config`` law to the real
filesystem and CLI.

Consolidates the five slice-2 obligations declared under "Amendment - Slice
2: user surface wiring" into one walking-skeleton oracle driven through the
real production surfaces named by that amendment's own target table:
``DESConfig`` (the I/O boundary adapter), the activation gate (the
hook-enabled decision point), and the ``nwave-ai`` CLI (``doctor``,
``install``) -- exactly the observable steps the delivery's own
PublicStartRecipe names.

Where the amendment leaves an exact accessor name to "a DISTILL/crafter
decision" (``des_config.py``'s new merged-fields surface), this oracle picks
``DESConfig.effective_config()`` and pins it here as the contract the
crafter must satisfy.

Two obligations use a DIFFERENTIAL assertion (comparing the wired output
against a direct ``merge_config`` call on the same inputs) rather than a
literal expected dict: the delivered ``merge_config``'s own DEFAULT values
and its malformed-value typing law are already proven by slice 1's own
oracle and are not re-derived here -- this oracle proves only that the NEW
I/O boundary reuses that law instead of re-implementing it
(REUSE_CANDIDATE), which a differential comparison proves regardless of
what the internal defaults/typing rules are.
"""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from nwave_ai.cli import main

from des.adapters.driven.config.des_config import DESConfig
from des.adapters.drivers.hooks.activation_gate import GateOutcome, run_gate
from des.domain.config_merge import merge_config


class _Envelope:
    """Minimal duck-typed envelope: ``run_gate`` only reads ``.raw``."""

    def __init__(self, raw: str | None) -> None:
        self.raw = raw


def _write_json(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content))


def _write_raw(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _unified(**fields: object) -> dict:
    return {"schema-version": "1", **fields}


def _invoke_cli(args: list[str]) -> tuple[int, str]:
    """Invoke ``nwave-ai``'s CLI main() exactly as the installed console
    script does (same pattern as tests/nwave_ai/test_cli_doctor.py)."""
    stdout_capture = StringIO()
    with patch("sys.argv", ["nwave-ai", *args]):
        with patch("sys.stdout", stdout_capture):
            try:
                exit_code = main()
            except SystemExit as exc:
                exit_code = int(exc.code) if exc.code is not None else 0
    return exit_code, stdout_capture.getvalue()


# ---------------------------------------------------------------------------
# Obligations 1 + 2 (ARCHITECTURE_BOUNDARY_CHANGE / REUSE_CANDIDATE):
# src/des/adapters/driven/config/des_config.py -- one new I/O boundary that
# reads the two real files and reuses merge_config, never re-deriving the
# cascade law.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "global_raw, repo_raw, repo_corrupt",
    [
        # both files present, well-typed -> repo overrides global (Override)
        (
            _unified(verbosity="verbose", enabled=True, attribution="off"),
            _unified(verbosity="terse"),
            False,
        ),
        # global absent, repo present
        (None, _unified(enabled=False), False),
        # global present, repo absent -> falls through to global (Fallback)
        (_unified(verbosity="terse", attribution="on"), None, False),
        # both files absent -> whatever merge_config's own DEFAULT resolves to
        (None, None, False),
        # repo file present but corrupt JSON -> fail-open collapses it to {}
        # before merge_config sees it (the same law _load_json_file already
        # proves for every other config tier, des_config.py:106-130)
        (_unified(verbosity="terse"), "{not valid json", True),
    ],
)
def test_effective_config_reuses_merge_config_over_the_two_real_files(
    tmp_path: Path, global_raw: dict | None, repo_raw, repo_corrupt: bool
) -> None:
    """DESConfig.effective_config() upcasts ~/.nwave/config.json and
    .nwave/config.json through the existing ArtifactVersioningKernel and
    reports EXACTLY what merge_config computes over the same two inputs --
    proving the I/O boundary reuses the pure law (REUSE_CANDIDATE) rather
    than hand-rolling a second cascade (ARCHITECTURE_BOUNDARY_CHANGE)."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()

    global_path = home / ".nwave" / "config.json"
    repo_path = repo / ".nwave" / "config.json"

    global_effective: dict = {}
    if global_raw is not None:
        _write_json(global_path, global_raw)
        global_effective = global_raw

    repo_effective: dict = {}
    if repo_raw is not None:
        if repo_corrupt:
            _write_raw(repo_path, repo_raw)
            repo_effective = {}  # fail-open collapse, never raises
        else:
            _write_json(repo_path, repo_raw)
            repo_effective = repo_raw

    config = DESConfig(cwd=repo, global_config_path=global_path)
    wired = config.effective_config()
    direct = merge_config(global_effective, repo_effective)

    # "attribution" is excluded from this differential: `direct` is fed the
    # RAW, untranslated fixture content (the public "on"/"off" string),
    # while `wired` must translate that string into merge_config's internal
    # {"enabled": bool} shape BEFORE merging -- comparing it here would
    # require `wired` and `direct` to agree on a field one of them is
    # required to translate and the other is not. The translation law has
    # its own dedicated coverage, at both tiers, in
    # test_effective_config_translates_the_public_attribution_string and
    # test_effective_config_translates_a_repo_tier_attribution_override
    # below.
    assert wired.keys() == direct.keys(), (
        "DESConfig.effective_config() must report the same field set as a "
        "direct merge_config() call over the same two files' content"
    )
    for field in direct:
        if field == "attribution":
            continue
        assert wired[field] == direct[field], (
            f"DESConfig.effective_config()[{field!r}] must equal a direct "
            "merge_config() call over the same two files' content -- any "
            "divergence means the I/O boundary re-derived the cascade "
            "instead of reusing it"
        )


def test_effective_config_honours_a_literal_repo_verbosity_override(
    tmp_path: Path,
) -> None:
    """Canonical example from ADR-CFG-001 obligation 1: repo config.json
    present with verbosity 'terse', global absent -> effective 'terse'."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    repo_path = repo / ".nwave" / "config.json"
    _write_json(repo_path, _unified(verbosity="terse"))

    config = DESConfig(cwd=repo, global_config_path=global_path)

    assert config.effective_config()["verbosity"] == "terse"


# ---------------------------------------------------------------------------
# CITATION (charter session log 2026-08-21, defect 2 -- ATTRIBUTION
# TRANSLATION): the public config.json shape stores attribution as the
# on/off STRING PublicStartRecipe step 1 names (e.g. {"attribution": "on"}),
# but merge_config's own well-typed check for "attribution"
# (config_merge.py::_attribution_well_typed) requires a {"enabled": bool}
# dict -- the I/O boundary (des_config.py) must translate the public string
# shape into that internal shape BEFORE calling merge_config, or every
# public "on"/"off" silently degrades to merge_config's own
# ATTRIBUTION_DEFAULT (False) as if the tier were entirely absent. The
# existing differential test above
# (test_effective_config_reuses_merge_config_over_the_two_real_files) cannot
# catch this: it compares DESConfig.effective_config() against a DIRECT
# merge_config() call fed the SAME untranslated public-string fixture, so
# both sides degrade to the same wrong answer and agree by coincidence --
# these two tests use a LITERAL expected value instead, per PublicStartRecipe
# step 1's own canonical example.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "attribution_value, expected",
    [("on", True), ("off", False)],
)
def test_effective_config_translates_the_public_attribution_string(
    tmp_path: Path, attribution_value: str, expected: bool
) -> None:
    """PublicStartRecipe step 1's literal example ({"attribution": "on"})
    must resolve to the boolean effective value it names -- "on" maps to
    enabled True, "off" to False -- at the global tier, repo absent."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    _write_json(global_path, _unified(attribution=attribution_value))

    config = DESConfig(cwd=repo, global_config_path=global_path)

    assert config.effective_config()["attribution"] is expected, (
        f"public attribution={attribution_value!r} must resolve to "
        f"{expected} -- a public on/off string that never reaches "
        "merge_config's internal {'enabled': bool} shape silently degrades "
        "to ATTRIBUTION_DEFAULT regardless of the configured value"
    )


def test_effective_config_translates_a_repo_tier_attribution_override(
    tmp_path: Path,
) -> None:
    """Same translation law, exercised at the repo tier overriding a global
    'off' -- guards against a fix that only translates the global tier."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    _write_json(global_path, _unified(attribution="off"))
    _write_json(repo / ".nwave" / "config.json", _unified(attribution="on"))

    config = DESConfig(cwd=repo, global_config_path=global_path)

    assert config.effective_config()["attribution"] is True, (
        "a repo-tier attribution:'on' override must resolve to True even "
        "when the global tier is 'off'"
    )


# ---------------------------------------------------------------------------
# Obligation 3 (PRESERVATION): src/des/adapters/drivers/hooks/
# activation_gate.py -- the hook-enabled decision point reads the SAME
# merged 'enabled' value DESConfig now produces.
# ---------------------------------------------------------------------------


def test_gate_allows_without_dispatch_when_both_config_files_are_absent(
    tmp_path: Path,
) -> None:
    """Canonical example (a), RE-BASELINED 2026-08-23 (P5-bis): repo
    config.json absent, global config.json absent -> NO tier declares an
    opinion -> ``resolve_activation`` reaches its ``mode`` branch, which
    defaults to ``"opt-in"`` -> the repo is INACTIVE and the gate allows
    WITHOUT dispatching.

    This node previously asserted ``DISPATCHED``, pinning the ADR-CFG-001
    slice-2 shape in which ``enabled_for_repo`` collapsed to a plain ``bool``
    and ``merge_config``'s ``ENABLED_DEFAULT=True`` therefore decided every
    undeclared repo. That collapse made the ``mode`` branch UNREACHABLE and
    is the defect ``F-ADR-AG-002-TRUTH-TABLE-BROKEN-BOTH-DEFAULTS`` named;
    the acceptance row ``absent-marker x absent-mode -> inactive`` in
    ``tests/des/acceptance/activation_gating/test_activation_resolution.py``
    asserts the opposite of the old expectation and is green. Between a unit
    pin and the ratified law (ADR-AG-002 truth table, ADR-AG-005 opt-in), the
    law wins -- so the expectation is re-baselined, not the production path.
    """
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"

    envelope = _Envelope(raw=f'{{"cwd": "{repo}"}}')
    run = run_gate(envelope=envelope, project_root=repo, global_config_path=global_path)

    assert run.gate_outcome == GateOutcome.ALLOWED_EXIT_0
    assert run.exit_code == 0
    assert run.handler_stdin == envelope.raw


def test_gate_dispatches_on_a_declared_per_repo_opt_in(tmp_path: Path) -> None:
    """Obligation 3 (PRESERVATION) keeps its DISPATCHED half: the gate reads
    the SAME resolution ``DESConfig`` produces, so a repo tier that DECLARES
    ``enabled: true`` dispatches.

    Added 2026-08-23 with the re-baseline above: the node that used to carry
    the DISPATCHED assertion did so by DEFAULT, which is no longer the law.
    Without this sibling the whole obligation would only ever observe the
    allow-without-dispatch outcome, and the gate could stop dispatching
    entirely without a single test noticing.
    """
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    _write_json(repo / ".nwave" / "config.json", _unified(enabled=True))

    envelope = _Envelope(raw=f'{{"cwd": "{repo}"}}')
    run = run_gate(envelope=envelope, project_root=repo, global_config_path=global_path)

    assert run.gate_outcome == GateOutcome.DISPATCHED
    assert run.exit_code == 0
    assert run.handler_stdin == envelope.raw


def test_gate_allows_without_dispatch_on_a_per_repo_opt_out(tmp_path: Path) -> None:
    """Canonical example (b): repo config.json has enabled: false -> gate
    resolves to disabled, the per-repo opt-out path."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    _write_json(repo / ".nwave" / "config.json", _unified(enabled=False))

    envelope = _Envelope(raw=f'{{"cwd": "{repo}"}}')
    run = run_gate(envelope=envelope, project_root=repo, global_config_path=global_path)

    assert run.gate_outcome == GateOutcome.ALLOWED_EXIT_0
    assert run.exit_code == 0
    assert run.handler_stdin == envelope.raw


def test_enabled_for_repo_matches_effective_config_enabled_field(
    tmp_path: Path,
) -> None:
    """The existing enabled_for_repo property (unchanged signature per
    activation_gate.py) must resolve to the SAME value effective_config()
    reports -- the end-to-end wiring proof this PRESERVATION obligation
    names, at the property level the gate itself reads."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    global_path = home / ".nwave" / "config.json"
    _write_json(home / ".nwave" / "config.json", _unified(enabled=False))
    _write_json(repo / ".nwave" / "config.json", _unified(enabled=True))

    config = DESConfig(cwd=repo, global_config_path=global_path)

    assert config.enabled_for_repo == config.effective_config()["enabled"] is True


# ---------------------------------------------------------------------------
# Obligation 4 (ARCHITECTURE_BOUNDARY_CHANGE): scripts/docgen.py -- DocGen
# projects the merged config into installed output at install time
# (PublicStartRecipe steps 1-3).
# ---------------------------------------------------------------------------


def test_install_projects_the_configured_verbosity_into_installed_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """PublicStartRecipe steps 1-3: a verbosity edit in the global
    config.json is honoured by the installed surface after `nwave-ai
    install` -- DocGen reads the SAME merged config DESConfig now produces,
    not a second, independent config read."""
    home = tmp_path / "home"
    home.mkdir()
    _write_json(
        home / ".nwave" / "config.json", _unified(verbosity="terse", attribution="on")
    )

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Platform auto-detection is not itself under test here (ADR-CFG-001
    # Slice-2 amendment, oracle-side note) -- force claude-code host
    # selection explicitly so a clean box never falls through to the
    # "no supported host detected" exit 2 refusal.
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.chdir(repo)

    exit_code, _stdout = _invoke_cli(["install"])
    assert exit_code in (0, 1)

    installed_root = home / ".claude"
    assert installed_root.exists(), "install must render its output under $HOME/.claude"
    rendered = "\n".join(
        p.read_text(errors="ignore") for p in installed_root.rglob("*") if p.is_file()
    )
    assert "terse" in rendered.lower(), (
        "the installed nWave project section must reflect the configured "
        "verbosity in its communication rules"
    )


def test_install_with_no_config_files_matches_the_pre_slice2_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical example (b): no config files present -> install still
    succeeds (no silent behavior change / crash for the unconfigured case)."""
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir()
    repo.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # Same explicit-detection arrangement as the sibling test above --
    # platform auto-detection is not under test here, only the
    # no-config-files baseline.
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.chdir(repo)

    exit_code, _stdout = _invoke_cli(["install"])

    assert exit_code in (0, 1)
    assert (home / ".claude").exists()


def test_install_reflects_the_current_verbosity_across_two_successive_reinstalls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CITATION (charter session log 2026-08-21, defect 1 -- STALE TEMPLATE
    AFTER REINSTALL): editing ~/.nwave/config.json's verbosity and
    re-running `nwave-ai install` must update every installed surface
    carrying the communication-rules GENERATED region -- a rendering left
    over from the FIRST install is a wiring failure. Exercised through the
    real `nwave-ai install` CLI path across TWO successive installs with
    different verbosity values (not `load_section_content` directly, which
    the sibling test above already covers and which cannot observe an
    install-time caching/skip-if-exists defect on reinstall)."""
    home = tmp_path / "home"
    home.mkdir()
    config_path = home / ".nwave" / "config.json"
    _write_json(config_path, _unified(verbosity="terse", attribution="on"))

    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("CLAUDE_CODE", "1")
    monkeypatch.chdir(repo)

    def _rendered() -> str:
        installed_root = home / ".claude"
        return "\n".join(
            p.read_text(errors="ignore")
            for p in installed_root.rglob("*")
            if p.is_file()
        )

    exit_code, _stdout = _invoke_cli(["install"])
    assert exit_code in (0, 1)
    assert "communication verbosity: **terse**" in _rendered().lower(), (
        "the first install must render the configured verbosity into the "
        "communication-rules GENERATED region"
    )

    # Re-configure the SAME file, then re-run install a second time -- the
    # exact reinstall scenario the citation names.
    _write_json(config_path, _unified(verbosity="verbose", attribution="on"))
    exit_code, _stdout = _invoke_cli(["install"])
    assert exit_code in (0, 1)

    rendered_after_reinstall = _rendered().lower()
    assert "communication verbosity: **verbose**" in rendered_after_reinstall, (
        "a reinstall must re-render the communication-rules region from the "
        "CURRENT config value -- a stale prompt after reinstall is a wiring "
        "failure"
    )
    assert "communication verbosity: **terse**" not in rendered_after_reinstall, (
        "the installed section must not still show the FIRST install's "
        "verbosity after a reinstall with a changed config value"
    )


# ---------------------------------------------------------------------------
# New targets (ARCHITECTURE_BOUNDARY_CHANGE / REUSE_CANDIDATE, ADR-CFG-001
# Slice-2 amendment): nWave/templates/beta-project-claude-section.md (EXTEND
# -- carries the communication-rules GENERATED marker) + scripts/install/
# project_claude_section.py (EXTEND) -- load_section_content's returned
# Claude-host section body must be driven by docgen's single-asset
# projection (_project_asset/_render_region_body), which itself reuses
# DESConfig/merge_config, never a static placeholder or a second,
# independent config read. Exercised against the REAL production template
# (project_root=None, the same default every pre-existing test in
# tests/installer/unit/test_project_claude_section.py already relies on) --
# never a fixture-only stand-in template, so the assertion cannot pass
# without the real file actually carrying the marker.
# ---------------------------------------------------------------------------


def test_load_section_content_projects_the_merged_verbosity_via_docgen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The real beta-project-claude-section.md must carry the
    communication-rules GENERATED region, and load_section_content's Claude-
    host body must reflect it -- a differential over two distinct global
    verbosity values (both against the SAME real template, only $HOME's
    merged config changes) proves the body is actually driven by
    DESConfig.effective_config() through docgen's projection, not a
    hardcoded or stale value."""
    from scripts.install.project_claude_section import load_section_content

    home_terse = tmp_path / "home-terse"
    home_terse.mkdir()
    _write_json(home_terse / ".nwave" / "config.json", _unified(verbosity="terse"))
    monkeypatch.setenv("HOME", str(home_terse))
    terse_content = load_section_content(host="claude")

    home_verbose = tmp_path / "home-verbose"
    home_verbose.mkdir()
    _write_json(home_verbose / ".nwave" / "config.json", _unified(verbosity="verbose"))
    monkeypatch.setenv("HOME", str(home_verbose))
    verbose_content = load_section_content(host="claude")

    assert "terse" in terse_content.lower(), (
        "the Claude-host section body must carry the communication-rules "
        "GENERATED region rendered from the merged config -- either the "
        "marker is missing from beta-project-claude-section.md or "
        "load_section_content never projects it"
    )
    assert terse_content != verbose_content, (
        "the rendered section body must change with the configured "
        "verbosity -- an identical body across two different global "
        "configs means the projection call reuses a stale/hardcoded value "
        "instead of DESConfig.effective_config()"
    )


# ---------------------------------------------------------------------------
# Obligation 5 (PRESERVATION): nwave_ai/doctor/checks/config_ssot.py
# (CREATE_NEW) + nwave_ai/doctor/runner.py (EXTEND, _CHECKS registration) --
# one more report row, the ten existing checks unaffected.
# ---------------------------------------------------------------------------


def _doctor_checks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, home_files: dict, repo_files: dict
) -> list:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home.mkdir(parents=True)
    repo.mkdir(parents=True)
    for rel_path, content in home_files.items():
        _write_json(home / rel_path, content)
    for rel_path, content in repo_files.items():
        _write_json(repo / rel_path, content)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.chdir(repo)

    exit_code, stdout = _invoke_cli(["doctor", "--json"])
    assert exit_code in (0, 1), (
        f"Unexpected exit code {exit_code!r}, stdout: {stdout!r}"
    )
    data = json.loads(stdout)
    assert "checks" in data and isinstance(data["checks"], list)
    return data["checks"]


def test_doctor_registers_the_new_config_ssot_check_alongside_the_ten_existing_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """runner.py's _CHECKS list (ten *Check() entries today) grows by
    exactly one entry -- no new registration mechanism, no check dropped."""
    checks = _doctor_checks(
        tmp_path,
        monkeypatch,
        home_files={
            ".nwave/config.json": _unified(
                verbosity="terse", enabled=True, attribution="on"
            )
        },
        repo_files={".nwave/config.json": _unified(enabled=True)},
    )

    assert len(checks) == 11, (
        "expected the ten pre-existing doctor checks plus the new "
        f"config_ssot check, got {len(checks)}: {checks!r}"
    )


def test_doctor_config_ssot_check_distinguishes_migrated_from_unmigrated_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Canonical examples (a)/(b): a valid unified config.json pair passes
    the new check; a tree still carrying the three legacy files
    (global-config.json, des-config.json, local-config.json) with no
    unified config.json flags the unmigrated state instead -- while the
    other ten checks' verdicts stay fixed by fixture."""
    migrated = _doctor_checks(
        tmp_path / "migrated",
        monkeypatch,
        home_files={
            ".nwave/config.json": _unified(
                verbosity="terse", enabled=True, attribution="on"
            )
        },
        repo_files={".nwave/config.json": _unified(enabled=True)},
    )
    unmigrated = _doctor_checks(
        tmp_path / "unmigrated",
        monkeypatch,
        home_files={".nwave/global-config.json": {"verbosity": "terse"}},
        repo_files={
            ".nwave/des-config.json": {"enabled": True},
            ".nwave/local-config.json": {"enabled": True},
        },
    )

    assert len(migrated) == len(unmigrated) == 11
    assert json.dumps(migrated) != json.dumps(unmigrated), (
        "the new config_ssot check must report a DIFFERENT verdict for a "
        "migrated-vs-still-scattered config tree; a byte-identical report "
        "means the new check never actually observed the legacy files"
    )


def test_doctor_config_ssot_reports_attribution_consistent_with_the_public_on_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CITATION (charter session log 2026-08-21, defect 2 -- ATTRIBUTION
    TRANSLATION): the outcome's own obligation names doctor reporting "the
    effective values for enabled, verbosity and attribution" -- the
    config_ssot check's own reported attribution must be consistent with a
    public attribution:'on' input (True), not merge_config's own
    untranslated-degrades-to-False default. This end-to-end assertion proves
    doctor does not paper over the des_config.py boundary translation the
    sibling tests above pin directly."""
    checks = _doctor_checks(
        tmp_path,
        monkeypatch,
        home_files={
            ".nwave/config.json": _unified(
                verbosity="terse", enabled=True, attribution="on"
            )
        },
        repo_files={".nwave/config.json": _unified(enabled=True)},
    )
    config_ssot = next(c for c in checks if c.get("name") == "config_ssot")
    assert "attribution=True" in config_ssot["message"], (
        "doctor's config_ssot check must report the effective attribution "
        "consistent with the public 'on' input, got: "
        f"{config_ssot['message']!r}"
    )
