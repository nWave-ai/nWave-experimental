"""Regression AT — an installed nWave host resolves ZERO per-wave gates,
silently, exit 0 (GDP-6 silent-wrong / GDP-8 arity).

RCA: ``docs/feature/fix-installed-waves-registry-silent-empty/rca.md``.
Charter: ``docs/product/expectations/fix-installed-waves-registry-silent-empty/
wave-boundary-gates-fire-on-the-installed-runtime-or-refuse-loudly.md``.

THE DEFECT (RCA VERDICT): on an installed host ``nWave/waves/`` is absent
(shipped by no manifest — RCA Branch A), so
``wave_gate_stack_dispatch.resolve_stack`` returns ``[]`` for every wave x
boundary, and BOTH live hook call sites do ``if not stack: return None``
(RCA Branch C) — a directory that could not be READ is treated identically to
a wave that legitimately declares no gates. The two conditions are NOT the
same fact, and collapsing them makes "no gate ran" indistinguishable from
"every gate passed", silently disabling 5 `on_failure: block` rows
(RCA §4).

SCOPE — RCA Parts 1-3 only (ship the asset · consume the existing
``resolve_packaged_asset`` producer for origin · give the resolution seam a
third state that reaches the AGGREGATE). Part 4 (a shipped-asset-coherence
PREVENTION gate) is OUT OF SCOPE for this file — no AT here targets it.

DRIVING SURFACE (Mandate-13 driving-port-only): the two live production
composition roots — ``service_factory.create_pre_tool_use_service()`` /
``service_factory.create_subagent_stop_service()`` — driven via their real
``validate()`` entry, asserting on the AGGREGATE ``HookDecision`` (GDP-8 arity
corollary: the third state must reach the aggregate, not just the resolver's
raw return value). A handful of tests drive
``des.application.wave_gate_stack_dispatch.resolve_stack`` directly — the SAME
Layer-3-composition seam both live call sites consume, an established pattern
in this tree (e.g. ``composition_devops_review_gate.py``
``_devops_sequence_resolved_by_spine``) — for the legitimate-empty /
precedence pins where the aggregate is not the most direct witness.

TYPE-STABILITY NOTE: this file intentionally imports NO not-yet-existing
production symbol (no ``StackResolution``, no ``resolve_waves_dir``) — the
RCA's §6.2/§6.3 code is explicitly "illustrative, the crafter owns final
form". Tests that must observe a third state on a value ``resolve_stack``
returns use the local, duck-typed helpers ``_stack_rows`` /
``_stack_indeterminate`` below (``getattr(x, "rows"/"indeterminate", ...)``),
which read correctly whether the crafter keeps ``resolve_stack`` returning a
bare ``list[dict]`` (today) or a richer value carrying ``.rows`` /
``.indeterminate`` attributes (RCA §6.3's illustrative ``StackResolution``).

FLAGGED FOR THE CRAFTER, NOT WORKED AROUND (RCA §7.2, second caution): two
step-helper harnesses already swallow ``(KeyError, ValueError,
FileNotFoundError)`` into a bare ``return []`` and would MASK a new
INDETERMINATE third state if reused unmodified —
``tests/des/acceptance/declarative_gate_composition/
declarative_gate_composition_steps/composition_slice_02_iterator_contract.py``
(``:359``, ``:392``) and ``tests/des/acceptance/f-wave-contract-coherence/
acceptance/steps/composition_move_completion.py`` (``:426``, ``:495``). This
file does not touch them; the crafter must update or replace them so they stop
swallowing the third state.

NOT RED-ABLE TODAY, FLAGGED EXPLICITLY (RCA §6.2 AMBIGUOUS disposition): the
call sites this file drives (``wave_gate_stack_dispatch.resolve_stack`` via
``shipped_waves_dir()``) have ZERO ambiguity-detection today — they read
either ``NWAVE_WAVES_DIR`` or one fixed module-relative default, with no
comparison against a second tree at all. The DISPOSITION-level requirement
(AMBIGUOUS proceeds + emits a LOUD, non-blocking advisory, preferring the
developer-checkout copy) cannot be driven through any EXISTING call site
without asserting on a not-yet-existing ``resolve_waves_dir()`` /
AMBIGUOUS-aware entry — there is nothing in production to be RED against.
Section D below instead pins that the REUSABLE primitive the RCA designates
(``resolve_packaged_asset``) already classifies AMBIGUOUS correctly for this
exact asset key — a real, already-GREEN foundation check, explicitly NOT a
defect pin — and documents the gap so the crafter wires the disposition, not
re-derives the detection.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.filesystem.wave_active_filesystem_store import (
    WaveActiveFilesystemStore,
)
from des.adapters.drivers.hooks import service_factory
from des.application import wave_gate_stack_dispatch as wgs
from des.domain.wave_active import WaveActiveRecord, WaveProvenance
from des.ports.driver_ports.pre_tool_use_port import PreToolUseInput
from des.ports.driver_ports.subagent_stop_port import SubagentStopContext


_REPO_ROOT = Path(__file__).resolve().parents[3]
_REAL_WAVES_DIR = _REPO_ROOT / "nWave" / "waves"

_SSOT_MD_DOCS: tuple[str, ...] = ("vision.md", "backlog.md", "glossary.md")
_JOBS_DOC = "jobs.yaml"


def _write_product_docs(root: Path, docs: tuple[str, ...]) -> None:
    product_dir = root / "docs" / "product"
    product_dir.mkdir(parents=True, exist_ok=True)
    for doc in docs:
        (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")


def _stack_rows(resolved: object) -> list[dict[str, object]]:
    """Extract rows from a ``resolve_stack`` result whether it is today's bare
    ``list[dict]`` or a future value carrying a ``.rows`` attribute — no
    dependency on a not-yet-existing production type."""
    return list(getattr(resolved, "rows", resolved))  # type: ignore[arg-type]


def _stack_indeterminate(resolved: object) -> str | None:
    """Extract an INDETERMINATE marker if the result carries one — ``None``
    for today's bare list (which has no such attribute) and for a future
    legitimately-empty (non-indeterminate) result."""
    return getattr(resolved, "indeterminate", None)


def _arm_wave_floor(project_root: Path, wave: str) -> None:
    WaveActiveFilesystemStore().arm(
        project_root,
        WaveActiveRecord(wave=wave, provenance=WaveProvenance.COMMAND),
    )


def _subagent_stop_context(
    *, project_id: str, cwd: Path, slice_id: str
) -> SubagentStopContext:
    return SubagentStopContext(
        execution_log_path="",
        project_id=project_id,
        step_id="",
        cwd=str(cwd),
        mode="atdd_pure",
        slice_id=slice_id,
        atdd_pure_phase="D_REFACTOR_COMMIT",
    )


_LOUD_WHY_TOKENS = ("unverifiable", "could not", "cannot verify", "not verified")


def _assert_loud_indeterminate_message(reason: str | None, resolved_path: Path) -> None:
    """WHAT/WHY/HOW shape assertion shared by the aggregate-blocking tests
    (charter oracle: "names WHICH registry/tree it read, WHY it could not
    resolve or satisfy the gate, and HOW to repair it")."""
    text = reason or ""
    assert str(resolved_path) in text, (
        "WHAT: the block reason must NAME the registry directory it looked at "
        f"(charter oracle) -- got reason={reason!r}, expected the path "
        f"{resolved_path} to appear in it."
    )
    assert any(token in text.lower() for token in _LOUD_WHY_TOKENS), (
        "WHY: the block reason must explain that the boundary could NOT be "
        f"verified (never 'every gate passed') -- got reason={reason!r}"
    )
    assert "NWAVE_WAVES_DIR" in text, (
        "HOW: the block reason must name a REAL, actionable lever "
        f"(NWAVE_WAVES_DIR or a reinstall step) -- got reason={reason!r}"
    )


# ===========================================================================
# SECTION A — GDP-8 arity: an unusable registry directory must BLOCK at BOTH
# live call sites, loud, naming WHAT/WHY/HOW (RCA points 1, 2, 3, 6, 8).
# ===========================================================================


@pytest.mark.negative_at
def test_pre_tool_use_gate_in_blocks_when_shipped_waves_registry_directory_is_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The DEFAULT (no override) installed-host reproduction of the RCA (§1.1
    probe A): the shipped-registry default resolves to an ABSENT directory
    (module constant patched, mirroring an installed host missing
    ``nWave/waves/``). A discuss-wave-entering dispatch whose product SSOT is
    otherwise COMPLETE (i.e. the gate WOULD pass if it ran at all) is the
    cleanest discriminant: today's ALLOW is structurally IDENTICAL to "the
    gate ran and passed" — indistinguishable from "the gate never ran"
    (charter: "silence plus success is the exact bug being fixed").

    RED today: ``resolve_stack`` returns ``[]`` for the absent directory,
    ``_discuss_gate_in_declarative`` returns ``None`` (proceed), the dispatch
    ALLOWS. Must become a named BLOCK.
    """
    isolated_root = tmp_path / "isolated_root"
    isolated_root.mkdir()
    _write_product_docs(isolated_root, (*_SSOT_MD_DOCS, _JOBS_DOC))  # COMPLETE SSOT
    _arm_wave_floor(isolated_root, "discuss")
    WaveActiveFilesystemStore().arm(
        isolated_root,
        WaveActiveRecord(
            wave="discuss", provenance=WaveProvenance.COMMAND, entry_pending=True
        ),
    )
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.delenv("NWAVE_WAVES_DIR", raising=False)

    absent_waves_dir = tmp_path / "installed-host" / "lib" / "nWave" / "waves"
    monkeypatch.setattr(wgs, "_SHIPPED_WAVES_DIR", absent_waves_dir)

    service = service_factory.create_pre_tool_use_service()
    decision = service.validate(
        PreToolUseInput(
            prompt="begin the discuss wave", subagent_type="child", wave_entering=True
        )
    )

    assert decision.action == "block", (
        "an ABSENT wave-contract registry directory must BLOCK the discuss "
        "gate-IN dispatch (RCA §6.3 the third state must reach the "
        "aggregate) -- an unverifiable boundary is NOT the same as a "
        "verified pass. The product SSOT here is COMPLETE (the gate WOULD "
        "have passed had it actually run), so today's ALLOW is structurally "
        "identical to 'the gate ran and passed', proving the exact silent "
        f"defect the charter names. decision={decision!r}"
    )
    _assert_loud_indeterminate_message(decision.reason, absent_waves_dir)


@pytest.mark.negative_at
def test_subagent_stop_gate_out_blocks_when_nwave_waves_dir_names_nonexistent_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The SECOND live call site (SubagentStop gate-out), and RCA point 6:
    ``NWAVE_WAVES_DIR`` explicitly naming a NON-existent directory must ALSO
    degrade to a named INDETERMINATE -- not just the "no override, default
    absent" case Section A's sibling test covers.

    RED today: ``resolve_stack("design", "gate-out")`` returns ``[]``,
    ``_discuss_gate_out_declarative`` returns ``None`` (proceed), the
    atdd_pure wave-only return ALLOWS via ``_validate_atdd_pure``. Must
    become a named BLOCK.
    """
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _arm_wave_floor(repo_dir, "design")

    nonexistent = tmp_path / "explicit-override-does-not-exist"
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(nonexistent))

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        _subagent_stop_context(
            project_id="synthetic-installed-runtime-feature",
            cwd=repo_dir,
            slice_id="slice-01",
        )
    )

    assert decision.action == "block", (
        "NWAVE_WAVES_DIR naming a directory that does NOT exist must BLOCK "
        "the design gate-out return, exactly like the default-absent case -- "
        f"decision={decision!r}"
    )
    _assert_loud_indeterminate_message(decision.reason, nonexistent)


@pytest.mark.parametrize(
    "case_id, provision_nwave_tier, expected_action",
    [
        pytest.param("no_nwave_tier_at_all", False, "allow", id="genuinely-na-host"),
        pytest.param(
            "nwave_tier_present_waves_missing", True, "block", id="broken-tier"
        ),
    ],
)
def test_registry_absence_distinguishes_no_tier_from_broken_tier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    case_id: str,
    provision_nwave_tier: bool,
    expected_action: str,
) -> None:
    """RCA point 8 / R6: a host carrying NO nWave tier at all (a genuinely
    minimal / non-Claude host) must be DECLARED N/A (allow, mirroring
    ``des_plugin.py``'s own ``_nwave_tier_manifest`` sibling-presence check at
    install time, ``:801-810``) -- DISTINCT from a host whose nWave tier IS
    present (siblings like ``framework-catalog.yaml`` / ``flavors/`` exist)
    but specifically ``waves/`` is missing (the actual defect, must BLOCK).

    Both parametrized cases share the identical "waves/ absent" condition;
    only the SIBLING evidence differs. Today NEITHER case is distinguished
    (``resolve_stack`` has no sibling-presence check at all) -- both silently
    ALLOW. The ``genuinely-na-host`` case is therefore trivially green
    already (RCA's own baseline); the ``broken-tier`` case is the RED this
    parametrization pins: it must flip to BLOCK once the fix distinguishes
    the two.
    """
    lib_dir = tmp_path / "claude_dir" / "lib"
    lib_dir.mkdir(parents=True)
    nwave_root = lib_dir / "nWave"
    if provision_nwave_tier:
        nwave_root.mkdir()
        (nwave_root / "framework-catalog.yaml").write_text(
            "# catalog\n", encoding="utf-8"
        )
        (nwave_root / "flavors").mkdir()
    # "waves" is NEVER created in either branch -- the shared absent condition.
    waves_dir = nwave_root / "waves"
    monkeypatch.setattr(wgs, "_SHIPPED_WAVES_DIR", waves_dir)
    monkeypatch.delenv("NWAVE_WAVES_DIR", raising=False)

    repo_dir = tmp_path / f"repo-{case_id}"
    repo_dir.mkdir()
    _arm_wave_floor(repo_dir, "design")

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        _subagent_stop_context(
            project_id=f"synthetic-{case_id}", cwd=repo_dir, slice_id="slice-01"
        )
    )

    assert decision.action == expected_action, (
        f"case={case_id!r}: a host with provision_nwave_tier={provision_nwave_tier} "
        f"(siblings present={provision_nwave_tier}) must resolve action="
        f"{expected_action!r} -- 'no tier at all' is DECLARED N/A (allow, mirrors "
        "install-time des_plugin.py:801-810), while 'tier present, waves missing' "
        f"is the defect and must BLOCK (RCA point 8 / R6). got decision={decision!r}"
    )


# ===========================================================================
# SECTION B — a registry directory PRESENT and usable is unaffected (RCA
# point 3), and the four legitimate-empty shapes (RCA point 4 / §3) remain
# untouched -- the discriminant is directory usability, never row count.
# ===========================================================================


def test_pre_tool_use_gate_in_allows_when_waves_registry_directory_is_usable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Invariance pin (GREEN today AND after the fix): a USABLE registry
    directory behaves exactly as today -- the discriminant is directory
    usability, not the mere existence of an env override."""
    isolated_root = tmp_path / "isolated_root"
    isolated_root.mkdir()
    _write_product_docs(isolated_root, (*_SSOT_MD_DOCS, _JOBS_DOC))
    WaveActiveFilesystemStore().arm(
        isolated_root,
        WaveActiveRecord(
            wave="discuss", provenance=WaveProvenance.COMMAND, entry_pending=True
        ),
    )
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(_REAL_WAVES_DIR))

    service = service_factory.create_pre_tool_use_service()
    decision = service.validate(
        PreToolUseInput(
            prompt="begin the discuss wave", subagent_type="child", wave_entering=True
        )
    )

    assert decision.action == "allow", (
        "a USABLE registry directory with a COMPLETE product SSOT must ALLOW "
        f"exactly as today -- decision={decision!r}"
    )


_LEGIT_EMPTY_SHAPES = [
    pytest.param(
        "deliver",
        "gate-out",
        (
            "wave: deliver\n"
            "gate_stack:\n"
            "  gate-out: []\n"
            "output_contract:\n"
            "  ref_sections: []\n"
        ),
        id="declared-empty-list",
    ),
    pytest.param(
        "design",
        "gate-in",
        (
            "wave: design\n"
            "gate_stack:\n"
            "  gate-out:\n"
            "    - gate_id: verify-design-review\n"
            "      on_failure: block\n"
            "output_contract:\n"
            "  ref_sections: []\n"
        ),
        id="boundary-key-omitted",
    ),
    pytest.param("discover", "gate-in", None, id="no-registry-file-at-all"),
    pytest.param(
        "distill",
        "gate-out",
        "wave: distill\noutput_contract:\n  ref_sections: []\n",
        id="present-file-no-gate-stack-block",
    ),
    pytest.param(
        "devops",
        "gate-in",
        (
            "wave: devops\n"
            "gate_stack:\n"
            "  gate-out:\n"
            "    - gate_id: verify-devops-review\n"
            "      on_failure: block\n"
            "output_contract:\n"
            "  ref_sections: []\n"
        ),
        id="present-gate-stack-other-boundary-only",
    ),
]


@pytest.mark.parametrize("wave, boundary, yaml_text", _LEGIT_EMPTY_SHAPES)
def test_resolve_stack_legitimately_empty_registry_shapes_never_indeterminate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    wave: str,
    boundary: str,
    yaml_text: str | None,
) -> None:
    """RCA §3 / point 4: all FOUR legitimate-empty shapes over a PRESENT,
    USABLE registry directory must resolve to 'no gates', never indeterminate
    -- invariance pin (GREEN today AND after the fix)."""
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    if yaml_text is not None:
        (waves_dir / f"{wave}.yaml").write_text(yaml_text, encoding="utf-8")
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(waves_dir))

    resolved = wgs.resolve_stack(wave, boundary)

    rows = _stack_rows(resolved)
    assert rows == [], (
        f"a PRESENT, USABLE registry directory ({waves_dir}) legitimately "
        f"declaring no {boundary!r} rows for wave {wave!r} must resolve to "
        f"the empty list (RCA §3, declared-empty is legal) -- got rows={rows!r}"
    )
    indeterminate = _stack_indeterminate(resolved)
    assert indeterminate is None, (
        f"a legitimately-empty {boundary!r} declaration for wave {wave!r} "
        f"over a USABLE registry directory {waves_dir} must NEVER be marked "
        "indeterminate -- the discriminant is directory-level usability, "
        "never row count (RCA §3/§6.3/R2: 'a new bug wearing the old bug's "
        f"uniform'). got indeterminate={indeterminate!r}"
    )


def test_subagent_stop_gate_out_allows_when_registry_present_but_boundary_declares_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Aggregate-level counterpart of the parametrized resolve_stack pins
    above (shape (a)): a PRESENT, USABLE registry directory whose design
    gate-out boundary legitimately declares zero rows must ALLOW the live
    dispatch -- invariance pin, GREEN today AND after the fix."""
    waves_dir = tmp_path / "waves"
    waves_dir.mkdir()
    (waves_dir / "design.yaml").write_text(
        "wave: design\ngate_stack:\n  gate-out: []\noutput_contract:\n  ref_sections: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(waves_dir))

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    _arm_wave_floor(repo_dir, "design")

    service = service_factory.create_subagent_stop_service()
    decision = service.validate(
        _subagent_stop_context(
            project_id="synthetic-declared-empty-feature",
            cwd=repo_dir,
            slice_id="slice-01",
        )
    )

    assert decision.action == "allow", (
        "a PRESENT, USABLE registry directory whose design gate-out boundary "
        "legitimately declares zero rows must ALLOW the return (declared-"
        f"empty, RCA §3) -- got decision={decision!r}. A fix that blocks "
        "this is R2's 'legitimately-empty boundaries misread as failures'."
    )


# ===========================================================================
# SECTION C — NWAVE_WAVES_DIR is the highest-precedence source, and it is
# actually consulted (RCA point 5 / GDP-4: the HOW must invoke a real lever).
# ===========================================================================


def test_nwave_waves_dir_env_override_takes_precedence_and_is_actually_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Foundation pin (GREEN today): NWAVE_WAVES_DIR is the remedy the
    failure message names (RCA §6.2) -- it must actually work. Uses a
    distinguishing marker gate_id (absent from the real shipped registry) to
    prove the override is genuinely CONSULTED, not merely tolerated."""
    custom_waves_dir = tmp_path / "custom-waves"
    custom_waves_dir.mkdir()
    marker_gate_id = "synthetic-precedence-marker-gate"
    (custom_waves_dir / "discuss.yaml").write_text(
        "wave: discuss\n"
        "gate_stack:\n"
        "  gate-in:\n"
        f"    - gate_id: {marker_gate_id}\n"
        "      on_failure: block\n"
        "output_contract:\n"
        "  ref_sections: []\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(custom_waves_dir))

    rows = _stack_rows(wgs.resolve_stack("discuss", "gate-in"))
    resolved_gate_ids = [str(r.get("gate_id")) for r in rows if isinstance(r, dict)]

    assert resolved_gate_ids == [marker_gate_id], (
        "NWAVE_WAVES_DIR must be the HIGHEST-precedence source and must "
        "ACTUALLY be consulted (RCA §6.2 / GDP-4) -- resolved to a "
        f"distinguishing marker gate_id {marker_gate_id!r} (absent from the "
        f"real shipped registry), got {resolved_gate_ids!r}"
    )


def test_nwave_waves_dir_override_suppresses_block_even_when_default_location_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The suppression half of precedence: even when the DEFAULT installed
    location resolves absent, an explicit NWAVE_WAVES_DIR naming a real,
    usable directory must suppress the would-be block entirely -- GREEN
    today AND after the fix (today because the default-absent branch is
    simply never consulted; after the fix because precedence is honoured)."""
    monkeypatch.setattr(
        wgs, "_SHIPPED_WAVES_DIR", tmp_path / "default-absent-nWave" / "waves"
    )
    monkeypatch.setenv("NWAVE_WAVES_DIR", str(_REAL_WAVES_DIR))

    isolated_root = tmp_path / "isolated_root"
    isolated_root.mkdir()
    _write_product_docs(isolated_root, (*_SSOT_MD_DOCS, _JOBS_DOC))
    WaveActiveFilesystemStore().arm(
        isolated_root,
        WaveActiveRecord(
            wave="discuss", provenance=WaveProvenance.COMMAND, entry_pending=True
        ),
    )
    monkeypatch.setenv("DES_PROJECT_DIR", str(isolated_root))

    service = service_factory.create_pre_tool_use_service()
    decision = service.validate(
        PreToolUseInput(
            prompt="begin the discuss wave", subagent_type="child", wave_entering=True
        )
    )

    assert decision.action == "allow", (
        "NWAVE_WAVES_DIR naming a REAL, usable directory must suppress any "
        "would-be block even though the DEFAULT installed location resolves "
        f"absent (RCA §6.2 precedence) -- decision={decision!r}"
    )


# ===========================================================================
# SECTION D — AMBIGUOUS (RCA point 7). See the module docstring: the
# DISPOSITION-level requirement cannot be driven through any EXISTING
# production call site today. This is a FOUNDATION pin only (already GREEN),
# proving the primitive the fix is designated to reuse already classifies
# this exact asset correctly.
# ===========================================================================


def test_resolve_packaged_asset_classifies_divergent_waves_copies_as_ambiguous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FOUNDATION, already GREEN today -- NOT a defect pin. See module
    docstring "NOT RED-ABLE TODAY" for why the disposition-level requirement
    (proceed + LOUD advisory, prefer REPO) cannot be pinned RED yet."""
    from des.runtime.packaged_asset import AssetOrigin, resolve_packaged_asset

    checkout = tmp_path / "checkout"
    (checkout / ".git").mkdir(parents=True)
    (checkout / "nWave" / "waves").mkdir(parents=True)
    (checkout / "nWave" / "waves" / "discuss.yaml").write_text(
        "wave: discuss\n", encoding="utf-8"
    )

    fake_installed_root = tmp_path / "installed"
    (fake_installed_root / "nWave" / "waves").mkdir(parents=True)
    (fake_installed_root / "nWave" / "waves" / "discuss.yaml").write_text(
        "wave: discuss\n# divergent content\n", encoding="utf-8"
    )

    monkeypatch.setattr(
        "des.runtime.packaged_asset.installed_package_root", lambda: fake_installed_root
    )

    resolution = resolve_packaged_asset("nWave/waves", start=checkout)

    assert resolution.origin is AssetOrigin.AMBIGUOUS, (
        "two divergent copies of nWave/waves (installed vs developer "
        "checkout) must classify as AMBIGUOUS -- this is the REUSABLE "
        f"primitive RCA §6.2 designates for the fix. got {resolution.origin!r}"
    )


# ===========================================================================
# SECTION E — shipping manifests (RCA point 9 / §6.5): the shipped-set
# PROPERTY, derived per locus (des_plugin.py, build_dist.py, patch_pyproject.py)
# -- never a hardcoded literal list, never asserting only one prefix.
# ===========================================================================


def test_des_plugin_runtime_asset_dirs_includes_waves_and_excludes_gates() -> None:
    """Locus (i)+(ii): ``<claude_dir>/lib/nWave/<family>`` (drives BOTH the
    primary Claude-Code destination and the secondary mirror, RCA §6.5)."""
    from scripts.install.plugins.des_plugin import DESPlugin

    assert "waves" in DESPlugin._NWAVE_RUNTIME_ASSET_DIRS, (
        "the installed des package resolves nWave/waves as a sibling of "
        "lib/python (RCA WHY 3A) -- DESPlugin._NWAVE_RUNTIME_ASSET_DIRS "
        f"{DESPlugin._NWAVE_RUNTIME_ASSET_DIRS!r} must ship it; it does not "
        "today."
    )
    assert "gates" not in DESPlugin._NWAVE_RUNTIME_ASSET_DIRS, (
        "RCA §5 decided NOT to ship nWave/gates/ (no runtime reader exists; "
        "shipping it would add an AMBIGUOUS drift surface for zero benefit) "
        "-- do not overcorrect."
    )


def test_dist_builder_ships_waves_runtime_assets(tmp_path: Path) -> None:
    """Locus (iii): the FLAT ``dist/<family>`` layout ``build_dist.py`` builds
    and ``_install_nwave_runtime_assets``'s FLAT FALLBACK reads."""
    from scripts.build_dist import DistBuilder

    project_root = tmp_path / "project"
    (project_root / "nWave" / "waves").mkdir(parents=True)
    (project_root / "nWave" / "waves" / "discuss.yaml").write_text(
        "wave: discuss\n", encoding="utf-8"
    )

    builder = DistBuilder(project_root=project_root)
    builder.dist_dir.mkdir(parents=True, exist_ok=True)
    count = builder.build_nwave_runtime_assets()

    shipped_waves_dir = builder.dist_dir / "waves"
    assert shipped_waves_dir.is_dir(), (
        "build_nwave_runtime_assets() must ship nWave/waves/ into the FLAT "
        "dist/ layout (RCA §6.5 locus (iii)) -- it only loops "
        '("data", "flavors", "schemas", "dispatch") today (build_dist.py:179); '
        f"{shipped_waves_dir} does not exist. count={count!r}"
    )
    assert (shipped_waves_dir / "discuss.yaml").is_file()


def test_wheel_force_include_maps_waves_nested_and_excludes_gates() -> None:
    """Locus (iv): the pipx/PyPI wheel's NESTED ``nWave/nWave/<family>``
    force-include, mirroring the flavors/schemas/dispatch pattern already
    present -- no build-alias needed (waves needs one destination, unlike
    templates' dual-destination case, RCA §6.5 locus (iv))."""
    import tomllib

    from scripts.release.patch_pyproject import _patch_wheel_packages

    patched_text, _note = _patch_wheel_packages(
        '[tool.hatch.build.targets.wheel]\npackages = ["nWave"]\n', "nwave_ai"
    )
    parsed = tomllib.loads(patched_text)
    force_include = parsed["tool"]["hatch"]["build"]["targets"]["wheel"][
        "force-include"
    ]

    assert force_include.get("nWave/waves") == "nWave/nWave/waves", (
        "the wheel force-include map must ship nWave/waves NESTED under "
        "nWave/nWave/waves (RCA §6.5 locus (iv)) -- "
        f"force_include={force_include!r} carries no such mapping today."
    )
    gate_entries = {
        key: value
        for key, value in force_include.items()
        if "gates" in key or "gates" in str(value)
    }
    assert not gate_entries, (
        "RCA §5 decided NOT to ship nWave/gates/ in the wheel either -- "
        f"found {gate_entries!r}"
    )


# ===========================================================================
# SECTION F — the closure scorecard's third consumer (RCA point 10, §6.3
# "Third consumer, do not miss it"): an INDETERMINATE resolve_stack outcome
# must be DISTINCT from wired=False, never silently collapsed.
# ===========================================================================


@pytest.mark.negative_at
def test_closure_scorecard_live_resolved_does_not_collapse_indeterminate_into_wired_false(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_live_resolved`` (scripts/flow_v2_closure_scorecard.py:340-362) fail-
    closes ANY exception to bare ``False`` -- indistinguishable from
    'gate_id genuinely absent'. Uses a LOCAL, duck-typed test double (NOT a
    production type) simulating the shape a future INDETERMINATE-carrying
    ``resolve_stack`` return might take, so this is pinnable without
    depending on the not-yet-existing production type."""
    from scripts.flow_v2_closure_scorecard import _live_resolved

    class _FakeIndeterminateStackResolution:
        """LOCAL test double only -- simulates RCA §6.3's illustrative
        ``StackResolution`` shape (rows + an indeterminate marker) without
        asserting that production actually names it that."""

        def __init__(self, reason: str) -> None:
            self.indeterminate = reason
            self.rows: list[dict[str, object]] = []

    def _fake_resolve_stack(wave: str, boundary: str) -> object:
        return _FakeIndeterminateStackResolution(
            f"the wave-contract registry directory is absent for {wave}/{boundary}"
        )

    monkeypatch.setattr(
        "des.application.wave_gate_stack_dispatch.resolve_stack", _fake_resolve_stack
    )

    result = _live_resolved("distill", "gate-out", "gate-design-at-coherence")

    assert result is not False, (
        "_live_resolved must NOT silently collapse an INDETERMINATE "
        "resolve_stack outcome into the SAME bare `False` it returns for a "
        "genuinely-absent gate_id -- scoring incapacity as not-wired "
        "silently UNDERSTATES epic closure (RCA §6.3). Today the bare "
        "`except Exception: return False` (flow_v2_closure_scorecard.py:"
        "361-362) swallows the exception raised iterating a non-list-of-"
        "dicts INDETERMINATE result exactly like this fake, returning plain "
        f"False -- indistinguishable from 'gate_id genuinely absent'. "
        f"Observed result={result!r}"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
