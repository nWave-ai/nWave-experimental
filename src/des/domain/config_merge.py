"""Config-merge law (ADR-CFG-001): pure per-field override/fallback/malformed-
degrades resolution across the global and per-repo config tiers.

For field ``f`` in ``{enabled, verbosity, attribution}``::

    effective(f) = repo[f]     if f in repo and well_typed(f, repo[f])
                 = global[f]   if f in global and well_typed(f, global[f])
                 = DEFAULT[f]  otherwise

No I/O and no versioning import here (REUSE_CANDIDATE, ADR-CFG-001 obligation
1): both dicts are assumed already upcast by ``ArtifactVersioningKernel`` at
the (deferred) adapter boundary that will wire this pure function to the two
on-disk ``config.json`` tiers.
"""

VERBOSITY_VALUES = ("terse", "standard", "verbose")

ENABLED_DEFAULT = False
VERBOSITY_DEFAULT = "standard"
ATTRIBUTION_DEFAULT = False


def _enabled_well_typed(value: object) -> bool:
    return isinstance(value, bool)


def declares_enabled(config: dict) -> bool:
    """Does this tier explicitly declare a well-typed bool ``enabled``?

    Presence probe (same shape as the adapter's ``_declares_attribution``,
    ADR-CFG-003 correction 1): distinguishes "declared ``False``" from "not
    declared", a distinction the resolved bool of :func:`merge_config`
    collapses. Activation needs that distinction — ADR-AG-002 defers to the
    global ``activation.mode`` ONLY when no tier has an opinion.
    """
    return "enabled" in config and _enabled_well_typed(config["enabled"])


def declared_enabled(
    global_config: dict, repo_config: dict, legacy_repo_config: dict | None = None
) -> bool | None:
    """The FIRST tier that declares ``enabled`` wins; ``None`` when none does.

    Precedence (ADR-AG-002 "an explicit per-repo opinion wins over the global
    tier in BOTH directions", ADR-AG-005 consequence 3):

    1. repo ``<repo>/.nwave/config.json`` -> ``enabled``
    2. repo LEGACY marker ``<repo>/.nwave/local-config.json`` ->
       ``enabled_for_repo``, translated to ``{"enabled": bool}`` at the adapter
       boundary (P-SSOT-1 P5: legacy files stay READ as a tail tier)
    3. global ``~/.nwave/config.json`` -> ``enabled``

    ``None`` is the "no opinion" state the activation policy needs to reach its
    ``mode`` branch. This is the SINGLE precedence chain for ``enabled``:
    :func:`merge_config` resolves the same order and only substitutes
    ``ENABLED_DEFAULT`` for the ``None``.
    """
    for tier in (repo_config, legacy_repo_config or {}, global_config):
        if declares_enabled(tier):
            return tier["enabled"]
    return None


def _verbosity_well_typed(value: object) -> bool:
    return value in VERBOSITY_VALUES


def _attribution_well_typed(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("enabled"), bool)


def _attribution_value(value: dict) -> bool:
    return value["enabled"]


def _same_value(value):
    return value


def _resolve_field(
    repo_config, global_config, field, well_typed, default, unwrap=_same_value
):
    if field in repo_config and well_typed(repo_config[field]):
        return unwrap(repo_config[field])
    if field in global_config and well_typed(global_config[field]):
        return unwrap(global_config[field])
    return default


def merge_config(
    global_config: dict, repo_config: dict, legacy_repo_config: dict | None = None
) -> dict:
    """Resolve the effective ``enabled``/``verbosity``/``attribution`` values
    from the global-then-repo cascade (ADR-CFG-001 Config-merge law). Pure:
    never mutates ``global_config`` or ``repo_config``, never raises on
    malformed input -- a malformed value degrades to "absent for this tier".

    ``legacy_repo_config`` is the optional translated legacy per-repo marker
    tier (``.nwave/local-config.json``), which participates ONLY in the
    ``enabled`` field and only below the unified repo tier (P-SSOT-1 P5-bis).
    ``enabled`` is resolved through :func:`declared_enabled` so there is ONE
    precedence chain, shared with the tri-state activation reader.
    """
    declared = declared_enabled(global_config, repo_config, legacy_repo_config)
    return {
        "enabled": ENABLED_DEFAULT if declared is None else declared,
        "verbosity": _resolve_field(
            repo_config,
            global_config,
            "verbosity",
            _verbosity_well_typed,
            VERBOSITY_DEFAULT,
        ),
        "attribution": _resolve_field(
            repo_config,
            global_config,
            "attribution",
            _attribution_well_typed,
            ATTRIBUTION_DEFAULT,
            unwrap=_attribution_value,
        ),
    }
