"""Regression guard -- techdebt row
`hook-definitions-single-source-of-truth-claim-false-second-registration-path-exists`.

`scripts/shared/hook_definitions.py`'s module docstring claimed to provide
"the shared definitions so hook events, matchers, and actions are defined
exactly once" -- false: `scripts/install/attribution_utils.py`
(`register_attribution_hook`, gated by `attribution.enabled`) builds its own
independent `PreToolUse`/`Bash` entry (`pre-commit-attribution`) that is
entirely invisible to `HOOK_EVENTS` and to this module's own exhaustive test
(`test_hook_definitions.py`). Two independent code paths generate
`hooks.PreToolUse` entries in `~/.claude/settings.json`; a future
audit/count/invariant written against `HOOK_EVENTS` alone is blind to the
attribution hook.

Resolution chosen: option (b) from the row (the entry has an independent
on/off lifecycle -- attribution can be toggled without touching the install
manifest -- so folding it into `HOOK_EVENTS` was rejected as a lifecycle
mismatch, not attempted). Instead the docstring is rewritten to declare
explicitly that it covers only the fixed/always-installed set, and to point
at the conditionally-registered attribution hook by name. This test pins that
the disclaimer + pointer are present, so the doc cannot silently regress back
to the false "exactly once" claim.
"""

from __future__ import annotations

from scripts.shared import hook_definitions


def test_module_docstring_does_not_claim_hooks_are_defined_exactly_once():
    doc = hook_definitions.__doc__ or ""
    assert "exactly once" not in doc, (
        "hook_definitions.py's module docstring must not claim hook events "
        "are defined 'exactly once' -- attribution_utils.register_attribution_hook "
        "builds an independent PreToolUse/Bash entry this module never sees."
    )


def test_module_docstring_names_the_attribution_registration_path():
    doc = hook_definitions.__doc__ or ""
    assert "attribution" in doc.lower(), (
        "hook_definitions.py's module docstring must name the second, "
        "independent PreToolUse registration path "
        "(attribution_utils.register_attribution_hook) so a reader knows "
        "HOOK_EVENTS is not the complete PreToolUse registration surface."
    )
