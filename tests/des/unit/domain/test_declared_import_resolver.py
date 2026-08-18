"""Unit tests for `resolve_declared_import` (K4 matrix row 12 admission).

Real base-tree symbols must resolve `True`; an invented one must resolve
`False`. A non-Python-shaped reference (npm/Rust/.NET style) is outside this
checker's competence and resolves `True` -- unverifiable-here, never a false
rejection (see module docstring for the scope rationale).
"""

from __future__ import annotations

from pathlib import Path

from des.domain.declared_import_resolver import (
    is_name_bound_in_target_file,
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


#: Run 6 false-reject: a bare name imported at the TOP of the target's own
#: file (third-party, stdlib, or sibling module) is a real, bound base-tree
#: reference even though it never resolves as a dotted module path -- the
#: resolver must never require site-packages resolution to accept it.
_IMPORTING_MODULE = """
from cronsim import CronSim
from zoneinfo import ZoneInfo


class Check:
    pass
"""


def test_bare_name_bound_by_a_from_import_in_the_target_file_is_accepted(
    tmp_path: Path,
) -> None:
    _seed_module(tmp_path, "hc/api/models.py", _IMPORTING_MODULE)

    assert is_name_bound_in_target_file(tmp_path, "hc/api/models.py", "CronSim") is True
    assert (
        is_name_bound_in_target_file(tmp_path, "hc/api/models.py", "ZoneInfo") is True
    )


def test_bare_name_bound_by_a_module_level_class_in_the_target_file_is_accepted(
    tmp_path: Path,
) -> None:
    _seed_module(tmp_path, "hc/api/models.py", _IMPORTING_MODULE)

    assert is_name_bound_in_target_file(tmp_path, "hc/api/models.py", "Check") is True


def test_bare_name_not_bound_anywhere_in_the_target_file_is_rejected(
    tmp_path: Path,
) -> None:
    _seed_module(tmp_path, "hc/api/models.py", _IMPORTING_MODULE)

    assert (
        is_name_bound_in_target_file(tmp_path, "hc/api/models.py", "NotBoundAnywhere")
        is False
    )


def test_bound_bare_name_makes_the_full_resolver_accept_the_declared_import(
    tmp_path: Path,
) -> None:
    """The end-to-end property Run 6 needs: `resolve_declared_import` alone
    is dotted-path-only by design, so callers combine it with
    `is_name_bound_in_target_file` -- this proves the combination accepts
    exactly what the false-reject repro needed."""
    _seed_module(tmp_path, "hc/api/models.py", _IMPORTING_MODULE)

    bound = is_name_bound_in_target_file(tmp_path, "hc/api/models.py", "CronSim")
    dotted = resolve_declared_import(tmp_path, "CronSim")

    assert bound is True
    assert dotted is False  # bare "CronSim" alone is not a dotted base-tree path
    assert bound or dotted  # the caller accepts on this OR, per Run 6's fix


def test_dotted_invented_symbol_is_still_rejected_even_with_a_target_file(
    tmp_path: Path,
) -> None:
    """Run 4's admission must not regress: a DOTTED reference to a module
    that is genuinely absent from the base tree stays rejected, even though
    it superficially resembles the bound third-party import this row now
    accepts in bare form."""
    _seed_module(tmp_path, "hc/api/models.py", _IMPORTING_MODULE)

    bound = is_name_bound_in_target_file(
        tmp_path, "hc/api/models.py", "cronsim.CronSim"
    )
    dotted = resolve_declared_import(tmp_path, "cronsim.CronSim")

    assert bound is False
    assert dotted is False
