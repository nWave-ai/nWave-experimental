"""A sealed DES task identity that can cross a provider boundary.

Provider adapters receive this identity, never the role input's contents.
The referenced file remains a DES-owned artifact and is read locally by the
installed role through its declared tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath


_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class InvocationReference:
    """The only dynamic task data admitted to a provider invocation."""

    role_id: str
    artifact_path: str
    artifact_sha256: str

    def __post_init__(self) -> None:
        if not self.role_id or any(character.isspace() for character in self.role_id):
            raise ValueError("InvocationReference role_id must be one token")
        path = PurePosixPath(self.artifact_path)
        if (
            not self.artifact_path
            or path.is_absolute()
            or ".." in path.parts
            or path.as_posix() != self.artifact_path
        ):
            raise ValueError(
                "InvocationReference artifact_path must be a safe relative path"
            )
        if not _SHA256.fullmatch(self.artifact_sha256):
            raise ValueError(
                "InvocationReference artifact_sha256 must be lowercase hex"
            )

    def formula(self) -> str:
        """The bounded, provider-neutral task formula.

        It deliberately names identity and location only.  It cannot embed role
        specifications, skills, handoffs, or task-body bytes.
        """
        return (
            "DES-TASK-REFERENCE "
            f"role={self.role_id} path={self.artifact_path} "
            f"sha256={self.artifact_sha256}"
        )
