"""Parity unit test — inline `_canonical_tree_hash` in `des_plugin.py`
matches `des.runtime.tree_hash.canonical_tree_hash` byte-identically.

Slice: slice-01 of `fix-installer-self-referential-des-import`.
Mode: atdd_pure carpaccio (DISTILL phase — RED scaffold per ADR-028).
ATs: AT-2 of 2 (AT-1 is the existing e2e walking skeleton at
`tests/e2e/test_pypi_shape_install_chain.py`).

RCA anchor
----------
`scripts/install/plugins/des_plugin.py:491` calls
``from des.runtime.tree_hash import canonical_tree_hash`` AT INSTALL TIME.
At PyPI-install time, `des` lives under
``site-packages/nWave/lib/python/des/`` which is NOT on ``sys.path`` →
``ModuleNotFoundError: No module named 'des'`` → installer exits with
``DES module install failed: No module named 'des'``.

DELIVER fix (A_GREEN_ATS, NOT this DISTILL phase):
  1. Inline the 13-LOC `canonical_tree_hash` definition into
     `des_plugin.py` as private ``_canonical_tree_hash``.
  2. Remove the ``from des.runtime.tree_hash import ...`` line.
  3. Replace call site ``canonical_tree_hash(...)`` with
     ``_canonical_tree_hash(...)``.

This parity test is the SSOT guard: future drift between the inlined
copy and the canonical implementation fails loudly.

Mandate-13 driving-port note
----------------------------
This test imports BOTH the inlined function (`_canonical_tree_hash` on
`DESPlugin`) AND the canonical module-level function
(`des.runtime.tree_hash.canonical_tree_hash`) and compares their
outputs. This is the explicit "parity unit" exemption to Mandate-13 —
the test's contract IS comparing two implementations, so direct import
of both is essential to the contract, not a violation. See
docs/feature/fix-installer-self-referential-des-import/distill/
at-scaffold-notes.md § "Mandate-13 driving-port justification".

RED state (current, pre-DELIVER)
--------------------------------
The test is marked ``pytest.mark.skip(reason="RED scaffold — slice-01
A_GREEN_ATS will inline _canonical_tree_hash in des_plugin.py")``.
When the skip is lifted in DELIVER but BEFORE the fix lands, the
test fails with ``AttributeError: type object 'DESPlugin' has no
attribute '_canonical_tree_hash'`` — fail-for-right-reason RED.
Post-fix, all parametrized cases PASS.

Mandate-12 step-reuse
---------------------
Parametrize over ≥3 typed fixture trees (single-file, nested-dirs,
unicode-named). One test function body, N test cases — DSL emerges
from typed fixture parameter, zero per-case duplication.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Fixture trees — three materially-distinct tree shapes covering
# C1 boundary (single file, minimal), C2/C7 nesting depth (3 levels,
# multi-file-per-dir), and C6 robustness (non-ASCII filenames).
# ---------------------------------------------------------------------------


def _build_single_file_tree(root):
    """Tree #1 — single file at root. Minimum non-empty tree."""
    (root / "module.py").write_text("def f():\n    return 1\n", encoding="utf-8")
    return root


def _build_nested_dirs_tree(root):
    """Tree #2 — 3 levels deep, multiple files per dir. Exercises rglob
    ordering + path normalization (relative POSIX path key)."""
    (root / "top.py").write_text("TOP = 1\n", encoding="utf-8")
    pkg_a = root / "pkg_a"
    pkg_a.mkdir()
    (pkg_a / "__init__.py").write_text("", encoding="utf-8")
    (pkg_a / "alpha.py").write_text("ALPHA = 'a'\n", encoding="utf-8")
    (pkg_a / "beta.py").write_text("BETA = 'b'\n", encoding="utf-8")
    pkg_b = pkg_a / "sub"
    pkg_b.mkdir()
    (pkg_b / "__init__.py").write_text("", encoding="utf-8")
    (pkg_b / "deep.py").write_text("DEEP = True\n", encoding="utf-8")
    pkg_c = pkg_b / "deeper"
    pkg_c.mkdir()
    (pkg_c / "__init__.py").write_text("", encoding="utf-8")
    (pkg_c / "leaf.py").write_text("LEAF = None\n", encoding="utf-8")
    return root


def _build_unicode_names_tree(root):
    """Tree #3 — non-ASCII filenames. Exercises UTF-8 path encoding in
    the `<rel_path>\\0<md5>\\n` line concatenation. Only `.py` files
    are hashed per the algorithm; the `.txt` and `.md` are present to
    confirm rglob filter discipline (they MUST be ignored by both
    implementations equivalently)."""
    (root / "café.py").write_text("CAFE = 'café'\n", encoding="utf-8")
    (root / "日本語.py").write_text("NIHONGO = True\n", encoding="utf-8")
    (root / "émoji-\U0001f600.py").write_text("EMOJI = 1\n", encoding="utf-8")
    # Non-.py files — both implementations must ignore these.
    (root / "café.txt").write_text("ignored\n", encoding="utf-8")
    (root / "日本語.md").write_text("# ignored\n", encoding="utf-8")
    return root


TREE_BUILDERS = {
    "single_file": _build_single_file_tree,
    "nested_dirs": _build_nested_dirs_tree,
    "unicode_names": _build_unicode_names_tree,
}


# ---------------------------------------------------------------------------
# Parity assertion — parametrized over all three trees in one body.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("tree_kind", sorted(TREE_BUILDERS.keys()))
def test_inline_canonical_tree_hash_matches_module_level(tmp_path, tree_kind):
    """Inline `_canonical_tree_hash` in des_plugin produces byte-identical
    output to the canonical `des.runtime.tree_hash.canonical_tree_hash`
    on every fixture tree.

    Drift between the two implementations fails loudly — this is the
    SSOT guard for the install-time bootstrap copy.
    """
    # Driving port (production): the DESPlugin class — the inline
    # implementation will be a static or instance method on DESPlugin
    # (decision deferred to A_GREEN_ATS; either shape satisfies the
    # parity contract). This import locates the production module
    # `scripts.install.plugins.des_plugin` and accesses the inlined
    # symbol as an attribute — fail-for-right-reason RED when the
    # symbol is absent.
    # Canonical SSOT — `des.runtime.tree_hash.canonical_tree_hash`.
    # This import IS the parity-comparison partner; importing both
    # in the test body is the explicit Mandate-13 "parity unit"
    # exemption (see module docstring).
    from des.runtime.tree_hash import canonical_tree_hash
    from scripts.install.plugins.des_plugin import DESPlugin

    # Build the fixture tree under tmp_path / tree_kind to isolate
    # the parametrize cases from one another.
    tree_root = tmp_path / tree_kind
    tree_root.mkdir()
    TREE_BUILDERS[tree_kind](tree_root)

    # Resolve the inlined function — A_GREEN_ATS decides between
    # `DESPlugin._canonical_tree_hash` (instance/staticmethod) and
    # a module-level `_canonical_tree_hash` in des_plugin. The test
    # accepts either: attribute on DESPlugin first, module-level
    # fallback. Both shapes are valid private inlinings.
    inline_fn = getattr(DESPlugin, "_canonical_tree_hash", None)
    if inline_fn is None:
        import scripts.install.plugins.des_plugin as des_plugin_mod

        inline_fn = getattr(des_plugin_mod, "_canonical_tree_hash", None)
    assert inline_fn is not None, (
        "DELIVER must inline `_canonical_tree_hash` either as a "
        "method on DESPlugin or as a module-level function in "
        "scripts.install.plugins.des_plugin. Neither found."
    )

    # If it's a method, call as unbound function (it's pure — takes
    # only tree_root). If it's a free function, call directly.
    # Both calling conventions are tolerated to keep the parity
    # contract decoupled from inlining shape.
    try:
        inline_hash = inline_fn(tree_root)
    except TypeError:
        # Method case — A_GREEN_ATS chose an instance method.
        # Construct minimal DESPlugin and bind.
        plugin = DESPlugin.__new__(DESPlugin)
        inline_hash = inline_fn(plugin, tree_root)

    canonical_hash = canonical_tree_hash(tree_root)

    # Byte-identical contract — exact string equality (both functions
    # return "sha256:<hex>" strings; any difference in algorithm,
    # sort order, line separator, or digest function diverges here).
    assert inline_hash == canonical_hash, (
        f"Parity violation on tree '{tree_kind}':\n"
        f"  inline   ({inline_fn.__qualname__}): {inline_hash}\n"
        f"  canonical (des.runtime.tree_hash):   {canonical_hash}\n"
        "Inline copy in des_plugin.py has drifted from the SSOT in "
        "src/des/runtime/tree_hash.py. Either re-sync the inline "
        "copy or update the canonical function — but never one "
        "without the other."
    )


def test_inline_canonical_tree_hash_returns_prefixed_format(tmp_path):
    """Inline implementation returns the `"sha256:<hex>"` prefix-tagged
    form. Locks the §1.6 contract independently of the SSOT comparison —
    if both implementations drift in the same direction, this catches
    it.
    """
    from scripts.install.plugins.des_plugin import DESPlugin

    tree_root = tmp_path / "single_file"
    tree_root.mkdir()
    _build_single_file_tree(tree_root)

    inline_fn = getattr(DESPlugin, "_canonical_tree_hash", None)
    if inline_fn is None:
        import scripts.install.plugins.des_plugin as des_plugin_mod

        inline_fn = getattr(des_plugin_mod, "_canonical_tree_hash", None)
    assert inline_fn is not None

    try:
        result = inline_fn(tree_root)
    except TypeError:
        plugin = DESPlugin.__new__(DESPlugin)
        result = inline_fn(plugin, tree_root)

    assert isinstance(result, str)
    assert result.startswith("sha256:"), (
        f"Inline `_canonical_tree_hash` returned {result!r}; "
        "expected `sha256:<hex>` prefix-tagged form per §1.6."
    )
    # Hex digest after the prefix is 64 chars (SHA-256).
    digest = result.split(":", 1)[1]
    assert len(digest) == 64
    int(digest, 16)  # raises ValueError if not hex


# ---------------------------------------------------------------------------
# Config-asset envelope parity (M1 slice-05, SYS-4 / AD-27).
#
# The bootstrap inline `_canonical_config_assets_hash` in des_plugin.py is the
# second install-time copy under the same bootstrap-self exemption: it cannot
# import `des.runtime.tree_hash.canonical_config_assets_hash` at install time
# (the `des` package is off `sys.path` during PyPI install). These cases lock
# byte-identical parity between the inline copy and the canonical SSOT over the
# shipped config glob (`*.yaml` / `*.yml` / `*.json`), mirroring the `*.py`
# tree-hash parity above. Drift between the two implementations fails loudly.
# ---------------------------------------------------------------------------


def _build_single_config_tree(root):
    """Config tree #1 — single yaml at root. Minimum non-empty asset tree."""
    (root / "flavor.yaml").write_text("flavor_id: atdd_pure\n", encoding="utf-8")
    return root


def _build_mixed_suffix_config_tree(root):
    """Config tree #2 — nested dirs spanning all three config suffixes plus
    non-config siblings that BOTH implementations must ignore (`.py`, `.txt`)."""
    (root / "catalog.yaml").write_text("a: 1\n", encoding="utf-8")
    (root / "manifest.json").write_text('{"b": 2}\n', encoding="utf-8")
    flavors = root / "flavors"
    flavors.mkdir()
    (flavors / "classic.yml").write_text("flavor_id: classic\n", encoding="utf-8")
    (flavors / "atdd_pure.yaml").write_text("flavor_id: atdd_pure\n", encoding="utf-8")
    data = flavors / "data"
    data.mkdir()
    (data / "ports.json").write_text('{"ports": []}\n', encoding="utf-8")
    # Non-config siblings — both implementations must ignore these.
    (root / "module.py").write_text("X = 1\n", encoding="utf-8")
    (flavors / "README.txt").write_text("ignored\n", encoding="utf-8")
    return root


def _build_unicode_config_tree(root):
    """Config tree #3 — non-ASCII config filenames. Exercises UTF-8 path
    encoding in the `<rel_path>\\0<md5>\\n` concatenation for the config glob."""
    (root / "café.yaml").write_text("k: café\n", encoding="utf-8")
    (root / "日本語.json").write_text('{"k": "v"}\n', encoding="utf-8")
    return root


CONFIG_TREE_BUILDERS = {
    "single_config": _build_single_config_tree,
    "mixed_suffixes": _build_mixed_suffix_config_tree,
    "unicode_config": _build_unicode_config_tree,
}


@pytest.mark.parametrize("tree_kind", sorted(CONFIG_TREE_BUILDERS.keys()))
def test_inline_canonical_config_assets_hash_matches_module_level(tmp_path, tree_kind):
    """Inline `_canonical_config_assets_hash` in des_plugin produces
    byte-identical output to the canonical
    `des.runtime.tree_hash.canonical_config_assets_hash` on every config tree.

    Drift between the two implementations fails loudly — the SSOT guard for the
    install-time config-asset bootstrap copy (SYS-4 / AD-27).
    """
    # Canonical SSOT — the parity-comparison partner (Mandate-13 "parity unit"
    # exemption, identical justification to the tree-hash case above).
    from des.runtime.tree_hash import canonical_config_assets_hash
    from scripts.install.plugins.des_plugin import DESPlugin

    assets_root = tmp_path / tree_kind
    assets_root.mkdir()
    CONFIG_TREE_BUILDERS[tree_kind](assets_root)

    inline_fn = getattr(DESPlugin, "_canonical_config_assets_hash", None)
    if inline_fn is None:
        import scripts.install.plugins.des_plugin as des_plugin_mod

        inline_fn = getattr(des_plugin_mod, "_canonical_config_assets_hash", None)
    assert inline_fn is not None, (
        "Install-time bootstrap must inline `_canonical_config_assets_hash` "
        "either as a method on DESPlugin or as a module-level function in "
        "scripts.install.plugins.des_plugin. Neither found."
    )

    try:
        inline_hash = inline_fn(assets_root)
    except TypeError:
        plugin = DESPlugin.__new__(DESPlugin)
        inline_hash = inline_fn(plugin, assets_root)

    canonical_hash = canonical_config_assets_hash(assets_root)

    assert inline_hash == canonical_hash, (
        f"Config-asset parity violation on tree '{tree_kind}':\n"
        f"  inline   ({inline_fn.__qualname__}): {inline_hash}\n"
        f"  canonical (des.runtime.tree_hash):   {canonical_hash}\n"
        "Inline copy in des_plugin.py has drifted from the SSOT in "
        "src/des/runtime/tree_hash.py. Re-sync the inline copy or update "
        "the canonical function — but never one without the other."
    )
