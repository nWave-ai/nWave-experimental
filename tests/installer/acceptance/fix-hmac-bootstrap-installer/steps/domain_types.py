"""Domain types for fix-hmac-bootstrap-installer (Mandate-12 criterion 1).

Every domain noun in the slice-01 Gherkin is expressed once here as a typed
enum / NewType. The composition root consumes these typed parameters; step
bodies coerce a Gherkin phrase to a typed value via `*_BY_PHRASE` maps and
delegate — no raw `str` where a domain enum exists, no inline business
logic.
"""

from __future__ import annotations

from enum import Enum


class BootstrapVerdict(str, Enum):
    """The operator-observable outcome of a fresh install with respect to the
    reviewer signing key.

    A walking-skeleton-level enum: the SUT either provisioned a usable key
    file (PROVISIONED), or recognised an operator-supplied env var and
    declined to provision a file (ENV_OVERRIDDEN), or left an existing key
    untouched on re-install (PRESERVED).
    """

    PROVISIONED = "provisioned"
    PRESERVED = "preserved"
    ENV_OVERRIDDEN = "env_overridden"


class InstallManifestField(str, Enum):
    """Operator-observable fields of the post-install reviewer-signing-key
    surface. Universe entries for state-delta assertions live in this enum.
    """

    KEY_FILE_EXISTS = "key_file.exists"
    KEY_FILE_BYTES = "key_file.bytes"
    KEY_FILE_MODE_BITS = "key_file.mode_bits"
    VERIFY_MESSAGE = "verify.message"


# Phrase → BootstrapVerdict table, used by step bodies to coerce a Gherkin
# phrase to a typed verdict and delegate.
VERDICT_BY_PHRASE: dict[str, BootstrapVerdict] = {
    "auto-provisions an HMAC reviewer signing key": BootstrapVerdict.PROVISIONED,
    "leaves the existing signing key untouched": BootstrapVerdict.PRESERVED,
    "suppresses provisioning": BootstrapVerdict.ENV_OVERRIDDEN,
}
