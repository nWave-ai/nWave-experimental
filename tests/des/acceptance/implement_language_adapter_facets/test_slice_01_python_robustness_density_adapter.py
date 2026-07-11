"""Slice-01 AT: PythonRobustnessDensityAdapter.covered_domain_ids genuinely scans.

Feature `implement-language-adapter-facets`, slice-01 (feature-delta.md
Slice Plan row 1, component D1). Value statement: a contributor running
`check-robustness-density` against nWave-dev's own Python AT scope gets
routed through a REAL ``PythonRobustnessDensityAdapter`` -- not a silent
fall-through to the hardcoded body -- because ``covered_domain_ids``
genuinely wraps the existing ``*.py`` glob + ``# domain:``-comment scan
(``scripts/cli/check_robustness_density.py::_covered_domain_ids``, DDD-04).

Driving surface (Mandate 13 / composition-contract): the adapter class
``PythonRobustnessDensityAdapter`` ALREADY EXISTS in production
(``src/des/adapters/driven/robustness/python_robustness_density_adapter.py``,
shipped stub from the parent feature `unified-language-adapter-registry`
slice-04, ADR-ULAR-005) -- it is not a not-yet-created SUT module, so no
DISTILL scaffold is authored here (nw-distill-red-scaffolding step 1
"inventory not-yet-existing modules" finds none). This is a driven-ADAPTER
test (Mandate 6: every driven adapter earns >=1 @real-io scenario) --
the adapter is instantiated and driven DIRECTLY with real filesystem I/O
against a ``tmp_path`` fixture tree, exactly as the DESIGN Contract Shapes
table prescribes for D1 ("behavior-parity fixture test: adapter output
byte-identical to the pre-extraction Python gate's own
``_covered_domain_ids`` on the same fixture tree"). This is NOT a
driving-port-boundary violation (Mandate 16): the port under test here IS
the driven port (``RobustnessDensityPort``), which by definition is
exercised via direct adapter instantiation, never via a fake.

Replicated scan semantics (read verbatim via Tsunami `atoms-in-file` +
`Read` from ``scripts/cli/check_robustness_density.py:177-194``, the
``_covered_domain_ids`` function DDD-04 requires D1 to duplicate, not
import -- F-D-09 forbids ``src/des/**`` importing ``scripts.*``)::

    covered: set[str] = set()
    for path in at_scope_dir.rglob("*.py"):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("# domain:"):
                continue
            marker = stripped[len("# domain:") :].strip()
            if marker:
                covered.add(marker)
    return covered

The exact contract the crafter must match:
  * recursive ``*.py`` glob (``rglob``, not ``glob`` -- subdirectories count)
  * a line only counts when its STRIPPED form starts with the literal
    ``"# domain:"`` (one space after ``#``, colon immediately after
    ``domain``, no leading ``#domain:`` or ``#  domain:`` variant)
  * the marker text is everything after ``"# domain:"``, stripped
  * an empty marker (``"# domain:"`` with nothing/only-whitespace after)
    contributes NOTHING -- not an error, not a spurious empty-string id
  * non-``*.py`` files are never read
  * repeated markers (same file or across files) dedupe via ``set``

Active-RED today: ``covered_domain_ids`` is a pure
``raise NotImplementedError(...)`` stub. Every scenario below imports ONLY
the already-shipped adapter class (safe: no collection-time ImportError --
the class exists, only its method body is unimplemented) and calls
``covered_domain_ids`` inside the test body; the call raises
``NotImplementedError`` before any assertion runs, which
``des verify-red-green`` classifies as a genuine SEMANTIC failure (the
JUnit testcase collects with a real classname and errors during execution,
not during collection -- see ``verify_red_green.py::_run_and_collect``,
which distinguishes BROKEN [empty-classname collection error] from RED
[named testcase, failed/errored during its own execution]). Never
``@skip``/``@pytest.mark.skip`` per ADR-GV-001 D6.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from des.adapters.driven.robustness.python_robustness_density_adapter import (
    PythonRobustnessDensityAdapter,
)


# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def adapter() -> PythonRobustnessDensityAdapter:
    """The real, production-composed adapter under test -- no fake, no mock."""
    return PythonRobustnessDensityAdapter()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- positive: genuine scan, not a silent fall-through ------------------------


def test_covered_domain_ids_scans_real_domain_comments_in_python_files(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """Two distinct `# domain:` markers across two files are both discovered."""
    _write(
        tmp_path / "test_alpha_scenarios.py",
        "# domain: alpha-input-shape\ndef test_alpha() -> None:\n    assert True\n",
    )
    _write(
        tmp_path / "nested" / "test_beta_scenarios.py",
        "def test_beta() -> None:\n    # domain: beta-input-shape\n    assert True\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"alpha-input-shape", "beta-input-shape"}, (
        "covered_domain_ids must genuinely scan the *.py tree and collect "
        "every '# domain: <id>' marker -- exactly matching "
        "check_robustness_density.py::_covered_domain_ids semantics -- but "
        f"today the method is a NotImplementedError stub. Got: {covered!r}"
    )


def test_covered_domain_ids_dedupes_the_same_domain_across_multiple_files(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """The same domain id declared in 2 files contributes exactly one entry."""
    _write(tmp_path / "test_one.py", "# domain: shared-domain\n")
    _write(tmp_path / "test_two.py", "# domain: shared-domain\n")

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"shared-domain"}, (
        "a domain id repeated across files must dedupe to one set entry "
        f"(set semantics, per _covered_domain_ids). Got: {covered!r}"
    )


def test_covered_domain_ids_recurses_into_subdirectories(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """`rglob("*.py")`, not `glob` -- a nested-directory marker is found too."""
    _write(
        tmp_path / "deep" / "deeper" / "test_nested.py",
        "# domain: deeply-nested-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"deeply-nested-domain"}, (
        "the scan must recurse into subdirectories (rglob, not a shallow "
        f"glob) -- matching _covered_domain_ids. Got: {covered!r}"
    )


# --- boundary: exact `# domain:` prefix, not a loose match --------------------


def test_covered_domain_ids_requires_the_exact_marker_prefix(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """Only the literal `# domain:` prefix counts; near-miss variants do not."""
    _write(
        tmp_path / "test_near_misses.py",
        "#domain: no-space-after-hash\n"
        "# Domain: wrong-case\n"
        "#  domain: extra-space-after-hash\n"
        "# domain-marker: not-the-real-prefix\n"
        "# domain: genuine-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"genuine-domain"}, (
        "only lines whose STRIPPED form starts with the exact literal "
        "'# domain:' count -- '#domain:' (no space), '# Domain:' (wrong "
        "case), '#  domain:' (extra space) and '# domain-marker:' must "
        f"all be ignored, matching str.startswith('# domain:'). Got: {covered!r}"
    )


# --- negative ATs: empty scope / empty marker must NOT fabricate coverage ----


def test_covered_domain_ids_rejects_a_scope_with_no_domain_comments(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """A *.py-bearing scope with zero `# domain:` markers returns EMPTY --

    never an error, and never a spurious/fabricated domain id.
    """
    _write(
        tmp_path / "test_plain.py",
        "def test_something() -> None:\n    assert True\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == set(), (
        "a scope with *.py files but zero '# domain:' markers must return "
        f"an EMPTY set, not raise and not fabricate a domain id. Got: {covered!r}"
    )


@pytest.mark.negative_at
def test_covered_domain_ids_never_records_an_empty_marker_as_a_domain_id(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """`# domain:` with nothing (or only whitespace) after it is NOT a domain id."""
    _write(
        tmp_path / "test_empty_marker.py",
        "# domain:\n# domain:   \n# domain: real-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert "" not in covered, (
        "an empty (or whitespace-only) marker after '# domain:' must NEVER "
        f"be recorded as a domain id -- the `if marker:` guard in "
        f"_covered_domain_ids must be replicated. Got: {covered!r}"
    )
    assert covered == {"real-domain"}, (
        "only the genuinely-populated marker line contributes; the two "
        f"empty-marker lines contribute nothing. Got: {covered!r}"
    )


def test_covered_domain_ids_ignores_non_python_files(
    adapter: PythonRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """A `# domain:` marker in a non-`*.py` file must never be picked up."""
    _write(tmp_path / "notes.txt", "# domain: should-be-ignored\n")
    _write(tmp_path / "test_real.py", "# domain: genuinely-python\n")

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"genuinely-python"}, (
        "the glob is *.py-scoped; a marker sitting in a .txt (or any "
        "non-.py) file must never contribute a domain id -- only the *.py "
        f"file's marker should appear. Got: {covered!r}"
    )
