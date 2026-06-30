"""Domain types for the oss-review-verdict-demotion S5 installer acceptance set.

S5 demotes the install surface: the reviewer signing plugin is DELETED, the
plugin registry honestly registers 7 plugins, no signing key is provisioned
at install, and an EXISTING operator key file is preserved untouched (a user
file -- never read, never deleted).

These typed nouns are the contract vocabulary every Gherkin step speaks. The
composition methods consume them so no step body inlines a literal where a
domain enum exists (Mandate-12 criterion 2).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


# The plugin name the demotion REMOVES from the production install registry.
DEMOTED_PLUGIN_NAME = "reviewer_signing"

# The honest post-demotion Claude-Code plugin count (was 8 with the signing
# plugin; 7 after it is deleted).
EXPECTED_CLAUDE_PLUGIN_COUNT = 7

# The operator key file the installer must NEVER touch (preserve-by-default).
KEY_RELPATH = ".nwave/secrets/reviewer-signing.key"

# The override env var the demoted installer no longer reads or provisions.
SIGNING_KEY_ENV = "NWAVE_REVIEWER_SIGNING_KEY"


class TargetKeyState(Enum):
    """The signing-key state of the install target before the pipeline runs."""

    NO_KEY = "no-key"
    PREEXISTING_USER_KEY = "preexisting-user-key"


@dataclass(frozen=True)
class RegistrySurface:
    """The operator-observable shape of the production plugin registry.

    Captured from the production composition root
    (`NWaveInstaller._create_plugin_registry`) -- the seam that wires the
    install plugins. `plugin_names` are the registered plugin identifiers in
    execution order; `count` is their cardinality.
    """

    plugin_names: tuple[str, ...]
    count: int


@dataclass(frozen=True)
class TargetKeyObservation:
    """The operator-observable state of the target's signing-key slot.

    `key_file_exists` reports whether `.nwave/secrets/reviewer-signing.key`
    is present on the target; `key_file_bytes` is its content (None when
    absent). Used to prove preserve-by-default (byte-identical survival) and
    keyless install (no file provisioned).
    """

    key_file_exists: bool
    key_file_bytes: bytes | None
