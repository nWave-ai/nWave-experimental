"""RED regression -- `TextSearchAdapter` language floor law (against ea1038976).

Charter clause under test (ADR-LA-001 tier-3 floor, `text_search_code_fact_adapter.py`
module docstring): the floor is "language-agnostic" and answers ``never-wired``
textually for every atom `_ATOM_DEFINITION` claims to recognize as a declaration --
``def``/``class``/``func``/``fn``/``function``, with optional ``export``/``async``
prefixes.

Floor law (one definition observation must never be interpreted as a call-site,
`lyra-algebraic-design-protocol` / `lyra-property-driven-design`): a symbol S
declared exactly once, with no textual use anywhere else in the tree, MUST answer
``never_wired=True`` with zero ``call_sites`` -- the declaration line itself is not
a call site.

`_call_sites`'s own definition-stripping regex (`text_search_code_fact_adapter.py`
``definition_pattern = re.compile(rf"^\\s*(?:def|class|func|fn)\\s+{name}\b", ...)``)
recognizes only the BARE ``def``/``class``/``func``/``fn`` keywords anchored at the
start of the line. It does NOT recognize a JS/TS ``function`` keyword (``func\\s+``
cannot match inside ``function foo`` -- the char after ``func`` is ``t``, not
whitespace) and does NOT recognize an ``export``/``async`` prefix pushing the real
keyword off the line start (``^\\s*(?:def|class|func|fn)`` never matches a line
starting with ``export`` or ``async``). `_ATOM_DEFINITION` DOES claim these forms
as atoms (its own alternation includes ``function`` and the ``export``/``async``
prefixes) -- so the atom-recognition law and the call-site-stripping law have
silently drifted apart: a bare JS/TS declaration line self-matches the CALL pattern
(``name\\s*\\(`` right after the keyword) and is never stripped, so the adapter counts
the declaration against itself as a "call site" and reports ``never_wired=False``.

Generates and writes REAL source text per language form and invokes the real public
`CodeFactPort.query` surface -- never a regex-shape assertion on production code.
"""

from __future__ import annotations

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.adapters.driven.codefact.code_fact_chain import CodeFactChain
from des.adapters.driven.codefact.text_search_code_fact_adapter import (
    TextSearchAdapter,
)
from des.ports.code_fact_port import (
    CAPABILITY_ATOMS_IN_FILE,
    CAPABILITY_NEVER_WIRED,
    CapabilityDescriptor,
    Confidence,
    Provider,
)


# The public non-Python declaration forms `_ATOM_DEFINITION` claims to recognize
# (its alternation: `(?:export\s+)?(?:async\s+)?(?:def|class|func|fn|function)\s+`).
# Each maps to (filename, source-template) so the generated file is REAL,
# parseable-looking JS/TS -- not a synthetic regex probe.
_DECLARATION_FORMS: dict[str, tuple[str, str]] = {
    "function": (
        "declared.js",
        "function {name}() {{\n    return 1;\n}}\n",
    ),
    "async function": (
        "declared.ts",
        "async function {name}() {{\n    return Promise.resolve(1);\n}}\n",
    ),
    "export class": (
        "declared.ts",
        "export class {name} {{\n    method() {{\n        return 1;\n    }}\n}}\n",
    ),
}

# Reserved words that must never collide with the generated symbol name --
# a name equal to a language keyword used inside the templates would make
# the fixture itself ambiguous, not the property under test.
_RESERVED = {
    "class",
    "def",
    "async",
    "await",
    "export",
    "function",
    "func",
    "fn",
    "return",
    "method",
    "promise",
}

_SYMBOL_NAME = st.from_regex(r"[A-Za-z_][A-Za-z0-9_]{2,20}", fullmatch=True).filter(
    lambda name: name.lower() not in _RESERVED
)


def _never_wired_descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CAPABILITY_NEVER_WIRED,
        stability="stable",
        contract_version="1.0.0",
        io_schema="never-wired",
        providing_adapter="test-text-search-language-floor",
    )


def _atoms_descriptor() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        id=CAPABILITY_ATOMS_IN_FILE,
        stability="stable",
        contract_version="1.0.0",
        io_schema="atoms-in-file/1",
        providing_adapter="test-text-search-language-floor",
    )


@given(form=st.sampled_from(sorted(_DECLARATION_FORMS)), name=_SYMBOL_NAME)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_supported_js_ts_declaration_produces_exact_atom(
    tmp_path_factory, form: str, name: str
) -> None:
    """CONTRACT_SHAPE: bounded-change

    Every supported real JS/TS declaration denotes exactly its public atom.
    """
    root = tmp_path_factory.mktemp("text-search-atoms")
    filename, template = _DECLARATION_FORMS[form]
    (root / filename).write_text(template.format(name=name), encoding="utf-8")

    result = TextSearchAdapter(root=root).query(_atoms_descriptor(), {})

    assert result.payload == {"atoms": [name]}, (
        f"{form!r} declaration of {name!r} must produce exactly that atom; "
        f"got payload={result.payload!r}"
    )


def test_mixed_python_typescript_tree_routes_to_text_floor_with_exact_atoms(
    tmp_path,
) -> None:
    """CONTRACT_SHAPE: bounded-change

    A subject-free mixed-tree query preserves atoms from both languages.
    """
    (tmp_path / "worker.py").write_text(
        "def python_task():\n    pass\n", encoding="utf-8"
    )
    (tmp_path / "worker.ts").write_text(
        "export function tsTask(): void {}\nexport class TsWorker {}\n",
        encoding="utf-8",
    )

    result = CodeFactChain(root=tmp_path).query(_atoms_descriptor(), {})

    assert result is not None
    assert result.provider == Provider.TEXTSEARCH.value
    assert result.confidence == Confidence.NOISY.value
    assert result.payload == {"atoms": ["TsWorker", "python_task", "tsTask"]}


@given(form=st.sampled_from(sorted(_DECLARATION_FORMS)), name=_SYMBOL_NAME)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_declaration_with_no_use_elsewhere_is_never_wired_with_zero_call_sites(
    tmp_path_factory, form: str, name: str
) -> None:
    root = tmp_path_factory.mktemp("text-search-floor")
    filename, template = _DECLARATION_FORMS[form]
    (root / filename).write_text(template.format(name=name), encoding="utf-8")

    adapter = TextSearchAdapter(root=root)
    result = adapter.query(_never_wired_descriptor(), {"symbol": name})

    assert result.payload["never_wired"] is True, (
        f"{form!r} declaration of {name!r} with no use anywhere else in the "
        f"tree must be never_wired=True (the declaration is not a call site); "
        f"got payload={result.payload!r}"
    )
    assert result.payload["call_sites"] == [], (
        f"{form!r} declaration of {name!r} must report zero call_sites; "
        f"got {result.payload['call_sites']!r}"
    )


# The real call EXPRESSION each `_DECLARATION_FORMS` form implies -- keyed by
# the same form names, reusing that table for the declaration half so the two
# properties share one generator/vocabulary instead of a second, independently
# drifting source-fixture table. A class is invoked via `new`; a (possibly
# `async`) function is called bare -- both are real, parseable-looking JS/TS.
_CALL_EXPRESSION: dict[str, str] = {
    "function": "{name}()",
    "async function": "{name}()",
    "export class": "new {name}()",
}


@given(form=st.sampled_from(sorted(_DECLARATION_FORMS)), name=_SYMBOL_NAME)
@settings(max_examples=30, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_declaration_with_one_real_call_same_file_is_wired_with_one_call_site(
    tmp_path_factory, form: str, name: str
) -> None:
    """Complement of the zero-call-sites property above: a symbol declared once
    AND called exactly once, on a separate line of the SAME source file, must
    be reported wired -- and the single call_site must identify the CALL line,
    never the declaration line (the exact drift `a57ef58e0` fixed: a
    declaration must not count against itself, and a real call must not go
    missing either). Declaration and call share one file -- not two -- so
    `_strip_own_declaration` actually processes a text containing both; an
    over-stripping regression eating past the declaration span would surface
    here as a lost or misattributed call_site. It cannot when the two live in
    separate files, since each file is stripped independently."""
    root = tmp_path_factory.mktemp("text-search-floor-wired")
    filename, declaration_template = _DECLARATION_FORMS[form]
    call_statement = _CALL_EXPRESSION[form].format(name=name)
    declaration_source = declaration_template.format(name=name)
    content = f"{declaration_source}{call_statement};\n"
    (root / filename).write_text(content, encoding="utf-8")

    adapter = TextSearchAdapter(root=root)
    result = adapter.query(_never_wired_descriptor(), {"symbol": name})

    assert result.payload["never_wired"] is False, (
        f"{form!r} declaration of {name!r} plus one real call on a separate "
        f"line of the SAME file must be never_wired=False; "
        f"got payload={result.payload!r}"
    )
    call_sites = result.payload["call_sites"]
    assert len(call_sites) == 1, (
        f"{form!r} declaration of {name!r} plus exactly one real call must "
        f"report exactly one call_site -- never zero (the real call must not "
        f"be missed) and never more than one (the declaration must not count "
        f"against itself); got {call_sites!r}"
    )

    # The expected call_site, derived only from OUR OWN authored fixture text
    # (never from the production regex): the declaration keyword phrase is
    # exactly the literal text preceding the `{name}` placeholder in the
    # template we wrote, so slicing that many leading characters off leaves
    # the text the call scan actually searches. The real call is always the
    # LAST `name(` occurrence in that remainder (it is the last thing written
    # to the file), which is what distinguishes it from the declaration line,
    # never picking a `name(` reflected in that line.
    declaration_head = declaration_template.split("{name}", 1)[0]
    declaration_span_length = len(declaration_head) + len(name)
    text_after_declaration = content[declaration_span_length:]
    expected_offset = text_after_declaration.rindex(f"{name}(")
    expected_call_site = f"{root / filename}:{expected_offset}"

    assert call_sites == [expected_call_site], (
        f"the single call_site for {form!r} declaration of {name!r} must "
        f"identify the CALL line, never the declaration line; expected "
        f"{expected_call_site!r}, got call_sites={call_sites!r}"
    )
