"""Request-only correction through both public constructors.

@contract-shape: real-io
The finite identity cases observe the emitted terminal and persisted authority;
no production internals or child pytest processes are used.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance.design_document_construction.test_design_document_construction import (
    MANIFEST,
)
from tests.des.acceptance.steps_for_the_orchestrator.conftest import base_repository


OLD_REQUEST = "Let a user choose a widget color."
CORRECTED_REQUEST = "Let a user choose and verify a widget color after PO review."
BRIEF = Path("docs/product/brief.md")
HANDOVER = Path(".nwave/des/handover.json")


def widget_request(request: str = OLD_REQUEST) -> dict:
    return {
        "schema_version": 1,
        "request": request,
        "outcomes": ["A user can choose and verify a widget color."],
        "scope": {
            "in_scope": ["Widget color selection."],
            "out_of_scope": {
                "applicability": "not_applicable",
                "reason": "No exclusions are needed for this brief.",
                "items": [],
            },
        },
        "decisions": ["Keep color selection in the Widget boundary."],
        "values": [
            {"observation": "A user can select a widget color.", "dependencies": []},
            {
                "observation": "A user sees the selected widget color.",
                "dependencies": ["A user can select a widget color."],
            },
        ],
    }


@pytest.fixture
def repository(tmp_path: Path, monkeypatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("NWAVE_AGENTS_HOME", str(home))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(home / "claude"))
    return base_repository(tmp_path / "repository")


def submit(root: Path, command: str, request: str, *options: str):
    return run_cli_in_process(
        [command, "--repo-root", str(root), "--project", "--input", "-", *options],
        cwd=root,
        stdin_text=json.dumps(widget_request(request)),
        catch_all=True,
    )


def terminal(result) -> dict[str, str]:
    return dict(
        line.split(": ", 1)
        for line in (result[1] + "\n" + result[2]).splitlines()
        if ": " in line
    )


def require_success(result, purpose: str) -> dict[str, str]:
    assert result[0] == 0, (
        f"WHAT: {purpose} refused: {result[1]}{result[2]}; WHY: the public "
        "correction journey must be reachable; HOW: admit the declared identity "
        "and publish its brief and handover together."
    )
    return terminal(result)


def authority_bytes(root: Path) -> tuple[bytes | None, bytes | None]:
    return tuple(
        (root / path).read_bytes() if (root / path).exists() else None
        for path in (BRIEF, HANDOVER)
    )


def require_refusal(root: Path, result, what: str, before) -> None:
    assert result[0] != 0 and terminal(result).get("WHAT") == what, (
        f"WHAT: expected {what}, observed {result}; WHY: identity must not be "
        "weakened to permit an unsafe correction; HOW: refuse this identity "
        "case through the public WHAT response before publishing."
    )
    facts = terminal(result)
    assert facts.get("WHY") and facts.get("HOW"), (
        f"WHAT: {what} lacks WHY or HOW: {facts}; WHY: a refusal must explain "
        "the safety boundary and its remedy; HOW: emit both public facts."
    )
    assert authority_bytes(root) == before, (
        "WHAT: refusal changed brief or handover bytes; WHY: rejected identity "
        "must preserve the complete persisted authority; HOW: perform identity "
        "checks before either write and leave both files byte-identical."
    )


def reviewed_authority(root: Path, command: str) -> str:
    facts = require_success(submit(root, command, OLD_REQUEST), "Initial PO authority")
    digest = facts.get("DOCUMENT-SHA256")
    assert digest == hashlib.sha256((root / BRIEF).read_bytes()).hexdigest(), (
        "WHAT: initial DOCUMENT-SHA256 does not identify the brief; WHY: the "
        "operator needs a real prior-authority operand; HOW: report the digest "
        "of the constructed brief bytes."
    )
    require_success(
        run_cli_in_process(
            ["design", "--repo-root", str(root), "--value", "1", "--input", "-"],
            cwd=root,
            stdin_text=json.dumps(MANIFEST),
            catch_all=True,
        ),
        "Binding DESIGN to the first observation",
    )
    return digest


@pytest.mark.parametrize("command", ["po", "discuss"])
def test_reviewed_request_correction_escapes_refusal_cycle_and_retains_authority(
    repository: Path,
    command: str,
) -> None:
    root = repository
    prior_digest = reviewed_authority(root, command)
    before = authority_bytes(root)
    prior = json.loads(before[1])
    assert prior["values"][0]["authority"] is not None, (
        "WHAT: DESIGN setup has no bound authority; WHY: retention needs a "
        "nonempty downstream witness; HOW: bind DESIGN through des design."
    )

    require_refusal(
        root,
        submit(root, command, CORRECTED_REQUEST),
        "DiscussHandoverConflict",
        before,
    )
    refused = submit(root, command, CORRECTED_REQUEST, "--replace-current")
    require_refusal(root, refused, "DiscussAuthorityIdentityMismatch", before)
    how = terminal(refused)["HOW"]
    assert (
        "--replace-current" in how
        and f"--expected-authority-sha256 {prior_digest}" in how
        and "--input -" in how
        and ("des po" in how or "des discuss" in how)
    ), (
        f"WHAT: no-digest correction remedy omits the supported path: {how}; "
        "WHY: the operator must escape the reported refusal cycle using the "
        "current identity; HOW: name replacement, stdin and the actual prior "
        "DOCUMENT-SHA256 in the public correction command."
    )
    corrected = require_success(
        submit(
            root,
            command,
            CORRECTED_REQUEST,
            "--replace-current",
            "--expected-authority-sha256",
            prior_digest,
        ),
        "Request-only correction with the explicit current DOCUMENT-SHA256",
    )
    after = authority_bytes(root)
    stored = json.loads(after[1])
    new_digest = corrected.get("DOCUMENT-SHA256")
    assert (
        new_digest != prior_digest
        and new_digest == hashlib.sha256(after[0]).hexdigest()
    ), (
        "WHAT: corrected DOCUMENT-SHA256 is missing, unchanged or not the brief "
        "digest; WHY: corrected authority needs its own truthful identity; HOW: "
        "emit the SHA256 of the newly published brief."
    )
    request_section = after[0].decode().split("## Request\n", 1)[1].split("\n## ", 1)[0]
    assert (
        CORRECTED_REQUEST in request_section and OLD_REQUEST not in request_section
    ), (
        "WHAT: brief Request was not corrected; WHY: the user consumes the brief "
        "as product authority; HOW: replace its Request section with corrected text."
    )
    assert (
        stored["request"] == CORRECTED_REQUEST
        and stored["product_authority"]["sha256"] == new_digest
    ), (
        "WHAT: handover Request or digest disagrees with corrected brief; WHY: "
        "downstream delivery must consume the same authority; HOW: rebind the "
        "handover to the corrected Request and published digest."
    )
    assert stored["values"] == prior["values"], (
        "WHAT: graph or downstream facts changed; WHY: Request-only correction "
        "must retain all observations, dependencies and bound DESIGN/acceptance "
        "facts; HOW: preserve every surviving value's complete persisted record."
    )
    assert {
        key: value
        for key, value in stored.items()
        if key not in {"request", "product_authority"}
    } == {
        key: value
        for key, value in prior.items()
        if key not in {"request", "product_authority"}
    }, (
        "WHAT: adjacent handover authority changed; WHY: correction changes only "
        "Request and its product binding, not scope or other authority; HOW: "
        "retain all other persisted handover facts."
    )
    require_success(
        submit(root, command, CORRECTED_REQUEST, "--replace-current"),
        "Replay of corrected Request",
    )
    assert authority_bytes(root) == after, (
        "WHAT: equal-Request replay changed bytes; WHY: existing replacement "
        "idempotency remains promised; HOW: retain identical brief and handover."
    )
    require_refusal(
        root,
        submit(
            root,
            command,
            "Let a user verify widget color twice.",
            "--replace-current",
            "--expected-authority-sha256",
            prior_digest,
        ),
        "DiscussAuthorityIdentityMismatch",
        after,
    )


@pytest.mark.parametrize("command", ["po", "discuss"])
@pytest.mark.parametrize("case", ["foreign-digest", "digest-without-replacement"])
def test_request_correction_rejects_unproved_identity_without_changing_bytes(
    repository: Path,
    command: str,
    case: str,
) -> None:
    digest = reviewed_authority(repository, command)
    before = authority_bytes(repository)
    foreign = ("0" if digest[0] != "0" else "1") + digest[1:]
    options, what = (
        (
            ("--replace-current", "--expected-authority-sha256", foreign),
            "DiscussAuthorityIdentityMismatch",
        )
        if case == "foreign-digest"
        else (("--expected-authority-sha256", digest), "InvalidDiscussInput")
    )
    require_refusal(
        repository,
        submit(repository, command, CORRECTED_REQUEST, *options),
        what,
        before,
    )


@pytest.mark.parametrize("command", ["po", "discuss"])
@pytest.mark.parametrize(
    "options",
    [
        ("--replace-current",),
        ("--replace-current", "--expected-authority-sha256", "0" * 64),
    ],
)
def test_request_correction_cannot_create_authority_without_prior_handover(
    repository: Path,
    command: str,
    options: tuple[str, ...],
) -> None:
    before = authority_bytes(repository)
    require_refusal(
        repository,
        submit(repository, command, CORRECTED_REQUEST, *options),
        "DiscussAuthorityIdentityMismatch",
        before,
    )
    assert before == (None, None), (
        "WHAT: missing-authority scenario was not empty; WHY: the no-create "
        "safeguard requires absence of both artifacts; HOW: use a fresh repository."
    )


@pytest.mark.parametrize("command", ["po", "discuss"])
def test_legacy_request_rebind_restores_a_supported_correction_path(
    repository: Path,
    command: str,
) -> None:
    root = repository
    digest = reviewed_authority(root, command)
    # Historical fixture only: old handovers predate product_authority.
    # The correction journey below never edits or quarantines either artifact.
    legacy = json.loads((root / HANDOVER).read_bytes())
    legacy.pop("product_authority")
    (root / HANDOVER).write_bytes(
        json.dumps(
            legacy, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        ).encode("utf-8")
    )
    before = authority_bytes(root)
    refused = submit(
        root,
        command,
        CORRECTED_REQUEST,
        "--replace-current",
        "--expected-authority-sha256",
        digest,
    )
    require_refusal(root, refused, "DiscussAuthorityIdentityMismatch", before)
    facts = terminal(refused)
    assert "none bound" in facts["WHY"], (
        f"WHAT: legacy refusal hides missing identity: {facts}; WHY: a present "
        "graph is not a bound authority; HOW: explain that no digest is bound."
    )
    assert "unchanged Request" in facts["HOW"] and "--input -" in facts["HOW"], (
        f"WHAT: legacy refusal omits unchanged-Request rebind: {facts}; WHY: "
        "the caller cannot safely invent an authority operand; HOW: direct "
        "the caller to plain construction with the persisted Request and scope."
    )

    rebound = require_success(
        submit(root, command, OLD_REQUEST),
        "Plain unchanged-Request rebind of a legacy handover",
    )
    rebound_bytes = authority_bytes(root)
    rebound_handover = json.loads(rebound_bytes[1])
    assert (
        rebound_bytes[0] == before[0]
        and rebound_handover["request"] == OLD_REQUEST
        and rebound_handover["product_authority"]["sha256"]
        == rebound["DOCUMENT-SHA256"]
        == hashlib.sha256(rebound_bytes[0]).hexdigest()
        and {
            key: value
            for key, value in rebound_handover.items()
            if key != "product_authority"
        }
        == legacy
    ), (
        "WHAT: plain legacy rebind altered authority or failed to bind its "
        "actual digest; WHY: this remedy must preserve the existing Request, "
        "graph, scope and downstream facts; HOW: bind only product_authority "
        "to the unchanged brief and retain the historical handover facts."
    )
    corrected = require_success(
        submit(
            root,
            command,
            CORRECTED_REQUEST,
            "--replace-current",
            "--expected-authority-sha256",
            rebound["DOCUMENT-SHA256"],
        ),
        "Supported correction after unchanged-Request legacy rebind",
    )
    after = authority_bytes(root)
    stored = json.loads(after[1])
    request_section = after[0].decode().split("## Request\n", 1)[1].split("\n## ", 1)[0]
    assert (
        stored["request"] == CORRECTED_REQUEST
        and CORRECTED_REQUEST in request_section
        and OLD_REQUEST not in request_section
        and stored["product_authority"]["sha256"]
        == corrected["DOCUMENT-SHA256"]
        == hashlib.sha256(after[0]).hexdigest()
        and corrected["DOCUMENT-SHA256"] != rebound["DOCUMENT-SHA256"]
        and {
            key: value
            for key, value in stored.items()
            if key not in {"request", "product_authority"}
        }
        == {key: value for key, value in legacy.items() if key != "request"}
    ), (
        "WHAT: rebound correction did not persist consistent Request authority "
        "while retaining the legacy graph and downstream facts; WHY: rebind "
        "must make the supported correction reachable without manual repair; "
        "HOW: publish corrected Request, bind its new digest and preserve "
        "all other handover authority."
    )


@pytest.mark.parametrize("command", ["po", "discuss"])
@pytest.mark.parametrize(
    "mutation,what",
    [
        ("edited", "DiscussAuthorityDrift"),
        ("deleted", "DiscussAuthorityUnavailable"),
        ("retargeted", "DiscussAuthorityIdentityMismatch"),
    ],
)
def test_matching_digest_cannot_overwrite_drifted_or_retargeted_authority(
    repository: Path,
    command: str,
    mutation: str,
    what: str,
) -> None:
    root = repository
    digest = reviewed_authority(root, command)
    document = root / BRIEF
    config = root / ".nwave/config.json"
    retargeted = root / "docs/product/retargeted.md"
    intact = authority_bytes(root)
    original_config = config.read_bytes() if config.exists() else None
    if mutation == "edited":
        document.write_bytes(document.read_bytes() + b"\nHuman authority edit.\n")
    elif mutation == "deleted":
        document.unlink()
    else:
        config.write_text(
            json.dumps(
                {
                    "documents": {
                        "discuss": {"destination": "docs/product/retargeted.md"}
                    }
                }
            )
        )
    before = authority_bytes(root)
    config_before = config.read_bytes() if config.exists() else None
    refused = submit(
        root,
        command,
        CORRECTED_REQUEST,
        "--replace-current",
        "--expected-authority-sha256",
        digest,
    )
    require_refusal(root, refused, what, before)
    facts = terminal(refused)
    why = facts["WHY"].lower()
    relevant_mismatch = {
        "edited": ("bytes", "identity"),
        "deleted": ("bound", "cannot be read"),
        "retargeted": ("configured", "destination", "differs"),
    }[mutation]
    assert all(detail in why for detail in relevant_mismatch), (
        f"WHAT: {mutation} refusal does not explain its authority mismatch: "
        f"{facts['WHY']}; WHY: the operator must distinguish edited bytes, "
        "unavailable authority and a foreign configured destination; HOW: "
        "identify the relevant mismatch rather than repeating a generic refusal."
    )
    how = facts["HOW"].lower()
    assert "restore" in how and "bound product authority" in how, (
        f"WHAT: drift remedy omits the restore prerequisite: {facts['HOW']}; "
        "WHY: even a matching digest cannot authorize externally changed or "
        "unavailable authority; HOW: explain restoring the bound product "
        "authority before attempting Request correction."
    )
    assert (
        config.read_bytes() if config.exists() else None
    ) == config_before and not retargeted.exists(), (
        "WHAT: refusal changed configuration or created a retargeted brief; "
        "WHY: matching the stored digest does not authorize adopting a foreign "
        "destination or repairing external drift; HOW: refuse before any "
        "configuration or destination write."
    )

    # Undo only this scenario's external mutation, as the restore remedy says.
    # This is not automatic recovery and never edits the handover.
    if mutation == "retargeted":
        if original_config is None:
            config.unlink()
        else:
            config.write_bytes(original_config)
    else:
        document.write_bytes(intact[0])
    assert authority_bytes(root) == intact, (
        "WHAT: restoring the fixture mutation did not recover bound authority; "
        "WHY: the supported correction requires the original brief and intact "
        "handover identity; HOW: restore only the external mutation's saved bytes."
    )
    corrected = require_success(
        submit(
            root,
            command,
            CORRECTED_REQUEST,
            "--replace-current",
            "--expected-authority-sha256",
            digest,
        ),
        "Explicit-digest Request correction after restoring bound authority",
    )
    after = authority_bytes(root)
    stored = json.loads(after[1])
    prior = json.loads(intact[1])
    request_section = after[0].decode().split("## Request\n", 1)[1].split("\n## ", 1)[0]
    assert (
        stored["request"] == CORRECTED_REQUEST
        and CORRECTED_REQUEST in request_section
        and OLD_REQUEST not in request_section
        and stored["product_authority"]["sha256"]
        == corrected["DOCUMENT-SHA256"]
        == hashlib.sha256(after[0]).hexdigest()
        and corrected["DOCUMENT-SHA256"] != digest
        and {
            key: value
            for key, value in stored.items()
            if key not in {"request", "product_authority"}
        }
        == {
            key: value
            for key, value in prior.items()
            if key not in {"request", "product_authority"}
        }
    ), (
        "WHAT: restored authority did not permit consistent correction with "
        "retained downstream facts; WHY: the restoration remedy must recover "
        "the supported Request-only path, not require handover repair; HOW: "
        "admit the matching prior digest, persist corrected Request and preserve "
        "scope, graph and all surviving authority."
    )
