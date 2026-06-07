"""Composition-root service for the M11 integration-sad-path gate AT (slice-07).

Mandate-12 (criteria 2+3): business logic lives here as the single source of
truth; step bodies invoke this service via typed parameters and never inline
logic. The service drives the REAL rule entrypoints
``des.testarch.rules.sad_path_pbt.detect`` (the PBT-layer half) and
``des.testarch.rules.sad_path_pbt.detect_failure_mode_coverage`` (the coverage
half) through the production ``PythonAstAdapter`` — the driving port the gate is
authored against (ADR-TEST-002 D-C; feature-delta Driving Ports).

Each golden-fixture corpus is read off its real disk path. The PBT-layer half is
classified at a SYNTHETIC representative layer-path (slice-03/04 pattern), so the
gate keys on the intended layer (3+ forbidden vs 1-2 home) independent of where
the fixture physically lives under ``acceptance/fixtures/``.

Honest tagging: this is an in-process pure-AST/YAML query of a source file. It is
``@component`` (auto-``unit`` under ``tests/build/``), NEVER
``@wiring_e2e``/``@subprocess`` — there is no spawn, no real I/O beyond reading a
fixture file off disk.
"""

from __future__ import annotations

from des.testarch.adapters.python_ast import PythonAstAdapter
from des.testarch.rules.sad_path_pbt import (
    SadPathPbtVerdict,
    detect,
    detect_failure_mode_coverage,
)
from tests.build.at_mandate_mechanical_enforcement.acceptance.steps.domain_types import (
    COVERED_FAILURE_MODE_TEST_NAMES,
    COVERED_MANIFEST_CORPUS,
    EXAMPLE_AT_LAYER_CORPUS,
    EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH,
    PBT_AT_HOME_CORPUS,
    PBT_AT_HOME_REPRESENTATIVE_PATH,
    PBT_STRANDED_CORPUS,
    PBT_STRANDED_REPRESENTATIVE_PATH,
    R6_ADVERSARIAL_CORPUS,
    R6_ADVERSARIAL_REPRESENTATIVE_PATH,
    UNCOVERED_MANIFEST_CORPUS,
    SadPathCorpusKind,
    SadPathOutcome,
)


# PBT-layer-half corpus kind → (real disk path, synthetic layer-path).
_PBT_CORPUS_BY_KIND = {
    SadPathCorpusKind.PBT_STRANDED_AT_LAYER_3PLUS: (
        PBT_STRANDED_CORPUS,
        PBT_STRANDED_REPRESENTATIVE_PATH,
    ),
    SadPathCorpusKind.EXAMPLE_AT_LAYER_3PLUS: (
        EXAMPLE_AT_LAYER_CORPUS,
        EXAMPLE_AT_LAYER_REPRESENTATIVE_PATH,
    ),
    SadPathCorpusKind.PBT_AT_HOME_LAYER: (
        PBT_AT_HOME_CORPUS,
        PBT_AT_HOME_REPRESENTATIVE_PATH,
    ),
    SadPathCorpusKind.R6_ADVERSARIAL: (
        R6_ADVERSARIAL_CORPUS,
        R6_ADVERSARIAL_REPRESENTATIVE_PATH,
    ),
}

# Coverage-half corpus kind → (manifest disk path, covering named tests).
_MANIFEST_CORPUS_BY_KIND = {
    SadPathCorpusKind.UNCOVERED_FAILURE_MODE: (UNCOVERED_MANIFEST_CORPUS, ()),
    SadPathCorpusKind.COVERED_FAILURE_MODE: (
        COVERED_MANIFEST_CORPUS,
        COVERED_FAILURE_MODE_TEST_NAMES,
    ),
}


class SadPathPbtGate:
    """Drives the real M11 rule through the production Python AST adapter."""

    def __init__(self) -> None:
        self._adapter = PythonAstAdapter()

    def path_for(self, corpus: SadPathCorpusKind):
        """The on-disk path of the named golden-fixture corpus (port-observable)."""
        if corpus in _PBT_CORPUS_BY_KIND:
            return _PBT_CORPUS_BY_KIND[corpus][0]
        return _MANIFEST_CORPUS_BY_KIND[corpus][0]

    def inspect(self, corpus: SadPathCorpusKind) -> SadPathPbtVerdict:
        """Run the real PBT-layer ``detect`` over the named golden-fixture corpus.

        The fixture content is read off disk; the layer is fixed by the synthetic
        representative path so the gate audits the intended layer.
        """
        disk_path, layer_path = _PBT_CORPUS_BY_KIND[corpus]
        source = disk_path.read_text(encoding="utf-8")
        return detect(
            source, adapter=self._adapter, path=layer_path, filename=str(disk_path)
        )

    def cross_check_coverage(self, corpus: SadPathCorpusKind) -> SadPathPbtVerdict:
        """Run the real failure-mode-coverage cross-check over a manifest corpus."""
        manifest_path, covering_tests = _MANIFEST_CORPUS_BY_KIND[corpus]
        manifest_source = manifest_path.read_text(encoding="utf-8")
        test_sources = dict.fromkeys(covering_tests, "")
        return detect_failure_mode_coverage(
            manifest_source,
            adapter=self._adapter,
            test_sources=test_sources,
            manifest_filename=str(manifest_path),
        )

    @staticmethod
    def outcome_of(verdict: SadPathPbtVerdict) -> SadPathOutcome:
        """Project the rule verdict onto the port-exposed outcome enum."""
        return SadPathOutcome.FLAGGED if verdict.flagged else SadPathOutcome.CLEAN


def build_gate() -> SadPathPbtGate:
    """Composition-root entry — the production object graph for the gate AT."""
    return SadPathPbtGate()
