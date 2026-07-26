"""Layer A arch test -- ban spawns with no explicit stdin decision / no bound.

Sibling of ``test_no_inline_des_module_spawn.py``. That test bans a spawn scoped by
CALLEE IDENTITY ("is the child a ``des`` module?" -> must route through
``des_spawn`` so ``PYTHONPATH`` is right). This one bans a spawn scoped by HAZARD
("does the child inherit the parent's stdio, and is it bounded?"). The two enforce
DIFFERENT properties and must both exist -- collapsing them loses one (RCA risk
#10). Neither implies the other: a callee-scoped rule enforced the stdio property
for 28% of the 60 spawn sites, which is how the deadlock shipped (RCA ROOT CAUSE
A).

THE INVARIANT. *No spawn without an explicit stdin decision and an explicit bound.*
Framed as a pure-AST, import-free predicate on purpose, NOT as "must call the
wrapper": ``scripts/refactor_agent.py`` may not import ``des`` by policy (its
docstring, ``:41-42`` -- nWave assets must run on any target with Python and
nothing else assumed present), so it must be able to satisfy the ban with two
literal kwargs and zero new dependency (RCA §7, risk #8).

PERIMETER = EXECUTION PERIMETER, not just the package. ``src/des/**`` AND
``scripts/**``. ``test_no_inline_des_module_spawn.py:41-42`` roots at ``src/des``
only; ``scripts/**`` ships and executes, and Root Cause B produced a new instance
of a known defect class on the same day the actuator shipped precisely because it
landed outside the walk (RCA §3 Branch B, §12.2).

WHY ``Popen`` IS NOT ASKED FOR A ``timeout=``. ``subprocess.Popen`` has no
``timeout`` parameter -- it is bounded at ``proc.wait(timeout=...)``, one call
later. Demanding it here would be an impossible requirement, so the bound is
required only of the boundable spawners (``run`` / ``call`` / ``check_call`` /
``check_output``). The stdin decision IS required of ``Popen``: it inherits fd 0
exactly like the others.

THIS BAN SHIPS GREEN. Its job in this slice is to stop NEW violations joining, not
to migrate 60 pre-existing sites (out of scope for a bugfix; a ban that ships RED
against ~180 pre-existing violations is a broken build, not enforcement). Every
currently-violating file is carried in a DATED, LITERAL allowlist below with its
violation count, and the ratchet is ``actual <= allowed``:

* a NEW file with a violation -> FAIL (it is not in the allowlist);
* an allowlisted file that GROWS a violation -> FAIL (count exceeded);
* an allowlisted file that SHEDS violations -> passes, and the entry may be
  lowered. The allowlist can only ever shrink;
* an allowlisted path that no longer EXISTS -> FAIL. Without that guard the ban
  would silently pass by tolerating paths that are gone -- the same rot
  ``test_no_inline_des_module_spawn.py:148-153`` guards against for its sanctioned
  exception.

Allowlist dated 2026-07-22: 104 files, 182 violation sites, AST census over
``src/des/**`` + ``scripts/**`` at the HEAD of ``bugfix/inherited-stdin-deadlocks-spawns``.
Burning it down is tracked separately (RCA §10 "Should change (migration behind the
ban)"); do NOT narrow the predicate to make a violation go away.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
PERIMETER = ("src/des", "scripts")

# The general spawn boundary the fix introduces (RCA §7 / §9.2 / §10) legitimately
# calls subprocess itself -- it IS the boundary that applies the stdin default and
# the bound. Exempt IF PRESENT: it does not exist yet, and an exemption for a
# non-existent path must never be able to make the ban silently pass, so absence is
# simply "nothing to exempt" rather than a hard requirement.
SANCTIONED_WRAPPER_HOME = "src/des/runtime/spawn.py"

# subprocess entry points that accept a `timeout` kwarg. `Popen` deliberately
# excluded: it has no `timeout` parameter (it is bounded at `proc.wait(timeout=)`).
_BOUNDABLE_SPAWNERS = {"run", "call", "check_call", "check_output"}
_SPAWNERS = _BOUNDABLE_SPAWNERS | {"Popen"}

# --------------------------------------------------------------------------- #
# DATED ALLOWLIST -- pre-existing unmigrated sites, census 2026-07-22.
# Ratchet: actual <= allowed. Entries may only shrink. Every path must exist.
# --------------------------------------------------------------------------- #
PRE_EXISTING_2026_07_22: dict[str, int] = {
    "src/des/adapters/driven/build/npm_pack_artifact_builder.py": 1,
    "src/des/adapters/driven/contract_gate/pytest_contract_gate_adapter.py": 1,
    "src/des/adapters/driven/contract_gate/vitest_contract_gate_adapter.py": 1,
    "src/des/adapters/driven/e2e/pytest_e2e_runner.py": 1,
    "src/des/adapters/driven/e2e/vitest_e2e_runner.py": 1,
    "src/des/adapters/driven/environment/real_environment_probe.py": 1,
    "src/des/adapters/driven/filesystem/feature_scan_adapter.py": 2,
    "src/des/adapters/driven/git/committed_scope_adapter.py": 1,
    "src/des/adapters/driven/git/git_commit_diff_adapter.py": 1,
    "src/des/adapters/driven/git/git_commit_verifier.py": 1,
    "src/des/adapters/driven/git/git_history_probe.py": 1,
    "src/des/adapters/driven/git/git_mutate.py": 1,
    "src/des/adapters/driven/git/git_subprocess.py": 5,
    "src/des/adapters/driven/git/git_track_probe.py": 1,
    "src/des/adapters/driven/install/npm_install_staged_installer.py": 1,
    "src/des/adapters/driven/package_managers/base_package_manager_adapter.py": 1,
    "src/des/adapters/driven/package_managers/package_manager_detector.py": 1,
    "src/des/adapters/driven/parallel_safety/subprocess_blast_radius_adapter.py": 1,
    "src/des/adapters/driven/refactor/shell_agent_invocation_adapter.py": 1,
    "src/des/adapters/driven/refactor/uv_env_provision_adapter.py": 1,
    "src/des/adapters/driven/runner/cargo_runner.py": 2,
    "src/des/adapters/driven/runner/csharp_runner.py": 1,
    "src/des/adapters/driven/runner/go_runner.py": 1,
    "src/des/adapters/driven/runner/java_runner.py": 1,
    "src/des/adapters/driven/runner/kotlin_runner.py": 1,
    "src/des/adapters/driven/runner/pytest_runner.py": 1,
    "src/des/adapters/driven/runner/vitest_runner.py": 1,
    "src/des/adapters/driven/validation/git_scope_checker.py": 1,
    "src/des/adapters/drivers/hooks/carpaccio_intercept.py": 2,
    "src/des/adapters/drivers/hooks/project_root_validator.py": 1,
    "src/des/adapters/drivers/hooks/subagent_stop_handler.py": 1,
    "src/des/application/slice_at_completeness.py": 1,
    "src/des/cli/_reverify_core.py": 2,
    "src/des/cli/commit.py": 1,
    "src/des/cli/commit_slice.py": 3,
    "src/des/cli/convert_to_atdd_pure.py": 1,
    "src/des/cli/examine_fixture.py": 1,
    "src/des/cli/run_contract_gate.py": 2,
    "src/des/cli/run_slice_ats.py": 1,
    "src/des/cli/verify_deliver_entry_contract.py": 1,
    "src/des/cli/verify_environmental_e2e.py": 1,
    "src/des/cli/verify_fresh_clone.py": 2,
    "src/des/cli/verify_red_green.py": 1,
    "src/des/cli/verify_refactor_trigger.py": 1,
    "src/des/runtime/interpreter.py": 4,
    "scripts/build_offline_bundle.py": 1,
    "scripts/cli/check_reuse_first_design.py": 1,
    "scripts/cli/check_scorecard_freshness.py": 1,
    "scripts/docs_site/build_site.py": 4,
    "scripts/flow_v2_closure_scorecard.py": 1,
    "scripts/framework/backlog_audit.py": 1,
    "scripts/framework/release_validation.py": 1,
    "scripts/hooks/autofix_python.py": 4,
    "scripts/hooks/check_end_of_file.py": 2,
    "scripts/hooks/check_formatter_available.py": 2,
    "scripts/hooks/check_merge_conflicts.py": 1,
    "scripts/hooks/check_trailing_whitespace.py": 1,
    "scripts/hooks/ci_author_check.py": 2,
    "scripts/hooks/detect_conflicts.py": 1,
    "scripts/hooks/detect_private_keys.py": 1,
    "scripts/hooks/nwave-bypass-detector.py": 2,
    "scripts/hooks/nwave-tdd-validator.py": 2,
    "scripts/hooks/nwave_precommit_marker.py": 1,
    "scripts/hooks/prevent_shell_scripts.py": 1,
    "scripts/hooks/reject_placeholder_git_identity.py": 1,
    "scripts/hooks/run_e2e_if_master.py": 1,
    "scripts/hooks/run_slice_ats_precommit.py": 1,
    "scripts/hooks/run_wave_contract_coherence.py": 1,
    "scripts/hooks/spine_ledger_pre_commit_hook.py": 1,
    "scripts/hooks/subagent_stop_robustness_gate.py": 1,
    "scripts/hooks/validate_author_identity.py": 1,
    "scripts/hooks/validate_docs.py": 2,
    "scripts/hooks/validate_push_identity.py": 2,
    "scripts/hooks/validate_skill_hashes.py": 1,
    "scripts/hooks/validate_tests.py": 5,
    "scripts/install/attribution_utils.py": 5,
    "scripts/install/plugins/des_plugin.py": 3,
    "scripts/install_nwave_target_hooks.py": 2,
    "scripts/local_ci.py": 13,
    "scripts/observability/test_runtime_collector.py": 1,
    "scripts/polyglot/smoke_csharp_pilot.py": 1,
    "scripts/polyglot/smoke_go_pilot.py": 1,
    "scripts/polyglot/smoke_java_pilot.py": 1,
    "scripts/polyglot/smoke_kotlin_pilot.py": 1,
    "scripts/polyglot/smoke_rust_pilot.py": 1,
    "scripts/polyglot/smoke_typescript_pilot.py": 2,
    "scripts/refactor_agent.py": 1,
    "scripts/release/cleanup/cleanup_tags.py": 2,
    "scripts/release/cleanup/test_cleanup_tags.py": 8,
    "scripts/release/collect_coauthors.py": 2,
    "scripts/release/discover_tag.py": 2,
    "scripts/release/generate_changelog.py": 3,
    "scripts/release/publish_experimental.py": 4,
    "scripts/release/rc_smoke/adapters.py": 1,
    "scripts/release/simulate.py": 8,
    "scripts/release/validate_published_rc_locally.py": 1,
    "scripts/reports/daily_usage_report.py": 2,
    "scripts/research/ab_token_probe.py": 1,
    "scripts/roadmap_e1_e12_closure_scorecard.py": 1,
    "scripts/shared/git_hooks_paths.py": 1,
    "scripts/sync/check_denylist.py": 2,
    "scripts/testpypi_validation.py": 1,
    "scripts/validation/validate_installed_wheel.py": 3,
    "scripts/validation/verify_hooks.py": 1,
}


def _perimeter_modules() -> list[Path]:
    """Every ``*.py`` under the EXECUTION perimeter, minus the wrapper home."""
    modules: list[Path] = []
    for base in PERIMETER:
        modules.extend(sorted((PROJECT_ROOT / base).rglob("*.py")))
    sanctioned = PROJECT_ROOT / SANCTIONED_WRAPPER_HOME
    return [m for m in modules if m != sanctioned]


def _scan_module(path: Path) -> list[str]:
    """Return one violation description per offending spawn (empty == clean)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, UnicodeDecodeError):
        return []
    rel = path.relative_to(PROJECT_ROOT)
    violations: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if not (isinstance(func, ast.Attribute) and func.attr in _SPAWNERS):
            continue
        if not (isinstance(func.value, ast.Name) and func.value.id == "subprocess"):
            continue
        kwargs = {kw.arg for kw in node.keywords if kw.arg}
        if "stdin" not in kwargs and "input" not in kwargs:
            violations.append(
                f"{rel}:{node.lineno} — subprocess.{func.attr}(...) makes no "
                f"explicit stdin decision: it passes neither stdin= nor input=, "
                f"so the child INHERITS fd 0 transitively and can block forever "
                f"on a descriptor that never reaches EOF"
            )
        elif func.attr in _BOUNDABLE_SPAWNERS and "timeout" not in kwargs:
            violations.append(
                f"{rel}:{node.lineno} — subprocess.{func.attr}(...) is UNBOUNDED: "
                f"it passes no timeout=, so a blocked child hangs the caller "
                f"forever with no wall clock anywhere on the path"
            )

    return violations


def _violations_by_file() -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for module in _perimeter_modules():
        hits = _scan_module(module)
        if hits:
            found[module.relative_to(PROJECT_ROOT).as_posix()] = hits
    return found


@pytest.mark.fast_gate
def test_no_new_spawn_without_explicit_stdin_and_bound():
    """No NEW spawn in src/des or scripts skips its stdin decision or its bound.

    Ratchet against the dated allowlist: a file absent from the allowlist must be
    clean, and an allowlisted file must not exceed its recorded count.
    """
    found = _violations_by_file()
    offences: list[str] = []

    for rel_path, hits in sorted(found.items()):
        allowed = PRE_EXISTING_2026_07_22.get(rel_path)
        if allowed is None:
            offences.append(
                f"[NEW FILE] {rel_path}: {len(hits)} violation(s)\n    "
                + "\n    ".join(hits)
            )
        elif len(hits) > allowed:
            offences.append(
                f"[RATCHET BROKEN] {rel_path}: {len(hits)} violation(s), "
                f"allowlisted at {allowed} on 2026-07-22\n    " + "\n    ".join(hits)
            )

    assert not offences, (
        "WHAT: spawn site(s) in the execution perimeter (src/des + scripts) make "
        "no explicit stdin decision, or carry no wall-clock bound, and are not "
        "covered by the dated 2026-07-22 allowlist.\n"
        "WHY: POSIX inherits fd 0 transitively, so a child with no explicit "
        "stdin= reads its grandparent's stdin and can block forever on a "
        "descriptor that delivers data and never reaches EOF; with no timeout= "
        "nothing on the path can escape. That is the confirmed root cause of the "
        "`des refactor --pile` deadlock (RCA ROOT CAUSE A) -- four nested "
        "processes, all sleeping on pipes, killed by hand.\n"
        "HOW: route the spawn through the general boundary "
        "`des.runtime.spawn.spawn` (RCA §7 / §9.2), which injects "
        "`stdin=subprocess.DEVNULL` when the caller passed neither stdin= nor "
        "input=, applies a tiered env-overridable bound (RCA §8), and reaps the "
        "process group on the timeout path. Where importing `des` is forbidden by "
        "policy (`scripts/refactor_agent.py:41-42`), satisfy the ban with two "
        "literal kwargs instead. Do NOT add the site to the allowlist: the "
        "allowlist is dated and may only shrink.\n"
        "--- offending sites ---\n" + "\n".join(offences)
    )


def test_allowlisted_spawn_sites_all_still_exist():
    """Guards the allowlist against rot.

    An entry naming a path that no longer exists would let the ban pass while
    silently tolerating nothing -- and would mask a real violation if the file were
    later re-created under the same name. Same guard shape as
    ``test_no_inline_des_module_spawn.py:148-153``.
    """
    missing = [
        rel
        for rel in sorted(PRE_EXISTING_2026_07_22)
        if not (PROJECT_ROOT / rel).is_file()
    ]
    assert not missing, (
        "WHAT: the dated spawn allowlist names path(s) that no longer exist.\n"
        "WHY: a stale entry is dead tolerance -- it protects nothing today and "
        "would silently re-authorise a violation if the path came back.\n"
        "HOW: delete the stale entry from PRE_EXISTING_2026_07_22 in this file "
        "(the allowlist may only shrink).\n    " + "\n    ".join(missing)
    )


def test_allowlist_never_grows_beyond_the_dated_census():
    """The allowlist is a ratchet, not a parking lot.

    Pins the 2026-07-22 census totals. Raising an entry, or adding one, is not a
    fix -- it is a licence, and it must be a visible, reviewed change to this
    assertion rather than a silent edit to the table above.
    """
    files, sites = len(PRE_EXISTING_2026_07_22), sum(PRE_EXISTING_2026_07_22.values())
    assert (files, sites) <= (104, 182), (
        "WHAT: the dated spawn allowlist has GROWN "
        f"({files} files / {sites} sites vs the 2026-07-22 census of 104 / 182).\n"
        "WHY: the allowlist exists to freeze pre-existing debt, not to absorb new "
        "debt. Growing it converts a ratchet into a parking lot and re-opens the "
        "hazard the ban was created to close.\n"
        "HOW: fix the spawn site instead -- route it through "
        "`des.runtime.spawn.spawn` (RCA §7) or pass explicit stdin= and timeout= "
        "kwargs. If the census genuinely needs re-baselining, that is a reviewed "
        "change to this assertion, made deliberately and visibly."
    )
