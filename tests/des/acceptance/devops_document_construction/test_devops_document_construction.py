"""Public oracle for deterministic DEVOPS operational-document construction.

The real ``des`` dispatcher is the sole production surface.  DEVOPS itself is
provider-free; the controlled provider below is used only by the separately
selected Product Owner consumer, where its recorded prompt makes the typed
sidecar fact observable without interpreting the Markdown document.
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest
from tests.common.in_process_cli import run_cli_in_process
from tests.des.acceptance import fake_provider
from tests.des.acceptance.steps_for_the_orchestrator.conftest import (
    PACKAGE_PARENT,
    base_repository,
    hermetic_environment,
)


DESTINATION = Path("docs/product/operations/release-brief.md")
SIDECAR = DESTINATION.with_suffix(".operational-facts.json")
HANDOVER = Path(".nwave/des/handover.json")

INPUT = {
    "schema_version": 1,
    "authority": {"heading": "Widget operational brief"},
    "purpose": "Operate the Widget service safely in production.",
    "environment": {
        "applicability": "applicable",
        "reason": "The service runs in a managed production environment.",
        "obligations": [
            {
                "id": "runtime-version",
                "requirement": "Pin the supported runtime version.",
                "verification": "Inspect the deployed runtime version.",
                "owner": "platform",
            }
        ],
    },
    "deployment": {
        "applicability": "applicable",
        "reason": "Widget releases are deployed to production.",
        "obligations": [
            {
                "id": "rollback",
                "requirement": "Keep a rollback command available.",
                "verification": "Exercise rollback in the release rehearsal.",
                "owner": "release-engineering",
            }
        ],
    },
    "recovery": {
        "applicability": "not_applicable",
        "reason": "This release introduces no durable state migration.",
        "obligations": [],
    },
    "observability": {
        "applicability": "applicable",
        "reason": "Operators need a production health signal.",
        "obligations": [
            {
                "id": "health-check",
                "requirement": "Publish a health check for Widget.",
                "verification": "Request the health check after deployment.",
                "owner": "service-team",
            }
        ],
    },
}

EXPECTED_FACTS = {
    "schema_version": 1,
    "authority": {
        "destination": str(DESTINATION),
        "heading": INPUT["authority"]["heading"],
    },
    **{
        name: INPUT[name]
        for name in (
            "purpose",
            "environment",
            "deployment",
            "recovery",
            "observability",
        )
    },
}


def _terminal(stdout: str, stderr: str) -> dict[str, str]:
    return {
        label: value
        for line in (stdout + "\n" + stderr).splitlines()
        for label, separator, value in [line.partition(": ")]
        if separator
    }


def _repository(tmp_path: Path, name: str) -> Path:
    root = base_repository(tmp_path / name)
    (root / ".nwave").mkdir()
    (root / ".nwave" / "config.json").write_text(
        json.dumps({"documents": {"devops": {"destination": str(DESTINATION)}}})
    )
    return root


def _devops(root: Path, raw: str) -> tuple[int, str, str]:
    return run_cli_in_process(
        ["devops", "--repo-root", str(root), "--input", "-"],
        cwd=root,
        stdin_text=raw,
        catch_all=True,
    )


def test_invalid_utf8_stdin_refuses_before_constructing_operational_artifacts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The public byte boundary refuses undecodable input before any effects."""
    root = _repository(tmp_path, "invalid-utf8")
    invalid_utf8 = (
        json.dumps(INPUT).encode("utf-8").replace(b"production.", b"production.\xff")
    )

    with monkeypatch.context() as patch:
        patch.setattr(
            sys,
            "stdin",
            io.TextIOWrapper(
                io.BytesIO(invalid_utf8), encoding="utf-8", errors="surrogateescape"
            ),
        )
        code, out, err = run_cli_in_process(
            ["devops", "--repo-root", str(root), "--input", "-"],
            cwd=root,
            catch_all=True,
        )

    assert code != 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Refusal", (
        "invalid UTF-8 at DEVOPS stdin must be a structured refusal before construction "
        f"rather than a process crash (stdout={out!r}, stderr={err!r})"
    )
    assert "Traceback" not in out + err, (
        "a rejected DEVOPS byte stream must not leak an implementation traceback; "
        "the public terminal must report a refusal"
    )
    assert not (root / DESTINATION).exists() and not (root / SIDECAR).exists(), (
        "undecodable DEVOPS input must leave both the configured document and sidecar "
        "absent, proving validation precedes artifact writes"
    )
    assert not (root / HANDOVER).exists(), (
        "undecodable DEVOPS input must leave the unrelated handover absent because "
        "construction invokes no downstream delivery step"
    )


def _po_with_facts(root: Path, tmp_path: Path) -> tuple[int, str, str, str]:
    answers, turns, counter = (
        tmp_path / "answers.json",
        tmp_path / "turns.json",
        tmp_path / "counter",
    )
    answers.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "decomposed",
                        "values": [
                            {
                                "observation": (
                                    "Widget deployments expose an operator-visible health "
                                    "result after every release."
                                )
                            }
                        ],
                    }
                }
            ]
        )
    )
    environment = hermetic_environment(
        fake_provider.environment(
            root,
            launcher_dir=tmp_path / "bin",
            results=answers,
            log=turns,
            counter=counter,
            package_parent=PACKAGE_PARENT,
        ),
        tmp_path / "claude-config",
    )
    code, out, err = run_cli_in_process(
        ["po", "--repo-root", str(root), "--operational-facts", str(SIDECAR)],
        cwd=root,
        env=environment,
        stdin_text="Decompose the Widget release.",
        catch_all=True,
    )
    return code, out, err, json.loads(turns.read_text())[0]["prompt"]


def test_complete_input_projects_configured_document_and_matching_operational_facts(
    tmp_path: Path,
) -> None:
    """Closed input yields both artifacts; refusal and PO selection stay isolated."""
    root = _repository(tmp_path, "configured")
    raw = json.dumps(INPUT)

    code, out, err = _devops(root, raw)
    authority, facts = root / DESTINATION, root / SIDECAR

    assert code == 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Success", (
        "a complete OperationalDocumentInput v1 must construct through the public "
        f"provider-free DEVOPS form (stdout={out!r}, stderr={err!r})"
    )
    assert authority.is_file() and facts.is_file(), (
        "a successful DEVOPS construction must write the configured regular Markdown "
        "authority and its literal adjacent OperationalFacts sidecar"
    )
    assert (
        facts.read_bytes()
        == json.dumps(
            EXPECTED_FACTS, ensure_ascii=False, separators=(",", ":")
        ).encode()
    ), (
        "OperationalFacts must be the canonical normalized input projection, retained "
        "as bytes rather than reconstructed from the Markdown authority"
    )
    document = authority.read_text()
    for text in (
        INPUT["authority"]["heading"],
        INPUT["purpose"],
        INPUT["environment"]["obligations"][0]["requirement"],
        INPUT["deployment"]["obligations"][0]["verification"],
        INPUT["recovery"]["reason"],
        INPUT["observability"]["obligations"][0]["owner"],
    ):
        assert text in document, (
            "the configured authority must be a human-readable deterministic projection "
            f"of every operational semantic constraint; missing {text!r}"
        )
    assert not (root / HANDOVER).exists(), (
        "DEVOPS construction invokes no provider or successor and must leave an absent "
        "handover absent"
    )

    authority_before, facts_before = authority.read_bytes(), facts.read_bytes()
    for invalid in (
        json.dumps({key: value for key, value in INPUT.items() if key != "purpose"}),
        json.dumps({**INPUT, "purpose": ""}),
        json.dumps({**INPUT, "unexpected": True}),
    ):
        rejected_code, rejected_out, rejected_err = _devops(root, invalid)
        assert (
            rejected_code != 0
            and _terminal(rejected_out, rejected_err).get("DELIVERY-OUTCOME")
            == "Refusal"
        ), (
            "missing, empty, or unknown closed-input constraints must refuse at the "
            f"public terminal (stdout={rejected_out!r}, stderr={rejected_err!r})"
        )
        assert (
            authority.read_bytes() == authority_before
            and facts.read_bytes() == facts_before
        ), "input validation must finish before either DEVOPS artifact changes"
        assert not (root / HANDOVER).exists(), (
            "a refused DEVOPS construction must not create or alter a handover"
        )

    retry_code, retry_out, retry_err = _devops(root, raw)
    assert (
        retry_code == 0
        and authority.read_bytes() == authority_before
        and facts.read_bytes() == facts_before
    ), (
        "an identical normalized retry must preserve both DEVOPS artifact byte sequences "
        f"(stdout={retry_out!r}, stderr={retry_err!r})"
    )

    po_code, po_out, po_err, prompt = _po_with_facts(root, tmp_path)
    assert po_code == 0 and (root / HANDOVER).is_file(), (
        "the existing public PO command must continue to create its ordinary handover "
        f"when explicitly given a valid OperationalFacts sidecar (stdout={po_out!r}, stderr={po_err!r})"
    )
    prompt_facts = {
        key: json.loads(value)
        for line in prompt.splitlines()
        for key, separator, value in [line.partition(": ")]
        if separator
    }
    assert prompt_facts.get("operational_facts") == EXPECTED_FACTS, (
        "explicit sidecar selection must supply its deserialized canonical facts to the "
        "Product Owner prompt without deriving or comparing Markdown"
    )

    ordinary = _repository(tmp_path, "ordinary-po")
    ambient = ordinary / SIDECAR
    ambient.parent.mkdir(parents=True)
    ambient.write_text("not operational facts")
    answers = tmp_path / "ordinary-answers.json"
    turns = tmp_path / "ordinary-turns.json"
    answers.write_text(
        json.dumps(
            [
                {
                    "structured_output": {
                        "outcome": "accepted",
                        "diagnostic": "ordinary",
                        "values": [
                            {
                                "observation": (
                                    "Product owners can decompose a request without selected "
                                    "operational facts."
                                )
                            }
                        ],
                    }
                }
            ]
        )
    )
    ordinary_environment = hermetic_environment(
        fake_provider.environment(
            ordinary,
            launcher_dir=tmp_path / "ordinary-bin",
            results=answers,
            log=turns,
            package_parent=PACKAGE_PARENT,
        ),
        tmp_path / "ordinary-claude-config",
    )
    ordinary_code, ordinary_out, ordinary_err = run_cli_in_process(
        ["po", "--repo-root", str(ordinary)],
        cwd=ordinary,
        env=ordinary_environment,
        stdin_text="Decompose without operational facts.",
        catch_all=True,
    )
    assert ordinary_code == 0 and (ordinary / HANDOVER).is_file(), (
        "ordinary PO behavior must ignore malformed ambient DEVOPS files when no "
        f"--operational-facts selection was made (stdout={ordinary_out!r}, stderr={ordinary_err!r})"
    )
    ordinary_prompt = json.loads(turns.read_text())[0]["prompt"]
    assert "operational_facts:" not in ordinary_prompt, (
        "without explicit selection, PO must not read ambient DEVOPS artifacts or add "
        "an operational-facts prompt fact"
    )
