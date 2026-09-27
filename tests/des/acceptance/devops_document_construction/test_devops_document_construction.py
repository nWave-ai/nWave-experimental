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

from des.application import operational_document_producer
from des.application.handover import Blocked


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


def _devops(
    root: Path, raw: str, *, replace_current: bool = False
) -> tuple[int, str, str]:
    arguments = ["devops", "--repo-root", str(root), "--project"]
    if replace_current:
        arguments.append("--replace-current")
    arguments.extend(("--input", "-"))
    return run_cli_in_process(
        arguments,
        cwd=root,
        stdin_text=raw,
        catch_all=True,
    )


def _corrected_input() -> dict[str, object]:
    """A closed B correction for exactly DEVOPS's existing authority identity."""
    corrected = json.loads(json.dumps(INPUT))
    corrected["purpose"] = "Operate the Widget service safely after the correction."
    return corrected


def _seed_replaceable_operational_authority(
    root: Path, tmp_path: Path
) -> tuple[bytes, bytes, bytes]:
    """Construct A publicly, then surround its sole owned H2 with human bytes."""
    code, out, err = _devops(root, json.dumps(INPUT))
    assert code == 0, out + err
    authority, facts = root / DESTINATION, root / SIDECAR
    authority_a, facts_a = authority.read_bytes(), facts.read_bytes()
    prefix = (
        b"# Operations authority\n\n"
        b"This introduction belongs to a human editor.\n\n"
        b"## Human preface\n\n"
        b"Keep this H2 byte-for-byte.\n\n"
    )
    suffix = b"\n\n## Human appendix\n\nKeep this H2 byte-for-byte too.\n"
    authority.write_bytes(prefix + authority_a + suffix)

    po_code, po_out, po_err, _prompt = _po_with_facts(root, tmp_path)
    assert po_code == 0, po_out + po_err
    return prefix, suffix, facts_a


def _public_b_projection(tmp_path: Path) -> tuple[bytes, bytes]:
    """Obtain B's canonical section and sidecar through DEVOPS itself."""
    reference = _repository(tmp_path, "corrected-projection")
    code, out, err = _devops(reference, json.dumps(_corrected_input()))
    assert code == 0, out + err
    return (reference / DESTINATION).read_bytes(), (reference / SIDECAR).read_bytes()


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
            ["devops", "--repo-root", str(root), "--project", "--input", "-"],
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
        [
            "po",
            "--repo-root",
            str(root),
            "--project",
            "--operational-facts",
            str(SIDECAR),
        ],
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
        ["po", "--repo-root", str(ordinary), "--project"],
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


def test_public_devops_replace_current_replaces_only_its_section_and_facts(
    tmp_path: Path,
) -> None:
    """B needs an explicit opt-in; surrounding human and PO bytes are immutable."""
    root = _repository(tmp_path, "replace-current")
    prefix, suffix, facts_a = _seed_replaceable_operational_authority(root, tmp_path)
    authority, facts, handover = root / DESTINATION, root / SIDECAR, root / HANDOVER
    authority_a, handover_a = authority.read_bytes(), handover.read_bytes()
    section_b, facts_b = _public_b_projection(tmp_path)

    refused_code, refused_out, refused_err = _devops(
        root, json.dumps(_corrected_input())
    )
    assert (
        refused_code != 0
        and _terminal(refused_out, refused_err).get("DELIVERY-OUTCOME") == "Refusal"
        and _terminal(refused_out, refused_err).get("WHAT")
        == "OperationalAuthorityDrift"
    ), (
        "a divergent B submission without the explicit replacement flag must refuse "
        f"at the public DEVOPS terminal (stdout={refused_out!r}, stderr={refused_err!r})"
    )
    assert (authority.read_bytes(), facts.read_bytes(), handover.read_bytes()) == (
        authority_a,
        facts_a,
        handover_a,
    ), "a no-flag refusal must retain authority A, facts A, and the PO handover"

    code, out, err = _devops(root, json.dumps(_corrected_input()), replace_current=True)
    assert code == 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Success", (
        "the explicit replacement form must publish B through the same configured "
        f"DEVOPS destination and heading (stdout={out!r}, stderr={err!r})"
    )
    assert authority.read_bytes() == prefix + section_b + suffix, (
        "B may replace only its sole DEVOPS-owned H2; every surrounding human byte "
        "must be retained exactly"
    )
    assert facts.read_bytes() == facts_b, "B must replace the canonical facts sidecar"
    assert handover.read_bytes() == handover_a, (
        "DEVOPS replacement must neither admit a route nor rewrite an existing handover"
    )

    authority_b, handover_b = authority.read_bytes(), handover.read_bytes()
    retry_code, retry_out, retry_err = _devops(
        root, json.dumps(_corrected_input()), replace_current=True
    )
    assert retry_code == 0, retry_out + retry_err
    assert (authority.read_bytes(), facts.read_bytes(), handover.read_bytes()) == (
        authority_b,
        facts_b,
        handover_b,
    ), "the same explicit B retry must create no duplicate section or new handover"


def test_public_devops_sidecar_cas_loss_after_authority_replacement_is_indeterminate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second-file loss is observable as B authority with A facts, then retryable."""
    root = _repository(tmp_path, "sidecar-cas-loss")
    prefix, suffix, facts_a = _seed_replaceable_operational_authority(root, tmp_path)
    authority, facts, handover = root / DESTINATION, root / SIDECAR, root / HANDOVER
    handover_a = handover.read_bytes()
    section_b, facts_b = _public_b_projection(tmp_path)

    original_replace = operational_document_producer.replace_exact_bytes

    def lose_sidecar_cas(
        path: Path, expected: bytes | None, raw: bytes, **kwargs: object
    ) -> Blocked | None:
        if path == facts:
            assert expected == facts_a and raw == facts_b
            return Blocked(
                "OperationalFactsDrift",
                "simulated sidecar compare-and-swap loss",
                "inspect the mixed DEVOPS projections and retry the same B input",
                refusal=True,
            )
        return original_replace(path, expected, raw, **kwargs)

    monkeypatch.setattr(
        operational_document_producer, "replace_exact_bytes", lose_sidecar_cas
    )
    code, out, err = _devops(root, json.dumps(_corrected_input()), replace_current=True)
    rows = _terminal(out, err)
    assert code != 0 and rows.get("DELIVERY-OUTCOME") == "Indeterminate", (
        "after authority CAS succeeds, a sidecar CAS loss must report the mixed "
        f"result honestly rather than claim refusal (stdout={out!r}, stderr={err!r})"
    )
    assert rows.get("WHAT") == "OperationalFactsDrift"
    assert authority.read_bytes() == prefix + section_b + suffix
    assert facts.read_bytes() == facts_a
    assert handover.read_bytes() == handover_a, (
        "the fault path must not mutate the existing PO handover or trigger a wave"
    )

    monkeypatch.setattr(
        operational_document_producer, "replace_exact_bytes", original_replace
    )
    retry_code, retry_out, retry_err = _devops(
        root, json.dumps(_corrected_input()), replace_current=True
    )
    assert retry_code == 0, retry_out + retry_err
    assert authority.read_bytes() == prefix + section_b + suffix
    assert facts.read_bytes() == facts_b
    assert handover.read_bytes() == handover_a


@pytest.mark.parametrize(
    ("case", "foreign_authority"),
    (
        (
            "different-heading",
            {
                "destination": str(DESTINATION),
                "heading": "Another operational brief",
            },
        ),
        (
            "different-destination",
            {
                "destination": "docs/product/operations/other-brief.md",
                "heading": INPUT["authority"]["heading"],
            },
        ),
        ("missing-sidecar", None),
    ),
)
def test_public_devops_refuses_before_mutating_when_required_sidecar_is_not_this_authority(
    tmp_path: Path,
    case: str,
    foreign_authority: dict[str, str] | None,
) -> None:
    """One existing sidecar is canonical only for its own destination and heading."""
    root = _repository(tmp_path, case)
    _prefix, _suffix, facts_a = _seed_replaceable_operational_authority(root, tmp_path)
    authority, facts, handover = root / DESTINATION, root / SIDECAR, root / HANDOVER
    if foreign_authority is None:
        facts.unlink()
    else:
        foreign_facts = json.loads(facts_a)
        foreign_facts["authority"] = foreign_authority
        facts.write_bytes(
            json.dumps(foreign_facts, ensure_ascii=False, separators=(",", ":")).encode(
                "utf-8"
            )
        )
    before = (
        authority.read_bytes(),
        facts.read_bytes() if facts.exists() else None,
        handover.read_bytes(),
    )

    code, out, err = _devops(root, json.dumps(INPUT), replace_current=True)
    assert code != 0 and _terminal(out, err).get("DELIVERY-OUTCOME") == "Refusal", (
        "DEVOPS must reject a different or absent required canonical sidecar before "
        f"writing either projection (case={case!r}, stdout={out!r}, stderr={err!r})"
    )
    assert (
        authority.read_bytes(),
        facts.read_bytes() if facts.exists() else None,
        handover.read_bytes(),
    ) == before, (
        "a sidecar that names another authority, or a missing required sidecar, must "
        "leave the authority, sidecar state, and handover bytes unchanged"
    )
