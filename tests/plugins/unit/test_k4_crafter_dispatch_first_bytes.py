"""K4 crafter dispatch — exact first-bytes forwarding (2026-08-12).

Installs the K4 ceiling slice fix: ATD's first result carries exactly two
header lines; root forwards them byte-for-byte as the crafter prompt's first
bytes, with no reconstruction/repair/retry/fallback permitted.

Confirmed defect (K4 exact bc79aace1): ATD produced a schema-valid
DeliveryContract and passing RED tests, but its own agent spec
(nw-acceptance-designer.md) never instructed it to emit the two-header block
as its terminal output -- that contract lived only in nw-auto/SKILL.md,
root's routing description of what ATD *should* send, never in ATD's own
runtime instruction surface. ATD's terminal text began "Now let's..." and
closed with a "## Summary" heading; zero THIN-DELIVERY-CONTRACT header
occurrences. Root then prefixed/duplicated facts when dispatching the
crafter, which refused. Checking only nw-auto/SKILL.md, as the prior version
of this suite did, cannot catch this class of defect because that file was
never wrong.

Tests verify, anchored on ATD's own runtime instruction surface
(nw-acceptance-designer.md Route contract, Auto branch) in agreement with
the shared "## Crafter dispatch — first bytes" section of nw-auto/SKILL.md
and both crafters' accepted-authority headers:
(a) ATD's own agent spec -- not merely nw-auto/SKILL.md -- instructs it to
    compute the SHA-256 of the exact final DeliveryContract bytes and begin
    its FINAL response at byte zero with the two exact thin headers, then
    one blank line, then only concise optional evidence; and the two
    header-line prefixes agree across ATD's spec, nw-auto/SKILL.md, and
    both crafter specs
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
AGENTS_DIR = NWAVE_DIR / "agents"

SECTION_ANCHOR = "## Crafter dispatch — first bytes"
ATD_AUTO_ANCHOR = "**Thin Auto M/L route"
ATD_HUMAN_ANCHOR = "**Human route:**"

HEADER_LOCATOR_PREFIX = "THIN-DELIVERY-CONTRACT: "
HEADER_DIGEST_PREFIX = "THIN-DELIVERY-CONTRACT-DIGEST: sha256:"

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


def _atd_auto_route_section(body: str) -> str:
    return body[body.index(ATD_AUTO_ANCHOR) : body.index(ATD_HUMAN_ANCHOR)]


def _normalized(text: str) -> str:
    """Collapse markdown line-wrap whitespace so phrase checks aren't wrap-fragile."""
    return " ".join(text.split())


class TestCrafterDispatchFirstBytesRule:
    """ATD -> root -> crafter first-bytes contract and terminal fallback ban."""

    def test_atd_ready_to_forward_block_has_exact_two_header_lines(self):
        """(a) ATD's own spec owns the terminal contract, agreeing with root/crafters."""
        section = _crafter_dispatch_section(_skill_body())
        for token in (
            "ATD returns a ready-to-forward authority block",
            "first two lines",
            "byte-for-byte",
        ):
            assert token in section, f"Missing: {token}"
        exact_pair = (
            "THIN-DELIVERY-CONTRACT: <repository-relative-json-locator>\n"
            "THIN-DELIVERY-CONTRACT-DIGEST: sha256:<64-lowercase-hex>"
        )
        assert exact_pair in section, "Header lines are not adjacent/exact"

        atd_section_raw = _atd_auto_route_section(_atd_body())
        assert exact_pair in atd_section_raw, "ATD header lines are not adjacent/exact"

        atd_section = _normalized(atd_section_raw)
        for token in (
            "compute the SHA-256 of the exact final",
            "bytes as written to disk",
            "begins at byte zero",
            "No greeting",
            "summary heading",
            "code fence",
            "absolute path",
            "JSON paste",
            "duplicate header",
            "root-computed hash",
            "ready-to-forward block",
        ):
            assert token in atd_section, (
                f"ATD's own spec missing terminal-output obligation: {token}"
            )

        for source_name, text in (
            ("nw-auto/SKILL.md", section),
            ("nw-acceptance-designer.md", atd_section_raw),
            *((f.name, f.read_text(encoding="utf-8")) for f in CRAFTER_FILES),
        ):
            assert HEADER_LOCATOR_PREFIX in text, (
                f"{source_name} missing locator header prefix"
            )
            assert HEADER_DIGEST_PREFIX in text, (
                f"{source_name} missing digest header prefix"
            )
            assert exact_pair in text, (
                f"{source_name} header lines are not the same exact adjacent pair"
            )

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
        boundaries = body[body.index("## Route boundaries") :].lower()
        for token in ("single-pass", "is terminal", "no retry"):
            assert token in boundaries, f"Single-pass rule missing: {token}"

    def test_section_anchor_is_the_sole_stable_owner(self):
        """The section must exist exactly once; removal must fail this suite."""
        body = _skill_body()
        assert body.count(SECTION_ANCHOR) == 1

        atd_body = _atd_body()
        anchor = "begins at byte zero"
        assert atd_body.count(anchor) == 1, (
            "ATD terminal directive must be a sole owner"
        )
        generated_start = atd_body.index("<!-- GENERATED:role-skill-loading START")
        generated_end = atd_body.index("<!-- GENERATED:role-skill-loading END") + len(
            "<!-- GENERATED:role-skill-loading END -->"
        )
        anchor_index = atd_body.index(anchor)
        assert not (generated_start <= anchor_index <= generated_end), (
            "ATD terminal directive must not live inside the generated Skill Loading region"
        )
        assert ATD_AUTO_ANCHOR in atd_body[:anchor_index], (
            "ATD terminal directive must sit inside the Auto route branch"
        )
        assert anchor_index < atd_body.index(ATD_HUMAN_ANCHOR), (
            "ATD terminal directive must precede the Human-route handoff"
        )
