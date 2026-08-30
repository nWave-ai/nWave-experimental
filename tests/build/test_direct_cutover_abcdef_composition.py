"""Root composition laws for the direct DeliveryContract cutover.

The leaf suites prove AB, CD and EF in isolation.  These tests pin the two
adjacent identity joins and execute the provider-neutral contract-to-finalize
root on one real temporary repository.  No certificate is persisted: the
joined values are observations derived from the existing contract and result
surfaces.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from des.cli import dispatch
from tests.common.delivery_contract_fixture import seed_referenced_oracle


ROOT = Path(__file__).resolve().parents[2]
EXAMPLE = ROOT / "docs/delivery-contracts/fix-language-agnostic-contract-paths.json"
DISTILL_TASK = ROOT / "nWave/tasks/nw/distill.md"
DELIVER_TASK = ROOT / "nWave/tasks/nw/deliver.md"
DELIVER_SKILL = ROOT / "nWave/skills/nw-deliver/SKILL.md"
AUTO_SKILL = ROOT / "nWave/skills/nw-auto/SKILL.md"
CRAFTER_DISCIPLINE = (
    ROOT / "nWave/skills/nw-crafter-discipline-delivery-contract/SKILL.md"
)
FINALIZE_SKILL = ROOT / "nWave/skills/nw-finalize/SKILL.md"
OO_CRAFTER = ROOT / "nWave/agents/nw-software-crafter.md"
FP_CRAFTER = ROOT / "nWave/agents/nw-functional-software-crafter.md"
EXAMINER = ROOT / "nWave/agents/nw-user-examiner.md"
IMPLEMENTATION_REVIEWER = ROOT / "nWave/agents/nw-software-crafter-reviewer.md"


def test_abc_handoff_conserves_the_complete_contract_locator() -> None:
    distill = DISTILL_TASK.read_text(encoding="utf-8")
    deliver = DELIVER_TASK.read_text(encoding="utf-8")
    skill = DELIVER_SKILL.read_text(encoding="utf-8")

    for field in (
        "REPO-ROOT: <absolute physical repository root>",
        "DELIVERY-CONTRACT: <repo-relative locator>",
    ):
        assert field in distill
    assert "--repo-root <ROOT>" in deliver
    assert "--delivery-contract <PATH>" in deliver
    # Root's single dispatch boundary, never des validate-delivery-contract by root
    assert "des dispatch --repo-root ROOT --delivery-contract PATH" in deliver
    assert deliver.count("des dispatch --repo-root ROOT --delivery-contract PATH") == 1
    assert "des validate-delivery-contract" not in DELIVER_TASK.read_text(
        encoding="utf-8"
    )
    assert "bind its returned two-line contract+oracle closure digest" in " ".join(
        deliver.split()
    )
    # DELIVER skill describes exact canonical validator command for crafter consumer calls
    assert (
        "des validate-delivery-contract --repo-root <absolute-current-repository-root> --delivery-contract <locator>"
        in skill
        or (
            "des validate-delivery-contract" in skill
            and "--repo-root" in skill
            and "--delivery-contract" in skill
        )
    )


def test_def_handoff_joins_terminal_identities_before_finalization() -> None:
    delivery = DELIVER_SKILL.read_text(encoding="utf-8")
    finalize = FINALIZE_SKILL.read_text(encoding="utf-8")

    for identity in ("contract:", "candidate:", "oracle:", "review:", "examine:"):
        assert identity in delivery
    assert (
        "Join contract, candidate, oracle, review and applicable EXAMINE identities."
        in finalize
    )
    assert "A partial or non-PASS join stops without retry or repair." in finalize
    assert "complete pending Git path set" in finalize
    assert "No temporary feature root, promotion plan or cleanup runtime." in finalize


def test_c_to_f_uses_one_causal_identity_and_one_global_byte_binding() -> None:
    auto = " ".join(AUTO_SKILL.read_text(encoding="utf-8").split())
    deliver = " ".join(DELIVER_SKILL.read_text(encoding="utf-8").split())
    discipline = " ".join(CRAFTER_DISCIPLINE.read_text(encoding="utf-8").split())
    examiner = " ".join(EXAMINER.read_text(encoding="utf-8").split())
    reviewer = " ".join(IMPLEMENTATION_REVIEWER.read_text(encoding="utf-8").split())
    finalize = " ".join(FINALIZE_SKILL.read_text(encoding="utf-8").split())

    assert "candidate:" not in discipline
    assert "execution-root: <absolute-execution-root>" in discipline
    assert "+worktree:" not in discipline
    assert "forwarded byte-for-byte" in auto
    assert "Never send changed-targets to Vera" in auto
    assert "Send no changed-targets" in deliver
    assert "Never derive, recompute or validate it with Git" in examiner
    assert "candidate: <opaque candidate identity supplied by root>" in examiner
    examiner_terminal = examiner[
        examiner.index("EXAMINE-RESULT") : examiner.index("Echo `candidate`")
    ]
    assert "execution-root" in examiner
    assert "execution-root:" not in examiner_terminal
    assert "Echo `candidate` byte-for-byte" in examiner
    assert "candidate: git-<algorithm>:<revision>" in reviewer
    reviewer_terminal = reviewer[
        reviewer.index("IMPLEMENTATION-REVIEW") : reviewer.index(
            "Route only this existing grammar"
        )
    ]
    assert "execution-root" in reviewer
    assert "execution-root:" not in reviewer_terminal
    assert "root's HEAD to be exactly K" in reviewer

    # E4, not the crafter, seals and injects K. B is ancestry only; neither
    # E4 field is a root-derived/combined presentation.
    for projection in (auto, deliver, discipline, reviewer, finalize):
        assert "+worktree:" not in projection
    assert "first implementation-reviewer/Examiner/finalize" in auto
    assert "seals or replays K" in auto
    assert "seals or replays K" in deliver
    assert "has no `candidate:` field" in deliver
    assert "first implementation-reviewer/Examiner/finalize consumer" in deliver
    assert "root HEAD=K" in finalize
    assert "Final `Commit` remains F and never relabels K" in deliver

    assert (
        "complete pending Git path set, including formerly-untracked paths" in finalize
    )
    assert "one typed final F result" in auto
    assert "Root never commits" in deliver
    assert "fresh clean checkout" in auto
    assert "fresh clean checkout of F" in finalize
    assert "<admitted-predecessor>" in finalize
    assert "admitted predecessor is B or K" in finalize
    assert "Clean-checkout: true" in finalize
    assert "no second commit or state-changing" in finalize
    assert "atomic same-object no-op" in finalize
    assert "candidate K" in auto
    assert "Commit: git-<algorithm>:<F>" in deliver


def test_crafter_stops_at_the_first_unavailable_execution_substrate() -> None:
    discipline = " ".join(CRAFTER_DISCIPLINE.read_text(encoding="utf-8").split())

    assert "terminal `INDETERMINATE` after the first failed attempt" in discipline
    for waste_probe in ("`echo`", "`pwd`", "`true`"):
        assert waste_probe in discipline


def test_crafter_consumer_validation_at_exact_sites() -> None:
    """Crafter consumer-boundary validation at two required sites.
    Root/DELIVER never calls des validate-delivery-contract; crafter owns both."""
    deliver_skill = DELIVER_SKILL.read_text(encoding="utf-8")
    oo_crafter = OO_CRAFTER.read_text(encoding="utf-8")
    fp_crafter = FP_CRAFTER.read_text(encoding="utf-8")

    # Root/DELIVER describes single dispatch, not validation
    assert deliver_skill.count("des dispatch --repo-root") == 1
    assert "des validate-delivery-contract" not in DELIVER_TASK.read_text(
        encoding="utf-8"
    )

    # Both crafters own the consumer-boundary validation at exact two sites
    for crafter_text in (oo_crafter, fp_crafter):
        compact = " ".join(crafter_text.split())
        compact_lower = compact.lower()
        # Exact canonical validator command, discoverable
        assert (
            "des validate-delivery-contract --repo-root <absolute-current-repository-root> --delivery-contract <locator>"
            in compact
        )
        # Two required call sites
        assert "before BASELINE" in compact
        assert "before PASS/REPORT" in compact
        # Ban reimplementation
        assert "never guess, hand-hash or reimplement" in compact_lower


def test_c_projection_and_finalize_join_shape_without_temporary_feature_workspace(
    tmp_path: Path, capsys
) -> None:
    """Projection/join-shape evidence only: dispatch.main() digest projection plus
    finalize-skill prose join, on a synthetic temp repo. NOT an installed ABCDEF
    root proof — no PO/crafter/Examiner runs and no finalize commit/clean-checkout
    executes here."""
    contract_path = tmp_path / "contracts" / "delivery.json"
    contract_path.parent.mkdir()
    contract = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    seed_referenced_oracle(tmp_path, contract)
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    (tmp_path / "CLAUDE.md").write_text(
        "- Run the whole suite: `python3 -c 'pass' test`\n", encoding="utf-8"
    )
    for args in (
        ("init", "-q"),
        ("config", "user.name", "fixture"),
        ("config", "user.email", "fixture@example.invalid"),
        ("add", "."),
        ("commit", "-qm", "base"),
    ):
        subprocess.run(["git", "-C", str(tmp_path), *args], check=True)
    base = subprocess.run(
        ["git", "-C", str(tmp_path), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    contract["repository"]["base-revision"] = f"git-sha1:{base}"
    contract["verification-scope"] = {
        "commands": [
            {
                "executable": {"kind": "toolchain", "name": "python3"},
                "arguments": ["-c", "pass", "test"],
            }
        ]
    }
    contract_path.write_text(json.dumps(contract), encoding="utf-8")

    assert (
        dispatch.main(
            [
                "--repo-root",
                str(tmp_path),
                "--delivery-contract",
                "contracts/delivery.json",
            ]
        )
        == 0
    )
    oracle_path = tmp_path / str(contract["acceptance-tests"]["locator"])
    digest = dispatch.closure_digest(
        contract_path.read_bytes(), oracle_path.read_bytes()
    )
    assert capsys.readouterr().out == (
        "THIN-DELIVERY-CONTRACT: contracts/delivery.json\n"
        f"THIN-DELIVERY-CONTRACT-DIGEST: sha256:{digest}\n"
    )

    assert contract_path.is_file()
    assert not (tmp_path / "docs/feature").exists()

    finalize = FINALIZE_SKILL.read_text(encoding="utf-8")
    assert "Compute the complete pending Git path set" in finalize
    assert "single whole-delivery commit" in finalize
    assert "No temporary feature root" in finalize
    assert "fresh clean checkout of F" in finalize
