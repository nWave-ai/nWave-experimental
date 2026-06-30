"""AT-A7 (slice-05, DDD-8): the wave-dispatch guard policy's wave->owner map covers
every wave-OWNER agent, excludes every reviewer, and its map keys EQUAL the
policy-owned ``DISPATCH_GUARD_VOCABULARY`` (the 7 wave-owners incl. discover/diverge).

RE-HOMED (orchestrator augment 2026-06-16): the production guard is PRODUCTION
RUNTIME enforcement in the DES runtime -- the wave->owner map lives in
``src/des/domain/wave_dispatch_guard_policy.py`` (a pure domain policy), NOT in the
hand-placed ``~/.claude/hooks/des_crafter_dispatch_guard.py`` (which has no repo
source -- DDD-8). This arch test reads the IN-TREE policy source as DATA -- no
``~/.claude`` path (the acceptance-hermeticity guard forbids it).

Arch-tier, pure-function (no subprocess, no behavioral execution): reads the SHIPPED
policy source as DATA and asserts coherence. Recognized as an arch test
(``test_arch_`` prefix under ``tests/build/``) per the AT-completeness S2
tolerable-variant rule (it introspects structure, it does not exercise behavior).

VOCABULARY CORRECTNESS (§22.0 H-1, resolved at source): the DDD-8 wave->owner map
includes DISCOVER (`discover`) + DIVERGE (`diverge`) owners, but the shipped ledger
``WAVE_VOCABULARY`` at ``src/des/domain/wave_active.py`` is
``{discuss, design, devops, distill, deliver, feature-end}`` -- it does NOT contain
`discover`/`diverge` and MUST NOT (DISCOVER/DIVERGE emit no wave-active record). The
RESOLUTION (Reuse Analysis, feature-delta): the policy DECLARES ITS OWN
``DISPATCH_GUARD_VOCABULARY = frozenset({"discover","diverge","discuss","design",
"devops","distill","deliver"})`` -- distinct from the ledger vocab. This test pins
``map-keys ≡ DISPATCH_GUARD_VOCABULARY`` (NOT the ledger vocab), so the guard
protects DISCOVER/DIVERGE too.

ACTIVE-RED (atdd_pure -- NOT @skip): at HEAD ``src/des/domain/wave_dispatch_guard_
policy.py`` does not exist. The "policy ships a wave->owner map + a
``DISPATCH_GUARD_VOCABULARY`` whose members EQUAL the map's wave tokens" assertion
RED-fails with a semantic AssertionError on the absent module/symbols. GREEN once
DELIVER ships the policy (DDD-8).
"""

from __future__ import annotations

import ast
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]  # parents[3] = REPO_ROOT
_POLICY_PATH = _REPO_ROOT / "src" / "des" / "domain" / "wave_dispatch_guard_policy.py"

# The DDD-8 wave->owner agents the policy must recognize (owners only; reviewers
# excluded -- §22.0 controls). Mirrors the feature-delta map.
_EXPECTED_WAVE_OWNERS: frozenset[str] = frozenset(
    {
        "nw-product-discoverer",
        "nw-diverger",
        "nw-product-owner",
        # The DESIGN wave has FOUR authoring owners (feature-delta:114, ADR-NB-001):
        # solution-architect (app), ddd-architect (domain modelling), system-designer
        # (infra-level), platform-architect (infra-design). All four must be guarded
        # off-spine -- omitting ddd-architect/system-designer left a silent wave-entry
        # hole (F_FINAL_REVIEW BLOCKER 2026-06-16: this expected-set mirrored the
        # implementation's narrowed map instead of the spec, so the gap shipped green).
        "nw-solution-architect",
        "nw-ddd-architect",
        "nw-system-designer",
        "nw-acceptance-designer",
        "nw-platform-architect",
    }
)
# The 7 wave tokens the policy's DISPATCH_GUARD_VOCABULARY must own (incl. the two
# the ledger WAVE_VOCABULARY deliberately excludes).
_EXPECTED_DISPATCH_VOCABULARY: frozenset[str] = frozenset(
    {"discover", "diverge", "discuss", "design", "devops", "distill", "deliver"}
)
# A reviewer subagent_type that MUST NOT appear in the map (always-allowed, CT-9).
_FORBIDDEN_REVIEWER = "nw-solution-architect-reviewer"


def _policy_module_tree() -> ast.Module | None:
    """Parse the SHIPPED policy source as an AST, or None at HEAD (module absent)."""
    if not _POLICY_PATH.is_file():
        return None
    return ast.parse(_POLICY_PATH.read_text(encoding="utf-8"))


def _literal_assignment(tree: ast.Module, name: str) -> object | None:
    """Return the literally-evaluable value of a module-level ``name = ...`` assign.

    Handles a bare dict/set literal AND a ``frozenset({...})`` call literal. Reads
    the source as an AST literal -- no import, no behavioral execution. Returns None
    if the symbol is absent or its value is not a recognized literal.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            continue
        value = node.value
        if (
            isinstance(value, ast.Call)
            and getattr(value.func, "id", None) == "frozenset"
            and value.args
        ):
            try:
                return frozenset(ast.literal_eval(value.args[0]))
            except (ValueError, SyntaxError):
                return None
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None
    return None


def _wave_owner_map() -> dict[str, str] | None:
    """The policy's wave->owner map read from the SHIPPED policy source as DATA.

    Looks for a module-level ``WAVE_OWNERS`` dict literal (subagent_type ->
    DES-WAVE token). Returns the dict, or None when the policy ships no such symbol
    (HEAD state -- the module itself is absent).
    """
    tree = _policy_module_tree()
    if tree is None:
        return None
    value = _literal_assignment(tree, "WAVE_OWNERS")
    if isinstance(value, dict):
        return {str(k): str(v) for k, v in value.items()}
    return None


def _dispatch_guard_vocabulary() -> frozenset[str] | None:
    """The policy-owned ``DISPATCH_GUARD_VOCABULARY`` frozenset, read as DATA."""
    tree = _policy_module_tree()
    if tree is None:
        return None
    value = _literal_assignment(tree, "DISPATCH_GUARD_VOCABULARY")
    if isinstance(value, frozenset):
        return frozenset(str(x) for x in value)
    if isinstance(value, (set, list, tuple)):
        return frozenset(str(x) for x in value)
    return None


def test_wave_dispatch_guard_policy_ships_wave_owner_map() -> None:
    """AT-A7 leg 1: the policy SHIPS a wave->owner map (DDD-8)."""
    owner_map = _wave_owner_map()
    assert owner_map is not None, (
        "the wave-dispatch guard policy must ship a module-level WAVE_OWNERS map "
        "(subagent_type -> DES-WAVE token) in src/des/domain/wave_dispatch_guard_"
        "policy.py so a wave-owner dispatched off-spine is BLOCKED (DDD-8); at HEAD "
        "the policy module does not exist. GREEN once DELIVER ships the policy."
    )


def test_wave_owner_map_covers_every_owner_and_excludes_reviewers() -> None:
    """AT-A7 leg 2: the map covers every wave-owner and contains no reviewer."""
    owner_map = _wave_owner_map()
    assert owner_map is not None, (
        "WAVE_OWNERS map absent at HEAD -- see "
        "test_wave_dispatch_guard_policy_ships_wave_owner_map. GREEN once DELIVER "
        "ships the policy."
    )
    missing = _EXPECTED_WAVE_OWNERS - frozenset(owner_map)
    assert not missing, (
        "the wave->owner map must cover EVERY wave-owner agent (the DDD-8 map); "
        f"missing owners: {sorted(missing)}."
    )
    assert _FORBIDDEN_REVIEWER not in owner_map, (
        "reviewers are §22.0 controls (never wave-authoring) -- they MUST NOT be "
        f"in the wave->owner map; {_FORBIDDEN_REVIEWER!r} was found."
    )


def test_dispatch_guard_vocabulary_owns_discover_and_diverge() -> None:
    """AT-A7 leg 3: the policy owns DISPATCH_GUARD_VOCABULARY incl. discover/diverge.

    §22.0 H-1: the policy declares its OWN vocabulary -- it MUST cover the 7
    wave-owners (incl. discover/diverge the ledger WAVE_VOCABULARY excludes), so
    the guard protects DISCOVER/DIVERGE too.
    """
    vocabulary = _dispatch_guard_vocabulary()
    assert vocabulary is not None, (
        "the policy must declare its OWN `DISPATCH_GUARD_VOCABULARY` frozenset "
        "(distinct from the ledger wave_active.WAVE_VOCABULARY, §22.0 H-1) so a "
        "DISCOVER/DIVERGE marker is not silently out-of-vocab; at HEAD the policy "
        "module is absent. GREEN once DELIVER ships it."
    )
    assert vocabulary == _EXPECTED_DISPATCH_VOCABULARY, (
        "the policy-owned DISPATCH_GUARD_VOCABULARY must EQUAL the 7 wave-owner "
        f"tokens {sorted(_EXPECTED_DISPATCH_VOCABULARY)!r} (incl. discover/diverge); "
        f"got {sorted(vocabulary)!r}."
    )


def test_wave_owner_markers_are_in_the_dispatch_guard_vocabulary() -> None:
    """AT-A7 leg 4: every map marker token is in the policy-owned vocabulary.

    §22.0 H-1: the coherence is map-tokens ⊆ DISPATCH_GUARD_VOCABULARY (the
    policy-owned set), NOT the ledger WAVE_VOCABULARY -- so discover/diverge tokens
    are valid. RED-fails first on the absent map/vocabulary at HEAD.
    """
    owner_map = _wave_owner_map()
    vocabulary = _dispatch_guard_vocabulary()
    assert owner_map is not None and vocabulary is not None, (
        "WAVE_OWNERS map / DISPATCH_GUARD_VOCABULARY absent at HEAD. GREEN once "
        "DELIVER ships the policy."
    )
    out_of_vocab = {tok for tok in owner_map.values() if tok not in vocabulary}
    assert not out_of_vocab, (
        "every wave->owner marker token must be in the policy-owned "
        f"DISPATCH_GUARD_VOCABULARY {sorted(vocabulary)!r}; out-of-vocabulary "
        f"tokens: {sorted(out_of_vocab)}."
    )
