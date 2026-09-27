"""EVERY declared consumer is reached by ONE artifact built by the REAL producer.

The observation this corpus measures: driven from the public surface, an
artifact built by the real producer travels an EXECUTABLE path to EVERY consumer
the declaration lists, and the outcome reports whether each one accepts it. When
one disagrees, the outcome is red and NAMES which consumer refuses and what it
refuses -- while still reporting every other declared consumer, because a
refusal that hid the remaining parties would report a complete traversal that
never happened.

What makes this an executable agreement rather than a claim about one: nothing
here reads source, an import graph or a syntax tree. The artifact exists ONLY
because the declared producer really ran and really wrote it, and acceptance IS
the declared consumer's own process exit code. A green verdict therefore cannot
be produced by a crossing that carried nothing.

The declaration under test is the FIRST SHIPPED one -- the real shared contract
`nwave.test_result.v1` -- read from the repository tree, not synthesised here.
The corpus drives `des verify-agreement`, the single registered subcommand that
is this slice's whole public driving port.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tests.common.in_process_cli import run_cli_in_process


#: The real repository root. This corpus deliberately points the checker at the
#: LIVE tree rather than a fixture: the producer it executes is this
#: repository's own `des verify-test-runner`, and the target it runs is a real
#: committed unit corpus. A synthesised tree would measure a stand-in.
REPOSITORY_ROOT = Path(__file__).resolve().parents[4]

#: The declaration the crossing is driven from -- repository-relative, exactly
#: as an operator names it on the command line. This corpus only READS it: the
#: shipped declaration is production-owned data, migrated to the plural
#: `consumers` grammar by value 2's implementation, not by this corpus.
DECLARATION = "schemas/agreements/nwave-test-result-v1.json"

#: The shared contract the declaration names.
CONTRACT = "nwave.test_result.v1"

#: A COMMITTED declaration whose SECOND of three declared consumers refuses the
#: real artifact. The refuser is declared in the middle on purpose: an
#: implementation that stops at the first refusal loses the third consumer, and
#: the oracle below can see that loss. The refusing party is SYNTHETIC and named
#: for exactly what it is -- a declared consumer requiring a field this real
#: producer does not emit -- because no in-tree party refuses the real artifact
#: today and inventing a real-sounding one would be the fabrication this checker
#: exists to prevent.
REFUSING_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/"
    "one-declared-consumer-refuses.json"
)


#: A COMMITTED declaration whose two declared consumers are written in DIFFERENT
#: LANGUAGES: one Python reader of the real contract, and one POSIX-shell reader
#: that DERIVES the frozen field list from the shared schema file rather than
#: restating it, so the fixture cannot drift away from the contract it checks.
#: The shipped declaration is deliberately NOT migrated to a second language --
#: its two consumers are the real in-tree readers and both are Python, and
#: swapping a real check for a shell shim to stage a demonstration is exactly the
#: fabrication this checker exists to prevent.
TWO_LANGUAGE_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/"
    "consumers-in-two-languages.json"
)

#: The shared schema the shell consumer derives its field list from. Named here
#: only so the oracle can check the fixture really reads it.
FROZEN_SCHEMA = "nWave/schemas/nwave.test_result.v1.schema.json"


#: A COMMITTED declaration whose MIDDLE of three declared consumers asks for an
#: argv[0] that answers to no program on this machine. The unresolvable fact is
#: REAL and euid-INDEPENDENT: no permission bit, no root escape, nothing that
#: could make this oracle pass VACUOUSLY under a root CI -- which is the exact
#: failure this observation forbids. Declared in the middle so a short-circuit
#: remains visible.
UNRESOLVABLE_RUNTIME_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/"
    "consumer-runtime-unresolvable.json"
)

#: The declared consumer in that fixture whose structural fact -- which program
#: its argv[0] names -- the checker cannot resolve.
UNRESOLVABLE_CONSUMER = "consumer.whose.runtime.answers.to.nothing"

#: A COMMITTED declaration whose MIDDLE consumer is a genuine foreign-encoding
#: party: it really reads the artifact, really accepts it, and writes its note on
#: stderr in latin-1. It is not a crash fixture -- it is an ordinary party whose
#: language the checker shares nothing with, which is precisely the population
#: this crossing exists to reach.
FOREIGN_ENCODING_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/consumer-stderr-not-utf8.json"
)

#: A declaration path that is not in the tree. Used to drive the EARLIEST
#: indeterminate there is, where the checker has not even learnt the contract.
ABSENT_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/"
    "no-such-declaration-exists.json"
)


#: A COMMITTED declaration that is an HONEST UNDER-DECLARATION of a REAL
#: population: it is the shipped declaration with the REAL frozen-schema
#: consumer DROPPED. Its green is therefore genuinely CORRECT -- every consumer
#: it declares really accepted the real artifact -- and genuinely NARROW, because
#: a real in-tree reader of the same contract was never executed. Measured
#: today this run exits 0 reporting `VERIFIED 1 of 1` and an empty `unverified`,
#: indistinguishable from the full declaration's green: that indistinguishability
#: IS the quiet closing this oracle exists to end. Inventing a fake refusing
#: outsider instead would stage a demonstration rather than expose a boundary.
UNDER_DECLARED_DECLARATION = (
    "tests/des/acceptance/agreement_crossing/declarations/"
    "under-declared-population.json"
)

#: The REAL consumer of the SAME contract that the under-declaration drops. It
#: is a declared party of the shipped declaration, so it is a reader this
#: repository genuinely has -- and the under-declared run must never name it,
#: because the boundary is DECLARED, never measured by reading the tree.
DROPPED_REAL_CONSUMER = "nWave/schemas/nwave.test_result.v1.schema.json"

#: The fixed literal predicate a machine reader applies to decide whether a
#: given reader was inside the run's reach, rather than parsing prose.
OUT_OF_REACH_RULE = (
    "a reader of this contract whose name is not listed in in_reach was NOT "
    "executed by this run"
)

#: The fixed literal act that WIDENS the boundary. A boundary an operator
#: cannot widen is a disclaimer rather than an instruction.
WIDEN_ACTION = (
    "declare that reader as a consumer in this declaration and re-run the crossing"
)

#: The greppable lead-in both human forms share, so an examiner who sees no
#: source can find the stated limit on any terminal.
BOUNDARY_LEAD_IN = "SPEAKS ONLY FOR"


def _declared_argv0s(declaration: str) -> list[str]:
    """The literal ``argv[0]`` each declared consumer asks for, in order."""
    document = json.loads((REPOSITORY_ROOT / declaration).read_text(encoding="utf-8"))
    return [consumer["argv"][0] for consumer in document["consumers"]]


def _declared_consumer_names(declaration: str) -> list[str]:
    """The consumer names the DECLARATION itself lists, in declaration order.

    Read from the declaration rather than restated here, so this corpus cannot
    drift into asserting against a remembered copy of who the parties are.
    """
    document = json.loads((REPOSITORY_ROOT / declaration).read_text(encoding="utf-8"))
    return [consumer["name"] for consumer in document["consumers"]]


def _outcome(stdout: str) -> dict:
    """The ONE single-line JSON object the public surface emits on stdout.

    The terminal also carries a human line; the machine surface is the single
    JSON object, and this helper asserts there is exactly one of them rather
    than scanning for the first thing that happens to parse.
    """
    objects = []
    for line in stdout.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        objects.append(json.loads(stripped))
    assert len(objects) == 1, (
        f"expected exactly one single-line JSON outcome on stdout, "
        f"got {len(objects)}:\n{stdout}"
    )
    return objects[0]


def test_an_artifact_built_by_the_real_producer_reaches_a_declared_consumer_and_the_outcome_reports_acceptance():
    exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # The crossing completed and the declared consumer ACCEPTED the artifact.
    # Exit 0 is reserved for that one world: a refusal is 1 and an
    # indeterminate crossing is 2, so a green here cannot be an unreadable
    # declaration, a producer that failed, or an artifact that never appeared.
    assert exit_code == 0, (
        f"expected the declared consumer to accept the real artifact "
        f"(exit 0); got {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )

    outcome = _outcome(stdout)

    assert outcome["verdict"] == "AgreementCrossed"

    # The outcome NAMES the agreement that was crossed -- which contract, which
    # producer, and which consumer -- so a reader learns what was proven rather
    # than only that something passed.
    assert outcome["contract"] == CONTRACT
    assert outcome["producer"]["name"]
    # Value 1's observation, MIGRATED rather than replaced: the reached consumer
    # is read from the declaration's single source of truth for who consumes the
    # contract -- the `consumers` array -- and acceptance is still its own exit
    # code. There is no second list of parties to disagree with it.
    assert outcome["consumers"][0]["name"]
    assert outcome["consumers"][0]["exit_code"] == 0

    # The producer argv REALLY EXECUTED is reported, with the {artifact} token
    # already substituted for the run-scoped path the checker owned. A reported
    # argv still carrying the literal token would mean nothing was substituted
    # and therefore nothing could have crossed.
    executed = outcome["producer"]["argv"]
    assert isinstance(executed, list) and executed
    assert "{artifact}" not in " ".join(executed), (
        f"the reported producer argv must be the one actually executed, with "
        f"the artifact path substituted: {executed}"
    )

    # An artifact genuinely crossed: it has real bytes and a real digest. This
    # is the assertion that makes a hollow green impossible -- a crossing that
    # carried nothing cannot report a non-empty length and a sha256 over it.
    assert outcome["artifact_bytes"] > 0
    digest = outcome["artifact_sha256"]
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef"), (
        f"expected a lowercase hex sha256 over the artifact that crossed, "
        f"got {digest!r}"
    )

    # The human line names the same agreement the machine line does, so the two
    # halves of the terminal cannot drift into disagreeing about what happened.
    human = [
        line
        for line in stdout.splitlines()
        if line.strip() and not line.strip().startswith("{")
    ]
    assert human, f"expected one human-readable line beside the JSON:\n{stdout}"
    assert any(CONTRACT in line for line in human)

    # EVERY declared consumer of the shipped contract was reached by the one
    # artifact -- not merely the first one. Both are real parties measured to
    # accept the real artifact today.
    declared = _declared_consumer_names(DECLARATION)
    assert [reached["name"] for reached in outcome["consumers"]] == declared


def test_every_declared_consumer_is_reached_by_the_one_real_artifact_and_a_refusal_names_which_consumer_and_what_it_refuses():
    """One producer run; every declared consumer reached; the red NAMES the refuser.

    Driven from the same public surface as the green above, over a committed
    declaration whose middle consumer refuses. Three claims are measured at once
    because they are the same observation: the traversal is COMPLETE (no
    short-circuit), it is ONE artifact that reaches every party (a single
    digest), and the disagreement is REPORTED SPECIFICALLY (which consumer, and
    what it refuses) rather than as an anonymous failure.
    """
    declared = _declared_consumer_names(REFUSING_DECLARATION)
    assert len(declared) == 3, (
        f"this oracle needs three declared consumers with the refuser in the "
        f"middle to detect a short-circuit; the fixture declares {declared}"
    )

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            REFUSING_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # A declared consumer really ran and really said no: exit 1. Not 2 -- an
    # indeterminate crossing would mean nothing was learnt, and here something
    # decisive was. Not 0 -- a disagreement is never green.
    assert exit_code == 1, (
        f"expected a declared consumer to refuse the real artifact (exit 1); "
        f"got {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )

    outcome = _outcome(stdout)
    assert outcome["verdict"] == "AgreementRefused"
    assert outcome["contract"] == CONTRACT

    # NO SHORT-CIRCUIT. Every declared consumer is reported, in declaration
    # order, INCLUDING the one declared AFTER the refuser. An implementation
    # that stopped at the first refusal would leave the third party unmeasured
    # while reporting a complete run, and an operator fixing the named consumer
    # would meet the next disagreement only on the following run.
    reached = outcome["consumers"]
    assert [consumer["name"] for consumer in reached] == declared, (
        f"expected EVERY declared consumer to be reached in declaration order "
        f"{declared}, got {[c.get('name') for c in reached]}"
    )

    # Each consumer carries its OWN exit code and its OWN substituted argv, so
    # the outcome distinguishes who agreed from who did not.
    for consumer in reached:
        executed = consumer["argv"]
        assert isinstance(executed, list) and executed
        assert "{artifact}" not in " ".join(executed), (
            f"consumer {consumer['name']} must report the argv actually "
            f"executed, with the artifact path substituted: {executed}"
        )
    assert reached[0]["exit_code"] == 0
    assert reached[1]["exit_code"] != 0
    assert reached[2]["exit_code"] == 0, (
        f"the consumer declared AFTER the refuser must still have been reached "
        f"and must still have accepted; got {reached[2]}"
    )

    # ONE producer run, ONE artifact: the crossing reports a single length and a
    # single digest for the whole run, which is what makes "the SAME artifact
    # reached every declared consumer" a checkable claim rather than a hope. Two
    # producer runs could hand two consumers different bytes under one verdict.
    assert outcome["artifact_bytes"] > 0
    digest = outcome["artifact_sha256"]
    assert len(digest) == 64 and set(digest) <= set("0123456789abcdef"), (
        f"expected one lowercase hex sha256 over the one artifact that crossed, "
        f"got {digest!r}"
    )
    assert outcome["producer"]["name"]
    assert "{artifact}" not in " ".join(outcome["producer"]["argv"])

    # THE RED NAMES WHICH CONSUMER REFUSES AND WHAT IT REFUSES. A refusal that
    # only said "someone disagreed" would leave the operator to bisect the
    # parties by hand.
    refuser = declared[1]
    refused = outcome["refused"]
    assert [entry["name"] for entry in refused] == [refuser], (
        f"expected the refusal to name exactly the refusing consumer "
        f"{refuser!r}, got {refused}"
    )
    assert refused[0]["exit_code"] == reached[1]["exit_code"]
    reason = refused[0]["reject_reason"]
    assert "generated_at" in reason, (
        f"expected the VERBATIM reason the refusing consumer wrote, naming the "
        f"field it requires and did not find; got {reason!r}"
    )

    # The human line names the SAME consumer and the SAME reason as the machine
    # line, so the two halves of the terminal cannot drift into disagreeing
    # about who refused and why.
    human = [
        line
        for line in stdout.splitlines()
        if line.strip() and not line.strip().startswith("{")
    ]
    assert human, f"expected one human-readable line beside the JSON:\n{stdout}"
    assert any(refuser in line for line in human), (
        f"the human line must name the refusing consumer {refuser!r}:\n{stdout}"
    )
    assert any("generated_at" in line for line in human), (
        f"the human line must carry the same reject reason as the machine "
        f"line:\n{stdout}"
    )


def test_the_crossing_reaches_consumers_in_different_languages_and_names_the_runtime_that_produced_each_verdict():
    """No population is declared verified by reading ONE language's syntax tree.

    Driven from the same single public surface as the two oracles above, over a
    committed declaration whose consumers are written in DIFFERENT LANGUAGES --
    one Python, one POSIX shell. Two claims are measured because they are one
    observation: the crossing really REACHES a party whose language the checker
    shares nothing with, and every verdict in the payload NAMES THE ABSOLUTE
    EXECUTABLE THAT REALLY PRODUCED IT. A runtime name is what makes the
    language-independence claim checkable instead of merely asserted: an
    operator can read the payload and see which real programs spoke.

    The runtime is the RESOLVED path, and it is the SAME value as ``argv[0]``,
    so the terminal cannot carry two disagreeing claims about what executed. It
    is a runtime, never a LANGUAGE NAME: mapping an executable to "python" would
    be exactly the single-language reading this observation forbids, and a wrong
    inference would declare verified a population nobody looked at.

    Resolution must NOT follow symlinks: ``sh`` is a multi-call binary on many
    systems (``/usr/bin/sh`` -> ``/usr/bin/dash``) that dispatches on argv[0], so
    a runtime that rewrote the declared basename would name -- and execute -- a
    different program than the one declared.
    """
    declared = _declared_consumer_names(TWO_LANGUAGE_DECLARATION)
    declared_argv0s = _declared_argv0s(TWO_LANGUAGE_DECLARATION)
    assert len(set(declared_argv0s)) == 2, (
        f"this oracle needs consumers in two DIFFERENT languages; the fixture "
        f"declares argv[0]s {declared_argv0s}"
    )

    # The non-Python consumer DERIVES the frozen field list from the shared
    # schema rather than restating it, so a contract change cannot leave this
    # fixture quietly agreeing with a list nobody maintains.
    document = json.loads(
        (REPOSITORY_ROOT / TWO_LANGUAGE_DECLARATION).read_text(encoding="utf-8")
    )
    assert any(
        FROZEN_SCHEMA in " ".join(consumer["argv"])
        for consumer in document["consumers"]
    ), f"the non-Python consumer must read {FROZEN_SCHEMA}, not a restated copy"

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            TWO_LANGUAGE_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # Both consumers really ran and both accepted the one real artifact. Exit 0
    # is reserved for that world, so a green here cannot be a consumer the
    # checker failed to reach: an unresolvable argv[0] leaves a party UNREACHED
    # and the shipped precedence makes the whole outcome indeterminate (2).
    assert exit_code == 0, (
        f"expected consumers in two languages to accept the real artifact "
        f"(exit 0); got {exit_code}\nstdout:\n{stdout}\nstderr:\n{stderr}"
    )

    outcome = _outcome(stdout)
    assert outcome["verdict"] == "AgreementCrossed"
    assert outcome["contract"] == CONTRACT

    reached = outcome["consumers"]
    assert [consumer["name"] for consumer in reached] == declared

    # EVERY consumer verdict NAMES THE RUNTIME THAT PRODUCED IT, and that runtime
    # IS the argv[0] actually executed -- one derived value projected twice, not
    # two facts that can drift apart. `runtime` exists so the claim is readable
    # without positional knowledge of argv.
    for consumer, declared_argv0 in zip(reached, declared_argv0s, strict=True):
        runtime = consumer["runtime"]
        assert isinstance(runtime, str) and Path(runtime).is_absolute(), (
            f"consumer {consumer['name']} must name the ABSOLUTE executable that "
            f"really produced its verdict, got {runtime!r}"
        )
        assert consumer["argv"][0] == runtime, (
            f"the reported runtime and the executed argv[0] must be the SAME "
            f"resolved value for {consumer['name']}: {runtime!r} vs "
            f"{consumer['argv'][0]!r}"
        )
        # RESOLUTION PRESERVES THE DECLARED BASENAME. A multi-call binary
        # dispatches on argv[0], so rewriting `sh` to `dash` would execute a
        # different program than the declaration names.
        assert os.path.basename(runtime) == os.path.basename(declared_argv0), (
            f"resolution must not follow symlinks: consumer "
            f"{consumer['name']} declared {declared_argv0!r} but the runtime "
            f"reports {runtime!r}"
        )

    # The producer side is equally language-free: it too names the absolute
    # executable that really built the artifact.
    producer_runtime = outcome["producer"]["runtime"]
    assert Path(producer_runtime).is_absolute()
    assert outcome["producer"]["argv"][0] == producer_runtime

    # THE CONSUMER POPULATION IS SUMMARISED BY RUNTIME -- sorted, de-duplicated,
    # and covering the CONSUMER verdicts only. This is the value that makes the
    # breadth of a verified population visible at a glance, and here it reports
    # TWO distinct runtimes: the artifact was accepted by parties the checker
    # shares no language with.
    runtimes = outcome["consumer_runtimes"]
    assert runtimes == sorted({consumer["runtime"] for consumer in reached}), (
        f"consumer_runtimes must be the sorted, de-duplicated set of the runtimes "
        f"that produced the consumer verdicts, got {runtimes}"
    )
    assert len(runtimes) == 2, (
        f"expected the two declared consumers to have run under two distinct "
        f"runtimes, got {runtimes}"
    )

    # The human line states the SAME count and NAMES the same runtimes, so the
    # two halves of the terminal cannot drift into disagreeing about what the
    # verdict rests on.
    human = [
        line
        for line in stdout.splitlines()
        if line.strip() and not line.strip().startswith("{")
    ]
    assert human, f"expected one human-readable line beside the JSON:\n{stdout}"
    assert any("2 distinct runtime(s)" in line for line in human), (
        f"the human line must state how many distinct runtimes the consumer "
        f"verdicts rest on:\n{stdout}"
    )
    for runtime in runtimes:
        assert any(runtime in line for line in human), (
            f"the human line must NAME the runtime {runtime!r} the machine line "
            f"reports:\n{stdout}"
        )

    # THE SHIPPED DECLARATION'S NARROWNESS BECOMES VISIBLE RATHER THAN HIDDEN.
    # Its real consumers are both Python, so it must honestly report ONE distinct
    # runtime. This is also what pins `consumer_runtimes` to the CONSUMER
    # verdicts: folding the producer's own runtime in would inflate this real,
    # single-runtime population into a false 2.
    shipped_exit, shipped_stdout, shipped_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert shipped_exit == 0, (
        f"expected the shipped declaration to stay green (exit 0); got "
        f"{shipped_exit}\nstdout:\n{shipped_stdout}\nstderr:\n{shipped_stderr}"
    )
    shipped = _outcome(shipped_stdout)
    assert len(shipped["consumer_runtimes"]) == 1, (
        f"the shipped declaration's consumers are all Python today, so it must "
        f"report exactly ONE distinct consumer runtime rather than borrowing "
        f"breadth from the producer: {shipped['consumer_runtimes']}"
    )
    shipped_human = [
        line
        for line in shipped_stdout.splitlines()
        if line.strip() and not line.strip().startswith("{")
    ]
    assert any("1 distinct runtime(s)" in line for line in shipped_human), (
        f"the human line must state the narrow population honestly:\n{shipped_stdout}"
    )


def _human_lines(stdout: str) -> list[str]:
    """The human half of the terminal: every non-JSON, non-blank line."""
    return [
        line
        for line in stdout.splitlines()
        if line.strip() and not line.strip().startswith("{")
    ]


def _assert_census_is_well_formed(outcome: dict, stdout: str) -> list[dict]:
    """Every verdict carries the same three census fields, in the same shape.

    Checked on EVERY terminal this oracle drives -- green, red and indeterminate
    alike -- because a census that only appears when something went wrong cannot
    be the thing a green is gated on.
    """
    for key in ("unverified", "declared_consumers", "verified_consumers"):
        assert key in outcome, (
            f"every verdict must carry {key!r} so a reader can account for the "
            f"declared population without parsing prose; got keys "
            f"{sorted(outcome)}\nstdout:\n{stdout}"
        )
    census = outcome["unverified"]
    assert isinstance(census, list), f"unverified must be an array, got {census!r}"
    for entry in census:
        assert isinstance(entry, dict) and set(entry) == {
            "subject",
            "fact",
            "detail",
        }, (
            f"every census entry names the subject, the fact the checker needed "
            f"and the verbatim detail, and nothing else; got {entry!r}"
        )
        for value in entry.values():
            assert isinstance(value, str) and value.strip(), (
                f"a census entry with an empty field names nothing: {entry!r}"
            )

    declared_count = outcome["declared_consumers"]
    verified_count = outcome["verified_consumers"]
    assert isinstance(declared_count, int) and isinstance(verified_count, int)

    # THE HUMAN HALF NAMES THE SAME COUNTS. Same two-halves-cannot-drift
    # discipline the contract, the refuser and the runtimes already hold.
    human = _human_lines(stdout)
    assert human, f"expected one human-readable line beside the JSON:\n{stdout}"
    expected = f"VERIFIED {verified_count} of {declared_count} declared consumer(s)"
    assert any(expected in line for line in human), (
        f"the human line must state {expected!r}, the same counts the machine "
        f"line carries:\n{stdout}"
    )
    for entry in census:
        clause = f"COULD NOT VERIFY: {entry['subject']} -- {entry['fact']}"
        assert any(clause in line for line in human), (
            f"the human line must carry {clause!r} for every census entry, so "
            f"the two halves cannot disagree about what went unverified:\n{stdout}"
        )
    return census


def test_every_declared_consumer_is_accounted_for_in_one_terminal_and_an_unresolvable_fact_is_named_never_green():
    """No missed verification can be green, and the miss is named, not inferred.

    Driven from the same single public surface as every oracle above. Four
    worlds are measured in one place because they are one observation: the
    terminal ACCOUNTS FOR THE WHOLE DECLARED POPULATION, always.

    1. An unresolvable structural fact about a declared consumer produces an
       INDETERMINATE (2) whose machine census NAMES that consumer and what could
       not be resolved -- never a REFUSAL (1), which would record a verdict the
       checker never reached.
    2. A party whose stderr is not UTF-8 is a party, not a crash: it is REACHED,
       VERIFIED by its own exit code, and the run still emits ONE terminal.
    3. The earliest indeterminate there is -- an absent declaration, before any
       contract is known -- is still accounted for in the census rather than
       left to prose alone.
    4. THE GREEN IS GATED ON THE CENSUS ITSELF: a green requires an EMPTY census
       and `verified_consumers == declared_consumers`, so completeness is
       checkable on the pass rather than only inferred from the failures.

    The invariant tying them together, asserted in every world:
    `verified_consumers + (consumer entries in the census) == declared_consumers`.
    A population nobody ever counted is exactly how a partial list passes.
    """
    # ---------------------------------------------------------------- world 1
    declared = _declared_consumer_names(UNRESOLVABLE_RUNTIME_DECLARATION)
    assert len(declared) == 3 and declared[1] == UNRESOLVABLE_CONSUMER, (
        f"this oracle needs the unresolvable consumer declared in the MIDDLE of "
        f"three, so a short-circuit stays visible; the fixture declares {declared}"
    )

    exit_code, stdout, stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            UNRESOLVABLE_RUNTIME_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # THE CRASH IS CONTAINED AS A TERMINAL. Measured today: an unresolvable
    # structural fact kills the run with a traceback, exit 1 and ZERO BYTES on
    # stdout -- so a lane reading the exit code records that a declared consumer
    # REFUSED, a verdict the checker never reached. Indeterminate (2) is the
    # only honest colour for "nothing decisive was learnt".
    assert exit_code == 2, (
        f"an unresolvable structural fact is INDETERMINATE (2), never a refusal "
        f"(1) and never green (0); got {exit_code}\nstdout:\n{stdout}\n"
        f"stderr:\n{stderr}"
    )
    outcome = _outcome(stdout)
    assert outcome["verdict"] == "AgreementIndeterminate"
    assert outcome["contract"] == CONTRACT

    census = _assert_census_is_well_formed(outcome, stdout)

    # THE CENSUS NAMES THE SUBJECT WHOSE FACT COULD NOT BE RESOLVED. A census
    # that only said "something was unverified" would leave the operator to
    # bisect the declared parties by hand -- and a reader counting the payload
    # would still record a population the run never looked at.
    subjects = [entry["subject"] for entry in census]
    assert subjects == [UNRESOLVABLE_CONSUMER], (
        f"expected the census to name exactly the consumer whose runtime could "
        f"not be resolved, got {census}"
    )

    # THE DECLARED POPULATION IS COUNTED AGAINST THE VERIFIED ONE, and the two
    # are reconciled by the census. This is the arithmetic nobody was doing.
    assert outcome["declared_consumers"] == len(declared)
    assert outcome["verified_consumers"] == len(declared) - 1
    consumer_entries = [entry for entry in census if entry["subject"] in declared]
    assert (
        outcome["verified_consumers"] + len(consumer_entries)
        == (outcome["declared_consumers"])
    ), (
        f"every verdict must account for each declared consumer exactly once: "
        f"{outcome['verified_consumers']} verified + {len(consumer_entries)} "
        f"unverified != {outcome['declared_consumers']} declared"
    )

    # NO SHORT-CIRCUIT, still. The consumer declared AFTER the unresolvable one
    # was really reached and really verified.
    reached = [consumer["name"] for consumer in outcome["consumers"]]
    assert reached == [declared[0], declared[2]], (
        f"the consumers on either side of the unresolvable one must still have "
        f"been reached, in declaration order; got {reached}"
    )

    # ---------------------------------------------------------------- world 2
    foreign = _declared_consumer_names(FOREIGN_ENCODING_DECLARATION)
    assert len(foreign) == 3 and foreign[1] == "consumer.whose.stderr.is.not.utf8"

    foreign_exit, foreign_stdout, foreign_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            FOREIGN_ENCODING_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # A party that does not emit UTF-8 is REACHED AND VERIFIED. Acceptance IS
    # the exit code, which no decoding choice can touch, so this consumer
    # genuinely belongs in the verified population and NOT in the census.
    # Measured today: this run dies while decoding, exit 1, zero bytes on
    # stdout -- which would make the shipped promise of reaching parties whose
    # language the checker shares nothing with false for every non-UTF-8 party.
    assert foreign_exit == 0, (
        f"a declared consumer writing non-UTF-8 on stderr still ACCEPTED the "
        f"artifact by its own exit code (exit 0); got {foreign_exit}\n"
        f"stdout:\n{foreign_stdout}\nstderr:\n{foreign_stderr}"
    )
    foreign_outcome = _outcome(foreign_stdout)
    assert foreign_outcome["verdict"] == "AgreementCrossed"
    foreign_census = _assert_census_is_well_formed(foreign_outcome, foreign_stdout)
    assert foreign_census == [], (
        f"a party whose output merely decoded lossily was genuinely verified "
        f"and must not appear in the unverified census: {foreign_census}"
    )
    assert [c["name"] for c in foreign_outcome["consumers"]] == foreign
    assert foreign_outcome["verified_consumers"] == len(foreign)
    assert foreign_outcome["declared_consumers"] == len(foreign)

    # ---------------------------------------------------------------- world 3
    assert not (REPOSITORY_ROOT / ABSENT_DECLARATION).exists(), (
        f"this oracle needs {ABSENT_DECLARATION} to really be absent"
    )
    absent_exit, absent_stdout, absent_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            ABSENT_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert absent_exit == 2, (
        f"an unreadable declaration is indeterminate (2); got {absent_exit}\n"
        f"stdout:\n{absent_stdout}\nstderr:\n{absent_stderr}"
    )
    absent_outcome = _outcome(absent_stdout)
    assert absent_outcome["verdict"] == "AgreementIndeterminate"

    # EVEN THE EARLIEST INDETERMINATE IS ACCOUNTED FOR ON THE MACHINE SURFACE.
    # Measured today it emits `verdict` and a prose `reason` and nothing else --
    # not even the contract -- so no machine reader can learn what was not
    # verified. Here the subject is the declaration itself, and the declared
    # consumer population is honestly zero: none were ever learnt.
    absent_census = _assert_census_is_well_formed(absent_outcome, absent_stdout)
    assert [entry["subject"] for entry in absent_census] == ["declaration"], (
        f"an indeterminate reached before any party is known must still name "
        f"WHAT it could not verify on the machine surface; got {absent_census}"
    )
    assert absent_outcome["declared_consumers"] == 0
    assert absent_outcome["verified_consumers"] == 0

    # ---------------------------------------------------------------- world 4
    # THE GATE IS CHECKED ON THE GREEN ITSELF. The shipped declaration -- the
    # real contract, crossed by real parties -- must pass the same structural
    # gate: an empty census and every declared consumer verified. That is what
    # makes "no missed verification can be green" a property of the green rather
    # than an emergent accident of whichever branch happened to run first.
    green_exit, green_stdout, green_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert green_exit == 0, (
        f"expected the shipped declaration to stay green; got {green_exit}\n"
        f"stdout:\n{green_stdout}\nstderr:\n{green_stderr}"
    )
    green = _outcome(green_stdout)
    assert _assert_census_is_well_formed(green, green_stdout) == [], (
        f"a green requires an EMPTY unverified census: {green['unverified']}"
    )
    shipped_declared = _declared_consumer_names(DECLARATION)
    assert green["declared_consumers"] == len(shipped_declared)
    assert green["verified_consumers"] == green["declared_consumers"], (
        f"a green requires every declared consumer to have been verified: "
        f"{green['verified_consumers']} of {green['declared_consumers']}"
    )

    # `consumer_runtimes` KEEPS ITS VALUE-3 MEANING -- the runtimes that really
    # produced a consumer verdict -- and is neither widened nor renamed. The
    # honest repair for mistaking breadth for completeness is the explicit count
    # and the census beside it, not a redefinition of a shipped key.
    assert green["consumer_runtimes"] == sorted(
        {consumer["runtime"] for consumer in green["consumers"]}
    )


def _assert_scope_states_the_boundary(
    outcome: dict, stdout: str, *, declaration: str
) -> dict:
    """Every terminal carries a CLOSED `scope` derived from THIS run.

    Checked on the green, the red and the indeterminate alike: a limit that only
    appeared when something went wrong could not qualify the verdict an operator
    actually trusts, and the green is the one that today reads as a claim about
    the contract rather than about a list.

    The shape is CLOSED on purpose -- exactly the five keys, and `out_of_reach`
    and `widen_by` closed in turn -- because a field a reader may or may not find
    cannot be relied on to state a limit.
    """
    assert "scope" in outcome, (
        f"EVERY terminal must state the population it speaks for; the outcome "
        f"carries only {sorted(outcome)}\nstdout:\n{stdout}"
    )
    scope = outcome["scope"]
    assert isinstance(scope, dict) and set(scope) == {
        "declaration",
        "contract",
        "measured",
        "out_of_reach",
        "widen_by",
    }, f"scope is a closed object of exactly those five keys; got {scope!r}"

    # THE DECLARATION PATH THE OPERATOR PASSED, VERBATIM. Measured today: the
    # payload contains ZERO occurrences of it, so an operator cannot even locate
    # the file that decided the population.
    assert scope["declaration"] == declaration, (
        f"scope.declaration must be the repository-relative declaration path the "
        f"operator passed, verbatim: expected {declaration!r}, got "
        f"{scope['declaration']!r}"
    )

    out_of_reach = scope["out_of_reach"]
    assert isinstance(out_of_reach, dict) and set(out_of_reach) == {
        "rule",
        "in_reach",
        "count",
    }, (
        f"scope.out_of_reach is closed over exactly those three keys; got {out_of_reach!r}"
    )

    # THE PREDICATE ITSELF, so a machine reader can APPLY the boundary instead of
    # parsing prose about it.
    assert out_of_reach["rule"] == OUT_OF_REACH_RULE, (
        f"scope.out_of_reach.rule must be the fixed predicate a reader can apply; "
        f"got {out_of_reach['rule']!r}"
    )

    # THE BOUNDARY IS STATED BY ENUMERATING ITS INSIDE -- the only side an
    # executable crossing can know.
    in_reach = out_of_reach["in_reach"]
    assert isinstance(in_reach, list) and all(isinstance(n, str) for n in in_reach)

    # ABSENCE OF A COUNT IS WHAT FORBIDS READING THIS AS "nobody else consumes
    # this contract". A number here -- `0` above all -- would be a claim strictly
    # stronger than an executable crossing can ever make, and would require
    # exactly the source-reading census this checker refuses.
    assert out_of_reach["count"] == "UNKNOWN", (
        f"scope.out_of_reach.count is the literal string 'UNKNOWN' and is NEVER a "
        f"number and never 0; got {out_of_reach['count']!r}"
    )

    widen_by = scope["widen_by"]
    assert isinstance(widen_by, dict) and set(widen_by) == {
        "action",
        "edit",
        "rerun",
    }, f"scope.widen_by is closed over exactly those three keys; got {widen_by!r}"
    assert widen_by["action"] == WIDEN_ACTION
    # THE FILE THAT DECIDES THE POPULATION is the file to edit -- the same path
    # scope.declaration names, never a second one that could disagree with it.
    assert widen_by["edit"] == scope["declaration"], (
        f"widen_by.edit must be the SAME verbatim declaration path scope.declaration "
        f"names: {widen_by['edit']!r} vs {scope['declaration']!r}"
    )
    # AND THE EXACT COMMAND THAT RE-RUNS *THIS* CROSSING, not a generic template.
    rerun = widen_by["rerun"]
    assert isinstance(rerun, list) and rerun[:2] == ["des", "verify-agreement"], (
        f"widen_by.rerun must be the argv that re-runs this crossing; got {rerun!r}"
    )
    assert rerun[2] == "--repo-root" and rerun[4] == "--declaration", (
        f"widen_by.rerun must name the repository root and the declaration the "
        f"operator gave: {rerun!r}"
    )
    assert rerun[5] == declaration, (
        f"widen_by.rerun must re-run THIS declaration verbatim: {rerun!r}"
    )
    assert rerun[3] == str(REPOSITORY_ROOT), (
        f"widen_by.rerun must carry the repository root as the operator gave it: "
        f"{rerun!r}"
    )
    return scope


def test_every_terminal_states_the_boundary_of_what_it_measured_and_an_undeclared_reader_is_out_of_reach():
    """The limit of the measure is VISIBLE on every verdict, not closed quietly.

    Driven from the same single public driving port as every oracle above --
    `des verify-agreement --repo-root ROOT --declaration JSON`, unchanged, with
    NO new subcommand, NO new flag and above all NO OPT-IN. An operator who has
    to ASK for the limit of a measurement is an operator who reads a universal
    claim by default, which is exactly the quiet closing this oracle ends.

    Five worlds are measured in one place because they are one observation: the
    terminal SPEAKS FOR A NAMED POPULATION AND SAYS SO.

    1. An HONEST UNDER-DECLARATION of a real population is still green -- and its
       green now says, on its face, that it speaks only for the one consumer
       somebody declared, while a REAL in-tree reader of the same contract went
       unexecuted.
    2. THE BOUNDARY IS DERIVED FROM THE RUN, never a constant banner: the scope
       of the 1-consumer, 2-consumer and 3-consumer runs are ALL DISTINCT. A
       scope whose bytes do not change between declarations is indistinguishable
       from boilerplate nobody reads.
    3. THE BOUNDARY IS DECLARED, NEVER MEASURED BY READING THE TREE: `in_reach`
       carries exactly the names the declaration itself lists, and the
       under-declared run NEVER names the real consumer it dropped. A scan that
       found nothing would read as "nobody else consumes this" -- strictly
       stronger than an executable crossing can ever say -- and adjudicating a
       grep census is the single-language source reading this checker refuses.
    4. THE LIMIT IS ON THE RED TOO, and the undeclared population is NEVER folded
       into the counts: `declared_consumers`, `verified_consumers` and
       `unverified` keep exactly the meaning the census oracle above fixed. The
       boundary is a QUALIFIER stated beside the counts, not a term inside them.
    5. WHERE THE POPULATION IS UNKNOWN -- an unreadable declaration, before any
       contract is learnt -- the terminal says it could not find out WHAT to
       measure, rather than that there was nothing to measure, and never invents
       a contract name to fill the field.
    """
    # ---------------------------------------------------------------- world 1
    # The fixture must really be an under-declaration OF A REAL POPULATION: same
    # contract as the shipped declaration, and missing a consumer the shipped one
    # really declares. Otherwise this oracle would be staging a demonstration.
    narrow_declared = _declared_consumer_names(UNDER_DECLARED_DECLARATION)
    shipped_declared = _declared_consumer_names(DECLARATION)
    assert DROPPED_REAL_CONSUMER in shipped_declared, (
        f"this oracle needs {DROPPED_REAL_CONSUMER!r} to be a REAL declared "
        f"consumer of the shipped contract; the shipped declaration lists "
        f"{shipped_declared}"
    )
    assert DROPPED_REAL_CONSUMER not in narrow_declared, (
        f"the under-declared fixture must DROP the real consumer "
        f"{DROPPED_REAL_CONSUMER!r}; it declares {narrow_declared}"
    )
    assert len(narrow_declared) < len(shipped_declared)

    narrow_exit, narrow_stdout, narrow_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            UNDER_DECLARED_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )

    # THE NARROW GREEN IS STILL A GREEN. Every consumer this declaration names
    # really ran and really accepted the real artifact, so the verdict is
    # CORRECT. What was missing was never its colour -- it was its SCOPE.
    assert narrow_exit == 0, (
        f"an honest under-declaration whose declared consumer accepts the real "
        f"artifact is still green (exit 0); got {narrow_exit}\n"
        f"stdout:\n{narrow_stdout}\nstderr:\n{narrow_stderr}"
    )
    narrow = _outcome(narrow_stdout)
    assert narrow["verdict"] == "AgreementCrossed"

    # THE COUNTS KEEP EXACTLY THEIR PREVIOUS MEANING. An undeclared reader is NOT
    # a census entry: the census lists structural facts the checker NEEDED and
    # could not resolve, while an undeclared party is one it was never asked
    # about. Folding them in would break `verified + consumer entries ==
    # declared` and make every green unreachable.
    assert _assert_census_is_well_formed(narrow, narrow_stdout) == []
    assert narrow["declared_consumers"] == len(narrow_declared)
    assert narrow["verified_consumers"] == len(narrow_declared)

    narrow_scope = _assert_scope_states_the_boundary(
        narrow, narrow_stdout, declaration=UNDER_DECLARED_DECLARATION
    )
    assert narrow_scope["contract"] == CONTRACT
    assert narrow_scope["measured"] == (
        f"{len(narrow_declared)} declared consumer(s) of {CONTRACT}, "
        f"listed in {UNDER_DECLARED_DECLARATION}"
    ), (
        f"scope.measured must name the COUNT, the CONTRACT and the FILE that "
        f"decided the population; got {narrow_scope['measured']!r}"
    )

    # `in_reach` IS THE DECLARED NAMES, IN DECLARATION ORDER, AND NOTHING ELSE.
    assert narrow_scope["out_of_reach"]["in_reach"] == narrow_declared, (
        f"in_reach must be exactly the consumer names the declaration lists, in "
        f"declaration order: expected {narrow_declared}, got "
        f"{narrow_scope['out_of_reach']['in_reach']}"
    )

    # NO TREE WAS READ TO PRODUCE THIS. The dropped consumer is a real reader of
    # the same contract sitting in the same repository -- and the terminal does
    # not mention it ANYWHERE, on either half. A checker that named it would have
    # had to scan for it, and a scan that found nothing would have licensed the
    # far stronger claim "nobody else consumes this".
    assert DROPPED_REAL_CONSUMER not in narrow_stdout, (
        f"the boundary is DECLARED, never measured by reading the tree: the "
        f"under-declared run must never name the dropped real consumer "
        f"{DROPPED_REAL_CONSUMER!r}:\n{narrow_stdout}"
    )

    # THE HUMAN HALF STATES THE SAME LIMIT, in the same single line, behind a
    # FIXED greppable lead-in so an examiner who sees no source can find it.
    narrow_human = _human_lines(narrow_stdout)
    expected_clause = (
        f"{BOUNDARY_LEAD_IN} {len(narrow_declared)} consumer(s) declared in "
        f"{UNDER_DECLARED_DECLARATION}; any other reader of {CONTRACT} was NOT "
        f"executed and is counted in no field of this outcome."
    )
    assert any(expected_clause in line for line in narrow_human), (
        f"the human half must state the SAME limit as the machine half:\n"
        f"expected {expected_clause!r}\nstdout:\n{narrow_stdout}"
    )

    # ---------------------------------------------------------------- world 2
    # THE SAME PUBLIC INVOCATION over the FULL declaration: no flag, no opt-in,
    # and a scope that is DIFFERENT because the population is different.
    full_exit, full_stdout, full_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert full_exit == 0, (
        f"expected the shipped declaration to stay green; got {full_exit}\n"
        f"stdout:\n{full_stdout}\nstderr:\n{full_stderr}"
    )
    full = _outcome(full_stdout)
    full_scope = _assert_scope_states_the_boundary(
        full, full_stdout, declaration=DECLARATION
    )
    assert full_scope["contract"] == CONTRACT
    assert full_scope["out_of_reach"]["in_reach"] == shipped_declared
    assert full_scope["measured"] == (
        f"{len(shipped_declared)} declared consumer(s) of {CONTRACT}, "
        f"listed in {DECLARATION}"
    )

    # THE SHIPPED GREEN NOW SAYS WHAT IT SPEAKS FOR TOO. This is the verdict that
    # today reads as a claim about the CONTRACT rather than about a LIST.
    assert any(
        f"{BOUNDARY_LEAD_IN} {len(shipped_declared)} consumer(s) declared in "
        f"{DECLARATION};" in line
        for line in _human_lines(full_stdout)
    ), f"the shipped green must state its own boundary:\n{full_stdout}"

    # ---------------------------------------------------------------- world 4
    # THE LIMIT IS ON THE RED, with a THIRD, larger declared population.
    refusing_declared = _declared_consumer_names(REFUSING_DECLARATION)
    red_exit, red_stdout, red_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            REFUSING_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    assert red_exit == 1, (
        f"expected the committed refusal to stay red (exit 1); got {red_exit}\n"
        f"stdout:\n{red_stdout}\nstderr:\n{red_stderr}"
    )
    red = _outcome(red_stdout)
    assert red["verdict"] == "AgreementRefused"
    red_scope = _assert_scope_states_the_boundary(
        red, red_stdout, declaration=REFUSING_DECLARATION
    )
    assert red_scope["contract"] == CONTRACT
    assert red_scope["out_of_reach"]["in_reach"] == refusing_declared

    # THE QUALIFIER DOES NOT REINTERPRET A SINGLE SHIPPED FIELD. The red still
    # names WHICH consumer refused, and the counts still reconcile through the
    # census exactly as before: this value ADDS a qualifier beside them.
    red_census = _assert_census_is_well_formed(red, red_stdout)
    assert red_census == []
    assert red["declared_consumers"] == len(refusing_declared)
    assert red["verified_consumers"] == len(refusing_declared)
    assert [entry["name"] for entry in red["refused"]] == [refusing_declared[1]]

    # ALL THREE RENDERINGS ARE DISTINCT. A scope whose bytes do not change
    # between a 1-, 2- and 3-consumer declaration is a constant banner, and a
    # constant banner is indistinguishable from boilerplate nobody reads.
    renderings = [
        json.dumps(narrow_scope, sort_keys=True),
        json.dumps(full_scope, sort_keys=True),
        json.dumps(red_scope, sort_keys=True),
    ]
    assert len(set(renderings)) == 3, (
        f"scope must be DERIVED FROM THE RUN, never a constant banner; the "
        f"1-, 2- and 3-consumer runs rendered {renderings}"
    )

    # ---------------------------------------------------------------- world 5
    assert not (REPOSITORY_ROOT / ABSENT_DECLARATION).exists()
    unknown_exit, unknown_stdout, unknown_stderr = run_cli_in_process(
        [
            "verify-agreement",
            "--repo-root",
            str(REPOSITORY_ROOT),
            "--declaration",
            ABSENT_DECLARATION,
        ],
        cwd=REPOSITORY_ROOT,
    )
    # AN UNREADABLE DECLARATION STAYS INDETERMINATE (2) -- and STILL carries the
    # boundary, naming the declaration path the operator was pointed at.
    assert unknown_exit == 2, (
        f"an unreadable declaration is indeterminate (2); got {unknown_exit}\n"
        f"stdout:\n{unknown_stdout}\nstderr:\n{unknown_stderr}"
    )
    unknown = _outcome(unknown_stdout)
    assert unknown["verdict"] == "AgreementIndeterminate"
    unknown_scope = _assert_scope_states_the_boundary(
        unknown, unknown_stdout, declaration=ABSENT_DECLARATION
    )

    # A CONTRACT NAME IS NEVER INVENTED TO FILL THE FIELD.
    assert unknown_scope["contract"] == "UNKNOWN", (
        f"where no declaration could be read, the contract is the literal "
        f"'UNKNOWN'; got {unknown_scope['contract']!r}"
    )
    # Measured today this run prints `VERIFIED 0 of 0 declared consumer(s)`,
    # which reads as "there was nothing to measure" rather than "I could not
    # find out WHAT to measure". That is the distinction this states.
    assert unknown_scope["measured"] == (
        f"UNKNOWN: the declared population could not be read from {ABSENT_DECLARATION}"
    ), f"got {unknown_scope['measured']!r}"
    assert unknown_scope["out_of_reach"]["in_reach"] == [], (
        f"with no declaration read, the INSIDE of the boundary is empty rather "
        f"than guessed; got {unknown_scope['out_of_reach']['in_reach']}"
    )

    # THE SAME GREPPABLE LEAD-IN, ONE unambiguous other form, so `_terminal` never
    # has to render an `<n>` or a `<contract>` it does not have.
    unknown_clause = (
        f"{BOUNDARY_LEAD_IN} the consumer(s) declared in {ABSENT_DECLARATION}, and "
        f"that population is UNKNOWN because the declaration could not be read; "
        f"this run executed no reader of any contract and counts none in any "
        f"field of this outcome."
    )
    assert any(unknown_clause in line for line in _human_lines(unknown_stdout)), (
        f"the unknown-population human half must state the same limit:\n"
        f"expected {unknown_clause!r}\nstdout:\n{unknown_stdout}"
    )
    assert CONTRACT not in unknown_stdout, (
        f"a contract name must never be invented for a declaration that could "
        f"not be read:\n{unknown_stdout}"
    )
