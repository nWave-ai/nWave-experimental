"""Regression net — backlog #105: `des verify-red-green` duplicate-testcase
false all-pass.

RCA (2026-07-12): `_run_and_collect` (src/des/cli/verify_red_green.py:120-206)
keys outcomes on ``classname::name`` and assigns unconditionally
(``outcomes[test_id] = "fail" if failed else "pass"``, :197) -- last write
wins. Two JUnit ``<testcase>`` elements sharing classname+name (the confirmed
real vector: a pytest-bdd Scenario Outline with 2 Examples rows) collapse to
one key; a later PASS silently overwrites an earlier FAIL, and
``--verify-green`` reports SEALED while the run genuinely failed.

Hermetic, same idiom as tests/des/unit/cli/test_verify_red_green.py: the
declared --run-cmd is a tiny copier script writing a CANNED JUnit XML to
{junit_out} (no pytest-in-pytest).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from des.cli.verify_red_green import main


_EXIT_OK = 0
_EXIT_INDETERMINATE = 2

# One prior RED record: a single, distinct, genuinely-failing test.
_XML_RED_BASELINE = (
    '<testsuite><testcase classname="t" name="test_scenario">'
    '<failure message="red"/></testcase></testsuite>'
)

# The real vector: two <testcase> elements, SAME classname::name, fail FIRST
# (real pytest-bdd execution order) then pass.
_XML_GREEN_DUP_FAIL_THEN_PASS = (
    "<testsuite>"
    '<testcase classname="t" name="test_scenario"><failure message="red"/></testcase>'
    '<testcase classname="t" name="test_scenario"/>'
    "</testsuite>"
)

# All-distinct ids -- the well-formed path the fix must not disturb.
_XML_ALL_PASS = (
    '<testsuite><testcase classname="t" name="test_a"/>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)
_XML_ONE_FAIL = (
    '<testsuite><testcase classname="t" name="test_a">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t" name="test_pin"/></testsuite>'
)

# A duplicate-id group where BOTH entries pass, alongside one real distinct
# failure -- the fold must not fabricate a failure for the all-passing group.
_XML_RED_WITH_ALL_PASS_DUP_GROUP = (
    "<testsuite>"
    '<testcase classname="t" name="test_real"><failure message="red"/></testcase>'
    '<testcase classname="t" name="test_dup"/>'
    '<testcase classname="t" name="test_dup"/>'
    "</testsuite>"
)


def _fake_runner(tmp_path: Path, xml: str) -> str:
    """A single-string --run-cmd that copies canned XML to {junit_out}."""
    slug = hashlib.md5(xml.encode()).hexdigest()[:8]
    xml_src = tmp_path / f"canned_{slug}.xml"
    xml_src.write_text(xml)
    copier = tmp_path / f"copier_{slug}.py"
    copier.write_text("import shutil, sys\nshutil.copy(sys.argv[1], sys.argv[2])\n")
    return f"{sys.executable} {copier} {xml_src} {{junit_out}}"


def _repo_with_test(tmp_path: Path) -> Path:
    (tmp_path / "test_x.py").write_text("# content v1\n")
    return tmp_path


def _run(repo: Path, phase: str, xml: str) -> int:
    return main(
        [
            "--repo",
            str(repo),
            "--test-file",
            "test_x.py",
            phase,
            "--run-cmd",
            _fake_runner(repo, xml),
        ]
    )


def _seal_outcomes(repo: Path) -> dict[str, str]:
    seal = repo / ".nwave" / "telemetry" / "red-green" / "test_x.py.json"
    return json.loads(seal.read_text())["outcomes"]


def test_duplicate_fail_then_pass_is_not_reported_all_green_and_declares_collapse(
    tmp_path: Path, capsys
) -> None:
    """WITNESS 1+2: a duplicate-id fail-then-pass run must not SEAL as
    all-green (the fold is fail-dominant), AND the id-collapse (2 raw
    <testcase> elements folding to 1 test id) must be declared loudly in
    the gate's output -- not proceed silently.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_RED_BASELINE) == _EXIT_OK

    exit_code = _run(repo, "--verify-green", _XML_GREEN_DUP_FAIL_THEN_PASS)
    out = capsys.readouterr().out

    # WITNESS 1 -- fail-dominant fold: never reported all-green/SEALED.
    assert exit_code != _EXIT_OK, (
        "duplicate-id fail-then-pass was reported as GREEN/SEALED "
        f"(exit={exit_code}); the fold must be fail-dominant"
    )
    assert "SEALED" not in out

    # WITNESS 2 -- the collapse is declared loudly (what collapsed, not
    # proceeding silently). Exact wording is the crafter's to choose
    # (module's existing self-explaining conventions); assert presence of
    # a collapse declaration naming the folded id, not exact phrasing.
    lowered = out.lower()
    assert any(kw in lowered for kw in ("collaps", "duplicate")), (
        f"no collapse/duplicate declaration found in gate output: {out!r}"
    )
    assert "t::test_scenario" in out, (
        f"collapse declaration does not name the folded test id: {out!r}"
    )


def test_all_distinct_ids_never_declare_a_collapse(tmp_path: Path, capsys) -> None:
    """NEGATIVE: an all-distinct-id JUnit run keeps today's verdict
    byte-identical -- no new noise, no collapse declaration on the
    well-formed path.
    """
    repo = _repo_with_test(tmp_path)
    assert _run(repo, "--record-red", _XML_ONE_FAIL) == _EXIT_OK
    capsys.readouterr()  # drain the RED-phase output before the assertion

    exit_code = _run(repo, "--verify-green", _XML_ALL_PASS)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_OK
    assert "SEALED" in out
    lowered = out.lower()
    assert not any(kw in lowered for kw in ("collaps", "duplicate")), (
        f"spurious collapse declaration on an all-distinct-id run: {out!r}"
    )


def test_all_passing_duplicate_group_never_fabricates_a_failure(
    tmp_path: Path,
) -> None:
    """NEGATIVE: a duplicate-id group whose entries ALL pass must not
    manufacture a failure -- at most a declared collapse, never a
    fabricated red for that id.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_RED_WITH_ALL_PASS_DUP_GROUP)

    assert exit_code == _EXIT_OK  # the real distinct failure witnesses RED
    outcomes = _seal_outcomes(repo)
    assert outcomes["t::test_real"] == "fail"
    assert outcomes["t::test_dup"] == "pass", (
        "an all-passing duplicate-id group must not be fabricated as a "
        f"failure: {outcomes}"
    )


# ---------------------------------------------------------------------------
# Recurrence guard -- fix-seal-keys-on-nodeid-not-docstring (RCA:
# docs/feature/fix-seal-keys-on-nodeid-not-docstring/deliver/rca.md).
#
# `_run_and_collect` (verify_red_green.py:172-174) promotes the JUnit XML
# `name` attribute -- content produced by an environment the tool neither
# controls nor validates -- straight into an ATTESTATION IDENTITY with no
# fail-closed check at the content->identity boundary. The #105 fix above
# made the FOLD fail-dominant and loud but left that identity key itself
# byte-identical: it taught the tool to NOTICE and SURVIVE the collapse, not
# to not have it. This is the THIRD time this defect class is encountered
# (docstring-shaped JUnit `name`, first via last-write-wins, then via a
# fail-dominant fold that still loses per-case identity) -- if these ATs are
# satisfied by special-casing `pytest-pspec` by name rather than validating
# the SHAPE of the identity key, the fourth nodeid-mutating plugin walks
# straight past the guard and this recurs a fourth time.
#
# CORRECTION (same feature, same authoring pass): the block below originally
# pinned the shipped `_is_content_shaped` PROXY (embedded newline OR
# len > 200) instead of the actual invariant. Every fixture used a
# multi-line or >200-char name -- the proxy's blind spot is exactly a SHORT,
# SINGLE-LINE docstring, which is the overwhelmingly common real case (it is
# what produced the 122 corrupt seals). A crafter satisfied the proxy
# perfectly and the defect is still alive: 3 real @parametrize cases sharing
# one short docstring collapse to 1 identity and the run still SEALS.
#
# The settled invariant is COUNT, not SHAPE: the number of raw <testcase>
# elements the tool is handed must equal the number of DISTINCT identities
# it derives. If N cases collapse into fewer than N identities, the
# environment is not giving honest identities -- REFUSE, fail-closed, LOUD,
# never fold-and-proceed. It is runner-agnostic BY CONSTRUCTION: it never
# inspects a name's content, only whether identity is injective over the
# cases -- so it catches pytest-pspec at ANY docstring length, catches the
# next nodeid-mutating plugin nobody has written yet, and leaves honest
# vitest prose titles (distinct per test) untouched. Assertions below never
# key on a name's length or on an embedded newline -- only on collapse
# (raw <testcase> count vs. distinct identity count) and on distinctness.
# ---------------------------------------------------------------------------

# THE FALSIFYING FIXTURE (reproduced verbatim from the real CLI repro): a
# SHORT, SINGLE-LINE docstring shared by 3 @parametrize cases -- neither
# multi-line nor >200 chars, so `_is_content_shaped` is BLIND to it.
_SHORT_SINGLE_LINE_DOCSTRING_NAME = (
    "Every case of this test shares this one description."
)

# @pytest.mark.parametrize("n", [1, 2, 3]) / assert n < 3 -- n=1 and n=2
# pass, n=3 genuinely fails. A nodeid-mutating environment (pytest-pspec-
# shaped) writes the SAME shared docstring as `name` for all three raw
# <testcase> elements: 3 real cases, 1 identity.
_XML_SHORT_DOCSTRING_COLLAPSE_THREE_CASES = (
    "<testsuite>"
    f'<testcase classname="t.mod" name="{_SHORT_SINGLE_LINE_DOCSTRING_NAME}"/>'
    f'<testcase classname="t.mod" name="{_SHORT_SINGLE_LINE_DOCSTRING_NAME}"/>'
    f'<testcase classname="t.mod" name="{_SHORT_SINGLE_LINE_DOCSTRING_NAME}">'
    '<failure message="case n=3 is deliberately red"/></testcase>'
    "</testsuite>"
)

# A docstring-shaped JUnit `name`: prose with an embedded newline (`&#10;`),
# reproduced plugin-agnostically -- this is the SHAPE any nodeid-mutating
# plugin writes (pytest-pspec today, whatever comes next tomorrow), never a
# real pytest nodeid segment (`test_func` / `test_func[param]`).
_DOCSTRING_NAME = (
    "Verify that the seal REFUSES to promote docstring-shaped&#10;"
    "    JUnit name content into an attestation identity."
)

# Re-pinned on the COUNT relation (was: a single, non-colliding testcase --
# a shape assertion). Two raw <testcase> elements sharing ONE multi-line
# name, BOTH genuinely failing: the collapse is what must refuse, not the
# embedded newline -- a lone, non-colliding multi-line name collides with
# nothing and must NOT refuse (see the agnosticism guard below).
_XML_MULTILINE_NAME_COLLAPSE_BOTH_FAIL = (
    "<testsuite>"
    f'<testcase classname="t.mod" name="{_DOCSTRING_NAME}">'
    '<failure message="case A red"/></testcase>'
    f'<testcase classname="t.mod" name="{_DOCSTRING_NAME}">'
    '<failure message="case B red"/></testcase>'
    "</testsuite>"
)

# The exact false-green collision (seal-forensics.md S4): ONE identity (both
# raw <testcase> elements share the SAME content-shaped name -- e.g. two
# @parametrize cases of one docstringed function), TWO real cases, one
# genuinely FAILING and one genuinely PASSING.
_XML_DOCSTRING_COLLISION_FAIL_THEN_PASS = (
    "<testsuite>"
    f'<testcase classname="t.mod" name="{_DOCSTRING_NAME}">'
    '<failure message="case A genuinely fails"/></testcase>'
    f'<testcase classname="t.mod" name="{_DOCSTRING_NAME}"/>'
    "</testsuite>"
)

# Prose long enough to be unmistakably content-shaped even with NO embedded
# newline -- kept for shape-agnostic breadth (a collapse must refuse whether
# the colliding name is short, long, single-line, or multi-line). Single
# line, > 200 chars, matching seal-forensics.md's own corruption heuristic.
_LONG_SINGLE_LINE_PROSE_NAME = (
    "Verify that a docstring longer than any reasonable pytest nodeid, "
    "entirely on a single line with no embedded newline whatsoever, is "
    "still recognized as content-shaped prose rather than a legitimate "
    "test bracketed parameter nodeid, and is refused fail-closed at the "
    "content-to-identity boundary exactly like its multi-line sibling case."
)

# Re-pinned on the COUNT relation (was: a single, non-colliding testcase --
# a length assertion). Two raw <testcase> elements sharing ONE long, single-
# line name, BOTH genuinely passing: even a fold whose collapsed verdicts
# happen to AGREE (both pass, looks "safe") must still refuse -- the tool
# was handed 2 real cases and can mint only 1 identity, which is the
# dishonest condition under test, independent of verdict agreement.
_XML_LONG_SINGLE_LINE_NAME_COLLAPSE_BOTH_PASS = (
    "<testsuite>"
    f'<testcase classname="t.mod" name="{_LONG_SINGLE_LINE_PROSE_NAME}"/>'
    f'<testcase classname="t.mod" name="{_LONG_SINGLE_LINE_PROSE_NAME}"/>'
    "</testsuite>"
)

# Positive control: legitimate nodeid-shaped names -- single line, no
# newline, ordinary parametrize-bracket syntax -- must NOT be caught by the
# shape guard (the fix must not turn the tool into a rubber stamp that
# refuses everything).
_XML_LEGITIMATE_NODEID_SHAPED_ONE_FAIL = (
    "<testsuite>"
    '<testcase classname="t.mod" name="test_thing[case_alpha]">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t.mod" name="test_thing[case_beta-2]"/>'
    "</testsuite>"
)
_XML_LEGITIMATE_NODEID_SHAPED_ALL_PASS = (
    "<testsuite>"
    '<testcase classname="t.mod" name="test_thing[case_alpha]"/>'
    '<testcase classname="t.mod" name="test_thing[case_beta-2]"/>'
    "</testsuite>"
)

# Countability: N=5 distinct, well-formed, nodeid-shaped ids -- the seal
# must account for every one of them; nothing silently dropped.
_XML_FIVE_DISTINCT_NODEID_SHAPED = (
    "<testsuite>"
    '<testcase classname="t.mod" name="test_one"><failure message="r"/></testcase>'
    '<testcase classname="t.mod" name="test_two"/>'
    '<testcase classname="t.mod" name="test_three"><failure message="r"/></testcase>'
    '<testcase classname="t.mod" name="test_four"/>'
    '<testcase classname="t.mod" name="test_five"/>'
    "</testsuite>"
)

# The AGNOSTICISM GUARD fixtures (load-bearing, new): honest prose-shaped
# names that are DISTINCT per real case -- the vitest `describe > it` shape,
# one <testcase> per case, no collision at all. `verify-red-green` is
# deliberately runner-agnostic (pytest / cargo-nextest / vitest all emit
# JUnit XML); a "fix" that refused every prose-shaped name to satisfy the
# falsifying AT above would break every honest vitest run.
_XML_VITEST_STYLE_DISTINCT_PROSE_ONE_FAIL = (
    "<testsuite>"
    '<testcase classname="t.mod" name="renders the header">'
    '<failure message="red"/></testcase>'
    '<testcase classname="t.mod" name="renders the footer"/>'
    "</testsuite>"
)
_XML_VITEST_STYLE_DISTINCT_PROSE_ALL_PASS = (
    "<testsuite>"
    '<testcase classname="t.mod" name="renders the header"/>'
    '<testcase classname="t.mod" name="renders the footer"/>'
    "</testsuite>"
)


def _seal_exists(repo: Path) -> bool:
    return (repo / ".nwave" / "telemetry" / "red-green" / "test_x.py.json").is_file()


def test_short_single_line_docstring_collapse_across_parametrize_cases_refuses(
    tmp_path: Path, capsys
) -> None:
    """THE FALSIFYING AT (verbatim repro): a SHORT, SINGLE-LINE docstring
    shared by a 3-case @parametrize, fed through a nodeid-mutating
    environment (pytest-pspec-shaped: `name` = the shared docstring, not a
    per-case nodeid), with exactly one of the three cases genuinely failing.
    `_is_content_shaped` (embedded newline OR len > 200) is BLIND to this --
    the name is one short, single-line sentence, the overwhelmingly common
    real case. The shipped guard never fires; three raw <testcase> elements
    silently fold into ONE identity and the run SEALS red on a single
    witness, discarding two real passing cases behind an advisory print
    only. Per the settled invariant (count, not shape) this must REFUSE
    fail-closed (RedGreenIndeterminate, exit 2) -- never fold and proceed.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_SHORT_DOCSTRING_COLLAPSE_THREE_CASES)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_INDETERMINATE, (
        "3 <testcase> elements sharing one short single-line docstring name "
        "collapsed to 1 identity must REFUSE (exit 2, INDETERMINATE) -- the "
        f"length/newline shape guard is blind to this: exit={exit_code}, "
        f"out={out!r}"
    )
    assert "INDETERMINATE" in out
    assert not _seal_exists(repo), (
        "a collapsed-identity run must never write a seal -- 3 real cases "
        "were handed to the tool and only 1 identity would be recorded"
    )


def test_multiline_name_collapse_is_refused_because_cases_collapsed_not_shape(
    tmp_path: Path, capsys
) -> None:
    """RE-PINNED (was: refuse-because-multiline on a single, non-colliding
    testcase -- a shape assertion, not a count assertion). Two <testcase>
    elements sharing one multi-line docstring name, BOTH genuinely failing:
    refusal is pinned to the 2-into-1 COLLAPSE, not to the embedded newline.
    A single multi-line-named testcase with no collision must NOT refuse
    (see the agnosticism guard below); this scenario refuses because two
    real cases collapsed into one identity.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_MULTILINE_NAME_COLLAPSE_BOTH_FAIL)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_INDETERMINATE, (
        "2 <testcase> elements collapsing to 1 identity must REFUSE "
        f"regardless of name shape: exit={exit_code}, out={out!r}"
    )
    assert "INDETERMINATE" in out
    assert not _seal_exists(repo)


def test_long_single_line_name_collapse_is_also_refused_because_cases_collapsed(
    tmp_path: Path, capsys
) -> None:
    """RE-PINNED (was: refuse-because->200-chars on a single, non-colliding
    testcase -- a length assertion, not a count assertion). Two <testcase>
    elements sharing one long, single-line, no-newline name, BOTH genuinely
    passing: still a 2-into-1 collapse, still refused -- the fold would look
    "safe" (both agree pass) but the tool handed 2 real cases and can mint
    only 1 identity, which is the dishonest condition under test,
    independent of whether the collapsed verdicts happen to agree.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(
        repo, "--record-red", _XML_LONG_SINGLE_LINE_NAME_COLLAPSE_BOTH_PASS
    )
    out = capsys.readouterr().out

    assert exit_code == _EXIT_INDETERMINATE, (
        "2 <testcase> elements collapsing to 1 identity must REFUSE even "
        f"when both collapsed instances agree: exit={exit_code}, out={out!r}"
    )
    assert "INDETERMINATE" in out
    assert not _seal_exists(repo)


def test_two_distinct_cases_sharing_docstring_content_never_collapse_silently(
    tmp_path: Path, capsys
) -> None:
    """NEGATIVE AT (the durable one, on the CLASS -- not on `pytest-pspec`
    by name): two DISTINCT real test cases (one genuinely failing, one
    genuinely passing) whose JUnit `name` CONTENT happens to coincide (the
    exact false-green mechanism in seal-forensics.md S4) must NEVER be
    folded into one identity and sealed. If the tool cannot mint a distinct
    identity for each case it must REFUSE loudly (RedGreenIndeterminate,
    exit 2) -- never pick a verdict and proceed.

    This is the THIRD encounter with this defect class (backlog #105
    recurrence). #105's fix made the fold fail-dominant and loud but left
    the identity key itself untouched -- it taught the tool to survive the
    collapse, not to not have it. Asserting against `pytest-pspec` by name
    would repeat that exact mistake a fourth time: this AT is written
    against the SHAPE of the identity key, so it fails for ANY producer of
    content-shaped names, including whatever plugin does this differently
    next.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_DOCSTRING_COLLISION_FAIL_THEN_PASS)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_INDETERMINATE, (
        "an unresolvable content-shaped identity collision (one failing "
        "case + one passing case sharing one docstring-shaped `name`) must "
        "REFUSE loudly (exit 2, INDETERMINATE) rather than fold to a single "
        f"verdict and proceed: exit={exit_code}, out={out!r}"
    )
    assert not _seal_exists(repo), (
        "the seal's witness set must cover EVERY real case, or the seal "
        "refuses -- it must never silently attest one verdict for two "
        "distinct cases"
    )


def test_five_distinct_wellformed_ids_are_all_accounted_for_countability(
    tmp_path: Path,
) -> None:
    """WITNESS: nothing is silently dropped -- hand the tool 5 distinct,
    well-formed (nodeid-shaped) test cases; the seal must account for all
    5. A tester must be able to count.
    """
    repo = _repo_with_test(tmp_path)
    exit_code = _run(repo, "--record-red", _XML_FIVE_DISTINCT_NODEID_SHAPED)

    assert exit_code == _EXIT_OK
    outcomes = _seal_outcomes(repo)
    assert len(outcomes) == 5, (
        f"expected all 5 distinct well-formed ids accounted for, got "
        f"{len(outcomes)}: {sorted(outcomes)}"
    )
    assert outcomes["t.mod::test_one"] == "fail"
    assert outcomes["t.mod::test_two"] == "pass"
    assert outcomes["t.mod::test_three"] == "fail"
    assert outcomes["t.mod::test_four"] == "pass"
    assert outcomes["t.mod::test_five"] == "pass"


def test_legitimate_nodeid_shaped_names_still_seal_normally_positive_control(
    tmp_path: Path, capsys
) -> None:
    """POSITIVE CONTROL: the fix must not turn the tool into a rubber stamp
    that refuses everything. Ordinary pytest parametrize-bracket nodeids
    (single line, no newline, well within any reasonable length bound) must
    pass through the new shape guard untouched and still seal RED then
    GREEN exactly as today.
    """
    repo = _repo_with_test(tmp_path)
    assert (
        _run(repo, "--record-red", _XML_LEGITIMATE_NODEID_SHAPED_ONE_FAIL) == _EXIT_OK
    )
    capsys.readouterr()  # drain the RED-phase output before the assertion

    exit_code = _run(repo, "--verify-green", _XML_LEGITIMATE_NODEID_SHAPED_ALL_PASS)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_OK, (
        f"a legitimate nodeid-shaped run must still SEAL, got exit="
        f"{exit_code}, out={out!r}"
    )
    assert "SEALED" in out


def test_distinct_prose_named_cases_vitest_shape_still_seal_normally_agnosticism_guard(
    tmp_path: Path, capsys
) -> None:
    """AGNOSTICISM GUARD (load-bearing, new): honest prose-shaped names that
    are DISTINCT per real case -- the vitest `describe > it` shape -- must
    seal exactly like ordinary nodeid names do. `verify-red-green` is
    deliberately runner-agnostic (pytest / cargo-nextest / vitest all emit
    JUnit XML); a fix that refused every prose-shaped name to satisfy the
    falsifying AT above would break every honest vitest run. What matters is
    COUNT (distinct per case), never CONTENT (prose vs. nodeid) -- this AT
    makes that regression impossible.
    """
    repo = _repo_with_test(tmp_path)
    assert (
        _run(repo, "--record-red", _XML_VITEST_STYLE_DISTINCT_PROSE_ONE_FAIL)
        == _EXIT_OK
    )
    capsys.readouterr()  # drain the RED-phase output before the assertion

    exit_code = _run(repo, "--verify-green", _XML_VITEST_STYLE_DISTINCT_PROSE_ALL_PASS)
    out = capsys.readouterr().out

    assert exit_code == _EXIT_OK, (
        "distinct, honest, prose-shaped names (vitest shape) must still "
        f"SEAL, got exit={exit_code}, out={out!r}"
    )
    assert "SEALED" in out
