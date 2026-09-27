"""Public oracle: the route choice meets the agent at the start of a Request.

Authority: docs/product/architecture/brief.md#Route Choice Meets the Agent at the
Start of a Request.

An agent opening a Request in a project where nWave was installed reads its
CLAUDE.md. The observation is about WHAT THAT AGENT ENCOUNTERS FIRST: the nWave
section must open by naming the three available routes and what each one costs
and buys, so choosing to bypass the method is a recorded choice rather than an
unnoticed omission -- while the prose stays descriptive and never commands the
agent to route.

Driving port: the real process ``python -m nwave_ai.cli project enable --yes``,
run in a throwaway project directory. Nothing here imports a production symbol,
reads a template, or reaches into the splice engine: the oracle only observes the
guidance file a real user would end up reading. That keeps the dependency
direction intact (templates are data the installer reads; the installer never
knows this oracle exists) and keeps the oracle honest about the published bytes
rather than about the template source.

The fail-open boundary in ``nwave_ai/cli.py`` silently skips injection when a
template is missing or a write fails. Because every assertion below demands the
PRESENCE of the block, such a skip surfaces here as a failed observation rather
than as a pass.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[4]

BEGIN_MARKER = "<!-- BEGIN nWave-beta-section (managed by nwave-ai; do not edit) -->"
END_MARKER = "<!-- END nWave-beta-section -->"

SECTION_HEADING = "## nWave (beta)"

# The affordance table the section has always carried. Everything the agent must
# meet FIRST has to stand before this row.
AFFORDANCE_TABLE_ROW = "| User wants"

# The route-choice block ends with the sentence that names the choice (GDP-9
# interrogative framing). No imperative pair: the block is guidance, not a gate.
CHOICE_SENTENCE_MARKER = "whichever route"

# The three routes, each named with its consequence.
ROUTE_NAMES = ("spine waves", "des steps", "working directly")

# Consequences that make the choice informed rather than decorative.
ROUTE_CONSEQUENCES = (
    "independent review",  # spine waves keep it; working directly does not
    "public oracle",  # DES steps put the oracle before the code
    "gate",  # spine waves carry them; working directly keeps none
)

# The DES route is only a real alternative if its steps are named.
DES_STEP_SEQUENCE = re.compile(
    r"po\s*/\s*design\s*/\s*oracle\s*/\s*craft\s*/\s*verify\s*/\s*integrate",
    re.IGNORECASE,
)

# Descriptive, never commanding -- kept decidable as a closed forbidden set.
# These were measured absent from today's published section, so this guard
# preserves the standing descriptive decision instead of inventing a new one.
COMMANDING_PHRASES = (
    "you must",
    "must route",
    "always route",
    "never bypass",
    "mandatory",
    "is required",
    "do not work directly",
)

# The section is an INDEX with an enforced size ceiling. The route-choice block
# is spent from that budget, never on top of it.
INDEX_BUDGET_BYTES = 4096

# The identical fragment bytes also ship into the Codex host's AGENTS.md, where
# slash-command and Skill-tool prose is forbidden. Host-specific tokens in the
# block would therefore break that host.
HOST_SPECIFIC_TOKENS = ("/nw-", "skill tool")


# --- What DECIDES the route -------------------------------------------------
#
# Authority: docs/product/architecture/brief.md#The Index States What Decides
# the Route. nWave/skills/nw-auto/SKILL.md section 6 remains the sole OWNER of
# the criterion; the published block only PROJECTS two of its factors into the
# agent's first-encounter position. Nothing below reads that skill file: this
# oracle only ever questions published bytes.

# Factor (a): what the Request has to leave behind once the session ends.
# Measured NON-discriminating on its own -- today's block already says "what
# survives it" and "outlive the session" -- so it is never the sole assertion.
LEAVE_BEHIND_TOKENS = ("leave behind", "survives", "outlive")

# Factor (b): the cost of a late refusal, because review and integration happen
# once per Request. Measured ABSENT from today's block: the load-bearing token.
LATE_REFUSAL_TOKENS = ("late refusal", "refused late", "refusal arrives late")

# Size is VISIBLY not the criterion. Stated as a sentence-level predicate rather
# than a token count: deleting the size mention would also satisfy a count, but
# the observation needs the denial to be READABLE.
SIZE_TOKENS = ("size", "s/m/l", "how big", "small request")
DENIAL_WORDS = re.compile(r"\b(not|never|no)\b", re.IGNORECASE)

# Working directly stays an available answer, so the correction cannot become a
# silent push toward the method.
STILL_OPEN_TOKENS = ("legitimate", "remains open")

SENTENCE_SPLIT = re.compile(r"(?<=[.;:!?])\s+|\n")


def sentences_of(text: str) -> tuple[str, ...]:
    """The published block cut into sentences, as a reader meets them."""
    return tuple(s.strip() for s in SENTENCE_SPLIT.split(text) if s.strip())


class InstalledGuidance:
    """The CLAUDE.md a real agent reads after nWave was installed.

    Constructed only by running the real CLI against a real directory, so every
    question below is answered about published bytes.
    """

    @classmethod
    def produced_by_enabling_nwave_in(cls, project_dir: Path) -> InstalledGuidance:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(REPO_ROOT)
        env["HOME"] = str(project_dir / "home")
        (project_dir / "home").mkdir(parents=True, exist_ok=True)

        result = subprocess.run(
            [sys.executable, "-m", "nwave_ai.cli", "project", "enable", "--yes"],
            cwd=str(project_dir),
            env=env,
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, (
            "enabling nWave in a project failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

        guidance_file = project_dir / "CLAUDE.md"
        assert guidance_file.exists(), (
            "nWave was enabled but wrote no CLAUDE.md for the agent to read.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        return cls(guidance_file.read_text(encoding="utf-8"))

    def __init__(self, published_text: str) -> None:
        self._published_text = published_text

    def managed_section(self) -> str:
        """The marker-bounded block nWave owns -- the only bytes it publishes."""
        begin = self._published_text.find(BEGIN_MARKER)
        end = self._published_text.find(END_MARKER, begin)
        assert begin != -1 and end != -1, (
            "the published CLAUDE.md carries no managed nWave section; the agent "
            "starting a Request meets no route choice at all"
        )
        return self._published_text[begin + len(BEGIN_MARKER) : end].strip()

    def section_body(self) -> str:
        """Everything after the section heading -- what the agent reads in order."""
        section = self.managed_section()
        heading_at = section.find(SECTION_HEADING)
        assert heading_at != -1, (
            f"the managed section carries no '{SECTION_HEADING}' heading"
        )
        heading_line_end = section.find("\n", heading_at)
        assert heading_line_end != -1, "the section heading has no body after it"
        return section[heading_line_end + 1 :].strip()

    def opening_paragraph(self) -> str:
        """The first thing the agent reads under the heading."""
        return self.section_body().split("\n\n", 1)[0].strip()

    def route_choice_block(self) -> str:
        """The opening run of prose, up to and including the sentence that names
        the choice. Defined by the published text itself, never by a designation."""
        body = self.section_body()
        lowered = body.lower()
        closes_at = lowered.find(CHOICE_SENTENCE_MARKER)
        assert closes_at != -1, (
            "the section never names the choice itself, so bypassing the method "
            f"stays unnoticed; expected a sentence containing "
            f"'{CHOICE_SENTENCE_MARKER}'"
        )
        paragraph_end = body.find("\n\n", closes_at)
        return (body if paragraph_end == -1 else body[:paragraph_end]).strip()

    def text_before_the_affordance_table(self) -> str:
        body = self.section_body()
        table_at = body.find(AFFORDANCE_TABLE_ROW)
        assert table_at != -1, (
            f"the section carries no affordance table row '{AFFORDANCE_TABLE_ROW}'"
        )
        return body[:table_at]


@pytest.fixture()
def project_dir(tmp_path: Path) -> Path:
    workspace = tmp_path / "some-user-project"
    workspace.mkdir()
    return workspace


def test_installed_guidance_meets_the_route_choice_first(project_dir: Path) -> None:
    """An agent starting a Request meets the route choice before anything else,
    stated as a choice with consequences and never as a command."""
    guidance = InstalledGuidance.produced_by_enabling_nwave_in(project_dir)

    block = guidance.route_choice_block()
    lowered_block = block.lower()

    # 1. FIRST-ENCOUNTERED -- the body OPENS with the route choice. The opening
    #    paragraph must already be about routes, not orientation prose that the
    #    agent reads before learning a choice exists.
    opening = guidance.opening_paragraph().lower()
    assert any(route in opening for route in ROUTE_NAMES), (
        "the nWave section does not OPEN with the route choice; the agent reads "
        "something else first, so the choice is not what it meets at the start of "
        f"a Request. Opening paragraph was:\n{guidance.opening_paragraph()}"
    )

    # 2. ...and all three routes are named before the affordance table, which is
    #    where the agent would otherwise start picking a command.
    before_table = guidance.text_before_the_affordance_table().lower()
    for route in ROUTE_NAMES:
        assert route in before_table, (
            f"the route '{route}' is never named before the affordance table, so "
            "the agent chooses among commands without knowing the routes exist"
        )

    # 3. NAMED WITH CONSEQUENCES -- a choice without stakes is not a choice.
    for consequence in ROUTE_CONSEQUENCES:
        assert consequence in lowered_block, (
            f"the route-choice block never states '{consequence}', so the agent "
            "cannot tell what each route costs or buys"
        )
    assert DES_STEP_SEQUENCE.search(block), (
        "the DES route does not name its steps (po/design/oracle/craft/verify/"
        "integrate), so it is not a route the agent can actually take"
    )

    # 4. THE CHOICE IS RECORDED -- the block closes by asking which route this
    #    Request takes, so bypassing the method is a stated choice.
    assert "say which one" in lowered_block, (
        "the block never asks the agent to say which route this Request takes, so "
        "bypassing the method stays an unnoticed omission"
    )

    # 5. DESCRIPTIVE, NEVER COMMANDING -- across the whole published section.
    lowered_section = guidance.managed_section().lower()
    for phrase in COMMANDING_PHRASES:
        assert phrase not in lowered_section, (
            f"the published section commands the route via '{phrase}'; the block "
            "is guidance, not a gate"
        )

    # 6. HOST-NEUTRAL -- the same block bytes ship into the Codex host.
    for token in HOST_SPECIFIC_TOKENS:
        assert token not in lowered_block, (
            f"the route-choice block carries host-specific token '{token}'"
        )

    # 7. The INDEX budget is never raised to make room for the block.
    section_bytes = len(guidance.managed_section().encode("utf-8"))
    assert section_bytes <= INDEX_BUDGET_BYTES, (
        f"the published section is {section_bytes} bytes, over the INDEX budget "
        f"of {INDEX_BUDGET_BYTES}; trim content rather than raise the budget"
    )


def test_the_block_names_what_decides_the_route(project_dir: Path) -> None:
    """An agent reading the shipped route-choice block sees the route decided by
    what the Request must leave behind and by what a late refusal would cost,
    sees that the Request's size is visibly NOT that criterion, and can still
    choose to work directly -- while the block commands no route and the INDEX
    stays within its existing byte budget.

    This constructs its own throwaway project through the same real port, so it
    shares no state with the first observation.
    """
    guidance = InstalledGuidance.produced_by_enabling_nwave_in(project_dir)

    block = guidance.route_choice_block()
    lowered_block = block.lower()

    # 1. The criterion is stated with BOTH factors. Leave-behind alone separates
    #    nothing (today's bytes already carry it), so the late-refusal cost must
    #    stand beside it for the criterion to be readable at all.
    assert any(token in lowered_block for token in LEAVE_BEHIND_TOKENS), (
        "the route-choice block never names what this Request has to leave "
        f"behind, one of the two deciding factors. Block was:\n{block}"
    )
    assert any(token in lowered_block for token in LATE_REFUSAL_TOKENS), (
        "the route-choice block never names what a LATE REFUSAL would cost, so "
        "the agent reads no reason why review and integration happening once "
        f"per Request bears on the route. Block was:\n{block}"
    )

    # 2. SIZE IS VISIBLY NOT THE CRITERION -- every sentence that raises size
    #    must, in the same breath, tie it to the route and deny it. Silently
    #    dropping the size mention does not satisfy this: the denial has to be
    #    there to be read.
    size_sentences = [
        sentence
        for sentence in sentences_of(block)
        if any(token in sentence.lower() for token in SIZE_TOKENS)
    ]
    assert size_sentences, (
        "the block never mentions the Request's size, so an agent carrying the "
        "size-to-route assumption meets nothing that contradicts it; size must "
        f"be VISIBLY denied, not omitted. Block was:\n{block}"
    )
    for sentence in size_sentences:
        lowered_sentence = sentence.lower()
        assert "route" in lowered_sentence and DENIAL_WORDS.search(sentence), (
            "a sentence pairs the Request's size with the route without denying "
            "that size decides it, so the block still reads as a size-to-route "
            f"rule. Sentence was:\n{sentence}"
        )

    # 3. WORKING DIRECTLY STAYS OPEN -- naming the criterion must not turn the
    #    block into a push toward the method.
    assert any(
        "working directly" in sentence.lower()
        and any(token in sentence.lower() for token in STILL_OPEN_TOKENS)
        for sentence in sentences_of(block)
    ), (
        "no sentence keeps working directly open as an available answer, so "
        "naming the criterion reads as a push toward the method. Block was:\n"
        f"{block}"
    )

    # 4. STILL DESCRIPTIVE, NEVER COMMANDING -- the standing guard, across the
    #    whole published section, unchanged by this correction.
    lowered_section = guidance.managed_section().lower()
    for phrase in COMMANDING_PHRASES:
        assert phrase not in lowered_section, (
            f"the published section commands the route via '{phrase}'; naming "
            "what decides the route must not add a gate"
        )

    # 5. HOST-NEUTRAL -- the identical bytes ship into the Codex host's
    #    AGENTS.md, published by this same single invocation.
    agents_file = project_dir / "AGENTS.md"
    assert agents_file.exists(), (
        "enabling nWave published no AGENTS.md, so the Codex host's agent meets "
        "no route criterion at all"
    )
    agents_text = agents_file.read_text(encoding="utf-8")
    assert block in agents_text, (
        "the corrected route-choice block does not reach AGENTS.md byte for "
        "byte, so the two hosts state different criteria for the same Request"
    )
    for token in HOST_SPECIFIC_TOKENS:
        assert token not in lowered_block, (
            f"the route-choice block carries host-specific token '{token}'"
        )

    # 6. The INDEX budget is spent from, never raised.
    section_bytes = len(guidance.managed_section().encode("utf-8"))
    assert section_bytes <= INDEX_BUDGET_BYTES, (
        f"the published section is {section_bytes} bytes, over the INDEX budget "
        f"of {INDEX_BUDGET_BYTES}; trim prose rather than raise the budget"
    )


if __name__ == "__main__":
    # The declared invocation is `python <this file>`. Running the module must
    # EXECUTE the observation, not merely define it, so the exit status carries
    # the verdict: 0 only when the published guidance meets the route choice
    # first, non-zero otherwise.
    sys.exit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
