<!--
Requirement checklist — the DISTILL-open extraction the spec-coverage gate consumes
(evolution-plan P3.1/P3.2). One row per requirement, extracted from the spec /
feature-delta at DISTILL-open. The gate `des verify-spec-coverage --checklist <this
file> --at-dir <at corpus>` refuses (or, at DISTILL gate-out, surfaces ADVISORY) any
row lacking a covering AT — so no requirement is silently uncovered (the external
eval's largest lost pool: UI/e2e/NFR/security/validation/build requirements with no
AT and no trace).

GRAMMAR (both forms accepted; pick one and be consistent):
  - table row:  | R12 | requirement text | category |
  - list row:   - R12 [category] requirement text
  - hierarchical example: | R-S01-03 | requirement text | category |

ID    : ^(?:R\d+|R-S\d{2}-\d{2})$  (unique per checklist; exact only)
CATEGORY (closed set): ui | e2e | nfr | security | validation | build | functional
  ui         — a screen / control / visible state the user interacts with
  e2e        — a full user journey across the stack (persists, survives restart)
  nfr        — a non-functional requirement (latency, throughput, resource bound)
  security   — identity / authz / input-trust / secret-handling requirement
  validation — input validation / rejection of malformed or hostile input
  build      — build / packaging / fresh-clone / install requirement
  functional — core domain behaviour not in the above classes

An AT covers an ID iff it carries the exact same marker: pytest
`@pytest.mark.covers("R12")` or `@pytest.mark.covers("R-S01-03")`, a
`# covers: R12` / `# covers: R-S01-03` comment in the test body, that exact ID
in the test docstring, or a Gherkin `@covers-R12` / `@covers-R-S01-03` tag.
Partial or lookalike IDs do not cover another row.
-->

# Requirement Checklist — {feature-id}

Source: {spec / feature-delta path + section}
Extracted at: DISTILL-open

| ID | Requirement | Category |
|----|-------------|----------|
| R1 | {the user can see the available seats} | ui |
| R2 | {a client-supplied identity is rejected server-side} | security |
| R3 | {a confirmed booking survives a restart and is retrievable} | e2e |
| R4 | {confirming an already-booked seat is rejected} | validation |
| R5 | {the app builds and starts from a fresh clone via the declared recipe} | build |
