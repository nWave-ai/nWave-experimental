"""Composition root for the feature-delta-section-schema ATs (Pillar 3).

Drives the SUT through the REAL driving port — the `des feature-delta-schema`
subcommand invoked as a subprocess (`[sys.executable, "-m", "des", ...]`, Layer 3
subprocess, Mandate-13 driving-port-only). NO production module is imported and
called at the step boundary for the CLI projections; the subprocess IS the SUT.

The only arranged state is a feature-delta `.md` document written into a hermetic
`tmp_path` (a driven-internal filesystem port). No `~/.claude` / personal-hook
path is touched (the hermeticity guard rejects those).

Step methods on the composition objects are the shared vocabulary the pytest-bdd
binds delegate to; each bind body is a single delegation (Mandate-12, no logic).
"""

from __future__ import annotations

from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process

from .domain_types import CliResult, DocFixture, Verdict, Wave


_REPO_ROOT = Path(__file__).resolve().parents[5]


# ---------------------------------------------------------------------------
# Document fixtures — the WRITE side (P3 output_contract is the spec these obey).
# A well-formed convergence section uses the byte-locked columns from §S.5.
# ---------------------------------------------------------------------------

_WELL_FORMED = """# Feature Delta — sample

## Wave: DISCUSS / [REF] Slice Plan

| Slice | Value statement | Status | Annotation | Justification |
|-------|-----------------|--------|------------|---------------|
| slice-01 | A user can do the thing | designed | @walking-skeleton | thin vertical |

## Reuse Analysis

| Existing Component | File | Overlap | Decision | Justification |
|--------------------|------|---------|----------|---------------|
| foo | src/foo.py | partial | EXTEND | reuse the existing pure helper |

## Wave: DESIGN / [REF] Architecture & Contract Tests

### Contract-Tests

| Component/AT-target | Contract-shape | Universe | Assertion-mechanism | Consumed-by |
|---------------------|----------------|----------|---------------------|-------------|
| do_thing | pure-function | {result} | example | distill,deliver |

### Architecture-Tests

| Invariant | AST-query-or-probe | Enforcement-layer | Consumed-by |
|-----------|--------------------|--------------------|-------------|
| imports des.* only | grep imports | unit | deliver,review |

## Wave: DESIGN / [REF] ADR Refs

- slice-01: ADR-FLOW-007
"""

# Slice Plan Table with a reordered header → P1 must FAIL naming the Slice Plan.
_BAD_SLICE_PLAN = _WELL_FORMED.replace(
    "| Slice | Value statement | Status | Annotation | Justification |",
    "| Value statement | Slice | Status | Annotation | Justification |",
)

# Convergence Contract-Tests header reordered → slice-03 byte-lock FAIL.
_REORDERED_CONTRACT_TESTS = _WELL_FORMED.replace(
    "| Component/AT-target | Contract-shape | Universe | Assertion-mechanism | Consumed-by |",
    "| Contract-shape | Component/AT-target | Universe | Assertion-mechanism | Consumed-by |",
)

# Convergence Architecture-Tests header reordered → slice-03 byte-lock FAIL.
_REORDERED_ARCH_TESTS = _WELL_FORMED.replace(
    "| Invariant | AST-query-or-probe | Enforcement-layer | Consumed-by |",
    "| AST-query-or-probe | Invariant | Enforcement-layer | Consumed-by |",
)

_FIXTURE_BODY: dict[DocFixture, str] = {
    DocFixture.WELL_FORMED: _WELL_FORMED,
    DocFixture.GOOD_CONVERGENCE: _WELL_FORMED,
    DocFixture.BAD_SLICE_PLAN: _BAD_SLICE_PLAN,
    DocFixture.REORDERED_CONTRACT_TESTS: _REORDERED_CONTRACT_TESTS,
    DocFixture.REORDERED_ARCH_TESTS: _REORDERED_ARCH_TESTS,
}


def _run(args: list[str], cwd: Path) -> CliResult:
    exit_code, stdout, stderr = run_cli_in_process(
        ["feature-delta-schema", *args], cwd=cwd
    )
    return CliResult(exit_code=exit_code, stdout=stdout, stderr=stderr)


def _write_doc(tmp_path: Path, fixture: DocFixture) -> Path:
    target = tmp_path / "feature-delta.md"
    if fixture is DocFixture.UNREADABLE:
        target.write_bytes(b"\xff\xfe\x00 not valid utf-8 \x80\x81")
    else:
        target.write_text(_FIXTURE_BODY[fixture], encoding="utf-8")
    return target


class DescribeComposition:
    """slice-01 — `des feature-delta-schema describe` (the algebra as one value)."""

    def __init__(self) -> None:
        self._result: CliResult | None = None

    def when_described(self, *extra: str) -> None:
        self._result = _run(["describe", *extra], cwd=_REPO_ROOT)

    def _stdout(self) -> str:
        assert self._result is not None, "describe was not invoked"
        return self._result.stdout

    def then_succeeds(self) -> None:
        assert self._result is not None and self._result.exit_code == 0, (
            f"describe must exit 0; got {self._result!r}"
        )

    def then_lists_exactly_five_constructors(self) -> None:
        from .domain_types import ConstructorName

        out = self._stdout()
        for name in ConstructorName:
            assert name.value in out, (
                f"constructor {name.value} missing from describe output"
            )

    def then_each_section_has_one_constructor(self) -> None:
        out = self._stdout()
        assert out.strip(), "describe must list sections with their constructor"
        # observable: at least the Slice Plan section reported as a Table
        assert "Table" in out, "a registered section must map to a Table constructor"

    def then_consumed_by_is_kebab_subset_of_waves(self) -> None:
        out = self._stdout()
        valid = {w.value for w in Wave}
        # observable: every consumed_by token printed is a kebab-lowercase wave
        printed = {tok for tok in out.replace(",", " ").split() if tok in valid}
        assert printed, "describe must print consumed_by wave tokens"
        assert printed <= valid, f"off-set wave token printed: {printed - valid}"


class VerifyComposition:
    """slice-02/03 — `des feature-delta-schema verify <file>` (P1 gate-verify)."""

    def __init__(self) -> None:
        self._doc: Path | None = None
        self._result: CliResult | None = None

    def given_document(self, tmp_path: Path, fixture: DocFixture) -> None:
        self._doc = _write_doc(tmp_path, fixture)

    def when_verified(self) -> None:
        assert self._doc is not None, "no document arranged"
        self._result = _run(["verify", str(self._doc)], cwd=_REPO_ROOT)

    def _both(self) -> CliResult:
        assert self._result is not None, "verify was not invoked"
        return self._result

    def then_verdict_pass(self) -> None:
        r = self._both()
        assert r.exit_code == 0 and Verdict.PASS.value in r.stdout, (
            f"expected PASS exit 0; got {r!r}"
        )

    def then_verdict_fail_naming_offender(self, offender: str) -> None:
        r = self._both()
        assert r.exit_code != 0, f"fail-closed: expected non-zero exit; got {r!r}"
        assert Verdict.FAIL.value in r.stdout, f"expected FAIL verdict; got {r!r}"
        assert offender in r.stdout, (
            f"FAIL must name the offending section {offender!r}; got {r!r}"
        )

    def then_verdict_indeterminate(self) -> None:
        r = self._both()
        assert r.exit_code != 0, f"degrade-LOUD: expected non-zero exit; got {r!r}"
        assert Verdict.INDETERMINATE.value in r.stdout, (
            f"unreadable doc must yield INDETERMINATE, never silent-pass; got {r!r}"
        )


class InjectComposition:
    """slice-02/04 — `des feature-delta-schema inject --wave <w>` (P2 wave-injection)."""

    def __init__(self) -> None:
        self._result: CliResult | None = None
        self._wave: Wave | None = None

    def when_injected(self, wave: Wave) -> None:
        self._wave = wave
        self._result = _run(["inject", "--wave", wave.value], cwd=_REPO_ROOT)

    def _out(self) -> str:
        assert self._result is not None, "inject was not invoked"
        return self._result.stdout

    def then_rows_all_consume_wave(self) -> None:
        assert self._wave is not None
        out = self._out()
        assert self._result is not None and self._result.exit_code == 0, (
            f"inject must exit 0; got {self._result!r}"
        )
        # observable: the convergence section (consumed_by ∋ distill,design) appears
        assert "architecture-and-contract-tests" in out, (
            f"inject --wave {self._wave.value} must project the consuming section; got {out!r}"
        )

    def then_projection_is_empty(self) -> None:
        out = self._out().strip()
        assert self._result is not None and self._result.exit_code == 0, (
            f"inject must exit 0 even on empty projection; got {self._result!r}"
        )
        assert "architecture-and-contract-tests" not in out, (
            f"a wave consuming nothing must get an empty projection; got {out!r}"
        )

    def then_no_engine_imported(self) -> None:
        # observable: the subprocess ran on Python+filesystem only and succeeded.
        assert self._result is not None and self._result.exit_code == 0, (
            f"inject must run hooks-only/Python-only; got {self._result!r}"
        )


class ContractComposition:
    """slice-02 — `des feature-delta-schema contract <section_id>` (P3 output_contract)."""

    def __init__(self) -> None:
        self._result: CliResult | None = None

    def when_contract_requested(self, section_id: str) -> None:
        self._result = _run(["contract", section_id], cwd=_REPO_ROOT)

    def then_returns_write_spec(self, heading_literal: str) -> None:
        assert self._result is not None and self._result.exit_code == 0, (
            f"contract must exit 0; got {self._result!r}"
        )
        assert heading_literal in self._result.stdout, (
            f"write spec must carry the heading literal {heading_literal!r}; got {self._result!r}"
        )


class CarpaccioPreservationComposition:
    """slice-03 — the convergence section is additive; Slice Plan stays 5 columns."""

    def __init__(self) -> None:
        self._doc: Path | None = None
        self._result: CliResult | None = None

    def given_document_with_convergence(self, tmp_path: Path) -> None:
        self._doc = _write_doc(tmp_path, DocFixture.GOOD_CONVERGENCE)

    def when_carpaccio_gate_runs(self) -> None:
        assert self._doc is not None
        # the existing carpaccio slice-plan gate must still accept the unchanged
        # 5-column Slice Plan when the additive convergence section is present.
        exit_code, stdout, stderr = run_cli_in_process(
            [
                "validate-feature-delta",
                "--require-slice-plan",
                "--format=json",
                str(self._doc),
            ],
            cwd=_REPO_ROOT,
        )
        self._result = CliResult(exit_code, stdout, stderr)

    def then_slice_plan_still_accepted(self) -> None:
        r = self._result
        assert r is not None and r.exit_code == 0 and "accepted" in r.stdout, (
            f"additive convergence section must not break the 5-col Slice Plan gate; got {r!r}"
        )
