"""Compose and check the integrated commit's message from runner-held facts.

The delivery runner integrates through Git PLUMBING (`commit-tree` plus a
compare-and-swap on the ref), so no `commit-msg` hook, no `pre-commit` stage
and no local `gitlint` ever observes the message it writes. The repository's
CI runs `gitlint` over every pushed commit, so a message that does not follow
the convention is not a cosmetic blemish: it is a red build nothing local
could have refused.

The answer is construction, not late validation (GDP-0). Every element of the
message is DERIVED from facts the runner already holds -- the Request text,
the admitted observations in their canonical order, the expected-old SHA, the
bound authority locators and the paths the candidate tree actually changes --
so no role is asked to author prose and no model decision enters a Git object
(`boundary:software-measures-model-decides`).

A fact's LENGTH is likewise the software's own doing: `authority typed:<path>
::<selector>` is a string this module concatenates, and a long test path is a
legitimate fact nobody chose badly. So a fact of any length is REPRESENTED,
never refused -- continued across lines at its own `::` seam, or at a fixed
width when no seam is available, with a marker that makes the original
recoverable by concatenation. Refusing one would bill the model for a form the
software controls (`boundary:software-measures-model-decides`, the
rejection-for-form corollary). Measured 2026-09-05, run 17: a 156-character
authority line stopped a delivery after every turn had been paid.

`CommitMessageRule` then re-applies the repository's OWN declared rule to the
composed message before the commit object is written. It is deliberately a
parse of `.gitlint` -- the file CI reads -- rather than a second, independently
drifting statement of the convention. This module stays pure: the caller reads
`.gitlint` and passes its text (mirroring `attribution_trailer.py`, which keeps
config resolution in the application seam).
"""

from __future__ import annotations

import configparser
import re
import textwrap
from dataclasses import dataclass


#: The types `.gitlint`'s `contrib-title-conventional-commits` admits. Restated
#: only as the FALLBACK for a repository that declares no `.gitlint`; where the
#: file exists its `title-match-regex` is the rule actually applied.
DEFAULT_TITLE_PATTERN = (
    r"^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)"
    r"(\(.+\))?: [a-zA-Z].*$"
)
DEFAULT_TITLE_MAX_LENGTH = 100
DEFAULT_BODY_MAX_LINE_LENGTH = 120

#: gitlint's own default vocabulary for `contrib-title-conventional-commits`,
#: applied when a `.gitlint` enables that rule without narrowing `types`.
DEFAULT_CONVENTIONAL_TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)
_CONVENTIONAL_RULE = "contrib-title-conventional-commits"

#: The ONE documented type default. Whether a delta adds new observable
#: behaviour or repairs existing behaviour is NOT derivable from anything the
#: runner holds: `EXTEND`/`CREATE_NEW` is a designation about a FILE, not about
#: behaviour (GDP-8), and pattern-matching the Request's prose for words like
#: "fix" would put a model's phrasing in charge of a release number.
#:
#: So one default is chosen and stated. `feat` is that default for two reasons.
#: First, it follows the runner's own invariant: a candidate exists only when
#: the tree changed under a public oracle that the value made pass, which is
#: new observable behaviour in the only sense the runner can measure -- an
#: observation that is now executable and was not before, bugfix included.
#: Second, the failure directions are not symmetric under this repository's
#: release mapping (`feat` -> minor, `fix` -> patch). Shipping a repair as a
#: minor bump is conservative and semver-legal; shipping a new capability as a
#: patch tells consumers pinned to a patch range that nothing was added, which
#: is a semver violation. `chore` would be worse still: it suppresses the
#: release entirely and drops a delivered change out of the changelog silently.
#: A human who knows the delta is a repair can reword before pushing; the
#: runner must not guess in the direction that loses information.
#:
#: The CLEAN way out of this default, when it is wanted, is a TYPED fact from
#: the Product Owner -- the role that already classifies a Request into its
#: observable value projection, and the only one holding the repair-or-capacity
#: distinction as knowledge rather than as phrasing. It would arrive through the
#: PO's structured output and the persisted graph, exactly as `observation` and
#: `dependencies` do, and reach this function as a field on `IntegrationFacts`.
#: What must NEVER replace it is a pattern over the Request's or the
#: observation's prose: that hands a release number to a model's wording, which
#: is the boundary `boundary:software-measures-model-decides` forbids crossing.
DEFAULT_TYPE = "feat"

#: Used only when the Request's first line yields no usable subject at all.
FALLBACK_SUBJECT = "integrate the requested value"

#: Below this many characters a scope is dropped rather than allowed to eat the
#: subject's budget: an unreadable subject is a worse commit than a scopeless one.
_MINIMUM_SUBJECT_BUDGET = 24

_TRAILING_PUNCTUATION = ".,;:!?-"
_SCOPE_TOKEN = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
#: The conventional type at the head of a composed subject.
_TYPE_TOKEN = re.compile(r"^([a-zA-Z]+)[(!:]")
#: Layout segments that name no domain: the scope is the segment BELOW them.
_CONTAINER_SEGMENTS = frozenset({"src", "tests", "test"})

#: A body line ending in this marker CONTINUES on the next one: drop the
#: marker, drop the next line's indent, concatenate, and the original line is
#: back, character for character.  A locator's grammar admits neither a space
#: nor a backslash, so the marker cannot occur inside the fact it delimits.
_CONTINUATION = " \\"
#: What a continuation line is indented by, so a wrapped fact reads as one.
_CONTINUATION_INDENT = "    "
#: The seam a typed locator offers -- `typed:<path>::<selector>` -- preferred
#: over a fixed-width cut so the path and the selector each stay whole.
_FACT_BOUNDARY = "::"


#: WHAT/WHY/HOW's two halves for one rejected message.  The HOW differs by
#: FAMILY: a limit or vocabulary the repository DECLARES that no composed
#: message could satisfy is repaired in `.gitlint`, while anything else is a
#: defect in this module and says so.  Neither family asks for a re-authored
#: fact or a re-paid turn -- since composition continues a fact of any length,
#: no FACT can make the message non-conforming any more.
@dataclass(frozen=True, slots=True)
class MessageDefect:
    why: str
    how: str


#: The declared-rule family's HOW.  It costs one edit to `.gitlint` and no
#: paid turn: the Request is untouched, so `des dispatch` matches the stored
#: handover byte for byte and the graph resumes where it stopped.
_RULE_HOW = (
    "make .gitlint admit what the runner composes -- add "
    f"'{DEFAULT_TYPE}' to the types declared under [{_CONVENTIONAL_RULE}], "
    "widen [title-match-regex] regex, or raise the declared line-length under "
    "[title-max-length] / [body-max-line-length] -- then reissue the Request; "
    "the Request is unchanged, so the stored graph resumes and no turn is "
    "paid twice"
)

#: The composer family's HOW.  `compose_integration_message` establishes these
#: properties unconditionally, so this branch is reachable only through a
#: defect in THIS module -- and it says exactly that instead of asking the
#: operator to re-author a fact for the software's own omission.
_COMPOSER_HOW = (
    "this is a defect in des itself: compose_integration_message emits only "
    "conforming lines, so the message quoted above could not have been built "
    "by it -- report it with that message, then reissue once des is repaired. "
    "No fact needs re-authoring and no turn needs re-paying"
)


@dataclass(frozen=True, slots=True)
class IntegrationFacts:
    """The runner-held facts the integrated commit's message is built from."""

    request: str
    observations: tuple[str, ...]
    authorities: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CommitMessageRule:
    """The repository's declared commit-message rule, as `.gitlint` states it."""

    title_pattern: str = DEFAULT_TITLE_PATTERN
    title_max_length: int = DEFAULT_TITLE_MAX_LENGTH
    body_max_line_length: int = DEFAULT_BODY_MAX_LINE_LENGTH
    #: Empty means the repository declares no conventional-commit vocabulary.
    conventional_types: tuple[str, ...] = ()

    @classmethod
    def declared(cls, config_text: str | None) -> CommitMessageRule:
        """Parse `.gitlint`'s text, degrading to the documented defaults.

        A repository with no `.gitlint` (every consumer repo that installs DES
        but keeps its own conventions) still gets a conventional-commit message
        -- the defaults are the same numbers this repository declares, so the
        composed message is identical either way. An unreadable or malformed
        file degrades the same way rather than raising: a commit refused by a
        config parser would be a worse failure than a slightly stale limit.

        `title-match-regex` is not the whole rule. gitlint's
        `contrib-title-conventional-commits` (CT1) enforces its own `types`
        list, and a `.gitlint` that narrows that list while leaving the regex
        unset would otherwise be approved here and REJECTED by the real
        gitlint. The vocabulary is therefore read too, and treated as binding
        whenever the rule is enabled OR the types are explicitly declared --
        deliberately one notch stricter than gitlint, because that direction
        can only produce a LOUD degrade, never a silent pass.
        """
        if not config_text:
            return cls()
        parser = configparser.RawConfigParser()
        try:
            parser.read_string(config_text)
        except configparser.Error:
            return cls()

        def option(section: str, name: str) -> str | None:
            try:
                return parser.get(section, name).strip()
            except configparser.Error:
                return None

        def number(section: str, name: str, fallback: int) -> int:
            raw = option(section, name)
            try:
                value = int(raw) if raw is not None else 0
            except ValueError:
                return fallback
            return value if value > 0 else fallback

        declared_types = option(_CONVENTIONAL_RULE, "types")
        enabled = _CONVENTIONAL_RULE in (option("general", "contrib") or "")
        types: tuple[str, ...] = ()
        if declared_types:
            types = tuple(
                item.strip() for item in declared_types.split(",") if item.strip()
            )
        elif enabled:
            types = DEFAULT_CONVENTIONAL_TYPES
        return cls(
            option("title-match-regex", "regex") or DEFAULT_TITLE_PATTERN,
            number("title-max-length", "line-length", DEFAULT_TITLE_MAX_LENGTH),
            number("body-max-line-length", "line-length", DEFAULT_BODY_MAX_LINE_LENGTH),
            types,
        )

    def defect(self, message: str) -> MessageDefect | None:
        """The one rule violation this message carries, or None when it conforms.

        `.gitlint` runs with `regex-style-search`, so `search` is the matching
        semantics; every pattern in play is anchored, which makes the two agree.
        """
        lines = message.split("\n")
        subject = lines[0]
        if len(subject) > self.title_max_length:
            # The subject is composed INSIDE this budget, so the only way it
            # overruns is a declared title length too small to hold the
            # shortest conventional subject there is.
            return MessageDefect(
                f"the subject is {len(subject)} characters, over the declared "
                f"limit of {self.title_max_length}",
                _RULE_HOW,
            )
        try:
            matched = re.search(self.title_pattern, subject) is not None
        except re.error:
            matched = re.search(DEFAULT_TITLE_PATTERN, subject) is not None
        if not matched:
            return MessageDefect(
                f"the subject {subject!r} does not match the declared title rule",
                _RULE_HOW,
            )
        token = _TYPE_TOKEN.match(subject)
        if self.conventional_types and (
            token is None or token.group(1) not in self.conventional_types
        ):
            return MessageDefect(
                f"the subject's type is not one of the types this repository "
                f"declares ({', '.join(self.conventional_types)})",
                _RULE_HOW,
            )
        if subject != subject.strip():
            return MessageDefect(
                "the subject carries leading or trailing whitespace", _COMPOSER_HOW
            )
        if subject.endswith(tuple(_TRAILING_PUNCTUATION)):
            return MessageDefect(
                f"the subject ends with punctuation ({subject[-1]!r})", _COMPOSER_HOW
            )
        body = lines[1:]
        if body and body[0] != "":
            return MessageDefect(
                "no blank line separates the subject from the body", _COMPOSER_HOW
            )
        for line in body:
            if len(line) > self.body_max_line_length:
                # Every body line is CONTINUED to fit this width, so the
                # only way one overruns is a declared width too narrow to
                # carry even one character beside the continuation marker.
                return MessageDefect(
                    f"this body line is {len(line)} characters, over the declared "
                    f"limit of {self.body_max_line_length}: {line}",
                    _RULE_HOW,
                )
            if line != line.rstrip():
                return MessageDefect(
                    f"a body line carries trailing whitespace: {line[:60]!r}",
                    _COMPOSER_HOW,
                )
            if "\t" in line:
                return MessageDefect(
                    f"a body line carries a hard tab: {line[:60]!r}", _COMPOSER_HOW
                )
        return None


def derive_scope(changed_paths: tuple[str, ...]) -> str | None:
    """The one scope every changed path agrees on, or None when they disagree.

    Decided on the paths the candidate TREE actually changes, never on the
    authorized scope: a value may own a path it did not touch, and the commit
    describes what moved (GDP-8, property over designation).

    `src/` and `tests/` name a layout, not a domain, so the scope is the
    segment below them -- which is why `src/des/...` and `tests/des/...` agree
    on `des`. A path with no directory component contributes no scope, and any
    disagreement omits the scope rather than picking a winner.
    """
    tokens: set[str] = set()
    for path in changed_paths:
        segments = [segment for segment in path.split("/") if segment]
        if segments and segments[0] in _CONTAINER_SEGMENTS:
            segments = segments[1:]
        if len(segments) < 2:
            return None
        token = segments[0].lower()
        if not _SCOPE_TOKEN.match(token):
            return None
        tokens.add(token)
    if len(tokens) != 1:
        return None
    return tokens.pop()


def _continued_lines(text: str, width: int) -> list[str]:
    """*text* as body lines no wider than *width*, losing not one character.

    A returned line ending in `` \\`` continues on the next: drop the marker,
    drop that next line's indent, concatenate. Nothing is truncated and nothing
    is guessed, so the fact is recovered by concatenation alone.

    The cut is taken at the LAST `::` seam that still fits -- a typed locator's
    own boundary, which keeps `typed:<path>` and `::<selector>` each whole --
    and falls back to the fixed width only when no seam is reachable, because a
    single path can be wider than the declared limit on its own.

    The one input this cannot represent is a declared *width* too narrow to
    carry the marker plus one character. That is a property of `.gitlint`, not
    of the fact, so the text is returned unwrapped and `CommitMessageRule.defect`
    names it against the declared limit whose repair is in that file.
    """
    if len(text) <= width:
        return [text]
    indent = _CONTINUATION_INDENT
    first = width - len(_CONTINUATION)
    following = first - len(indent)
    if following < 1:
        indent, following = "", first
    if following < 1:
        return [text]
    seams = [match.start() for match in re.finditer(_FACT_BOUNDARY, text)]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        budget = first if not chunks else following
        if start + budget >= len(text):
            chunks.append(text[start:])
            break
        stop = start + budget
        reachable = [seam for seam in seams if start < seam <= stop]
        cut = max(reachable) if reachable else stop
        chunks.append(text[start:cut])
        start = cut
    last = len(chunks) - 1
    return [
        (chunk if index == 0 else indent + chunk)
        + ("" if index == last else _CONTINUATION)
        for index, chunk in enumerate(chunks)
    ]


def _body_block(entries: list[str], width: int) -> str:
    """One body paragraph: every entry continued so no line exceeds *width*."""
    return "\n".join(
        line for entry in entries for line in _continued_lines(entry, width)
    )


def _subject_text(request: str, budget: int) -> str:
    """The Request's first line, reduced to one conforming subject."""
    first = next((line.strip() for line in request.splitlines() if line.strip()), "")
    collapsed = " ".join(first.split())
    # The declared title rule requires the subject to START with a letter.
    while collapsed and not collapsed[0].isalpha():
        collapsed = collapsed[1:].lstrip()
    if collapsed:
        head = collapsed.split(" ", 1)[0]
        # Lowercase to match this repository's subject case, but never flatten
        # an acronym the Request itself capitalised (API, DES, CI).
        if not (len(head) > 1 and head.isupper()):
            collapsed = collapsed[0].lower() + collapsed[1:]
    if len(collapsed) > budget:
        cut = collapsed[:budget]
        spaced = cut.rsplit(" ", 1)[0] if " " in cut else cut
        collapsed = spaced
    collapsed = collapsed.rstrip(_TRAILING_PUNCTUATION + " ")
    if not collapsed or not collapsed[0].isalpha():
        return FALLBACK_SUBJECT[:budget].rstrip(_TRAILING_PUNCTUATION + " ")
    return collapsed


def compose_integration_message(
    facts: IntegrationFacts,
    expected_old: str,
    changed_paths: tuple[str, ...],
    rule: CommitMessageRule,
) -> str:
    """The integrated commit's message, built from *facts* and nothing else.

    The body carries each admitted observation as its own paragraph in the
    canonical order the runner delivered them, then the two lines that identify
    the projection: the expected-old commit the candidate was built on, and the
    durable authority locator each value was bound to.

    The candidate's own SHA is deliberately absent: the candidate commit IS the
    integrated commit (integration is a compare-and-swap onto it, not a second
    commit object), so naming it inside its own message is not expressible in
    Git. Expected-old identifies the delta unambiguously instead.

    Prose wraps at word boundaries and an observation identical to the subject
    is dropped rather than repeated. A token longer than the declared width --
    a long test path, a long selector -- survives both of those, and is then
    CONTINUED across lines by `_continued_lines` rather than refused: the fact
    stays whole and recoverable, and the message conforms. No fact, of any
    length, can make this message non-conforming.
    """
    scope = derive_scope(changed_paths)
    prefix = f"{DEFAULT_TYPE}({scope}): " if scope else f"{DEFAULT_TYPE}: "
    if rule.title_max_length - len(prefix) < _MINIMUM_SUBJECT_BUDGET:
        prefix = f"{DEFAULT_TYPE}: "
    # A degenerate declared title length would otherwise make the budget
    # negative, and a negative slice cuts from the END instead of yielding an
    # empty subject -- silently keeping the tail of a Request as the subject.
    budget = max(0, rule.title_max_length - len(prefix))
    text = _subject_text(facts.request, budget)
    subject = prefix + text
    paragraphs = []
    for observation in facts.observations:
        collapsed = " ".join(observation.split())
        if not collapsed:
            continue
        # A single-value Request states its observation in the Request line, so
        # the body would repeat the subject word for word.  Dropping the
        # duplicate is not only tidier: it removes a whole family of lines that
        # could overflow the declared body width, shrinking what the check below
        # can ever reach (GDP-0).  A TRUNCATED subject lost information the
        # observation still carries, so those never compare equal and it stays.
        if collapsed.lower() == text.lower():
            continue
        # `break_long_words=False` keeps a fact-bearing token whole; the line
        # it lands on is then continued below if it is wider than the limit.
        filled = textwrap.fill(
            collapsed,
            width=rule.body_max_line_length,
            break_long_words=False,
            break_on_hyphens=False,
        )
        paragraphs.append(_body_block(filled.splitlines(), rule.body_max_line_length))
    # A locator is a whitespace-free token in every producer's grammar, so this
    # collapse is the identity on a real one -- and it is what keeps a stray
    # tab or trailing space out of a body line the composer must guarantee.
    identity = [" ".join(("expected-old", *expected_old.split()))]
    identity.extend(
        " ".join(("authority", *locator.split()))
        for locator in facts.authorities
        if locator.strip()
    )
    paragraphs.append(_body_block(identity, rule.body_max_line_length))
    return subject + "\n\n" + "\n\n".join(paragraphs)
