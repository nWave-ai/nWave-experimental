"""The DESIGN section renders Markdown that a default markdownlint run accepts.

A consumer repository lints every Markdown file it tracks, so the section DESIGN
appends to its architecture authority must satisfy the default rule set with no
configuration: blank lines around every block, unique compiled-scope sub-headings,
catalog prose wrapped at 80 columns without creating markup, and escaped inline HTML.
"""

from __future__ import annotations

import copy
import json
import re
from itertools import pairwise

from des.domain.design_document import DesignDocument
from tests.des._helpers.host_facts import design_manifest


WIDTH = 80

MANIFEST: dict[str, object] = {
    "architectural_tests": {
        "applicability": "not_applicable",
        "reason": "The fixture has no structural boundary change.",
    },
    "contract_tests": {
        "applicability": "not_applicable",
        "reason": "The fixture changes no shared contract.",
    },
    "purpose": "Expose the selected widget color.",
    "constraints": ["Preserve existing callers."],
    "targets": [
        {
            "path": "src/widget.py",
            "decision": "EXTEND",
            "reason": "Widget already owns color.",
        }
    ],
    "paradigm": "object_oriented",
    "decisions": ["Keep color validation at Widget construction."],
    "reuse_analysis": {
        "candidates": [
            {
                "symbol": "Widget",
                "locator": "src/widget.py:10",
                "decision": "EXTEND",
                "reason": "Existing public owner.",
            }
        ]
    },
    "impact_closure": {
        "applicability": "not_applicable",
        "reason": "The fixture reaches no public surface, consumer or build metadata.",
    },
    "prefactoring": {
        "applicability": "applicable",
        "existing_oracle": "tests/test_widget.py::test_default_color",
        "move": "Extract the current default lookup without changing output.",
        "preserved_observation": "A default widget remains blue.",
        "verification": [["pytest", "-q", "tests/test_widget.py::test_default_color"]],
        "acceptance_supports": [],
    },
    "agreement_analysis": {
        "applicability": "applicable",
        "parties": [
            {
                "contract": "widget report",
                "role": "producer",
                "locator": "src/widget.py:40",
                "decision": "MIGRATED",
                "reason": "Emits the selected color.",
            }
        ],
    },
    "boundaries": {
        "applicability": "applicable",
        "driving_port": "The widget CLI.",
        "driven_ports": ["standard output"],
        "dependency_direction": "The CLI depends inward on the widget.",
        "failures": [
            {
                "condition": "An unknown color is selected by the author at the CLI.",
                "outcome": "Refusal",
                "observation": "The CLI names the unknown color and exits non-zero.",
            }
        ],
    },
    "public_oracle": {
        "observation": "CLI prints the selected color.",
        "stimulus": "Run widget show --color red.",
        "expected": "stdout is red and exit is zero.",
        "falsifier": "Any other stdout or non-zero exit.",
    },
    "oracle": "tests/test_widget.py::test_selected_color",
    "acceptance_supports": ["tests/helpers/widget_fixtures.py"],
    "verification": [
        ["pytest", "-q", "tests/test_widget.py"],
        ["bash", "-c", "echo 'one'\necho two"],
    ],
    "oracle_verification_index": 0,
}


def _document(*, value: int = 1, **changes: object) -> DesignDocument:
    source = copy.deepcopy(MANIFEST)
    source.update(changes)
    manifest = design_manifest(source, source["purpose"], value)
    return DesignDocument.from_json(json.dumps(manifest), value=value)


def _render(*, value: int = 1, **changes: object) -> str:
    return _document(value=value, **changes).markdown()


def _filler(length: int) -> str:
    """Words that fill exactly ``length`` columns, so a wrap point is forced."""
    text = ("word " * length)[:length]
    return text[:-1] + "s" if text.endswith(" ") else text


def _blocks(markdown: str) -> list[tuple[str, list[str]]]:
    """Split the section into (kind, lines) blocks, fences kept whole."""
    lines = markdown.split("\n")
    assert lines[-1] == "", "the section must end with a newline"
    lines = lines[:-1]
    blocks: list[tuple[str, list[str]]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            blocks.append(("blank", [line]))
            index += 1
            continue
        if line.startswith("```"):
            end = lines.index(line[: len(line) - len(line.lstrip("`"))], index + 1)
            blocks.append(("fence", lines[index : end + 1]))
            index = end + 1
            continue
        start = index
        while index < len(lines) and lines[index]:
            index += 1
        group = lines[start:index]
        if group[0].startswith("#"):
            kind = "heading"
        elif group[0].startswith("|"):
            kind = "table"
        elif group[0].startswith("- "):
            kind = "list"
        else:
            kind = "paragraph"
        blocks.append((kind, group))
    return blocks


def test_every_heading_list_table_and_fence_is_surrounded_by_one_blank_line() -> None:
    blocks = _blocks(_render())
    kinds = [kind for kind, _ in blocks]

    assert kinds[0] == "heading" and kinds[-1] == "fence"
    for before, after in pairwise(blocks):
        assert (before[0] == "blank") != (after[0] == "blank"), (
            "blocks must alternate with exactly one blank line between them, "
            f"got {before!r} then {after!r}"
        )
    for kind, group in blocks:
        if kind == "heading":
            assert len(group) == 1, f"a heading must stand alone: {group!r}"
        if kind == "table":
            assert all(line.startswith("|") for line in group), group
        if kind == "list":
            assert all(line.startswith(("- ", "  ")) for line in group), group
        if kind == "paragraph":
            assert not any(line.startswith(("- ", "|", "#")) for line in group), group
    assert {"list", "table", "fence", "paragraph"} <= set(kinds)


def test_sub_headings_carry_compiled_scope_so_two_sections_never_collide() -> None:
    first = _render(value=1)
    second = _render(value=2)
    first_subs = [line for line in first.splitlines() if line.startswith("### ")]
    second_subs = [line for line in second.splitlines() if line.startswith("### ")]

    assert first.startswith("## Value 1\n\n### Facts (Value 1)\n")
    assert all(line.endswith(" (Value 1)") for line in first_subs), first_subs
    assert len(set(first_subs)) == len(first_subs)
    assert not set(first_subs) & set(second_subs)


def _prose_lines(markdown: str) -> list[str]:
    lines: list[str] = []
    fence: str | None = None
    for line in markdown.splitlines():
        if fence is None and line.startswith("```"):
            fence = line[: len(line) - len(line.lstrip("`"))]
        elif fence is not None and line == fence:
            fence = None
        elif fence is None and not line.startswith("|"):
            lines.append(line)
    return lines


def test_prose_wraps_at_80_columns_and_keeps_an_unbreakable_token_whole() -> None:
    token = "skills/" + "x" * 100 + ".mjs"
    long_purpose = " ".join(["Expose the selected widget color."] * 6)
    markdown = _render(purpose=f"See {token} now. {long_purpose}")
    lines = _prose_lines(markdown)

    assert token in [line.strip() for line in lines], (
        "an unbreakable token must stay whole"
    )
    assert all(len(line) <= WIDTH for line in lines if line.strip() != token), [
        line for line in lines if len(line) > WIDTH and line.strip() != token
    ]
    assert " ".join(" ".join(lines).split()).count(long_purpose) == 1


def test_list_item_continuation_lines_are_indented_two_spaces() -> None:
    constraint = " ".join(["Preserve existing callers of the widget."] * 4)
    document = _document(constraints=[constraint])
    lines = document.markdown().splitlines()
    identifier = document.facts.constraints[0].ref
    start = next(
        index
        for index, line in enumerate(lines)
        if line.startswith(f"- {identifier}: ")
    )
    end = start + 1
    while end < len(lines) and lines[end].startswith("  "):
        end += 1
    item = lines[start:end]

    assert len(item) > 1 and item[0].startswith("- ")
    assert all(re.match(r"^  \S", line) for line in item[1:]), item
    assert " ".join(part.strip() for part in item) == f"- {identifier}: " + constraint


def test_a_continuation_line_never_starts_block_markup() -> None:
    # A catalog definition prefix leaves its marker just short of fitting.
    document = _document()
    purpose_prefix = f"- {document.facts.purpose.ref}: "
    decision_prefix = f"- {document.facts.decisions[0].ref}: "
    observation_prefix = f"- {document.facts.public_oracle.observation.ref}: "
    filler = _filler(WIDTH - len(purpose_prefix) - 1)
    markdown = _render(
        purpose=f"{filler} - dash tail",
        decisions=[f"{_filler(WIDTH - len(decision_prefix) - 1)} # hash tail"],
        public_oracle={
            **MANIFEST["public_oracle"],  # type: ignore[dict-item]
            "observation": f"{_filler(WIDTH - len(observation_prefix) - 2)} 1. ordered tail",
        },
    )

    assert f"{purpose_prefix}{filler}\n  \\- dash tail\n" in markdown
    assert "\n  \\# hash tail\n" in markdown
    assert "\n  1\\. ordered tail\n" in markdown


def test_angle_brackets_are_escaped_in_prose_but_verbatim_inside_code_spans() -> None:
    markdown = _render(purpose="Refuse <field> but keep `a<b` verbatim.")

    assert "Refuse \\<field> but keep `a<b` verbatim.\n" in markdown


def test_a_pipe_in_a_legitimate_scalar_table_cell_is_escaped() -> None:
    contract = "Owns <color> left | right and `a|b<c` in code."
    markdown = _render(
        agreement_analysis={
            "applicability": "applicable",
            "parties": [
                {
                    "contract": contract,
                    "role": "producer",
                    "locator": "src/widget.py:40",
                    "decision": "MIGRATED",
                    "reason": "Emits the selected color.",
                }
            ],
        },
    )

    # The scalar join key is allowed prose; reasons remain FactRefs.
    assert "Owns \\<color> left \\| right and `a\\|b<c` in code." in markdown


def test_each_verification_argv_renders_whole_inside_one_sh_fence() -> None:
    markdown = _render()

    assert markdown.endswith(
        "Verification command:\n\n"
        "```sh\npytest -q tests/test_widget.py\n```\n\n"
        "Verification command:\n\n"
        "```sh\nbash -c 'echo '\"'\"'one'\"'\"'\necho two'\n```\n"
    )


def test_no_line_has_trailing_whitespace_and_the_section_ends_with_one_newline() -> (
    None
):
    markdown = _render(purpose="Trailing   spaces   collapse.   ")

    assert markdown.endswith("```\n") and not markdown.endswith("\n\n")
    assert "\n\n\n" not in markdown
    assert not [line for line in markdown.split("\n") if line != line.rstrip()]
