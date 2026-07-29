# @feature-agnostic-at-discovery
# @slice-01
"""AT-KIND suffix->runner map has ONE SSOT definition, not two (ADR-AAD-001).

agnostic-at-discovery slice-01. Value statement (feature-delta.md [REF] Slice
Plan): "The suffix->at_kind map has one definition, not two, so a future 3rd
copy (this feature's own new function) never has to be written independently
and cannot silently diverge from its siblings."

Today ``des.cli.carpaccio_format._AT_DISCOVERY_SUFFIX_RUNNER`` and
``des.application.slice_at_completeness._NATIVE_REGRESSION_SUFFIX_RUNNER``
are two byte-identical, independently-maintained dict literals
(``{".py": "pytest", ".rs": "cargo-test"}`` -- verified in this feature's own
DESIGN Prefactoring Assessment DA-5). This slice promotes ONE SSOT,
``des.ports.test_runner_port.AT_KIND_SUFFIX_MAP``, and makes both existing
private names IMPORT it (identity, not value-copy) rather than each keeping
an independent literal.

Contract-shape: pure-function (constant substitution -- no behavior change,
per feature-delta.md [REF] Architecture & Contract Tests, Contract-Tests row
3 "AT_KIND_SUFFIX_MAP import replacement").

Driving surface (Mandate 13, Layer 3 composition-root default): every
scenario drives the REAL, STABLE, EXISTING production entries
``des.ports.test_runner_port`` / ``des.cli.carpaccio_format.
native_regression_at_discovery`` / ``des.application.slice_at_completeness.
_native_regression_at_evidence_exists`` -- the exact two consumer call sites
this feature's own DESIGN names (Contract-Tests row 3 "Consumed-by:
native_regression_at_discovery, DELIVER" + Reuse Analysis table). No new CLI
driving port exists at this granularity (slice-03 wires the CLI); these
application-layer functions ARE the composition root this repo's own
precedent already tests directly (e.g.
``tests/bugs/des/test_at_discovery_facet_pair_unifies_rust_and_python_
regression_slices.py`` calls ``RunnerAdapter.discover_ats`` and
``commit_slice._committed_scope_digest_or_degrade_reason`` directly).

RED-for-right-reason (P1-P4, ``nw-distill-red-scaffolding``): module top
imports ONLY the three STABLE, already-existing modules -- never a not-yet-
defined name. Each scenario's own absent-behaviour guard
(``hasattr(test_runner_port, "AT_KIND_SUFFIX_MAP")``) converts the otherwise-
raw ``AttributeError`` into a semantic, message-carrying ``AssertionError``
at RUNTIME inside the test body, never a collection-time error. Scenario 1
(the SSOT-cardinality architecture-test) needs no guard: it is a genuine
COUNT assertion (2 duplicate literals found today, not 1) that fails on its
own terms.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from des.application import slice_at_completeness
from des.cli import carpaccio_format
from des.ports import test_runner_port


_EXPECTED_SUFFIX_MAP = {".py": "pytest", ".rs": "cargo-test"}


def _src_des_root() -> Path:
    """Locate ``src/des`` from an already-imported, stable module's ``__file__``."""
    return Path(test_runner_port.__file__).resolve().parent.parent


def _suffix_map_definitions(root: Path) -> list[tuple[Path, str]]:
    """Every module-level ``name = {".py": ..., ".rs": ...}`` assignment under ``root``.

    Structural (AST) match on the KEY SET, never on a name/path pattern (GDP-8:
    decide on the property the object HAS, not a designation that merely
    stands for it) -- so a differently-named private copy is caught exactly
    as readily as the SSOT itself.
    """
    found: list[tuple[Path, str]] = []
    for py_file in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except (SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            keys = {
                key.value
                for key in node.value.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            }
            if keys != {".py", ".rs"}:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.append((py_file, target.id))
    return found


def test_at_kind_suffix_map_never_has_a_second_definition_in_the_tree() -> None:
    """The WRONG state -- a second, independently-maintained
    ``{".py": ..., ".rs": ...}`` dict literal anywhere under ``src/des`` --
    must NEVER be produced; exactly ONE such literal may exist, and it must
    be ``AT_KIND_SUFFIX_MAP`` in ``test_runner_port.py`` (the D2-class
    divergence risk this ADR closes; feature-delta.md [REF] Architecture &
    Contract Tests, Architecture-Tests row 1). This is the negative AT for
    slice-01: it asserts the duplicate-copy defect class does not recur, not
    merely that the SSOT itself is present.
    """
    # covers: R1
    root = _src_des_root()
    definitions = _suffix_map_definitions(root)
    assert len(definitions) == 1, (
        "expected exactly ONE suffix->runner dict literal "
        f"({_EXPECTED_SUFFIX_MAP!r}-shaped) under {root} -- found "
        f"{len(definitions)}: "
        f"{[(str(p.relative_to(root)), name) for p, name in definitions]!r}. "
        "des.ports.test_runner_port.AT_KIND_SUFFIX_MAP must be the ONE SSOT "
        "(ADR-AAD-001 DA-5); the private copies in carpaccio_format.py and "
        "slice_at_completeness.py must IMPORT it, not redefine it."
    )
    (only_file, only_name) = definitions[0]
    assert only_file.name == "test_runner_port.py", (
        f"the ONE suffix->runner definition must live in test_runner_port.py "
        f"-- found it in {only_file.relative_to(root)} instead"
    )
    assert only_name == "AT_KIND_SUFFIX_MAP", (
        f"the ONE suffix->runner definition must be named AT_KIND_SUFFIX_MAP "
        f"(ADR-AAD-001) -- found it named {only_name!r} instead"
    )


def test_carpaccio_format_resolves_native_regression_at_kind_through_the_ssot_suffix_map(
    tmp_path: Path,
) -> None:
    """``carpaccio_format.native_regression_at_discovery`` must resolve a
    ``.py`` and a ``.rs`` regression file through the promoted SSOT
    (identity, not an independently-defined literal), yielding the SAME
    discovered AT ids / content hash it always has (regression, not new
    coverage; feature-delta.md Contract-Tests row 3).
    """
    # covers: R2
    assert hasattr(test_runner_port, "AT_KIND_SUFFIX_MAP"), (
        "des.ports.test_runner_port must expose AT_KIND_SUFFIX_MAP -- the "
        "promoted suffix->runner SSOT (ADR-AAD-001 slice-01) -- not yet "
        "promoted."
    )
    assert test_runner_port.AT_KIND_SUFFIX_MAP == _EXPECTED_SUFFIX_MAP, (
        f"AT_KIND_SUFFIX_MAP must be {_EXPECTED_SUFFIX_MAP!r} (byte-identical "
        f"to the pre-promotion private copies) -- got "
        f"{test_runner_port.AT_KIND_SUFFIX_MAP!r}"
    )
    assert hasattr(carpaccio_format, "_AT_DISCOVERY_SUFFIX_RUNNER"), (
        "carpaccio_format must still expose _AT_DISCOVERY_SUFFIX_RUNNER as an "
        "IMPORT of the SSOT (DA-5: 'function body otherwise unchanged') -- "
        "the name is missing entirely."
    )
    assert (
        carpaccio_format._AT_DISCOVERY_SUFFIX_RUNNER
        is test_runner_port.AT_KIND_SUFFIX_MAP
    ), (
        "carpaccio_format._AT_DISCOVERY_SUFFIX_RUNNER must be the SAME "
        "object as test_runner_port.AT_KIND_SUFFIX_MAP (an import, not an "
        "independently-defined literal) -- identity check failed, got "
        f"{carpaccio_format._AT_DISCOVERY_SUFFIX_RUNNER!r}"
    )

    py_file = tmp_path / "test_mixed_regression.py"
    py_file.write_text("def test_one():\n    assert True\n", encoding="utf-8")
    at_ids, content_hash = carpaccio_format.native_regression_at_discovery(py_file)
    assert list(at_ids) == ["test_one"], f"got at_ids={at_ids!r}"
    assert content_hash == hashlib.sha256(py_file.read_bytes()).hexdigest()

    rs_file = tmp_path / "balance_invariants.rs"
    rs_file.write_text(
        "#[test]\nfn balance_ok() {\n    assert_eq!(1 + 1, 2);\n}\n", encoding="utf-8"
    )
    at_ids_rs, content_hash_rs = carpaccio_format.native_regression_at_discovery(
        rs_file
    )
    assert list(at_ids_rs) == ["balance_ok"], f"got at_ids={at_ids_rs!r}"
    assert content_hash_rs == hashlib.sha256(rs_file.read_bytes()).hexdigest()


def test_slice_at_completeness_resolves_native_regression_evidence_through_the_ssot_suffix_map(
    tmp_path: Path,
) -> None:
    """``slice_at_completeness._native_regression_at_evidence_exists`` must
    resolve a ``.py`` and a ``.rs`` regression file through the promoted SSOT
    (identity, not an independently-defined literal), yielding the SAME
    evidence-exists verdict it always has (regression, not new coverage;
    feature-delta.md Contract-Tests row 3).
    """
    # covers: R3
    assert hasattr(test_runner_port, "AT_KIND_SUFFIX_MAP"), (
        "des.ports.test_runner_port must expose AT_KIND_SUFFIX_MAP -- the "
        "promoted suffix->runner SSOT (ADR-AAD-001 slice-01) -- not yet "
        "promoted."
    )
    assert hasattr(slice_at_completeness, "_NATIVE_REGRESSION_SUFFIX_RUNNER"), (
        "slice_at_completeness must still expose "
        "_NATIVE_REGRESSION_SUFFIX_RUNNER as an IMPORT of the SSOT (DA-5) -- "
        "the name is missing entirely."
    )
    assert (
        slice_at_completeness._NATIVE_REGRESSION_SUFFIX_RUNNER
        is test_runner_port.AT_KIND_SUFFIX_MAP
    ), (
        "slice_at_completeness._NATIVE_REGRESSION_SUFFIX_RUNNER must be the "
        "SAME object as test_runner_port.AT_KIND_SUFFIX_MAP (an import, not "
        "an independently-defined literal) -- identity check failed, got "
        f"{slice_at_completeness._NATIVE_REGRESSION_SUFFIX_RUNNER!r}"
    )

    repo = tmp_path
    py_rel = "tests/regression/test_balance.py"
    py_file = repo / py_rel
    py_file.parent.mkdir(parents=True, exist_ok=True)
    py_file.write_text("def test_balance():\n    assert True\n", encoding="utf-8")
    assert (
        slice_at_completeness._native_regression_at_evidence_exists(repo, py_rel)
        is True
    ), f"expected AT evidence for a well-formed {py_rel} -- got False"

    rs_rel = "tests/regression/balance_invariants.rs"
    rs_file = repo / rs_rel
    rs_file.parent.mkdir(parents=True, exist_ok=True)
    rs_file.write_text(
        "#[test]\nfn balance_ok() {\n    assert_eq!(1 + 1, 2);\n}\n", encoding="utf-8"
    )
    assert (
        slice_at_completeness._native_regression_at_evidence_exists(repo, rs_rel)
        is True
    ), f"expected AT evidence for a well-formed {rs_rel} -- got False"
