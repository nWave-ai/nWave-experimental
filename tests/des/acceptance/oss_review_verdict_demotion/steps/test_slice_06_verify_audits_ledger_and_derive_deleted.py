"""Step definitions: the delivery verifier audits a slice's review record and
the trailer-derivation CLI is gone (oss-review-verdict-demotion, S6).

Decision SSOT: docs/analysis/oss-hmac-signing-demotion-2026-06-11.md
  (D-verify-repurpose + D-derive-hard-delete; Ale "ok 1-2-3").

Mandate 13 (Layer 3 subprocess): the driving ports are the production des
dispatcher subcommands ``des verify-commit-trailers`` (the repurposed audit
window) and ``des carpaccio-slice-gate`` (the gate it must agree with), both
invoked through the ``DemotionAuditComposition`` composition root as subprocess
black boxes. No direct-domain import of ``check_at_review`` or any
``verify_commit_trailers`` internal.

Layer 3 (subprocess/FS acceptance). Example-only, no PBT machinery (Mandate 9
v2 / 11): the driven adapters are the real filesystem (tmp_path) + a real git
repo, so the slice is @real-io and each S6 state is a named example, not a
Hypothesis @given.

The repurposed verifier is a pure observer: the audit-clears Then-step asserts
via ``assert_state_delta`` over a port-exposed filesystem universe that NO
repository file is written AND no signing-key file appears (Mandate 8).

Step bodies delegate to ``DemotionAuditComposition``; no inline business logic
(Mandate-12 criterion 3) -- each body is a typed lookup plus a composition call.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.common.state_delta import assert_state_delta, unchanged

from .composition_slice_06 import CliResult, DemotionAuditComposition
from .domain_types_slice_06 import (
    GATE_REASON_BY_PHRASE,
    RECORD_STATE_BY_PHRASE,
    FeatureId,
)


scenarios("../slice-06-verify-audits-ledger-and-derive-deleted.feature")


@pytest.fixture
def audit_composition(tmp_path: Path) -> DemotionAuditComposition:
    """Production-wired composition root over a tmp_path git work-tree."""
    return DemotionAuditComposition(repo_dir=tmp_path / "repo")


@pytest.fixture
def audit_box() -> dict[str, object]:
    """Carrier for CLI results + the captured universe across When -> Then."""
    return {}


# --- Given -------------------------------------------------------------------


@given(
    "a delivered slice commit for an atdd_pure feature with no reviewer signing "
    "key anywhere"
)
def given_keyless_git_repository(audit_composition: DemotionAuditComposition) -> None:
    audit_composition.create_keyless_repo(FeatureId("oss-review-verdict-demotion"))


@given(parsers.parse("a slice commit whose slice has {record_phrase}"))
def given_slice_commit_with_record(
    audit_composition: DemotionAuditComposition, record_phrase: str
) -> None:
    audit_composition.provision_review_record(RECORD_STATE_BY_PHRASE[record_phrase])


@given("the audited commit carries no Slice-Id trailer")
def given_commit_without_slice_id_trailer(
    audit_composition: DemotionAuditComposition,
) -> None:
    audit_composition.provision_commit_without_slice_id_trailer()


@given("the demotion has removed the reviewer-trailer derivation command")
def given_derive_command_removed(audit_composition: DemotionAuditComposition) -> None:
    # Documentation anchor only: the Background already provisioned the keyless
    # repo, and the deletion is the production change this slice drives. The
    # observable (the derive module is gone) is read off the real repo tree in
    # the Then-steps -- nothing to provision here.
    assert audit_composition is not None


# --- When --------------------------------------------------------------------


@when("the operator audits that commit with the delivery verifier")
def when_audit_commit(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    before = audit_composition.capture_universe()
    audit_box["audit"] = audit_composition.run_verifier()
    audit_box["universe_before"] = before


@when("the operator runs the carpaccio slice gate for the same slice")
def when_run_gate_same_slice(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    audit_box["gate"] = audit_composition.run_gate()


@when("the operator looks for the reviewer-trailer derivation command")
def when_look_for_derive_command(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    audit_box["derive_on_disk"] = audit_composition.derive_cli_exists_on_disk()
    audit_box["derive_importable"] = audit_composition.derive_module_importable()


# --- Then --------------------------------------------------------------------


@then("the verifier reports the slice's review as present and approved")
def then_audit_present_and_approved(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    audit = audit_box["audit"]
    assert isinstance(audit, CliResult)
    assert audit_composition.audit_clears(audit), (
        "the repurposed verifier must audit the slice's ledger record and report "
        f"it present-and-approved; observed exit={audit.exit_code} "
        f"stdout={audit.stdout!r} stderr={audit.stderr!r}"
    )


@then("the verifier reports success with exit code zero")
def then_audit_exit_zero(audit_box: dict[str, object]) -> None:
    audit = audit_box["audit"]
    assert isinstance(audit, CliResult)
    assert audit.exit_code == 0, (
        f"the audit must clear with exit 0; observed exit={audit.exit_code} "
        f"stderr={audit.stderr!r}"
    )


@then("the audit writes no file in the repository")
def then_audit_writes_no_file(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    """Pure-function contract: the audit mutates no repository file (Mandate 8).

    The universe is every file the audit reads -- the feature-delta, the slice
    ``.feature``, the AT-completion ledger, the workflow config -- plus the
    keyless invariant: ``signing_key.exists`` must stay False (the audit never
    materializes a key). Each universe slot is asserted ``unchanged``.
    """
    assert_state_delta(
        before=audit_box["universe_before"],  # type: ignore[arg-type]
        after=audit_composition.capture_universe(),
        universe={
            "feature_delta.bytes",
            "feature_file.bytes",
            "ledger.exists",
            "ledger.bytes",
            "config.bytes",
            "signing_key.exists",
        },
        expected={
            "feature_delta.bytes": unchanged(),
            "feature_file.bytes": unchanged(),
            "ledger.exists": unchanged(),
            "ledger.bytes": unchanged(),
            "config.bytes": unchanged(),
            "signing_key.exists": unchanged(),
        },
    )


@then(parsers.parse('both surfaces refuse the slice for the reason "{reason}"'))
def then_both_surfaces_refuse(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
    reason: str,
) -> None:
    expected = GATE_REASON_BY_PHRASE[reason].value
    audit = audit_box["audit"]
    gate = audit_box["gate"]
    assert isinstance(audit, CliResult)
    assert isinstance(gate, CliResult)
    audit_reason = audit_composition.audit_refusal_reason(audit)
    gate_reason = audit_composition.gate_refusal_reason(gate)
    assert audit_reason == expected, (
        "the repurposed verifier must surface the gate's own rejection reason "
        f"{expected!r}; observed audit reason={audit_reason!r} "
        f"(exit={audit.exit_code}, stdout={audit.stdout!r}, stderr={audit.stderr!r})"
    )
    assert gate_reason == expected, (
        f"the carpaccio gate must refuse for reason {expected!r}; observed "
        f"gate reason={gate_reason!r} (exit={gate.exit_code})"
    )


@then("the audit window and the gate agree on the refusal reason")
def then_audit_and_gate_agree(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    """The no-drift spine: one check, one home.

    A record the carpaccio gate refuses MUST be refused by the audit window with
    the SAME reason token. If the audit window could reach a different verdict
    than the gate from the SAME ledger record, it would be a second verifier
    with its own drift -- the false-confidence oracle this slice rejects.
    """
    audit = audit_box["audit"]
    gate = audit_box["gate"]
    assert isinstance(audit, CliResult)
    assert isinstance(gate, CliResult)
    audit_reason = audit_composition.audit_refusal_reason(audit)
    gate_reason = audit_composition.gate_refusal_reason(gate)
    assert audit_reason is not None and audit_reason == gate_reason, (
        "the audit window and the gate must agree on the refusal reason (one "
        f"check, one home); audit reason={audit_reason!r}, gate reason={gate_reason!r}"
    )


@then("the audit is refused as indeterminate with nothing to audit")
def then_audit_nothing_to_audit(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    """A-absent-trailer (architect-final 2026-06-11): honest INDETERMINATE.

    A commit with no ``Slice-Id:`` trailer exits 7 (the verifier's existing
    cannot-evaluate channel) -- never a silent exit-0 (the unarmed-gate
    silent-pass class this feature kills, D-no-disarm) and never an exit-45
    BLOCK (non-slice commits -- docs/fix/chore/infra/merge -- are legitimate;
    a blocking auditor would assert a negative finding it did not find,
    violating asymmetric-authority).
    """
    audit = audit_box["audit"]
    assert isinstance(audit, CliResult)
    assert audit_composition.audit_is_nothing_to_audit(audit), (
        "a commit with no Slice-Id trailer must be reported as the distinct "
        "nothing-to-audit INDETERMINATE (exit 7), never silently cleared and "
        f"never blocked; observed exit={audit.exit_code} stdout={audit.stdout!r} "
        f"stderr={audit.stderr!r}"
    )


@then("the indeterminate reason names the missing Slice-Id trailer")
def then_indeterminate_names_missing_trailer(
    audit_composition: DemotionAuditComposition,
    audit_box: dict[str, object],
) -> None:
    """The stderr reason distinguishes nothing-to-audit from git-absent.

    Both INDETERMINATEs share exit 7 (zero new exit code per A-absent-trailer);
    the reason string is the distinguishing observable -- §22.7 honest-verdict
    split: "the mechanism had nothing to evaluate" never masquerades as PASS,
    VETO, or a git-readability failure.
    """
    audit = audit_box["audit"]
    assert isinstance(audit, CliResult)
    assert audit_composition.audit_names_missing_trailer(audit), (
        "the nothing-to-audit INDETERMINATE must name the missing Slice-Id "
        "trailer in its diagnostic (distinguishing it from the git-absent "
        f"INDETERMINATE); observed stdout={audit.stdout!r} stderr={audit.stderr!r}"
    )


@then("the reviewer-trailer derivation command is absent from the codebase")
def then_derive_command_absent(audit_box: dict[str, object]) -> None:
    assert audit_box["derive_on_disk"] is False, (
        "scripts/cli/derive_review_trailer.py must be HARD-DELETED post-demotion; "
        "the module is still present on disk"
    )


@then("no slice can invoke it to project a signed reviewer trailer")
def then_derive_command_not_importable(audit_box: dict[str, object]) -> None:
    assert audit_box["derive_importable"] is False, (
        "the deleted trailer-derivation module must no longer be importable; "
        "importing it still succeeds, so a slice could still invoke it"
    )
