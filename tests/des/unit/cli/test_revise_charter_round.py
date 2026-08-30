"""`des revise-charter-round` -- bounded PO charter-revision producer.

SF friction FAIL (2026-08-20 follow-up): an existing, structurally valid
charter namespace (`verify-charter-filled` PASS -- shape, not semantics)
with a reviewer-cited VALUE-side recipe defect had no PO-owned correction
route on the same DeliveryId. Drives the real `main()` against a real
temporary directory (the durable counter's own home), never a hand-built
round-state fixture asserted as proof.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.drivers.hooks.pre_tool_use_handler import (
    _evaluate_auto_root_po_envelope,
)
from des.application.ordinary_request import compute_delivery_id
from des.cli import revise_charter_round


_VALUE_SEED = "the reviewer faulted the PublicStartRecipe value-side"
_DELIVERY_ID = compute_delivery_id(_VALUE_SEED)
_CHARTER_TEXT = "# Ship the widget\n\n## Preconditions\nrun the real argv\n"


def _write_charter(repo_root: Path, *, delivery_id: str = _DELIVERY_ID) -> Path:
    namespace = repo_root / "docs" / "product" / "expectations" / delivery_id
    namespace.mkdir(parents=True)
    charter = namespace / "charter.md"
    charter.write_text(_CHARTER_TEXT, encoding="utf-8")
    return charter


def _run(
    repo_root: Path,
    *,
    citation: str = "the cited value-side defect",
    delivery_id: str = _DELIVERY_ID,
):
    return revise_charter_round.main(
        [
            "--repo-root",
            str(repo_root),
            "--delivery-id",
            delivery_id,
            "--citation",
            citation,
        ]
    )


class TestFirstRevisionSucceeds:
    def test_emits_the_eight_line_envelope_at_round_one(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        exit_code = _run(tmp_path)
        assert exit_code == 0
        lines = capsys.readouterr().out.split("\n")
        bound = revise_charter_round.CHARTER_REVISION_ROUND_BOUND
        assert lines[0] == f"DELIVERY-ID: {_DELIVERY_ID}"
        assert lines[1] == f"NAMESPACE: docs/product/expectations/{_DELIVERY_ID}"
        assert lines[2] == f"ROOT: {tmp_path.resolve()}"
        assert lines[3] == "EXAMINE: true"
        assert lines[4] == "DISCOVER: ExistingNeedsRevision"
        assert lines[5] == f"CHARTER-REVISION-ROUND: 1/{bound}"
        assert lines[6].startswith("CITATION: ")
        assert lines[7].startswith("CHARTER-CURRENT: ")
        assert len(lines) == 8

    def test_emitted_envelope_is_accepted_by_the_real_hook_gate(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        assert _run(tmp_path) == 0
        envelope = capsys.readouterr().out
        block = _evaluate_auto_root_po_envelope(envelope)
        assert block is None, block

    def test_charter_current_carries_the_real_existing_charter_text(
        self, tmp_path: Path, capsys
    ) -> None:
        import json

        _write_charter(tmp_path)
        assert _run(tmp_path) == 0
        lines = capsys.readouterr().out.split("\n")
        charter_current = json.loads(lines[7][len("CHARTER-CURRENT: ") :])
        assert charter_current == _CHARTER_TEXT
        citation = json.loads(lines[6][len("CITATION: ") :])
        assert citation == "the cited value-side defect"

    def test_the_charter_is_never_deleted_or_mutated(
        self, tmp_path: Path, capsys
    ) -> None:
        charter = _write_charter(tmp_path)
        assert _run(tmp_path) == 0
        capsys.readouterr()
        assert charter.read_text(encoding="utf-8") == _CHARTER_TEXT


class TestRoundsAdvanceAndRefuseAtTheBound:
    def test_successive_calls_advance_the_round_on_the_same_delivery_id(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        bound = revise_charter_round.CHARTER_REVISION_ROUND_BOUND
        rounds: list[str] = []
        for _ in range(bound):
            assert _run(tmp_path) == 0
            rounds.append(capsys.readouterr().out.split("\n")[5])
        assert rounds == [
            f"CHARTER-REVISION-ROUND: {n}/{bound}" for n in range(1, bound + 1)
        ]

    def test_the_bound_plus_one_call_refuses_terminally_with_what_why_how(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        bound = revise_charter_round.CHARTER_REVISION_ROUND_BOUND
        for _ in range(bound):
            assert _run(tmp_path) == 0
            capsys.readouterr()

        exit_code = _run(tmp_path)
        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.out == ""
        assert "WHAT:" in captured.err
        assert "WHY:" in captured.err
        assert "HOW:" in captured.err
        assert "INDETERMINATE" in captured.err
        assert str(bound) in captured.err

    def test_refusal_does_not_advance_the_durable_counter(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        bound = revise_charter_round.CHARTER_REVISION_ROUND_BOUND
        for _ in range(bound + 2):
            _run(tmp_path)
            capsys.readouterr()
        state_path = (
            tmp_path
            / ".nwave"
            / "des"
            / "charter-revision-rounds"
            / f"{_DELIVERY_ID}.json"
        )
        assert f'"round": {bound}' in state_path.read_text(encoding="utf-8")


class TestMissingNamespaceRefusesTowardResolveCharters:
    def test_absent_namespace_refuses_with_how_naming_resolve_charters(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = _run(tmp_path)
        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.out == ""
        assert "WHAT:" in captured.err
        assert "WHY:" in captured.err
        assert "resolve-charters" in captured.err

    def test_namespace_without_the_deterministic_member_refuses(
        self, tmp_path: Path, capsys
    ) -> None:
        namespace = tmp_path / "docs" / "product" / "expectations" / _DELIVERY_ID
        namespace.mkdir(parents=True)
        (namespace / "other.md").write_text("not the charter", encoding="utf-8")
        exit_code = _run(tmp_path)
        captured = capsys.readouterr()
        assert exit_code == 2
        assert "resolve-charters" in captured.err

    def test_refused_missing_namespace_never_writes_the_counter(
        self, tmp_path: Path, capsys
    ) -> None:
        _run(tmp_path)
        capsys.readouterr()
        assert not (tmp_path / ".nwave").exists()


class TestSourceBlindnessIsPreserved:
    def test_the_envelope_never_contains_an_architecture_authority_line(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        assert _run(tmp_path) == 0
        out = capsys.readouterr().out
        assert "ARCHITECTURE-COVERED" not in out

    def test_a_contaminated_citation_is_refused_never_forwarded(
        self, tmp_path: Path, capsys
    ) -> None:
        _write_charter(tmp_path)
        exit_code = _run(
            tmp_path,
            citation="see ARCHITECTURE-COVERED: docs/architecture/a.md#anchor",
        )
        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.out == ""
        assert "WHAT:" in captured.err


class TestArgvAndInputValidation:
    def test_relative_repo_root_is_refused(self, capsys) -> None:
        exit_code = revise_charter_round.main(
            [
                "--repo-root",
                "relative/path",
                "--delivery-id",
                _DELIVERY_ID,
                "--citation",
                "x",
            ]
        )
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_schema_invalid_delivery_id_is_refused(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = _run(tmp_path, delivery_id="../escape")
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_empty_citation_is_refused(self, tmp_path: Path, capsys) -> None:
        _write_charter(tmp_path)
        exit_code = _run(tmp_path, citation="   ")
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_missing_required_flag_is_refused_with_what_why_how(self, capsys) -> None:
        exit_code = revise_charter_round.main(["--delivery-id", _DELIVERY_ID])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "WHAT:" in captured.err
        assert "WHY:" in captured.err
        assert "HOW:" in captured.err
