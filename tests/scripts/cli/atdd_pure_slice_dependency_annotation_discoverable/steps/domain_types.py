"""Domain types for the slice-dependency-annotation-discoverable acceptance
slice.

`docs/feature/parallel-by-default-slice-plan/feature-delta.md` slice-02
(Mandate-12 criterion 1). Every domain noun used in the Gherkin is expressed
once here as a typed enum. Step bodies and the composition service consume
these typed parameters -- no raw ``str`` where a domain enum exists.
"""

from __future__ import annotations

from enum import Enum


class AuthoringSurface(str, Enum):
    """One of the two real files a PO is looking at while authoring a Slice
    Plan, in either its source-tree or its installed-tree location."""

    DISCUSS_SKILL_SOURCE = "discuss_skill_source"
    DISCUSS_SKILL_INSTALLED = "discuss_skill_installed"
    PRODUCT_OWNER_AGENT_SOURCE = "product_owner_agent_source"
    PRODUCT_OWNER_AGENT_INSTALLED = "product_owner_agent_installed"


class FabricatedFixture(str, Enum):
    """A synthetic section-text fixture used ONLY by the negative scenarios
    -- proves the check is not testing-theater by constructing the exact
    "documented in the wrong way" shapes a real bad edit could produce."""

    TOKEN_OUTSIDE_SECTION = "token_outside_section"
    BARE_TOKEN_NO_FLIP = "bare_token_no_flip"
    DROPS_EXISTING_TOKEN = "drops_existing_token"


AUTHORING_SURFACE_BY_PHRASE: dict[str, AuthoringSurface] = {
    "nw-discuss skill (source)": AuthoringSurface.DISCUSS_SKILL_SOURCE,
    "nw-discuss skill (installed)": AuthoringSurface.DISCUSS_SKILL_INSTALLED,
    "nw-product-owner agent (source)": AuthoringSurface.PRODUCT_OWNER_AGENT_SOURCE,
    "nw-product-owner agent (installed)": AuthoringSurface.PRODUCT_OWNER_AGENT_INSTALLED,
}
