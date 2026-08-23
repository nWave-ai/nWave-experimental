"""GENERATED-region projection -- the ONE engine that re-renders the
marker-delimited generated regions nWave assets carry.

Marker grammar (DESIGN SSOT, analysis 2.3.2):
    <!-- GENERATED:<region-id> START ... --> body <!-- GENERATED:<region-id> END -->
Each marker NAMES its source; assets carry projections only, never hand-edits.

WHY this lives in ``des`` and not in ``scripts/docgen.py``
----------------------------------------------------------
Two tiers consume this engine and only ONE of them ships:

* ``scripts/docgen.py`` is deliberately dev-only -- absent from
  ``scripts/build_dist.UTILITY_SCRIPTS`` and from both wheel force-include maps
  (``scripts/release/patch_pyproject.py``), a fact its own module header states.
* ``scripts/install/project_claude_section.py`` DOES ship, and renders the
  ``communication-rules`` region at install time against the TARGET project's
  merged config.

While the engine lived in ``docgen``, the shipping module imported the
non-shipping one, so ``nwave-ai install`` died with
``ModuleNotFoundError: No module named 'scripts.docgen'`` in every consumer
venv (claude-code / copilot / opencode / all-target, plus native
install+uninstall). ``des/`` is staged into every wheel BY CONSTRUCTION
(``patch_pyproject.py`` force-include ``"lib/python/des" = "des"``), so a
shipping caller of this module cannot be packaged without it: there is no
whitelist to keep in sync, and the packaging-tier mismatch is therefore
unrepresentable rather than merely guarded.

Renderer ownership is split along the SAME tier line. ``INSTALLABLE_RENDERERS``
holds only regions renderable from an installed layout (today:
``communication-rules``, whose inputs are the merged config files, always
present). Dev-only regions -- whose inputs are build-time registries that never
ship (``nWave/data/role-skill-loading.yaml``) or the dev ``src/`` tree -- are
registered by ``docgen`` in its own dispatcher. A shipped asset carrying a
dev-only region therefore fails LOUD at install time instead of rendering
something false.

Stdlib only, plus one deferred intra-``des`` import of the config adapter.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


GENERATED_REGION_RE = re.compile(
    r"<!--\s*GENERATED:(?P<region_id>[a-z][a-z0-9-]*)\s+START[^>]*-->\n"
    r"(?P<body>.*?)"
    r"<!--\s*GENERATED:(?P=region_id)\s+END\s*-->",
    re.DOTALL,
)

#: A region's marker DECLARES where its body comes from; a marker naming a source
#: that did not produce the body is a false fact shipped inside generated prose,
#: so each region names its own source instead of inheriting a default.
REGION_SOURCE_OF_TRUTH: dict[str, str] = {
    "des-command-catalog": "src/des/cli/__main__.py::_REGISTRY",
    "role-skill-loading": "role-skill-loading.yaml (build-time registry, not shipped)",
    "communication-rules": (
        "des.adapters.driven.config.des_config.DESConfig.effective_config() "
        "(ADR-CFG-001 Slice 2 -- ~/.nwave/config.json + .nwave/config.json)"
    ),
}

#: ``(region_id, asset_path, root) -> body``.
RegionRenderer = Callable[[str, Path, Path], str]


class GeneratedRegionError(Exception):
    """Raised when a GENERATED region cannot be rendered honestly."""


@dataclass(frozen=True)
class AssetProjection:
    """One asset's re-rendered GENERATED-region state vs what is on disk."""

    path: Path
    current_text: str
    projected_text: str

    @property
    def stale(self) -> bool:
        return self.current_text != self.projected_text


def generated_region(region_id: str, body: str) -> str:
    """The canonical full region text (markers + body) this engine owns."""
    source = REGION_SOURCE_OF_TRUTH.get(region_id)
    if source is None:
        raise GeneratedRegionError(
            f"Unknown GENERATED region id '{region_id}' -- refusing to serve "
            "a region with no declared source"
        )
    return (
        f"<!-- GENERATED:{region_id} START — source of truth: "
        f"{source}; do not hand-edit (docgen renders this region) -->\n"
        f"{body}\n"
        f"<!-- GENERATED:{region_id} END -->"
    )


def communication_rules_body(root: Path) -> str:
    """Render the ``communication-rules`` region body from the merged config
    (ADR-CFG-001 Slice 2): a verbosity edit in ``~/.nwave/config.json`` or
    ``<root>/.nwave/config.json`` is honoured by every installed surface
    carrying this region after reinstall.

    Reuses ``DESConfig.effective_config()`` (which itself reuses
    ``merge_config``) rather than re-deriving the cascade here
    (REUSE_CANDIDATE). The adapter import is deferred so importing this module
    stays cheap and side-effect-free for callers that never render this region.
    """
    from des.adapters.driven.config.des_config import DESConfig

    global_config_path = Path.home() / ".nwave" / "config.json"
    config = DESConfig(cwd=root, global_config_path=global_config_path)
    effective = config.effective_config()
    return f"- Communication verbosity: **{effective['verbosity']}**"


#: Regions renderable from an INSTALLED layout -- every input is present on a
#: consumer machine. Adding a row here is a decision to ship that region's
#: inputs too; a region whose inputs are dev/build-time-only belongs in
#: ``docgen``'s dispatcher instead.
INSTALLABLE_RENDERERS: dict[str, Callable[[Path], str]] = {
    "communication-rules": communication_rules_body,
}


def render_installable_region_body(region_id: str, asset_path: Path, root: Path) -> str:
    """Default renderer: the installable region set only, failing LOUD otherwise."""
    renderer = INSTALLABLE_RENDERERS.get(region_id)
    if renderer is None:
        raise GeneratedRegionError(
            f"WHAT: GENERATED region '{region_id}' in {asset_path} cannot be "
            f"rendered from an installed layout.\n"
            f"WHY: only {sorted(INSTALLABLE_RENDERERS)} have every input present "
            "on a consumer machine; the other regions are rendered at build time "
            "by scripts/docgen.py, which never ships.\n"
            "HOW: either drop that marker from the shipped asset, or move the "
            "region's inputs into the wheel and register its renderer in "
            "des.application.generated_region_projection.INSTALLABLE_RENDERERS."
        )
    return renderer(root)


def project_asset(
    path: Path,
    text: str,
    root: Path,
    render_body: RegionRenderer = render_installable_region_body,
) -> AssetProjection:
    """Re-render every GENERATED region in ``text`` for ``root``.

    ``render_body`` is injected so each tier declares exactly which regions it
    can render: the default covers the installable set, and ``docgen`` passes
    its wider build-time dispatcher.
    """

    def _replace(match: re.Match[str]) -> str:
        region_id = match.group("region_id")
        return generated_region(region_id, render_body(region_id, path, root))

    return AssetProjection(
        path=path,
        current_text=text,
        projected_text=GENERATED_REGION_RE.sub(_replace, text),
    )
