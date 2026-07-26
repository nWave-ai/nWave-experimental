"""Regression ATs -- fix-examiner-blindness-enforced.

RCA: docs/feature/fix-examiner-blindness-enforced/rca.md (root causes A + C + D).

THE DEFECT. `des dispatch` tells the reader of a NON-CODE-FACING envelope that
the dispatched agent has no source / design / acceptance-test access "BY
CONSTRUCTION" (`src/des/cli/dispatch.py:462-465` `_EXAMINER_SKILL_LOADING`;
`:499-502` `_NON_CODE_FACING_DESIGN_CONTEXT`). Nothing enforces that. The
single predicate all five claim sites consult (`_NON_CODE_FACING_AGENTS`,
`dispatch.py:218-220`) is a frozenset of agent NAMES -- it is never computed
from what the agent can actually DO. The examiner's own declared capability
(`nWave/agents/nw-user-examiner.md:6` -> `tools: Read, Edit, Bash, ...`) grants
unrestricted `Read` and `Bash`; `cat src/...` is one command away. The
guarantee is by INSTRUCTION, published as by CONSTRUCTION -- and "by
construction" is precisely the instruction to the orchestrator to STOP
verifying (RCA branch D). Five examinations were invalidated in one day by
verdicts reached from reading implementation.

WHAT THESE ATs PIN -- the RELATIONSHIP, never a string. An AT asserting "some
particular sentence appears in the envelope" is a SHAPE assertion: it passes
against a capability wired wrong, and it is exactly the class of guard that let
this defect live (RCA root cause C -- "the validation suite verifies
text-to-text consistency, never text-to-capability"; the incumbent AT
`tests/bugs/des/test_dispatch_lane_for_non_code_facing_agents.py:610` quotes the
literal verbatim and contains ZERO reference to the agent's `tools:`). These ATs
instead pin that the REGISTER of the envelope's claim is DERIVED from the
agent's declared capability, so the claim and the capability cannot disagree:

  R1 ENFORCED    -- declared tools grant NO source-reaching capability. Only
                    here MAY the envelope use an absolute ("by construction" /
                    "cannot read" / "guaranteed").
  R2 INSTRUCTED  -- the role is non-code-facing by INTENT, but its declared
                    tools DO grant a source-reaching capability. The envelope
                    must speak in the honest register (instructed, not
                    prevented) AND name a concrete way for the reader to
                    confirm it. This is the examiner's ACTUAL state today.
  R3 UNKNOWN     -- the agent's spec cannot be parsed. The envelope must say
                    plainly that the capability could not be determined; it
                    must NOT print a confident guarantee and must NOT silently
                    degrade to the permissive R1 wording. "I looked and she is
                    blind" and "I never looked" must not produce the same
                    sentence.

The capability is supplied as a FIXTURE (a temp checkout carrying
`nWave/agents/<agent>.md` with a chosen `tools:` frontmatter line) and the
envelope's register is asserted to CHANGE with it. The examiner's current tool
list is never hardcoded as the expected input -- the tests parametrize (and
property-generate) over capability SHAPES, so they still bind when someone edits
her frontmatter. When real enforcement later lands (a PreToolUse deny hook --
explicitly OUT of this slice's breadth), the SAME derivation simply starts
reporting R1 and not one line of this file needs to change.

DRIVING SURFACE (Mandate-16 / driving-port-only). The real `des dispatch` CLI
entry `des.cli.dispatch.main(argv)`, driven IN-PROCESS (L2 default -- no
interpreter fork), output captured at the stdout boundary. No production
internal (`_NON_CODE_FACING_AGENTS`, `_section_body`, ...) is imported or
asserted on: those are the implementation this fix is free to reshape. The
second surface is the SHIPPED agent-spec corpus (`nWave/agents/*.md`) read as
data -- the published role description must not contradict the envelope.

RED-not-BROKEN (Mandate 7): every module-level import names a stable, present
entry; the missing behaviour surfaces as a semantic `AssertionError` inside the
in-process call, never an import/collection error.

covers: fix-examiner-blindness-enforced (RCA root causes A, C, D -- the claim
register is not derived from the declared capability, no gate compares a CLAIM
to a FACT, and no vocabulary separates "instructed not to" from "unable to").
"""

from __future__ import annotations

import contextlib
import io
import re
import shutil
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from des.cli import dispatch


# tests/bugs/des/<this file> -> parents[3] == checkout root (same resolution
# style as the sibling `test_dispatch_lane_for_non_code_facing_agents.py`).
_REPO_ROOT = Path(__file__).resolve().parents[3]

#: Fixed so two envelopes rendered under two different capabilities differ ONLY
#: in what the capability changed (a differential/metamorphic comparison needs a
#: constant everything-else).
_FEATURE_ID = "probe-blindness-claim"


# ---------------------------------------------------------------------------
# Driving port -- the real `des dispatch` CLI, in-process.
# ---------------------------------------------------------------------------


def _run_dispatch_main(argv: list[str]) -> tuple[int, str, str]:
    """Drive `des dispatch`'s real `main()` in-process; capture exit/stdout/stderr.

    `argparse` raises `SystemExit` for a usage error -- caught so a test body
    asserts on an observed exit code rather than crashing with `SystemExit`.
    """
    stdout_buf, stderr_buf = io.StringIO(), io.StringIO()
    try:
        with (
            contextlib.redirect_stdout(stdout_buf),
            contextlib.redirect_stderr(stderr_buf),
        ):
            exit_code = dispatch.main(argv)
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else 1
    return exit_code, stdout_buf.getvalue(), stderr_buf.getvalue()


# ---------------------------------------------------------------------------
# Capability fixtures -- an agent spec whose `tools:` line we choose.
# ---------------------------------------------------------------------------

#: Tools that unambiguously REACH SOURCE. Deliberately narrow: `Edit`, `Write`
#: and `Task` are excluded from every generated/parametrized set below because
#: their classification is a judgement call this AT must not pre-empt (an
#: implementer may reasonably rule either way). Every case here is one no
#: reasonable implementation can classify differently.
_SOURCE_REACHING_TOOLS = ("Read", "Bash", "Grep", "Glob")

#: Tools that reach only the running product / the web -- never the tree.
_NON_SOURCE_REACHING_TOOLS = (
    "WebFetch",
    "WebSearch",
    "mcp__playwright__browser_navigate",
    "mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_click",
)

_TOOL_VOCABULARY = (*_SOURCE_REACHING_TOOLS, *_NON_SOURCE_REACHING_TOOLS)


def _grants_source_access(tools: tuple[str, ...] | list[str]) -> bool:
    return any(tool in _SOURCE_REACHING_TOOLS for tool in tools)


def _agent_spec_text(
    agent: str,
    *,
    tools: tuple[str, ...] | list[str] | None,
    frontmatter: bool = True,
) -> str:
    """Render a minimal, well-formed agent spec.

    `tools=None` omits the `tools:` key entirely; `frontmatter=False` produces a
    spec with no frontmatter delimiters at all (the unparseable case).
    """
    body = f"# {agent}\n\nA role body with no capability claim of its own.\n"
    if not frontmatter:
        return body
    lines = [
        "---",
        f"name: {agent}",
        "description: A dispatch-fixture agent spec.",
        "model: haiku",
    ]
    if tools is not None:
        lines.append("tools: " + ", ".join(tools))
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body


@pytest.fixture(scope="session")
def fixture_checkout(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A minimal CHECKOUT the dispatch CLI accepts via `--repo-root`.

    Carries the REAL dispatch SSOT (`nWave/dispatch/*.yaml`, copied -- never
    re-implemented) so `main()` renders a real envelope, plus an `nWave/agents/`
    directory whose specs each test writes to choose the declared capability.
    A checkout the generator is explicitly POINTED AT is the first of the two
    candidate roots for an agent spec (RCA 5(c): `<repo>/nWave/agents/<agent>.md`,
    then `<claude_dir>/agents/nw/<agent>.md`) -- a resolver that ignores the
    checkout it was handed cannot be capability-derived in a dev tree at all.
    """
    root = tmp_path_factory.mktemp("blindness-claim-checkout")
    (root / "nWave" / "dispatch").mkdir(parents=True)
    (root / "nWave" / "agents").mkdir(parents=True)
    for asset in ("atdd_pure.yaml", "vendors.yaml"):
        shutil.copyfile(
            _REPO_ROOT / "nWave" / "dispatch" / asset,
            root / "nWave" / "dispatch" / asset,
        )
    # The C_REVIEWER_AUDIT slot is EVIDENCE-armed: the user examiner is
    # dispatched because a charter promises an outcome for this slice, never
    # because the phase happens to be named after a review.  Without one the
    # CLI refuses OUT LOUD (it does not silently hand the slot to the technical
    # reviewer), so a checkout that means to render an examiner envelope must
    # carry the charter that arms it.
    charter_dir = root / "docs" / "product" / "expectations" / _FEATURE_ID
    charter_dir.mkdir(parents=True)
    (charter_dir / "slice-01-charter.md").write_text(
        f"# Expectation charter -- {_FEATURE_ID} slice-01\n\n"
        "Spec rows: slice-01\n\n"
        "Promised outcome: the dispatch envelope states its access register "
        "honestly.\n",
        encoding="utf-8",
    )
    return root


def _render_envelope(
    checkout: Path,
    *,
    agent: str,
    extra_argv: list[str],
    spec_text: str,
) -> str:
    """Install `spec_text` as `<checkout>/nWave/agents/<agent>.md`, then render
    the dispatch envelope for that agent through the real CLI."""
    (checkout / "nWave" / "agents" / f"{agent}.md").write_text(
        spec_text, encoding="utf-8"
    )
    exit_code, stdout, stderr = _run_dispatch_main(
        [
            "--mode",
            "atdd_pure",
            "--project-id",
            _FEATURE_ID,
            "--slice",
            "slice-01",
            *extra_argv,
            "--repo-root",
            str(checkout),
        ]
    )
    assert exit_code == 0, (
        f"the dispatch CLI must render an envelope for {agent} (exit "
        f"{exit_code}). stderr={stderr!r}"
    )
    return stdout


# ---------------------------------------------------------------------------
# The register oracle -- three mutually exclusive ways to speak about access.
# ---------------------------------------------------------------------------

#: An ABSOLUTE claim: an assertion of INCAPACITY, not of instruction. Each
#: pattern is guarded against a negated form ("not by construction", "never
#: guaranteed") so an honest sentence that mentions the absolute in order to
#: DENY it is not mistaken for making it.
_ABSOLUTE_CLAIM_PATTERNS: tuple[tuple[str, str], ...] = (
    ("by-construction", r"(?<!not )(?<!never )(?<!NOT )by construction"),
    ("structurally-X", r"structurally (?:excluded|impossible|prevented|blocked)"),
    ("cannot-reach", r"cannot (?:read|access|reach|see|open|inspect)"),
    ("unable-to-reach", r"unable to (?:read|access|reach|see|open|inspect)"),
    ("guaranteed", r"(?<!not )(?<!never )\bguaranteed\b"),
    ("impossible", r"(?<!not )(?<!never )\bimpossible\b"),
)

#: The HONEST (instructed-not-prevented) register.
_INSTRUCTED_REGISTER_PATTERNS: tuple[str, ...] = (
    r"instructed",
    r"not enforced",
    r"unenforced",
    r"not prevented",
    r"is not a guarantee",
    r"declared (?:tools|capability|capabilities)",
    r"role intent",
    r"by intent",
)

#: A FALSIFIABLE pointer -- a concrete place the reader can go to check the
#: claim for themselves. Fog ("trust the role boundary") is a FAIL: the whole
#: point of the honest register is that it leaves the reader able to verify.
_VERIFICATION_POINTER_PATTERNS: tuple[str, ...] = (
    r"agents/[\w.\-]+\.md",
    r"tools:",
    r"frontmatter",
)

#: The UNKNOWN register -- "I never looked", said plainly.
_UNKNOWN_REGISTER_PATTERNS: tuple[str, ...] = (
    r"could not (?:be )?(?:determined|read|resolved|verified|parsed)",
    r"cannot (?:be )?(?:determined|resolved|verified|parsed)",
    r"undetermined",
    r"not determined",
    r"unknown",
    r"unverified",
    r"indeterminate",
)


def _sections(envelope: str) -> dict[str, str]:
    """Split a rendered envelope into `{SECTION_ID: body}`.

    The envelope's section headers are `# SECTION_ID` lines (dispatch
    `_build_prompt`); everything before the first header is the marker block.
    """
    parts = re.split(r"^# ([A-Z_]+)\s*$", envelope, flags=re.MULTILINE)
    return {parts[index]: parts[index + 1] for index in range(1, len(parts) - 1, 2)}


def _absolute_claims(text: str) -> list[str]:
    """Every absolute-register claim in `text`, as `<pattern-id>: <match>`."""
    found: list[str] = []
    for label, pattern in _ABSOLUTE_CLAIM_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            found.append(f"{label}: {match.group(0)!r}")
    return found


def _absolute_claims_by_section(envelope: str) -> dict[str, list[str]]:
    return {
        section: claims
        for section, body in _sections(envelope).items()
        if (claims := _absolute_claims(body))
    }


def _matches_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)


# ---------------------------------------------------------------------------
# The dispatches under test -- every NON-CODE-FACING role the generator can
# emit, so the fix is proven CLASS-level and not examiner-special-cased. Both
# reach the same single predicate (`_NON_CODE_FACING_AGENTS`) and therefore all
# five of its claim sites (skill-loading, design-context, quality-gates,
# terminating-run, timeout-instruction -- RCA 5(c)).
# ---------------------------------------------------------------------------

_NON_CODE_FACING_DISPATCHES = (
    pytest.param(
        "nw-user-examiner",
        ["--phase", "C_REVIEWER_AUDIT", "--intent", "examine slice-01"],
        id="examiner-examine-phase",
    ),
    pytest.param(
        "nw-product-owner",
        ["--lane", "charter", "--intent", "author the charter for slice-01"],
        id="product-owner-charter-lane",
    ),
)

_SOURCE_GRANTING_SHAPES = (
    pytest.param(("Read", "Edit", "Bash"), id="read-edit-bash"),
    pytest.param(("Bash",), id="bash-only"),
    pytest.param(("Read",), id="read-only"),
    pytest.param(("Grep", "Glob"), id="grep-glob"),
    pytest.param(
        ("Read", "mcp__playwright__browser_navigate"),
        id="read-plus-browser",
    ),
)

_BLIND_SHAPES = (
    pytest.param(
        ("mcp__playwright__browser_navigate", "mcp__playwright__browser_click"),
        id="browser-only",
    ),
    pytest.param(("WebFetch", "WebSearch"), id="web-only"),
    pytest.param((), id="no-tools-at-all"),
)


class TestClaimRegisterDerivesFromDeclaredCapability:
    """R2 -- a source-reaching capability forbids the absolute register."""

    @pytest.mark.negative_at
    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    @pytest.mark.parametrize("tools", _SOURCE_GRANTING_SHAPES)
    def test_envelope_never_claims_an_absolute_when_declared_tools_reach_source(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
        tools: tuple[str, ...],
    ) -> None:
        """NEGATIVE AT (the sharp one). An absolute claim in the R2 case is a
        FAILURE -- so this asserts the absolute is ABSENT, never merely that
        some new honest string is present. Scanned over the WHOLE rendered
        envelope, not one section: this claim class is known to RELOCATE rather
        than disappear (the same RCA's predecessor fix moved the false phase out
        of the marker block and it reappeared inside the section bodies), and
        the one predicate feeds FIVE consumers.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=tools),
        )
        offenders = _absolute_claims_by_section(envelope)
        assert not offenders, (
            f"{agent} declares tools {list(tools)}, which GRANT source access "
            f"({[t for t in tools if t in _SOURCE_REACHING_TOOLS]}) -- the "
            "envelope must therefore speak in the INSTRUCTED register, never "
            "assert an absolute. Absolute claims found per section: "
            f"{offenders}. 'By construction' is the instruction to the "
            "orchestrator to stop verifying; asserting it over an unenforced "
            "constraint is the defect (RCA fix-examiner-blindness-enforced, "
            "root cause D)."
        )

    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    @pytest.mark.parametrize("tools", _SOURCE_GRANTING_SHAPES)
    def test_envelope_states_the_instructed_register_with_a_falsifiable_pointer(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
        tools: tuple[str, ...],
    ) -> None:
        """R2 positive leg -- and the anti-fog guard. Merely DELETING the claim,
        or hedging into something unverifiable, is a FAIL: the honest register
        must both (a) name the register (instructed / not enforced / declared
        capability) and (b) leave the reader a concrete place to CHECK (the
        agent spec path, its `tools:` field, its frontmatter). A briefing the
        reader cannot falsify has replaced a false guarantee with fog.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=tools),
        )
        assert _matches_any(envelope, _INSTRUCTED_REGISTER_PATTERNS), (
            f"{agent}'s declared tools {list(tools)} reach source, so the "
            "envelope must NAME the honest register (one of "
            f"{list(_INSTRUCTED_REGISTER_PATTERNS)}) -- silently dropping the "
            "claim leaves the reader with no register at all. Envelope:\n"
            f"{envelope}"
        )
        assert _matches_any(envelope, _VERIFICATION_POINTER_PATTERNS), (
            "the instructed register must be FALSIFIABLE: the envelope must "
            "name a concrete way to confirm the capability for oneself (one of "
            f"{list(_VERIFICATION_POINTER_PATTERNS)}). Fog is not honesty. "
            f"Envelope:\n{envelope}"
        )

    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    def test_claim_text_tracks_the_declared_capability_and_is_not_a_constant(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
    ) -> None:
        """THE RELATIONSHIP, stated as a differential. The exact same dispatch,
        rendered twice, differing ONLY in the agent's declared `tools:` line,
        must produce DIFFERENT claim prose. This is the assertion a shape-test
        cannot satisfy by accident: a hardcoded sentence is identical under both
        capabilities and fails here regardless of which words it uses.
        """
        blind = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(
                agent, tools=("mcp__playwright__browser_navigate",)
            ),
        )
        sighted = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=("Read", "Bash")),
        )
        assert blind != sighted, (
            "the envelope's claim about access must be DERIVED from the "
            f"declared capability: {agent} rendered with tools "
            "['mcp__playwright__browser_navigate'] (no source access) and with "
            "['Read', 'Bash'] (source access) produced BYTE-IDENTICAL prose -- "
            "so the claim is a constant, and the claim and the capability can "
            "disagree without anything noticing. That is the defect.\n"
            f"Envelope (identical under both capabilities):\n{blind}"
        )

    @settings(
        max_examples=40,
        deadline=None,
        suppress_health_check=[HealthCheck.function_scoped_fixture],
    )
    @given(
        tools=st.lists(
            st.sampled_from(_TOOL_VOCABULARY), unique=True, min_size=1, max_size=5
        )
    )
    def test_absolute_register_is_never_used_over_a_source_reaching_capability(
        self, fixture_checkout: Path, tools: list[str]
    ) -> None:
        """PROPERTY (the universal law behind the parametrized cases): over ANY
        declared tool set drawn from the unambiguous vocabulary, granting a
        source-reaching tool implies the envelope carries NO absolute claim.
        Property-generated rather than enumerated because the capability space
        is combinatorial and the defect is about the RELATION, not any one
        example -- a future edit to the examiner's frontmatter lands inside this
        space, not outside it.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent="nw-user-examiner",
            extra_argv=["--phase", "C_REVIEWER_AUDIT"],
            spec_text=_agent_spec_text("nw-user-examiner", tools=tools),
        )
        if _grants_source_access(tools):
            assert not _absolute_claims(envelope), (
                f"declared tools {tools} grant source access, yet the envelope "
                f"asserts {_absolute_claims(envelope)}"
            )


class TestUnknownCapabilityRegister:
    """R3 -- 'I never looked' must not sound like 'I looked and she is blind'."""

    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    def test_unparseable_agent_spec_reports_the_capability_as_undetermined(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
    ) -> None:
        """R3 positive leg. A spec with no frontmatter at all cannot yield a
        capability. The envelope must SAY SO plainly (degrade-LOUD, GDP-6) --
        an unreadable capability is an INDETERMINATE, never an inferred one.

        The unknown case is expressed as an UNPARSEABLE spec rather than a
        MISSING one on purpose: the resolver's second candidate is the installed
        `<claude_dir>/agents/nw/<agent>.md`, which legitimately exists on a
        machine with nWave installed -- so 'file absent' is not a hermetic way
        to reach R3, while 'found but unparseable' is, on any target machine.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=None, frontmatter=False),
        )
        assert _matches_any(envelope, _UNKNOWN_REGISTER_PATTERNS), (
            f"{agent}'s spec could not be parsed for a declared capability, so "
            "the envelope must state plainly that the capability could not be "
            f"determined (one of {list(_UNKNOWN_REGISTER_PATTERNS)}). Silence "
            "here is a false green: the reader cannot tell an unchecked claim "
            f"from a checked one. Envelope:\n{envelope}"
        )

    @pytest.mark.negative_at
    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    def test_unparseable_spec_never_degrades_to_the_permissive_absolute_wording(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
    ) -> None:
        """NEGATIVE AT. The R3 case must NOT print a confident guarantee. An
        undetermined capability that renders as 'no source access by
        construction' is strictly worse than the original defect: it launders an
        absence of evidence into evidence of absence.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=None, frontmatter=False),
        )
        offenders = _absolute_claims_by_section(envelope)
        assert not offenders, (
            f"{agent}'s capability could NOT be determined (unparseable spec) "
            f"yet the envelope asserts an absolute: {offenders}. Absence of "
            "evidence is not evidence of absence -- degrade LOUD."
        )

    @pytest.mark.negative_at
    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    def test_unknown_capability_does_not_produce_the_same_sentence_as_enforced(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
    ) -> None:
        """NEGATIVE AT -- the R3-vs-R1 discriminator. 'I looked and she is
        blind' (R1: declared tools grant nothing that reaches source) and 'I
        never looked' (R3: the spec would not parse) must not produce the same
        prose. If they do, the reader cannot distinguish a verified guarantee
        from an unverified one -- which is the whole defect, one layer down.
        """
        enforced = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(
                agent, tools=("mcp__playwright__browser_navigate",)
            ),
        )
        unknown = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=None, frontmatter=False),
        )
        assert enforced != unknown, (
            "an UNDETERMINED capability rendered byte-identically to a VERIFIED "
            f"no-source-access capability for {agent}: 'I looked and she is "
            "blind' and 'I never looked' must not be the same sentence.\n"
            f"Envelope (identical under both):\n{enforced}"
        )

    @pytest.mark.negative_at
    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    def test_a_spec_declaring_no_tools_key_is_not_read_as_an_enforced_blindness(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
    ) -> None:
        """NEGATIVE AT. A spec that OMITS `tools:` does not declare an empty
        capability -- in Claude Code an omitted `tools:` INHERITS the full tool
        set, i.e. maximally permissive. Whether the implementation calls that R2
        (inherits source access) or R3 (undetermined) is its choice; what it
        must NEVER do is read the omission as R1 and print an absolute.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=None),
        )
        offenders = _absolute_claims_by_section(envelope)
        assert not offenders, (
            f"{agent}'s spec declares NO `tools:` key (an omission that INHERITS "
            "every tool, not one that denies them all) yet the envelope asserts "
            f"an absolute: {offenders}."
        )


class TestWithholdingDoesNotRegress:
    """The trap in a naive derivation: deriving the ROUTING from capability
    would flip the examiner to code-facing today and start handing her design
    pointers. Routing/withholding stays keyed on ROLE INTENT; only the CLAIM
    REGISTER is derived. These pin the withholding under EVERY register.
    """

    #: Pointers a non-code-facing dispatch must never carry, whatever register
    #: its claim is in. The agent's own spec path (`nWave/agents/<x>.md`) is
    #: deliberately NOT in this set -- it is the verification pointer the honest
    #: register is required to name, and it points at a role declaration, never
    #: at implementation.
    _WITHHELD_POINTER_PATTERNS: tuple[tuple[str, str], ...] = (
        ("feature-delta", r"docs/feature/[\w.\-]+/feature-delta\.md"),
        ("source-tree", r"(?<![\w/])src/[\w./\-]+\.\w+"),
        ("test-tree", r"(?<![\w/])tests?/[\w./\-]+\.\w+"),
        ("gherkin-feature-file", r"[\w./\-]+\.feature\b"),
        ("architecture-brief", r"brief\.md"),
    )

    @pytest.mark.negative_at
    @pytest.mark.parametrize("agent,extra_argv", _NON_CODE_FACING_DISPATCHES)
    @pytest.mark.parametrize("tools", (*_SOURCE_GRANTING_SHAPES, *_BLIND_SHAPES))
    def test_non_code_facing_dispatch_never_carries_source_or_design_pointers(
        self,
        fixture_checkout: Path,
        agent: str,
        extra_argv: list[str],
        tools: tuple[str, ...],
    ) -> None:
        """NEGATIVE AT + non-regression pin. Under EVERY capability shape --
        including the R2 shape where the agent demonstrably CAN read source --
        the envelope carries ZERO pointers to source files, design documents or
        acceptance tests. Honesty about the claim must not become a licence to
        start routing implementation context to a role whose epistemic value is
        that it has not seen any.
        """
        envelope = _render_envelope(
            fixture_checkout,
            agent=agent,
            extra_argv=extra_argv,
            spec_text=_agent_spec_text(agent, tools=tools),
        )
        leaks = {
            label: matches
            for label, pattern in self._WITHHELD_POINTER_PATTERNS
            if (matches := re.findall(pattern, envelope))
        }
        assert not leaks, (
            f"{agent} is non-code-facing by ROLE INTENT regardless of declared "
            f"tools {list(tools)} -- withholding is keyed on intent, only the "
            f"CLAIM REGISTER is derived from capability. Leaked pointers: "
            f"{leaks}."
        )


class TestPublishedRoleDescriptionMatchesDeclaredCapability:
    """Same contract, second surface: the shipped agent spec must not contradict
    the envelope. `nWave/agents/nw-user-examiner.md` asserts 'cannot read source
    code' in its `description:` (line 3) and 'structurally excluded' in its body
    (line 30) -- both absolutes, 24 lines below the frontmatter that grants
    `Read` and `Bash`. One file contradicting itself is what let the claim
    accrue authority by repetition (RCA contributing factor 7).
    """

    #: Narrow on purpose: an absolute about THIS AGENT'S OWN access to source.
    #: Prose that merely contains 'by construction' about something else (e.g.
    #: `nw-acceptance-designer.md`'s "CLI = e2e by construction" note) is not a
    #: capability claim and must not be flagged.
    _SPEC_INCAPACITY_PATTERNS: tuple[tuple[str, str], ...] = (
        ("cannot-read-source", r"cannot read (?:production |the )?(?:source|code)"),
        ("structurally-excluded", r"structurally (?:excluded|impossible|prevented)"),
        (
            "access-by-construction",
            r"(?:source|design|code)[^.\n]{0,60}access (?<!not )by construction",
        ),
        ("unable-to-read-source", r"unable to read (?:production )?(?:source|code)"),
    )

    @staticmethod
    def _declared_tools(spec_text: str) -> list[str] | None:
        match = re.search(r"^tools:\s*(.+)$", spec_text, flags=re.MULTILINE)
        if match is None:
            return None
        return [tool.strip() for tool in match.group(1).split(",") if tool.strip()]

    @pytest.mark.negative_at
    @pytest.mark.parametrize(
        "spec_path",
        [
            pytest.param(path, id=path.stem)
            for path in sorted((_REPO_ROOT / "nWave" / "agents").glob("*.md"))
        ],
    )
    def test_agent_spec_never_asserts_an_incapacity_its_own_tools_contradict(
        self, spec_path: Path
    ) -> None:
        """NEGATIVE AT, over the WHOLE shipped corpus (not the examiner alone --
        the defect class is 'every restrictive claim about a role', and
        `_NON_CODE_FACING_AGENTS` auto-propagates to future roles). An agent
        whose declared tools grant source access must not carry an unbacked
        absolute in its description or body: the published role description must
        not contradict the envelope.
        """
        spec_text = spec_path.read_text(encoding="utf-8")
        tools = self._declared_tools(spec_text)
        if tools is None or not _grants_source_access(tools):
            pytest.skip(
                f"{spec_path.name} declares no source-reaching tool -- its "
                "absolutes (if any) are backed"
            )
        offenders = {
            label: [m.group(0) for m in re.finditer(pattern, spec_text, re.IGNORECASE)]
            for label, pattern in self._SPEC_INCAPACITY_PATTERNS
            if re.search(pattern, spec_text, re.IGNORECASE)
        }
        assert not offenders, (
            f"{spec_path.name} declares tools "
            f"{[t for t in tools if t in _SOURCE_REACHING_TOOLS]} -- which "
            "GRANT source access -- while its own text asserts a structural "
            f"incapacity: {offenders}. An unbacked absolute in a published role "
            "description is the same false guarantee the dispatch envelope "
            "carries, at a surface every reader trusts more."
        )
