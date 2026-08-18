"""Arch test -- ADR-LA-001 D6-R7: `des find-similar-responsibility` routes
THROUGH the composed `CodeFactPort`/`CodeFactChain` fold, never constructs an
`AstAdapter` directly.

R7's row: "RETARGET then delete the bypass: the fold-backed driving surface is
the same CLI routed through CodeFactPort.query [...] The direct-adapter
construction is deleted only after the fold-backed replacement passes
tests/des/unit/cli/test_find_similar_responsibility.py +
tests/bugs/des/test_find_similar_declares_unparseable_coverage.py". The
observable JSON contract those two files freeze is DELIBERATELY unchanged by
this retarget (a real-consumer black-box test cannot discriminate the
routing change) -- so the retarget itself needs a structural witness. This
is that witness: an AST-based scan of the ONE shipped module, sibling to
`test_no_inline_des_module_spawn.py`'s established arch-test pattern.

ACTIVE-RED at the start of this delivery: `find_similar_responsibility.py`
constructs `AstAdapter(root=...)` directly (the bypass R7 condemns) and never
names `CodeFactChain` at all. GREEN once DELIVER retargets it to
`CodeFactChain(root=...)`.
"""

from __future__ import annotations

import ast
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_TARGET = PROJECT_ROOT / "src" / "des" / "cli" / "find_similar_responsibility.py"


def _constructed_names(tree: ast.Module) -> set[str]:
    """Every bare-name callable constructed anywhere in ``tree`` (``Foo(...)``,
    never ``module.Foo(...)`` -- the adapters this module imports are always
    called by their bare imported name)."""
    return {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_find_similar_responsibility_never_constructs_ast_adapter_directly() -> None:
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"), filename=str(_TARGET))
    constructed = _constructed_names(tree)
    assert "AstAdapter" not in constructed, (
        "src/des/cli/find_similar_responsibility.py constructs `AstAdapter` "
        "directly -- ADR-LA-001 D6-R7 condemns this bypass. Route through the "
        "composed CodeFactChain (the SAME driving surface des code-fact uses) "
        f"instead. constructed names observed: {sorted(constructed)!r}"
    )


def test_find_similar_responsibility_constructs_the_composed_chain() -> None:
    tree = ast.parse(_TARGET.read_text(encoding="utf-8"), filename=str(_TARGET))
    constructed = _constructed_names(tree)
    assert "CodeFactChain" in constructed, (
        "src/des/cli/find_similar_responsibility.py must construct "
        "`CodeFactChain` (ADR-LA-001 D6-R7: the fold-backed driving surface) "
        f"-- no such construction found. constructed names observed: "
        f"{sorted(constructed)!r}"
    )
