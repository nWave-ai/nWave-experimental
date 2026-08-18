"""Unit tests for `resolve_declared_import` (K4 matrix row 12 admission).

Real base-tree symbols must resolve `True`; an invented one must resolve
`False`. A non-Python-shaped reference (npm/Rust/.NET style) is outside this
checker's competence and resolves `True` -- unverifiable-here, never a false
rejection (see module docstring for the scope rationale).
"""

from __future__ import annotations

from pathlib import Path

from des.domain.declared_import_resolver import (
    resolve_declared_import,
    unresolved_declared_import_owner,
)


REPO_ROOT = Path(__file__).resolve().parents[4]


def test_whole_module_reference_resolves() -> None:
    assert resolve_declared_import(REPO_ROOT, "des.domain.repo_path_resolver") is True


def test_module_level_function_reference_resolves() -> None:
    assert (
        resolve_declared_import(
            REPO_ROOT, "des.domain.repo_path_resolver.resolve_repo_root"
        )
        is True
    )


def test_nonexistent_module_is_rejected() -> None:
    assert (
        resolve_declared_import(REPO_ROOT, "des.domain.this_module_does_not_exist_zzz")
        is False
    )


def test_nonexistent_symbol_in_real_module_is_rejected() -> None:
    assert (
        resolve_declared_import(
            REPO_ROOT,
            "des.domain.repo_path_resolver.this_symbol_does_not_exist_zzz",
        )
        is False
    )


def test_non_python_shaped_reference_is_out_of_scope() -> None:
    assert resolve_declared_import(REPO_ROOT, "crate::module") is True
    assert resolve_declared_import(REPO_ROOT, "@scope/pkg") is True


#: Reviewer-reproduced false-reject: a 1-level module attribute resolved
#: True, a 2-level nested-class attribute chain resolved False even though
#: the symbol is real (declared_import_resolver.py only checked the
#: module's own top-level defs/classes, never descended into a class body).
_NESTED_CLASS_MODULE = """
class Outer:
    class Inner:
        CONST = 1

        def method(self):
            return self.CONST
"""


def _seed_module(tmp_path: Path, relative: str, source: str) -> None:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source, encoding="utf-8")


def test_nested_class_reference_resolves(tmp_path: Path) -> None:
    _seed_module(tmp_path, "mypkg.py", _NESTED_CLASS_MODULE)

    assert resolve_declared_import(tmp_path, "mypkg.Outer.Inner") is True


def test_nested_class_attribute_reference_resolves(tmp_path: Path) -> None:
    _seed_module(tmp_path, "mypkg.py", _NESTED_CLASS_MODULE)

    assert resolve_declared_import(tmp_path, "mypkg.Outer.Inner.CONST") is True


def test_nested_class_missing_member_is_rejected(tmp_path: Path) -> None:
    _seed_module(tmp_path, "mypkg.py", _NESTED_CLASS_MODULE)

    assert resolve_declared_import(tmp_path, "mypkg.Outer.NotThere") is False


def test_package_init_symbol_resolves(tmp_path: Path) -> None:
    _seed_module(tmp_path, "widgets/__init__.py", "WIDGET = 1\n")

    assert resolve_declared_import(tmp_path, "widgets.WIDGET") is True


def test_attribute_access_beyond_a_leaf_is_not_decidable_and_not_rejected(
    tmp_path: Path,
) -> None:
    """`CONST` is a plain class-level assignment (a leaf, not a class), so a
    further `.sub_attr` on it cannot be decided from static structure alone
    -- a validator must never false-reject; not-decidable resolves True."""
    _seed_module(tmp_path, "mypkg.py", _NESTED_CLASS_MODULE)

    assert resolve_declared_import(tmp_path, "mypkg.Outer.Inner.CONST.sub_attr") is True


#: Run 4 defect B: a declared-import citing a symbol that the SAME
#: DeliveryContract's own target creates (self-reference) -- the symbol
#: does not exist YET at the base revision, but its owning module DOES
#: (this delivery is going to add the symbol to it).
def test_owner_of_an_unresolved_symbol_in_an_existing_module_is_reported(
    tmp_path: Path,
) -> None:
    _seed_module(tmp_path, "mypkg.py", _NESTED_CLASS_MODULE)

    owner = unresolved_declared_import_owner(tmp_path, "mypkg.NotThere")

    assert owner == "mypkg.py"


def test_owner_is_none_when_the_module_does_not_exist_anywhere() -> None:
    owner = unresolved_declared_import_owner(
        Path(__file__).resolve().parents[4], "cronsim.CronSim"
    )

    assert owner is None


def test_owner_is_none_for_a_non_python_shaped_reference() -> None:
    owner = unresolved_declared_import_owner(
        Path(__file__).resolve().parents[4], "crate::module"
    )

    assert owner is None
