"""Acceptance oracle for delivery auto-77a47f64fc2f70ec (ADR-CFG-001, G1).

Exercises the single pure law this RED_TO_GREEN slice introduces --
``des.domain.config_merge.merge_config(global: dict, repo: dict) -> dict`` --
against the four obligations named in the contract: REUSE_CANDIDATE,
CONTESTED_LAW, PRESERVATION, BROAD_INPUT_DOMAIN.

Until ``src/des/domain/config_merge.py`` exists, every test below fails at
collection with ``ModuleNotFoundError: No module named 'des.domain.config_merge'``
-- the intended RED observation for every obligation (ADR-CFG-001,
"Obligations for DISTILL" section).

Config-merge law under test (ADR-CFG-001), for field ``f`` in
``{enabled, verbosity, attribution}``::

    effective(f) = repo[f]     if f in repo and well_typed(f, repo[f])
                 = global[f]   if f in global and well_typed(f, global[f])
                 = DEFAULT[f]  otherwise

``attribution`` is stored on both tiers as ``{"enabled": bool}`` -- the exact
shape ``DESConfig.attribution_enabled`` reads today
(``src/des/adapters/driven/config/des_config.py:275-289``) -- so its
well-typed check and resolution unwrap that inner boolean; ``enabled`` and
``verbosity`` are well-typed at the raw stored value directly. ``verbosity``'s
own DEFAULT is not stated anywhere in ADR-CFG-001, so this oracle asserts only
enum membership for the absent-or-malformed-both-tiers case, never a guessed
concrete default.
"""

import ast
import copy
import inspect

from hypothesis import given, settings
from hypothesis import strategies as st

from des.domain import config_merge
from des.domain.config_merge import merge_config


class TestReuseCandidateNoVersioningImport:
    """REUSE_CANDIDATE (ADR-CFG-001 obligation 1): ``config_merge.py`` takes
    already-upcast dicts -- the ``ArtifactVersioningKernel`` call stays at the
    (deferred) I/O boundary. Verified by absence, not presence, of any
    versioning import in the module under test."""

    def test_config_merge_module_declares_no_versioning_import(self):
        source = inspect.getsource(config_merge)
        tree = ast.parse(source)
        imported_names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module:
                    imported_names.add(module)
                for alias in node.names:
                    imported_names.add(
                        f"{module}.{alias.name}" if module else alias.name
                    )

        forbidden = {
            name
            for name in imported_names
            if "artifact_versioning" in name or "ArtifactVersioningKernel" in name
        }
        assert not forbidden, (
            "config_merge.py must not import the versioning kernel -- "
            "upcasting stays at the I/O boundary, a later adapter slice "
            f"(ADR-CFG-001 obligation 1); found: {forbidden}"
        )


class TestContestedLaw:
    """CONTESTED_LAW (ADR-CFG-001 obligation 2): the four Config-merge law
    equations -- Override, Fallback, Idempotence, Malformed-degrades -- plus
    the ADR's own canonical examples and invalid-boundary examples."""

    def test_override_repo_wins_regardless_of_global_value(self):
        # ADR-CFG-001 canonical example (a).
        repo = {"verbosity": "terse"}
        global_cfg = {"verbosity": "verbose"}

        effective = merge_config(global_cfg, repo)

        assert effective["verbosity"] == "terse"

    def test_fallback_attribution_from_global_nested_shape(self):
        # ADR-CFG-001 canonical example (b) -- matches
        # DESConfig.attribution_enabled (des_config.py:275-289): "attribution"
        # is stored as {"enabled": bool} on both tiers.
        repo: dict = {}
        global_cfg = {"attribution": {"enabled": True}}

        effective = merge_config(global_cfg, repo)

        assert effective["attribution"] is True

    def test_idempotence_pure_no_input_mutation(self):
        global_cfg = {"verbosity": "verbose", "enabled": False}
        repo = {"attribution": {"enabled": True}}
        global_before = copy.deepcopy(global_cfg)
        repo_before = copy.deepcopy(repo)

        first = merge_config(global_cfg, repo)
        second = merge_config(global_cfg, repo)

        assert first == second
        assert global_cfg == global_before
        assert repo == repo_before

    def test_malformed_degrades_never_raises_when_both_tiers_malformed(self):
        # ADR-CFG-001 "Invalid boundaries": verbosity: 3, enabled: "yes"
        # (both tiers malformed for the same field must still degrade to
        # DEFAULT[f], never raise).
        global_cfg = {"verbosity": 3, "enabled": "yes"}
        repo = {"verbosity": 3, "enabled": "yes"}

        effective = merge_config(global_cfg, repo)  # must not raise

        assert effective["verbosity"] in ("terse", "standard", "verbose")
        # DEFAULT[enabled] is False: activation is opt-in (ADR-AG-005,
        # P-SSOT-1 P6). A tier that declares nothing well-typed has NO
        # opinion, and no opinion means inactive.
        assert effective["enabled"] is False

    def test_no_tier_declares_enabled_resolves_inactive_opt_in(self):
        # ADR-AG-005 / P-SSOT-1 P6: opt-in is the RATIFIED default. When no
        # tier declares an opinion the merge law must resolve INACTIVE --
        # nWave does not act in a repository the user never activated.
        effective = merge_config({}, {})

        assert effective["enabled"] is False

    def test_verbosity_outside_enum_is_invalid_boundary(self):
        repo = {"verbosity": "chatty"}
        global_cfg = {"verbosity": "standard"}

        effective = merge_config(global_cfg, repo)

        assert effective["verbosity"] == "standard"

    def test_enabled_non_bool_is_invalid_boundary(self):
        repo = {"enabled": "yes"}
        global_cfg = {"enabled": False}

        effective = merge_config(global_cfg, repo)

        assert effective["enabled"] is False

    def test_attribution_non_bool_after_unwrap_is_invalid_boundary(self):
        repo = {"attribution": {"enabled": "yes"}}
        global_cfg = {"attribution": {"enabled": False}}

        effective = merge_config(global_cfg, repo)

        assert effective["attribution"] is False


class TestPreservation:
    """PRESERVATION (ADR-CFG-001 obligation 3): DESConfig.attribution_enabled's
    current fallback value (False, des_config.py:275-289) survives unchanged
    through merge_config for the absent-both-tiers case."""

    def test_attribution_absent_both_tiers_matches_current_fallback_false(self):
        effective = merge_config({}, {})

        assert effective["attribution"] is False


_ABSENT = object()

_ENABLED_VALID = st.booleans()
_ENABLED_MALFORMED = st.one_of(
    st.text(max_size=5),
    st.integers(),
    st.lists(st.booleans(), max_size=2),
    st.none(),
)
_ENABLED_FIELD = st.one_of(st.just(_ABSENT), _ENABLED_VALID, _ENABLED_MALFORMED)

_VALID_VERBOSITY = ("terse", "standard", "verbose")
_VERBOSITY_VALID = st.sampled_from(_VALID_VERBOSITY)
_VERBOSITY_MALFORMED = st.one_of(
    st.text(max_size=5).filter(lambda s: s not in _VALID_VERBOSITY),
    st.integers(),
    st.none(),
)
_VERBOSITY_FIELD = st.one_of(st.just(_ABSENT), _VERBOSITY_VALID, _VERBOSITY_MALFORMED)

_ATTRIBUTION_VALID = st.fixed_dictionaries({"enabled": st.booleans()})
_ATTRIBUTION_MALFORMED = st.one_of(
    st.text(max_size=5),
    st.integers(),
    st.fixed_dictionaries({}),
    st.fixed_dictionaries({"enabled": st.text(max_size=3)}),
)
_ATTRIBUTION_FIELD = st.one_of(
    st.just(_ABSENT), _ATTRIBUTION_VALID, _ATTRIBUTION_MALFORMED
)


@st.composite
def _config_tier(draw):
    """One tier (global or repo) with each of the three fields independently
    drawn from {absent, well-typed, malformed}, plus an occasional unrelated
    key (forward-compat: must be ignored)."""
    tier: dict = {}
    enabled = draw(_ENABLED_FIELD)
    if enabled is not _ABSENT:
        tier["enabled"] = enabled
    verbosity = draw(_VERBOSITY_FIELD)
    if verbosity is not _ABSENT:
        tier["verbosity"] = verbosity
    attribution = draw(_ATTRIBUTION_FIELD)
    if attribution is not _ABSENT:
        tier["attribution"] = attribution
    if draw(st.booleans()):
        tier["future_unrelated_key"] = draw(st.text(max_size=5))
    return tier


def _attribution_well_typed(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("enabled"), bool)


class TestBroadInputDomain:
    """BROAD_INPUT_DOMAIN (ADR-CFG-001 obligation 4): the four equations
    generalized as a property over the {absent, well-typed, malformed} x
    {global, repo} input domain, for all three fields."""

    @settings(max_examples=100, deadline=None)
    @given(global_cfg=_config_tier(), repo_cfg=_config_tier())
    def test_merge_config_never_raises_and_obeys_override_fallback_law(
        self, global_cfg, repo_cfg
    ):
        global_before = copy.deepcopy(global_cfg)
        repo_before = copy.deepcopy(repo_cfg)

        effective = merge_config(global_cfg, repo_cfg)  # must not raise

        assert global_cfg == global_before
        assert repo_cfg == repo_before

        # enabled: well-typed = bool; DEFAULT False -- activation is opt-in
        # (ADR-AG-005, P-SSOT-1 P6).
        repo_enabled = repo_cfg.get("enabled")
        global_enabled = global_cfg.get("enabled")
        if "enabled" in repo_cfg and isinstance(repo_enabled, bool):
            assert effective["enabled"] == repo_enabled
        elif "enabled" in global_cfg and isinstance(global_enabled, bool):
            assert effective["enabled"] == global_enabled
        else:
            assert effective["enabled"] is False

        # verbosity: well-typed = member of the closed enum; ADR-CFG-001
        # never states a concrete DEFAULT, so only enum membership is
        # asserted for the absent-or-malformed-both-tiers case.
        repo_verbosity = repo_cfg.get("verbosity")
        global_verbosity = global_cfg.get("verbosity")
        if "verbosity" in repo_cfg and repo_verbosity in _VALID_VERBOSITY:
            assert effective["verbosity"] == repo_verbosity
        elif "verbosity" in global_cfg and global_verbosity in _VALID_VERBOSITY:
            assert effective["verbosity"] == global_verbosity
        else:
            assert effective["verbosity"] in _VALID_VERBOSITY

        # attribution: well-typed = {"enabled": bool}; DEFAULT False (matches
        # DESConfig.attribution_enabled's current fallback, des_config.py:289).
        repo_attribution = repo_cfg.get("attribution")
        global_attribution = global_cfg.get("attribution")
        if "attribution" in repo_cfg and _attribution_well_typed(repo_attribution):
            assert effective["attribution"] == repo_attribution["enabled"]
        elif "attribution" in global_cfg and _attribution_well_typed(
            global_attribution
        ):
            assert effective["attribution"] == global_attribution["enabled"]
        else:
            assert effective["attribution"] is False
