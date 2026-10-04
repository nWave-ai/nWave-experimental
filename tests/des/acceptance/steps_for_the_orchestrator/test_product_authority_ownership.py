"""Only a constructed, current product authority belongs to a Request candidate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from des.application.handover import HandoverValue, StoredHandover, create_handover
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    accepted_values,
    block,
    git,
)
from tests.des.acceptance.steps_for_the_orchestrator.test_verify_and_integrate_close_the_request import (
    REQUEST,
    crafted,
)


@pytest.mark.parametrize("foreign", ("absent", "untracked", "tracked-dirty"))
def test_unbound_product_path_is_not_adopted_by_verify_or_integrate(
    root: Path, step, foreign: str
) -> None:
    path = root / "docs/product/brief.md"
    if foreign != "absent":
        path.parent.mkdir(parents=True, exist_ok=True)
        if foreign == "tracked-dirty":
            path.write_bytes(b"Previously committed independent product authority.\n")
            git(root, "add", "--", "docs/product/brief.md")
            git(root, "commit", "-qm", "Independent product authority")
        path.write_bytes(b"Uncommitted human work, unrelated to this Request.\n")
    original = path.read_bytes() if path.exists() else None
    base = git(root, "rev-parse", "HEAD")
    stored = create_handover(root, REQUEST, (HandoverValue("A", (), None),))
    assert isinstance(stored, StoredHandover), stored
    crafted(root, step, construct_product=False)

    code, out, err = step("verify", "--repo-root", str(root))
    assert code == 0, out + err
    candidate = block(out, err)["CANDIDATE"]
    if foreign == "tracked-dirty":
        assert git(root, "rev-parse", f"{candidate}:docs/product/brief.md") == git(
            root, "rev-parse", f"{base}:docs/product/brief.md"
        )
    else:
        assert (
            git(
                root, "ls-tree", "--name-only", candidate, "--", "docs/product/brief.md"
            )
            == ""
        )
    prepared = step(
        "prepare-role",
        "--repo-root",
        str(root),
        "--role",
        "reviewer",
        "--candidate",
        candidate,
    )
    assert prepared[0] == 0, prepared[1] + prepared[2]
    integrated = step("integrate", "--repo-root", str(root), "--candidate", candidate)
    assert integrated[0] == 0, integrated[1] + integrated[2]
    assert git(root, "rev-parse", "HEAD") == candidate
    assert (path.read_bytes() if path.exists() else None) == original
    if foreign != "absent":
        assert "docs/product/" in git(root, "status", "--porcelain")


@pytest.mark.parametrize(
    "mutation", ("edited", "deleted", "malformed-config", "retargeted-config")
)
def test_constructed_product_authority_must_remain_bound_and_current(
    root: Path, step, mutation: str
) -> None:
    code, out, err = step(
        "po",
        "--repo-root",
        str(root),
        "--feature",
        "bound-product",
        answers=[accepted_values("A")],
        stdin=REQUEST,
    )
    assert code == 0, out + err
    product = root / block(out, err)["DOCUMENT"]
    crafted(root, step, construct_product=False)
    verified = step("verify", "--repo-root", str(root))
    assert verified[0] == 0, verified[1] + verified[2]
    candidate = block(verified[1], verified[2])["CANDIDATE"]
    before_head = git(root, "rev-parse", "HEAD")
    before_records = git(
        root, "for-each-ref", "--format=%(refname) %(objectname)", "refs/nwave/turns"
    )
    if mutation == "edited":
        product.write_bytes(
            product.read_bytes() + b"\nHuman edit after PO construction.\n"
        )
    elif mutation == "deleted":
        product.unlink()
    else:
        config_path = root / ".nwave/config.json"
        config = json.loads(config_path.read_text()) if config_path.exists() else {}
        config["documents"] = {
            "feature": {
                "discuss": {
                    "destination": "../escape/{feature}.md"
                    if mutation == "malformed-config"
                    else "docs/retargeted/{feature}.md"
                }
            }
        }
        config_path.write_text(json.dumps(config))
    remaining = product.read_bytes() if product.exists() else None
    expected_defect = {
        "edited": "DiscussAuthorityDrift",
        "deleted": "DiscussAuthorityUnavailable",
        "malformed-config": "InvalidDocumentDestination",
        "retargeted-config": "DiscussAuthorityIdentityMismatch",
    }[mutation]

    for action in (
        ("state",),
        ("verify",),
        ("prepare-role", "--role", "reviewer", "--candidate", candidate),
        ("integrate", "--candidate", candidate),
    ):
        code, out, err = step(*action, "--repo-root", str(root))
        assert code != 0, (mutation, action, out, err)
        terminal = block(out, err)
        assert terminal["DELIVERY-OUTCOME"] in {"Refusal", "Indeterminate"}
        assert {"WHAT", "WHY", "HOW"} <= terminal.keys()
        assert terminal["WHAT"] == expected_defect
        assert "Traceback" not in out + err
    assert git(root, "rev-parse", "HEAD") == before_head
    assert (
        git(
            root,
            "for-each-ref",
            "--format=%(refname) %(objectname)",
            "refs/nwave/turns",
        )
        == before_records
    )
    assert (product.read_bytes() if product.exists() else None) == remaining
