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
    from des.application.delivery_state import DeliveryState, SelectionView
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
            f"oracle {value.oracle}",
            f"craft {value.craft}",
        )
    )


def _typed_facts_rows(facts: DesignFacts) -> list[str]:
    """The bound typed facts, as the table the terminals already name them by."""
    targets = ", ".join(f"`{t.path}` ({t.decision})" for t in facts.targets)
    supports = ", ".join(f"`{path}`" for path in facts.acceptance_supports)
    verification = "; ".join(" ".join(argv) for argv in facts.verification)
    rows = [
        "The bound design facts below describe this value's declared acceptance work.",
        "",
        "| Fact | Value |",
        "| --- | --- |",
        f"| PARADIGM | {facts.paradigm} |",
        f"| ORACLE | `{facts.oracle}` |",
        f"| TARGETS | {targets} |",
    ]
    if facts.authority_locator:
        rows.append(f"| AUTHORITY LOCATOR | `{facts.authority_locator}` |")
    if supports:
        rows.append(f"| SUPPORTS | {supports} |")
    rows.append(f"| VERIFICATION | `{verification}` |")
    rows.append("")
    return rows


def _command(argv: tuple[str, ...]) -> str:
    return " ".join(argv)


def _selection_rows(selection: SelectionView) -> list[str]:
    """One value's selected tuple with its source, labelled and never merged.

    Opens with one plain sentence before the table.  A selection whose facts are
    not derivable says so with the DES HOW and shows what was kept; nothing here
    is a new authority, every cell is read from the handover.
    """
    lines = [
        "The selected acceptance revision below is the one tuple every role "
        f"and the verification read; its source is {selection.source}.",
        "",
        "| Selected | Value |",
        "| --- | --- |",
        f"| SELECTED STATE | {selection.label} |",
        f"| SELECTED ORACLE | `{selection.oracle}` |",
    ]
    if selection.supports:
        lines.append(
            "| SELECTED SUPPORTS | "
            + ", ".join(f"`{path}`" for path in selection.supports)
            + " |"
        )
    if selection.verification is not None:
        lines.append(
            "| SELECTED VERIFICATION | "
            + "; ".join(f"`{_command(argv)}`" for argv in selection.verification)
            + f" (oracle command index {selection.oracle_verification_index}) |"
        )
    lines.append("")
    if selection.how is not None:
        lines += [f"Uncertain: repair with `{selection.how}`.", ""]
    return lines


def _evidence_section(state: DeliveryState) -> list[str]:
    lines = [
        "## Verification evidence",
        "",
        "Each retained native observation is labelled by what it was measured "
        "over; kept bytes are never deleted, and only one labelled current "
        "covers the graph as it stands.",
        "",
    ]
    if not state.evidence:
        return [
            *lines,
            "Verification evidence is absent: nothing was verified yet.",
            "",
        ]
    lines += ["| Evidence | State | SHA-256 |", "| --- | --- | --- |"]
    lines += [
        f"| `{row.locator}` | {row.label} | `{row.sha256}` |" for row in state.evidence
    ]
    return [*lines, ""]


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
        selection = state.values[position - 1].selection
        if selection is not None:
            lines += _selection_rows(selection)
    lines += _evidence_section(state)
    return "\n".join(lines)
