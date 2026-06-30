"""Domain types for the des-feature-id-marker-distinct slice (C5, AD-61).

Every domain noun used in the Gherkin is expressed once here as a typed NewType
or frozen value object (Mandate-15 / SSOT-via-types). Step bodies and the
composition root consume these typed parameters -- no raw ``str`` where a domain
type exists.

The two domain identities the feature distinguishes:

  * ``FeatureId`` -- the identity of the feature being DELIVERED. Carried by the
    distinct ``<!-- DES-FEATURE-ID : feat-X -->`` marker the fix introduces. The
    carpaccio in-order guard keys the AT-completion ledger on this value.
  * ``ProjectId`` -- the project-ROOT identity (Earned-Trust intake + Task-Id
    grep, subagent_stop_service:218). Carried by the shipped
    ``<!-- DES-PROJECT-ID : proj-Y -->`` marker. Its role is UNCHANGED by the fix.

Before AD-61 these two were conflated: the carpaccio resolution overloaded
``DES-PROJECT-ID`` as the feature-id. The fix gives the feature-id its own marker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import NewType


# The identity of the feature being delivered -- carried by DES-FEATURE-ID.
FeatureId = NewType("FeatureId", str)

# The project-ROOT identity -- carried by DES-PROJECT-ID (role unchanged by AD-61).
ProjectId = NewType("ProjectId", str)


@dataclass(frozen=True)
class DispatchMarkers:
    """The DES marker selection a dispatch prompt carries, as a typed value object.

    A value of ``None`` for either field means the corresponding marker line is
    omitted from the rendered prompt entirely. This lets a scenario assemble a
    prompt carrying both markers (AC-2 / AC-4), only the project-id marker
    (AC-3 fallback), or only the feature-id marker (AC-1).
    """

    feature_id: FeatureId | None = None
    project_id: ProjectId | None = None
