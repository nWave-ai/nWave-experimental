"""K4 crafter dispatch — exact first-bytes forwarding (2026-08-12).

Installs the K4 ceiling slice fix: ATD's first result carries exactly two
header lines; root forwards them byte-for-byte as the crafter prompt's first
bytes, with no reconstruction/repair/retry/fallback permitted.

Confirmed defect: prose-prefixed crafter dispatch (JSON paste before headers)
caused AUTHORITY_REFUSED; retry via helper agent wasted turns. First result is
terminal under the single-pass rule.

Tests verify, all anchored on the single owning section
"## Crafter dispatch — first bytes" of nw-auto/SKILL.md:
(a) ATD owns the two exact thin headers as its first result lines
(b) Root forwards them byte-for-byte as crafter prompt first bytes with
    optional context only after one blank line, no prefix of any kind
(c) Missing/malformed headers are terminal: no hash/reconstruct/repair/
    retry/re-invoke/helper/generic-writer
(d) Paradigm mapping (OO -> nw-software-crafter | FP -> nw-functional-*) and
    canonical-root-after-headers are preserved
(e) The terminal single-pass rule flows through to Route boundaries
"""

from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
NWAVE_DIR = PROJECT_ROOT / "nWave"
SKILLS_DIR = NWAVE_DIR / "skills"

SECTION_ANCHOR = "## Crafter dispatch — first bytes"


def _skill_body() -> str:
    return (SKILLS_DIR / "nw-auto" / "SKILL.md").read_text(encoding="utf-8")


def _crafter_dispatch_section(body: str) -> str:
    return body[body.index(SECTION_ANCHOR) :]


def _normalized(text: str) -> str:
    """Collapse markdown line-wrap whitespace so phrase checks aren't wrap-fragile."""
    return " ".join(text.split())


class TestCrafterDispatchFirstBytesRule:
    """ATD -> root -> crafter first-bytes contract and terminal fallback ban."""

    def test_atd_ready_to_forward_block_has_exact_two_header_lines(self):
        """(a) ATD's block leads with the two exact headers, byte-for-byte."""
        section = _crafter_dispatch_section(_skill_body())
        for token in (
            "ATD returns a ready-to-forward authority block",
            "first two lines",
            "byte-for-byte",
        ):
            assert token in section, f"Missing: {token}"
        exact_pair = (
            "THIN-DELIVERY-CONTRACT: <repo-relative-json-locator>\n"
            "THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>"
        )
        assert exact_pair in section, "Header lines are not adjacent/exact"

    def test_root_forwards_headers_as_first_bytes_no_prefix_blank_line_context(self):
        """(b) No prose/root line/JSON/fence may precede; context needs a blank line."""
        section = _normalized(_crafter_dispatch_section(_skill_body()))
        for token in ("no prose", "no root line", "no JSON paste", "no code fence"):
            assert token in section, f"Missing precondition: {token}"
        assert "optional context follows only after one blank line" in section.lower()

    def test_missing_or_malformed_header_is_terminal_forbids_all_fallbacks(self):
        """(c) Terminal under single-pass rule: no repair path of any kind."""
        section = _normalized(_crafter_dispatch_section(_skill_body()))
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

    def test_paradigm_mapping_and_root_propagation_preserved(self):
        """(d) Paradigm -> crafter mapping and canonical-root-after-headers intact."""
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

    def test_single_pass_rule_applies_across_route_boundaries(self):
        """(e) The terminal/single-pass rule flows into the standing route rules."""
        body = _skill_body()
        boundaries = body[body.index("## Route boundaries") :]
        for token in ("single-pass", "is terminal", "never"):
            assert token in boundaries, f"Single-pass rule missing: {token}"

    def test_section_anchor_is_the_sole_stable_owner(self):
        """The section must exist exactly once; removal must fail this suite."""
        body = _skill_body()
        assert body.count(SECTION_ANCHOR) == 1
