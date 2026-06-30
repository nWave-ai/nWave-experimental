"""Filesystem adapter for the product-SSOT presence reader (slice-07).

Implements ``ProductSsotReader`` over the DESIGN-PINNED product-SSOT layout
``{project_root}/docs/product/{vision,backlog,glossary}.md`` plus the structured
``docs/product/jobs.yaml`` JOB registry (git-free, Python stdlib only). The PATH
layout is the design-owned contract (one SSOT shared with the AT-seed); only the
read MECHANICS are this adapter's choice.

degrade-LOUD (§17): a project root whose read mechanism fails yields
``SsotPresence(indeterminate=True, ...)`` -- NEVER a fabricated all-present.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from des.ports.driven_ports.product_ssot_reader import ProductSsotReader, SsotPresence


if TYPE_CHECKING:
    from pathlib import Path


# DESIGN-PINNED product-SSOT layout (§8 gate-IN precondition): docs/product/ is
# the migration-gate; the four required SSOT docs live directly under it.
_PRODUCT_REL_DIR = ("docs", "product")
_REQUIRED_DOCS = ("vision.md", "backlog.md", "glossary.md", "jobs.yaml")


def _product_dir(project_root: Path) -> Path:
    return project_root.joinpath(*_PRODUCT_REL_DIR)


class ProductSsotFilesystemReader(ProductSsotReader):
    """Reads the product-SSOT presence off the pinned docs/product/ layout."""

    def ssot_present(self, project_root: Path) -> SsotPresence:
        """Read the product-SSOT presence (degrade-LOUD on read-mechanism failure)."""
        product_dir = _product_dir(project_root)
        try:
            product_dir_present = product_dir.is_dir()
            if not product_dir_present:
                return SsotPresence(
                    product_dir_present=False,
                    vision=False,
                    backlog=False,
                    glossary=False,
                    jobs=False,
                )
            present = {doc: (product_dir / doc).is_file() for doc in _REQUIRED_DOCS}
        except OSError:
            return SsotPresence(
                product_dir_present=False,
                vision=False,
                backlog=False,
                glossary=False,
                jobs=False,
                indeterminate=True,
            )
        return SsotPresence(
            product_dir_present=True,
            vision=present["vision.md"],
            backlog=present["backlog.md"],
            glossary=present["glossary.md"],
            jobs=present["jobs.yaml"],
        )

    def probe(self, project_root: Path) -> None:
        """Earned-trust probe (principle 13): all-present, one-missing, absent-root.

        Writes fixtures to a probe subdirectory, reads back, asserts presence
        fidelity (no fabricated all-present masking absence). A failed probe
        refuses startup with ``health.startup.refused``.
        """
        probe_root = project_root / ".nwave" / "discuss-gate" / "_probe_ssot"
        product_dir = _product_dir(probe_root)
        try:
            product_dir.mkdir(parents=True, exist_ok=True)
            for doc in _REQUIRED_DOCS:
                (product_dir / doc).write_text(f"# {doc}\n", encoding="utf-8")
            all_present = self.ssot_present(probe_root)
            if not (
                all_present.product_dir_present
                and not all_present.missing_docs()
                and not all_present.indeterminate
            ):
                raise RuntimeError(
                    "health.startup.refused: product-SSOT probe did not read back "
                    f"all-present (got {all_present!r})"
                )
            (product_dir / "vision.md").unlink()
            one_missing = self.ssot_present(probe_root)
            if one_missing.missing_docs() != ("vision.md",):
                raise RuntimeError(
                    "health.startup.refused: product-SSOT probe did not detect the "
                    f"removed doc (got missing={one_missing.missing_docs()!r})"
                )
            absent = self.ssot_present(probe_root / "nonexistent")
            if absent.product_dir_present:
                raise RuntimeError(
                    "health.startup.refused: product-SSOT probe fabricated presence "
                    "for an absent root"
                )
        finally:
            self._cleanup_probe(probe_root)

    @staticmethod
    def _cleanup_probe(probe_root: Path) -> None:
        import shutil

        shutil.rmtree(probe_root, ignore_errors=True)
