"""Typed vocabulary shared by the retained dormant-seam acceptance slices."""

from __future__ import annotations

from enum import Enum


class SeamVerdict(str, Enum):
    """Whether a net-new effectful symbol has a production caller."""

    DORMANT_NO_CALL_SITE = "dormant-no-call-site"
    WIRED = "wired"


class CallSiteWiring(str, Enum):
    """Source-level wiring forms retained by the dormant-seam gate."""

    NONE = "none"
    DIRECT = "direct"
    INDIRECT = "indirect"


class SeamEscape(str, Enum):
    """Visible ways to clear a dormant-seam finding."""

    CALL_SITE = "call-site"
    DORMANT_OK_MARKER = "dormant-ok"


class DeltaScope(str, Enum):
    """Whether a symbol belongs to the feature's added-file delta."""

    NET_NEW_ADDED_FILE = "net-new-added-file"
    PRE_EXISTING_STATIC_TREE = "pre-existing-static-tree"
    MODIFIED_FILE_ADD = "modified-file-add"


class EmissionChannel(str, Enum):
    """Observable channel for a non-halting dormant-seam warning."""

    STDERR = "stderr"
