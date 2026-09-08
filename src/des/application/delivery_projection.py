"""Project the owned delivery state into the document a HUMAN reads.

`docs/architecture/adr-ssot-document-model.md`, «Feature Brief — The Human
Layer»: «The SSOT files serve agents. The delta files serve the delivery
pipeline. Neither is designed for human consumption.»  The handover and the
typed design facts are exactly that.  A person deciding between an interactive
and an autonomous session reads neither happily, and `des state` -- the textual
projection -- is written for the orchestrating model, not for them.

`docs/product/architecture/ADR-BOARD-001-shared-slice-state-projection.md` fixes
what this may be: «The shared slice-state model is a projection function, never
a fourth persisted store», recomputed on every read.  So this module is a
function of the two owned facts and holds nothing.  The same state renders the
same document, and rendering it changes no byte the delivery owns.

NO NEW CONTENT, and that is a hard rule rather than a preference.  Every line
below is either a label the step terminals already print or a value read
verbatim from the owned state.  A projection that adds a sentence is a second
authority in prose, which is the drift `adr-ssot-document-model` exists to stop.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from des.application.delivery_state import DeliveryState
    from des.application.handover import StoredHandover
    from des.ports.driven_ports.task_invocation_port import DesignFacts


def _fence(text: str) -> list[str]:
    """One verbatim block, so a Request carrying markdown is SHOWN, not parsed.

    A Request is prose a human wrote and may contain anything -- a heading, a
    table, a stray backtick.  Rendering it as markdown would let the source
    restyle the projection, and the reader could no longer tell the page's own
    structure from the Request's.
    """
    return ["```", *text.splitlines(), "```", ""]


def _carried(state: DeliveryState, position: int) -> str:
    value = state.values[position - 1]
    return " · ".join(
        (
            f"design {'bound' if value.design_bound else 'absent'}",
            f"oracle {'recorded' if value.oracle_recorded else 'absent'}",
            f"craft {'recorded' if value.craft_recorded else 'absent'}",
        )
    )


def _typed_facts_rows(facts: DesignFacts) -> list[str]:
    """The bound typed facts, as the table the terminals already name them by."""
    targets = ", ".join(f"`{t.path}` ({t.decision})" for t in facts.targets)
    supports = ", ".join(f"`{path}`" for path in facts.acceptance_supports)
    verification = "; ".join(" ".join(argv) for argv in facts.verification)
    rows = [
        "| Fact | Value |",
        "| --- | --- |",
        f"| PARADIGM | {facts.paradigm} |",
        f"| ORACLE | `{facts.oracle}` |",
        f"| TARGETS | {targets} |",
    ]
    if supports:
        rows.append(f"| SUPPORTS | {supports} |")
    rows.append(f"| VERIFICATION | `{verification}` |")
    rows.append("")
    return rows


def project_markdown(stored: StoredHandover, state: DeliveryState) -> str:
    """The human layer of ONE Request, as markdown the shared renderer accepts.

    Markdown rather than HTML because the renderer that already exists takes
    markdown, carries the nWave palette and its dark mode, and is the one answer
    in this repository to "what does an nWave document look like".  Emitting
    HTML here would be a second stylesheet and a second answer.
    """
    lines: list[str] = ["# Delivery state", "", "## Request", ""]
    lines += _fence(stored.request)
    lines += ["## Values", ""]
    for position, value in enumerate(stored.values, start=1):
        lines += [f"### Value {position} — {_carried(state, position)}", ""]
        lines += _fence(value.observation)
        if value.dependencies:
            positions = {
                item.observation: index
                for index, item in enumerate(stored.values, start=1)
            }
            lines += [
                "Depends on: "
                + ", ".join(f"value {positions[d]}" for d in value.dependencies),
                "",
            ]
        authority = value.authority
        if authority is None:
            lines += ["No design facts are bound to this value yet.", ""]
        elif isinstance(authority, str):
            lines += [f"Authority cited: `{authority}`", ""]
        else:
            lines += _typed_facts_rows(authority)
    return "\n".join(lines)
