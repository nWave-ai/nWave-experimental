"""`des revise-contract-round` — bounded REVISE-CONTRACT producer.

Stable-design report 2026-08-19 §1.2: `_reserve_next_round_locked` is the
ONLY route to a new round number, mirroring `agda/StableDesign.agda` §2's
`attemptRevise : ReviseRound bound n -> (suc n <= bound) -> ReviseRound
bound (suc n)` -- no well-typed route past `bound`. Drives the real `main()`
against a real temporary directory (the durable counter's own home), never
a hand-built round-state fixture asserted as proof.
"""

from __future__ import annotations

from pathlib import Path

from des.adapters.drivers.hooks.pre_tool_use_handler import (
    _evaluate_auto_root_atd_body,
)
from des.application.ordinary_request import compute_delivery_id, contract_locator_for
from des.cli import revise_contract_round


_VALUE_SEED = "the crafter cited an invented import that does not exist"
_DELIVERY_ID = compute_delivery_id(_VALUE_SEED)
_LOCATOR = contract_locator_for(_DELIVERY_ID)


def _run(
    repo_root: Path, *, citation: str = "the cited defect", locator: str = _LOCATOR
):
    return revise_contract_round.main(
        [
            "--repo-root",
            str(repo_root),
            "--contract-locator",
            locator,
            "--citation",
            citation,
        ]
    )


class TestFirstRevisionSucceeds:
    def test_emits_the_three_line_body_at_round_one(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = _run(tmp_path)
        assert exit_code == 0
        out = capsys.readouterr().out
        lines = out.split("\n")
        assert lines[0] == f"REVISE-CONTRACT: {_LOCATOR}"
        assert lines[1] == f"REVISE-ROUND: 1/{revise_contract_round.REVISE_ROUND_BOUND}"
        assert lines[2].startswith("CITATION: ")
        assert len(lines) == 3

    def test_emitted_body_is_accepted_by_the_real_hook_gate(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = _run(tmp_path)
        assert exit_code == 0
        body = capsys.readouterr().out
        block = _evaluate_auto_root_atd_body(body)
        assert block is None, block

    def test_durable_counter_file_is_written(self, tmp_path: Path, capsys) -> None:
        _run(tmp_path)
        capsys.readouterr()
        state_path = (
            tmp_path / ".nwave" / "des" / "revise-rounds" / f"{_DELIVERY_ID}.json"
        )
        assert state_path.is_file()
        assert '"round": 1' in state_path.read_text(encoding="utf-8")


class TestRoundsAdvanceAndRefuseAtTheBound:
    def test_successive_calls_advance_the_round_on_the_same_delivery_id(
        self, tmp_path: Path, capsys
    ) -> None:
        rounds: list[str] = []
        for _ in range(revise_contract_round.REVISE_ROUND_BOUND):
            exit_code = _run(tmp_path)
            assert exit_code == 0
            out = capsys.readouterr().out
            rounds.append(out.split("\n")[1])
        assert rounds == [
            f"REVISE-ROUND: {n}/{revise_contract_round.REVISE_ROUND_BOUND}"
            for n in range(1, revise_contract_round.REVISE_ROUND_BOUND + 1)
        ]

    def test_the_bound_plus_one_call_refuses_with_what_why_how(
        self, tmp_path: Path, capsys
    ) -> None:
        for _ in range(revise_contract_round.REVISE_ROUND_BOUND):
            assert _run(tmp_path) == 0
            capsys.readouterr()

        exit_code = _run(tmp_path)
        captured = capsys.readouterr()
        assert exit_code == 2
        assert captured.out == ""
        assert "WHAT:" in captured.err
        assert "WHY:" in captured.err
        assert "HOW:" in captured.err
        assert str(revise_contract_round.REVISE_ROUND_BOUND) in captured.err

    def test_refusal_does_not_advance_the_durable_counter(
        self, tmp_path: Path, capsys
    ) -> None:
        """Idempotent refusal: a caller retrying a refused call must never
        see the counter creep past the bound."""
        for _ in range(revise_contract_round.REVISE_ROUND_BOUND):
            _run(tmp_path)
            capsys.readouterr()

        _run(tmp_path)
        capsys.readouterr()
        _run(tmp_path)
        capsys.readouterr()

        state_path = (
            tmp_path / ".nwave" / "des" / "revise-rounds" / f"{_DELIVERY_ID}.json"
        )
        assert (
            f'"round": {revise_contract_round.REVISE_ROUND_BOUND}'
            in state_path.read_text(encoding="utf-8")
        )

    def test_a_different_delivery_id_gets_its_own_independent_round_counter(
        self, tmp_path: Path, capsys
    ) -> None:
        other_locator = contract_locator_for(compute_delivery_id("a different seed"))
        for _ in range(revise_contract_round.REVISE_ROUND_BOUND):
            assert _run(tmp_path) == 0
            capsys.readouterr()
        assert _run(tmp_path) == 2  # first DeliveryId exhausted
        capsys.readouterr()

        exit_code = _run(tmp_path, locator=other_locator)
        out = capsys.readouterr().out
        assert exit_code == 0
        assert (
            out.split("\n")[1]
            == f"REVISE-ROUND: 1/{revise_contract_round.REVISE_ROUND_BOUND}"
        )


class TestArgvAndInputValidation:
    def test_relative_repo_root_is_refused(self, tmp_path: Path, capsys) -> None:
        exit_code = revise_contract_round.main(
            [
                "--repo-root",
                "relative/path",
                "--contract-locator",
                _LOCATOR,
                "--citation",
                "x",
            ]
        )
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_malformed_contract_locator_is_refused(
        self, tmp_path: Path, capsys
    ) -> None:
        exit_code = _run(tmp_path, locator="not-a-json-locator")
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_empty_citation_is_refused(self, tmp_path: Path, capsys) -> None:
        exit_code = _run(tmp_path, citation="   ")
        assert exit_code == 2
        assert "WHAT:" in capsys.readouterr().err

    def test_missing_required_flag_is_refused_with_what_why_how(self, capsys) -> None:
        exit_code = revise_contract_round.main(["--contract-locator", _LOCATOR])
        assert exit_code == 2
        captured = capsys.readouterr()
        assert "WHAT:" in captured.err
        assert "WHY:" in captured.err
        assert "HOW:" in captured.err
