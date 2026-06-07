"""Stdlib-only YAML-subset parser for `nWave/` data + flavor files.

This is the SSOT parser the DES bundle uses to read its hand-curated YAML
data (flavor compositions, log-persistence defaults, language-adapter
port catalogs). Per the DES-bundle hygiene contract (`tests/build/
acceptance/plugin/steps/test_des_bundle_steps.py::des_no_external_deps`),
the bundled `des/` module cannot import `yaml` / `pyyaml`. PyYAML pulls
in a C extension; `tomllib` would not cover the YAML syntax we already
ship as data files; rewriting every `.yaml` to JSON would lose the
operator-readable comments that document the shipped defaults.

Trade-off: this parser handles only the YAML subset our data files use.
It is intentionally narrow — feeding it richer YAML constructs raises
`ValueError` so silent mis-parses cannot mask a schema-authoring bug.

Supported subset
----------------

* Top-level string scalars: ``key: value`` (quoted, unquoted, bare
  ``true`` / ``false`` / ``null`` / ``~`` coerced to Python equivalents).
* Literal block scalars: ``key: |`` followed by indented lines; joined
  with ``\\n`` and a trailing ``\\n`` to match ``yaml.safe_load`` output.
* Folded block scalars: ``key: >`` or ``key: >-`` followed by indented
  lines; joined with single spaces. ``>`` keeps a trailing ``\\n``;
  ``>-`` strips the trailing newline (YAML chomping indicators).
* String lists: ``key:`` followed by indented ``- item`` lines.
* Mapping (nested or top-level) with arbitrary depth: ``key:`` followed
  by indented ``sub: value`` lines.
* List of dicts: ``key:`` followed by indented ``- field: value`` lines
  with the first key on the dash line and the remaining keys indented to
  match the first key's column. Each dict member may itself be a string
  list (e.g. the ``witnesses`` field) or a folded block scalar (e.g. the
  ``summary`` field).
* Full-line ``# ...`` comments and trailing ``... # ...`` inline comments
  (outside quoted strings; the ``#`` must follow whitespace).
* Blank lines.

Unsupported (raises ``ValueError`` on encounter)
------------------------------------------------

* Anchors (``&anchor``, ``*alias``).
* Flow-style sequences/maps (``[a, b, c]``, ``{a: 1, b: 2}``).
* Multi-document streams (``---`` separators beyond the first document).
* Tags (``!!str``, ``!!int``).
* Numeric scalars (every bare token is left as a string; quoted numeric
  strings stay strings). Schemas that need integers either parse the
  string in the caller or get rewritten to use a quoted scalar.

API
---

Two entry points:

* ``load(text)`` — parse YAML text, return a Python dict.
* ``load_file(path)`` — read a UTF-8 text file and call ``load`` on it.

Round-trip parity contract
--------------------------

For every YAML document in ``nWave/data/*.yaml`` and ``nWave/flavors/
*.yaml`` covered by this parser, ``load(text)`` MUST return a dict
identical to ``yaml.safe_load(text)``. The bundle-hygiene gate guards
the import boundary; the per-caller acceptance tests guard the value
boundary.
"""

from __future__ import annotations

from pathlib import Path


def load(text: str) -> dict[str, object]:
    """Parse a YAML-subset string into a Python dict.

    Drives an indent-aware line walker. The parser is strict: any
    construct outside the supported subset raises ``ValueError``.
    """
    lines = _strip_comments_and_blanks(text.splitlines())
    document: dict[str, object] = {}
    cursor = 0
    while cursor < len(lines):
        cursor = _consume_top_level_entry(lines, cursor, document)
    return document


def load_file(path: Path) -> dict[str, object]:
    """Read a UTF-8 text file and parse it with ``load``."""
    return load(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Line preparation: strip comments + blanks, preserve indentation.
# ---------------------------------------------------------------------------


def _strip_comments_and_blanks(raw_lines: list[str]) -> list[tuple[int, str]]:
    """Filter to data-bearing lines, preserving ``(indent, payload)`` tuples.

    Drops pure-comment lines and empty / whitespace-only lines. Trailing
    inline ``# ...`` is stripped only when outside a quoted string and the
    ``#`` is preceded by whitespace (YAML rule).
    """
    kept: list[tuple[int, str]] = []
    for raw in raw_lines:
        without_inline = _strip_trailing_inline_comment(raw)
        stripped = without_inline.rstrip()
        if not stripped.strip():
            continue
        if stripped.lstrip().startswith("#"):
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        kept.append((indent, stripped))
    return kept


def _strip_trailing_inline_comment(line: str) -> str:
    """Remove a trailing ``... # ...`` comment when not inside a quoted string."""
    in_single = False
    in_double = False
    for index, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double:
            if index == 0 or line[index - 1] in (" ", "\t"):
                return line[:index]
    return line


# ---------------------------------------------------------------------------
# Top-level entry walker.
# ---------------------------------------------------------------------------


def _consume_top_level_entry(
    lines: list[tuple[int, str]], cursor: int, document: dict[str, object]
) -> int:
    """Consume one top-level key (scalar / block / list / mapping)."""
    indent, payload = lines[cursor]
    if indent != 0:
        raise ValueError(f"unexpected indent at top level: {payload!r}")
    key, after_colon = _split_key(payload)

    if after_colon in ("|", "|+", "|-"):
        block_value, next_cursor = _consume_literal_block(
            lines, cursor + 1, chomp=after_colon
        )
        document[key] = block_value
        return next_cursor

    if after_colon in (">", ">+", ">-"):
        block_value, next_cursor = _consume_folded_block(
            lines, cursor + 1, chomp=after_colon
        )
        document[key] = block_value
        return next_cursor

    if after_colon == "":
        next_index = cursor + 1
        if next_index < len(lines) and lines[next_index][1].lstrip().startswith("- "):
            list_value, next_cursor = _consume_list(lines, next_index)
            document[key] = list_value
            return next_cursor
        if next_index >= len(lines) or lines[next_index][0] == 0:
            # Empty mapping (key: with nothing under it).
            document[key] = {}
            return next_index
        mapping_value, next_cursor = _consume_mapping(lines, next_index)
        document[key] = mapping_value
        return next_cursor

    document[key] = _coerce_scalar(after_colon)
    return cursor + 1


# ---------------------------------------------------------------------------
# Scalar tokenisation.
# ---------------------------------------------------------------------------


def _split_key(line: str) -> tuple[str, str]:
    """Split ``key: value`` (or ``key:``) into ``(key, value-after-colon)``."""
    if ":" not in line:
        raise ValueError(f"expected `key: value` line, got {line!r}")
    key, _, remainder = line.partition(":")
    return key.strip(), remainder.strip()


def _coerce_scalar(raw: str) -> object:
    """Turn a YAML scalar token into a Python value.

    Strips matching outer quotes, maps bare ``true`` / ``false`` /
    ``null`` / ``~`` (case-insensitive) to Python equivalents. Everything
    else stays a string — numeric coercion is intentionally NOT performed
    so a schema drift cannot silently coerce ``"1.0"`` to ``1.0``.
    """
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        return raw[1:-1]
    lowered = raw.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "~"):
        return None
    return raw


# ---------------------------------------------------------------------------
# Block scalars (literal `|` and folded `>`).
# ---------------------------------------------------------------------------


def _consume_literal_block(
    lines: list[tuple[int, str]], cursor: int, *, chomp: str
) -> tuple[str, int]:
    """Consume a ``|`` literal block scalar.

    Returns ``(joined-text, next-cursor)``. Joins child lines with ``\\n``.
    Chomping per YAML 1.2:

    * ``|``  (clip)  — keep a single trailing ``\\n`` (the default).
    * ``|-`` (strip) — drop the trailing ``\\n``.
    * ``|+`` (keep)  — keep all trailing newlines (we have no blank-line
      tracking, so this is treated like ``|`` for our subset).
    """
    block_indent, collected, next_cursor = _collect_block_lines(lines, cursor)
    if not collected:
        return "", next_cursor
    body = "\n".join(line[block_indent:] for line in collected)
    if chomp == "|-":
        return body, next_cursor
    return body + "\n", next_cursor


def _consume_folded_block(
    lines: list[tuple[int, str]], cursor: int, *, chomp: str
) -> tuple[str, int]:
    """Consume a ``>`` folded block scalar.

    Returns ``(joined-text, next-cursor)``. Joins child lines with single
    spaces (YAML folding). Chomping per YAML 1.2:

    * ``>``  (clip)  — keep a single trailing ``\\n``.
    * ``>-`` (strip) — drop the trailing ``\\n``.
    * ``>+`` (keep)  — treated like ``>`` for our subset.
    """
    block_indent, collected, next_cursor = _collect_block_lines(lines, cursor)
    if not collected:
        return "", next_cursor
    body = " ".join(line[block_indent:] for line in collected)
    if chomp == ">-":
        return body, next_cursor
    return body + "\n", next_cursor


def _collect_block_lines(
    lines: list[tuple[int, str]], cursor: int
) -> tuple[int, list[str], int]:
    """Collect indented lines belonging to a block scalar.

    Returns ``(block_indent, [raw_payloads], next_cursor)``. ``block_indent``
    is the indent of the FIRST line in the block — every subsequent line
    must be indented to at least that column to belong to the block.
    """
    if cursor >= len(lines):
        return 0, [], cursor
    block_indent = lines[cursor][0]
    collected: list[str] = []
    while cursor < len(lines):
        indent, payload = lines[cursor]
        if indent < block_indent:
            break
        collected.append(payload)
        cursor += 1
    return block_indent, collected, cursor


# ---------------------------------------------------------------------------
# Lists (string lists + lists of dicts) — discriminated at first child.
# ---------------------------------------------------------------------------


def _consume_list(
    lines: list[tuple[int, str]], cursor: int
) -> tuple[list[object], int]:
    """Consume a list whose items are strings, dicts, or a mix.

    Each item begins with a ``- `` marker at the same indent as the first
    item. A bare ``- value`` item is a scalar; a ``- key: value`` item is
    a dict whose subsequent keys are indented to match the column after
    the dash.
    """
    if cursor >= len(lines):
        return [], cursor
    list_indent = lines[cursor][0]
    items: list[object] = []
    while cursor < len(lines):
        indent, payload = lines[cursor]
        if indent < list_indent:
            break
        if indent != list_indent:
            break
        stripped = payload.lstrip(" ")
        if not stripped.startswith("- "):
            break
        item_body = stripped[2:].strip()
        if ":" in item_body and not _looks_like_quoted_scalar(item_body):
            dict_item, cursor = _consume_dict_item(lines, cursor, list_indent)
            items.append(dict_item)
        else:
            items.append(_coerce_scalar(item_body))
            cursor += 1
    return items, cursor


def _next_is_empty_flow_list(
    lines: list[tuple[int, str]], next_index: int, base_indent: int
) -> bool:
    """True when the line under a ``key:`` is the sole empty flow list ``[]``.

    The only flow-style construct the subset supports: an explicitly empty
    list written as ``[]`` on its own indented line (the YAML shape an empty
    string-list profile renders to, e.g. an empty
    ``feature_end_required_records`` composition field). A non-empty flow
    list (``[a, b]``) stays unsupported and raises ``ValueError`` downstream.
    """
    if next_index >= len(lines):
        return False
    indent, payload = lines[next_index]
    return indent >= base_indent and payload.lstrip(" ") == "[]"


def _looks_like_quoted_scalar(token: str) -> bool:
    """Return True when ``token`` is a fully-quoted scalar (no key:value)."""
    if len(token) < 2:
        return False
    if token[0] not in ("'", '"'):
        return False
    if token[0] != token[-1]:
        return False
    inner = token[1:-1]
    return token[0] not in inner


def _consume_dict_item(
    lines: list[tuple[int, str]], cursor: int, list_indent: int
) -> tuple[dict[str, object], int]:
    """Consume one dict item under a list of dicts.

    The first key sits on the ``- key: value`` line. Subsequent keys are
    indented to match the column where the first key starts (i.e. two
    columns past ``list_indent`` for the standard ``-  key:`` layout, or
    ``list_indent + 2`` for the compact ``- key:`` layout).
    """
    indent, payload = lines[cursor]
    stripped = payload.lstrip(" ")
    first_key, after_colon = _split_key(stripped[2:].strip())
    item: dict[str, object] = {}
    member_indent = list_indent + 2
    if after_colon in ("|", "|+", "|-"):
        block, cursor = _consume_literal_block(lines, cursor + 1, chomp=after_colon)
        item[first_key] = block
    elif after_colon in (">", ">+", ">-"):
        block, cursor = _consume_folded_block(lines, cursor + 1, chomp=after_colon)
        item[first_key] = block
    elif after_colon == "":
        next_index = cursor + 1
        if next_index < len(lines) and lines[next_index][1].lstrip().startswith("- "):
            sub_list, cursor = _consume_list(lines, next_index)
            item[first_key] = sub_list
        else:
            sub_map, cursor = _consume_mapping(
                lines, next_index, base_indent=member_indent
            )
            item[first_key] = sub_map
    else:
        item[first_key] = _coerce_scalar(after_colon)
        cursor += 1
    while cursor < len(lines):
        inner_indent, inner_payload = lines[cursor]
        if inner_indent < member_indent:
            break
        if inner_indent == list_indent and inner_payload.lstrip().startswith("- "):
            break
        if inner_indent != member_indent:
            break
        inner_stripped = inner_payload.lstrip(" ")
        inner_key, inner_after = _split_key(inner_stripped)
        if inner_after in ("|", "|+", "|-"):
            block, cursor = _consume_literal_block(lines, cursor + 1, chomp=inner_after)
            item[inner_key] = block
            continue
        if inner_after in (">", ">+", ">-"):
            block, cursor = _consume_folded_block(lines, cursor + 1, chomp=inner_after)
            item[inner_key] = block
            continue
        if inner_after == "":
            next_index = cursor + 1
            if _next_is_empty_flow_list(lines, next_index, member_indent + 2):
                item[inner_key] = []
                cursor = next_index + 1
            elif next_index < len(lines) and lines[next_index][1].lstrip().startswith(
                "- "
            ):
                sub_list, cursor = _consume_list(lines, next_index)
                item[inner_key] = sub_list
            else:
                sub_map, cursor = _consume_mapping(
                    lines, next_index, base_indent=member_indent + 2
                )
                item[inner_key] = sub_map
            continue
        item[inner_key] = _coerce_scalar(inner_after)
        cursor += 1
    return item, cursor


# ---------------------------------------------------------------------------
# Mappings (nested key: value blocks, recursive to N levels).
# ---------------------------------------------------------------------------


def _consume_mapping(
    lines: list[tuple[int, str]], cursor: int, *, base_indent: int | None = None
) -> tuple[dict[str, object], int]:
    """Consume an indented mapping. Recursive — values may themselves be
    mappings, lists, or block scalars.

    ``base_indent`` pins the expected column of every direct child key.
    When ``None``, it is inferred from the first line.
    """
    mapping: dict[str, object] = {}
    if cursor >= len(lines):
        return mapping, cursor
    if base_indent is None:
        base_indent = lines[cursor][0]
    while cursor < len(lines):
        indent, payload = lines[cursor]
        if indent < base_indent:
            break
        if indent != base_indent:
            break
        stripped = payload.lstrip(" ")
        if stripped.startswith("- "):
            break
        key, after_colon = _split_key(stripped)
        if after_colon in ("|", "|+", "|-"):
            block, cursor = _consume_literal_block(lines, cursor + 1, chomp=after_colon)
            mapping[key] = block
            continue
        if after_colon in (">", ">+", ">-"):
            block, cursor = _consume_folded_block(lines, cursor + 1, chomp=after_colon)
            mapping[key] = block
            continue
        if after_colon == "":
            next_index = cursor + 1
            if next_index < len(lines) and lines[next_index][1].lstrip().startswith(
                "- "
            ):
                sub_list, cursor = _consume_list(lines, next_index)
                mapping[key] = sub_list
                continue
            if next_index >= len(lines) or lines[next_index][0] <= base_indent:
                mapping[key] = {}
                cursor = next_index
                continue
            sub_map, cursor = _consume_mapping(lines, next_index)
            mapping[key] = sub_map
            continue
        mapping[key] = _coerce_scalar(after_colon)
        cursor += 1
    return mapping, cursor
