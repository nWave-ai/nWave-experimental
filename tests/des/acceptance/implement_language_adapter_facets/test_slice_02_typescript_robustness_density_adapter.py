"""Slice-02 AT: TypeScriptRobustnessDensityAdapter.covered_domain_ids genuinely scans.

Feature `implement-language-adapter-facets`, slice-02 (feature-delta.md
Slice Plan row 2, component D2). Value statement: a contributor running
``check-robustness-density`` against a TypeScript AT scope gets the
IDENTICAL guarantee slice-01 gave the Python adapter -- not a silent
fall-through to the hardcoded body -- because ``covered_domain_ids``
genuinely wraps the same ``# domain:``-comment scan algorithm, glob-scoped
to ``*.ts``/``*.tsx`` instead of ``*.py`` (DDD-05).

Driving surface (Mandate 13 / composition-contract): the adapter class
``TypeScriptRobustnessDensityAdapter`` ALREADY EXISTS in production
(``src/des/adapters/driven/robustness/typescript_robustness_density_adapter.py``,
shipped stub from the parent feature `unified-language-adapter-registry`
slice-03, ADR-ULAR-005) -- it is not a not-yet-created SUT module, so no
DISTILL scaffold is authored here (nw-distill-red-scaffolding step 1
"inventory not-yet-existing modules" finds none). This is a driven-ADAPTER
test (Mandate 6: every driven adapter earns >=1 @real-io scenario) -- the
adapter is instantiated and driven DIRECTLY with real filesystem I/O
against a ``tmp_path`` fixture tree, exactly as slice-01's AT does for the
Python sibling. This is NOT a driving-port-boundary violation (Mandate 16):
the port under test here IS the driven port (``RobustnessDensityPort``),
which by definition is exercised via direct adapter instantiation, never
via a fake.

Marker convention -- grounded, not assumed (DDD-05, feature-delta.md line
61): "The `# domain: <id>` marker convention is language-agnostic prose (a
comment), but the file-extension filter must match the target language's
source files." The TS adapter uses the IDENTICAL Python-style ``# domain:``
comment marker as slice-01 -- NOT a `//`-prefixed TS-native comment. Only
the glob pattern changes (``*.ts``/``*.tsx`` instead of ``*.py``); the scan
algorithm is otherwise byte-identical to
``PythonRobustnessDensityAdapter.covered_domain_ids``
(``src/des/adapters/driven/robustness/python_robustness_density_adapter.py``,
slice-01, already implemented)::

    covered: set[str] = set()
    for path in itertools.chain(
        at_scope_dir.rglob("*.ts"), at_scope_dir.rglob("*.tsx")
    ):
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("# domain:"):
                continue
            marker = stripped[len("# domain:") :].strip()
            if marker:
                covered.add(marker)
    return covered

The exact contract the crafter must match:
  * recursive glob over BOTH ``*.ts`` AND ``*.tsx`` (``rglob``, not
    ``glob`` -- subdirectories count for both extensions)
  * a line only counts when its STRIPPED form starts with the literal
    ``"# domain:"`` (one space after ``#``, colon immediately after
    ``domain``, no leading ``#domain:`` or ``#  domain:`` variant) --
    IDENTICAL marker syntax to the Python adapter, despite TS's native
    comment syntax being ``//``
  * the marker text is everything after ``"# domain:"``, stripped
  * an empty marker (``"# domain:"`` with nothing/only-whitespace after)
    contributes NOTHING -- not an error, not a spurious empty-string id
  * a ``*.py`` file bearing a marker is IGNORED -- the glob is TS-scoped,
    not language-agnostic
  * repeated markers (same file or across files, or across ``.ts``/``.tsx``)
    dedupe via ``set``

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

from des.adapters.driven.robustness.typescript_robustness_density_adapter import (
    TypeScriptRobustnessDensityAdapter,
)


# --- fixtures ----------------------------------------------------------------


@pytest.fixture
def adapter() -> TypeScriptRobustnessDensityAdapter:
    """The real, production-composed adapter under test -- no fake, no mock."""
    return TypeScriptRobustnessDensityAdapter()


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# --- positive: genuine scan, not a silent fall-through ------------------------


def test_covered_domain_ids_scans_real_domain_comments_in_ts_files(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """Two distinct `# domain:` markers across two `.ts` files are both found."""
    _write(
        tmp_path / "alpha.spec.ts",
        "# domain: alpha-input-shape\ntest('alpha', () => {});\n",
    )
    _write(
        tmp_path / "nested" / "beta.spec.ts",
        "test('beta', () => {\n  # domain: beta-input-shape\n});\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"alpha-input-shape", "beta-input-shape"}, (
        "covered_domain_ids must genuinely scan the *.ts tree and collect "
        "every '# domain: <id>' marker -- exactly matching "
        "PythonRobustnessDensityAdapter's scan semantics, TS-glob-scoped -- "
        f"but today the method is a NotImplementedError stub. Got: {covered!r}"
    )


def test_covered_domain_ids_scans_domain_comments_in_tsx_files(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """`.tsx` files are scanned too -- not just `.ts`."""
    _write(
        tmp_path / "Widget.spec.tsx",
        "# domain: widget-render-shape\nexport const Widget = () => <div />;\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"widget-render-shape"}, (
        "the glob must cover *.tsx (not only *.ts) -- a marker in a .tsx "
        f"file must be discovered. Got: {covered!r}"
    )


def test_covered_domain_ids_dedupes_the_same_domain_across_ts_and_tsx(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """The same domain id declared in a `.ts` and a `.tsx` file dedupes to one."""
    _write(tmp_path / "one.spec.ts", "# domain: shared-domain\n")
    _write(tmp_path / "two.spec.tsx", "# domain: shared-domain\n")

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"shared-domain"}, (
        "a domain id repeated across .ts and .tsx files must dedupe to one "
        f"set entry (set semantics). Got: {covered!r}"
    )


def test_covered_domain_ids_recurses_into_subdirectories(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """`rglob`, not a shallow glob -- a nested-directory marker is found too."""
    _write(
        tmp_path / "deep" / "deeper" / "nested.spec.ts",
        "# domain: deeply-nested-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"deeply-nested-domain"}, (
        "the scan must recurse into subdirectories (rglob, not a shallow "
        f"glob) for both *.ts and *.tsx. Got: {covered!r}"
    )


# --- boundary: exact `# domain:` prefix, not a loose match --------------------


def test_covered_domain_ids_requires_the_exact_marker_prefix(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """Only the literal `# domain:` prefix counts; near-miss variants do not."""
    _write(
        tmp_path / "near_misses.spec.ts",
        "#domain: no-space-after-hash\n"
        "# Domain: wrong-case\n"
        "#  domain: extra-space-after-hash\n"
        "# domain-marker: not-the-real-prefix\n"
        "// domain: ts-native-comment-not-the-marker\n"
        "# domain: genuine-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"genuine-domain"}, (
        "only lines whose STRIPPED form starts with the exact literal "
        "'# domain:' count -- '#domain:' (no space), '# Domain:' (wrong "
        "case), '#  domain:' (extra space), '# domain-marker:' and a "
        "TS-native '// domain:' comment must all be ignored, matching "
        f"str.startswith('# domain:'). Got: {covered!r}"
    )


# --- negative ATs: scope leakage / empty marker must NOT fabricate coverage ---


@pytest.mark.negative_at
def test_covered_domain_ids_rejects_python_files_in_a_typescript_scope(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """A `.py` file bearing a `# domain:` marker is IGNORED -- TS-glob-scoped."""
    _write(tmp_path / "leaked.py", "# domain: should-be-ignored-python-file\n")
    _write(tmp_path / "genuine.spec.ts", "# domain: genuinely-typescript\n")

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == {"genuinely-typescript"}, (
        "the glob is *.ts/*.tsx-scoped; a marker sitting in a .py (or any "
        "non-TS) file must never contribute a domain id -- only the TS "
        f"file's marker should appear. Got: {covered!r}"
    )


def test_covered_domain_ids_rejects_a_scope_with_no_domain_comments(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """A `.ts`-bearing scope with zero `# domain:` markers returns EMPTY --

    never an error, and never a spurious/fabricated domain id.
    """
    _write(
        tmp_path / "plain.spec.ts",
        "test('plain', () => { expect(true).toBe(true); });\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert covered == set(), (
        "a scope with *.ts files but zero '# domain:' markers must return "
        f"an EMPTY set, not raise and not fabricate a domain id. Got: {covered!r}"
    )


@pytest.mark.negative_at
def test_covered_domain_ids_never_records_an_empty_marker_as_a_domain_id(
    adapter: TypeScriptRobustnessDensityAdapter, tmp_path: Path
) -> None:
    """`# domain:` with nothing (or only whitespace) after it is NOT a domain id."""
    _write(
        tmp_path / "empty_marker.spec.ts",
        "# domain:\n# domain:   \n# domain: real-domain\n",
    )

    covered = adapter.covered_domain_ids(tmp_path)

    assert "" not in covered, (
        "an empty (or whitespace-only) marker after '# domain:' must NEVER "
        f"be recorded as a domain id -- the `if marker:` guard must be "
        f"replicated. Got: {covered!r}"
    )
    assert covered == {"real-domain"}, (
        "only the genuinely-populated marker line contributes; the two "
        f"empty-marker lines contribute nothing. Got: {covered!r}"
    )
