"""K4 ATD -> dispatch -> crafter exact-byte handoff laws."""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"
AGENTS_DIR = NWAVE_DIR / "agents"

SECTION_ANCHOR = "## CLI dispatch — the only bridge from CONTRACT_READY to a crafter"
ATD_HANDOFF_ANCHOR = "## Review and terminal handoff"

HEADER_LOCATOR_PREFIX = "THIN-DELIVERY-CONTRACT: "
HEADER_DIGEST_PREFIX = "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"
EXACT_PAIR = (
    "THIN-DELIVERY-CONTRACT: <repository-relative-json-locator>\n"
    "THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>"
)
EXACT_ATD_RESULT = (
    "DISTILL-RESULT: CONTRACT_READY\n"
    "REPO-ROOT: <absolute physical repository root>\n"
    "DELIVERY-CONTRACT: <repo-relative locator>"
)

CRAFTER_FILES = (
    AGENTS_DIR / "nw-software-crafter.md",
    AGENTS_DIR / "nw-functional-software-crafter.md",
)


def _skill_body() -> str:
    return (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _atd_body() -> str:
    return (AGENTS_DIR / "nw-acceptance-designer.md").read_text(encoding="utf-8")


def _crafter_dispatch_section(body: str) -> str:
    return body[body.index(SECTION_ANCHOR) :]


def _atd_handoff_section(body: str) -> str:
    return body[body.index(ATD_HANDOFF_ANCHOR) :]


def _normalized(text: str) -> str:
    """Collapse markdown line-wrap whitespace so phrase checks aren't wrap-fragile."""
    return " ".join(text.split())


class TestCrafterDispatchFirstBytesRule:
    """ATD -> root -> crafter first-bytes contract and terminal fallback ban."""

    def test_crafter_validation_at_two_consumer_boundaries(self):
        """Crafter validates contract before BASELINE and before PASS/REPORT.
        Never guesses, hand-hashes or reimplements the closure algorithm."""
        for crafter_file in CRAFTER_FILES:
            body = crafter_file.read_text(encoding="utf-8")
            compact = " ".join(body.split())
            compact_lower = compact.lower()
            # Exact canonical validator command
            assert (
                "des validate-delivery-contract --repo-root <absolute-current-repository-root> --delivery-contract <locator>"
                in compact
            )
            # Two required call sites
            assert "before BASELINE" in compact
            assert "before PASS/REPORT" in compact
            # No reimplementation of closure algorithm
            assert "never guess, hand-hash or reimplement" in compact_lower
            # Oracle is terminal identifier, not a digest carrier
            assert "oracle: <locator>" in body
            assert "oracle: <locator>@sha256:" not in body

    def test_atd_terminal_section_owns_contract_ready_without_a_digest(self):
        """ATD selects the contract; the runtime alone computes the closure digest."""
        atd_section = _atd_handoff_section(_atd_body())
        assert EXACT_ATD_RESULT in atd_section
        assert "DELIVERY-CONTRACT-SHA256:" not in atd_section

        assert (
            "never returns a thin header, a digest" in _normalized(atd_section).lower()
        )

    def test_dispatch_pair_is_adjacent_in_auto_and_both_crafters(self):
        """The runtime pair is forwarded byte-for-byte to either crafter."""
        for source_name, text in (
            ("nw-auto/SKILL.md", _crafter_dispatch_section(_skill_body())),
            *((f.name, f.read_text(encoding="utf-8")) for f in CRAFTER_FILES),
        ):
            assert HEADER_LOCATOR_PREFIX in text, (
                f"{source_name} missing locator prefix"
            )
            assert HEADER_DIGEST_PREFIX in text, f"{source_name} missing digest prefix"
            assert EXACT_PAIR in text, (
                f"{source_name} header lines are not the exact pair"
            )

    def test_root_forwards_byte_for_byte_missing_header_is_terminal_no_repair(self):
        """(c) Root forwards first bytes verbatim; missing/malformed is terminal
        with no reconstruction/repair/retry/helper/generic-writer fallback."""
        section = _normalized(_crafter_dispatch_section(_skill_body()))
        for token in ("no prose", "no root line", "no json paste", "no code fence"):
            assert token in section.lower(), f"Missing precondition: {token}"
        assert "exactly one blank line follows" in section.lower()
        assert "repo-root: <absolute physical root>" in section.lower()
        assert "terminal under the single-pass rule" in section
        for forbidden in (
            "never hashes",
            "never reconstructs",
            "never repairs",
            "never retries",
            "never re-invokes `nw-auto`",
            "dispatches a helper agent",
            "generic writer",
        ):
            assert forbidden in section, f"Did not forbid: {forbidden}"

    def test_paradigm_mapping_root_propagation_and_single_pass_boundary(self):
        """(d) Paradigm mapping, immutable root propagation and single-pass
        route boundary remain intact."""
        body = _skill_body()
        paradigm_section = body[
            body.index("## Deterministic crafter selection") : body.index(
                "If `paradigm` is missing"
            )
        ]
        assert "`functional` | `nw-functional-software-crafter`" in paradigm_section
        assert "`object_oriented` | `nw-software-crafter`" in paradigm_section

        root_section = body[
            body.index("## Worktree ownership") : body.index(
                "## Architecture readiness"
            )
        ]
        assert "Root propagation" in root_section
        assert "this root is an immutable dispatch input" in root_section
        assert "never rediscovered" in root_section

        boundaries = body[body.index("## Route boundaries") :].lower()
        for token in ("single-pass", "is terminal", "no retry"):
            assert token in boundaries, f"Single-pass rule missing: {token}"
