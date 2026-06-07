"""Domain types for copilot-cli-integration (Mandate-12 criterion 1).

Every domain noun in the slice-01 Gherkin is expressed once here as a typed
enum / NewType. The composition fixture consumes these typed parameters; step
bodies delegate to composition methods and never inline business logic
(Mandate-12 criterion 3).

Spike-validated constants (do NOT trust docs over the binary):
  - FM-1: the hook config is a file in the hooks directory, NOT an inline block
    in settings.json. So the install surface is `<copilot-home>/hooks/<name>.json`.
  - FS-1: each hook entry is double-nested:
    `{matcher?, hooks: [{type: "command", bash: ...}]}` — never flat.
"""

from __future__ import annotations

from enum import Enum


class CopilotInstallOutcome(str, Enum):
    """The operator-observable outcome of installing/uninstalling nWave for the
    Copilot runtime, expressed in domain terms.

    HOOK_WIRED        — install wrote the nWave DES hook config to the hooks dir.
    HOOK_REMOVED      — uninstall removed the nWave DES hook config cleanly.
    FOREIGN_PRESERVED — uninstall left an operator-authored Copilot hook intact.
    """

    HOOK_WIRED = "hook_wired"
    HOOK_REMOVED = "hook_removed"
    FOREIGN_PRESERVED = "foreign_preserved"


class CopilotHookSurface(str, Enum):
    """Operator-observable surfaces of the Copilot hook config (universe entries
    for state-delta assertions).

    FM-1 makes HOOK_FILE_EXISTS the install target and SETTINGS_INLINE_BLOCK the
    surface that MUST stay empty (the documented-but-broken mount point).
    """

    HOOK_FILE_EXISTS = "copilot.hook_file.exists"
    HOOK_FILE_CONTENT = "copilot.hook_file.content"
    SETTINGS_INLINE_BLOCK = "copilot.settings.inline_hooks_block"
    FOREIGN_HOOK_FILE = "copilot.foreign_hook_file.content"


class CopilotHookSchemaShape(str, Enum):
    """The shape the written hook entry takes (FS-1 contract).

    DOUBLE_NESTED — the working shape: `{matcher, hooks: [{type, bash}]}`.
    FLAT          — the broken shape research quoted: `{type, bash}` directly.
    """

    DOUBLE_NESTED = "double_nested"
    FLAT = "flat"


# Phrase → CopilotInstallOutcome table, used by step bodies to coerce a Gherkin
# phrase to a typed outcome and delegate. Keeps step bodies free of literals.
OUTCOME_BY_PHRASE: dict[str, CopilotInstallOutcome] = {
    "wires the DES hook into the Copilot hooks directory": (
        CopilotInstallOutcome.HOOK_WIRED
    ),
    "removes its Copilot hook": CopilotInstallOutcome.HOOK_REMOVED,
    "leaves the operator's own hook intact": (CopilotInstallOutcome.FOREIGN_PRESERVED),
}
