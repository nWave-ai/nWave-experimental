# PO + DES DISCUSS evaluation

Success criteria fixed before the first run: preserve the exact Request and recorded
human choices; leave undecided matters open; derive small visible increments;
respect visual exploration choices; invent no prototype, trace, proof or approval.
Use the existing `nw-po-review-dimensions` and `nw-por-review-criteria` for semantic
review, adding no aggregate score that can conceal invented decisions.

`cases.json` is a synthetic recorded-answer replay, not a human interview. The
native PO is the named `nw-product-owner` agent (`--agent`/`--agents`, Read plus
the StructuredOutput transport tool). Its one-line prompt refers to the role
instructions loaded once via `load_role_instructions` and appended with
`--append-system-prompt-file`. Input is DISCUSS v2 (jtbd/journey/gherkin may be
`not_explored`, Quint `not_run`; see `des discuss --describe-input`).
The harness acts as the host, asks for the current DISCUSS manifest, invokes real
`des discuss`, then the shared nWave HTML renderer in an isolated repository.
It does not invoke `des po`, whose decomposition envelope is a different contract.

```text
PYTHONPATH=src .venv/bin/python tests/evals/nw-product-owner-discuss/run_probe.py --output-root /absolute/persistent/new-directory --model sonnet --feature no-ui
```

Installed mode (parent supplies clean artifacts; PYTHONPATH is removed, the DES
CLI/renderer run from the fresh isolated repo):

```text
<wheel-venv>/bin/python run_probe.py --output-root /abs/new --feature no-ui \
  --role-spec <installed>/nw-product-owner.md --des-python <wheel-venv>/bin/python
```

Results record mode, role path and file hash, and all PRELOADED SKILL names.

This buys one native Claude turn per selected case (budget bounded per call).
Without `--feature` it runs the four cases. Records retain exact prompts, loaded role
instructions, their hashes, provider output/cost, elapsed time, constructor and
renderer results, manifest, Markdown and HTML. Failed turns remain evidence.
Preload is not evidence of semantic use. The native host can read conditional
skills; absent read traces leave that dimension unmeasured.

Mechanical checks cover construction, exact Request preservation and branding;
semantic checks require an independent reviewer of the conversation and artifacts.
Human comprehension remains INDETERMINATE until a person reads the actual view and
can explain or challenge its consequences. Model review cannot fill that result.

For a live test, the host facilitates an actual PO conversation using the same
role/skills. Keep the human answers verbatim and capture the resulting manifest.
Review one topic at a time through the generated HTML. Record misunderstood or
corrected consequences, unnecessary questions and unresolved decisions; do not
require a quiz or force approval. Compare the unchanged replay case after a fix,
then a fresh case to check transfer. Measure human waiting separately from active
time; missing cost stays unknown. No claims of causal improvement from one run.

Failure ownership: conversation/meaning -> PO; UX prototype -> UX specialist;
semantic input rejected -> inspect caller/schema; preserved input rendered wrongly
-> DES/renderer; downstream missing decision -> DISCUSS/DESIGN handoff.
