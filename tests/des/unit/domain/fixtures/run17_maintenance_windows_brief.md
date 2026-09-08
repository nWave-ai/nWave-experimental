# Architecture Brief

## ADR-MAINT-WIN-001: Recurring Maintenance Windows for Notification Suppression {#adr-maint-win-001}

### Context

Operators need to declare recurring maintenance windows on a `Check`
(cron-style recurrence + duration, interpreted in the check's own timezone)
such that: (1) a failure occurring while the check is inside a window does
not deliver a notification on any channel, and (2) the outage remains
visible afterward in that check's own ping/status history. Management API
v3 check representation gains `maintenance_windows: [{"schedule": "<cron
expr>", "duration": <seconds>}]`, readable via GET and writable via
POST/PUT on the existing check create/update endpoints.

### Decision

**Storage.** Add `maintenance_windows = models.JSONField(default=list,
blank=True)` to `Check`, alongside the existing `kind`/`schedule`/`tz`
fields (`hc/api/models.py:199-203`), storing a list of `{"schedule": str,
"duration": int}` objects. No new per-window timezone field: each window is
interpreted through the check's existing `tz` field
(`hc/api/models.py:203`), reused as-is — this is exactly what "interpreted
in the check's own timezone" already means for `kind="cron"` checks.

**Recurrence/timezone handling.** Reuse the cron-in-timezone pattern
`Check.get_grace_start()` already implements for `kind="cron"`
(`hc/api/models.py:311-322`): convert the reference instant to the check's
local time via `ZoneInfo(self.tz)`, drive occurrence computation through
the already-imported `CronSim` library, convert the result back to UTC.
Add `Check.in_maintenance_window(self, at: datetime) -> bool`: for each
`{schedule, duration}` entry, find the most recent `CronSim` trigger at/before
`at` in `ZoneInfo(self.tz)`, convert to UTC, and test `trigger_utc <= at <
trigger_utc + timedelta(seconds=duration)`. No new recurrence/timezone
library or algebra is introduced — pure extension of an existing,
production-proven pattern (REUSE_CANDIDATE). The same fail-safe shape
`get_grace_start()` uses for `kind="oncalendar"` — catching iterator
exhaustion rather than raising (`hc/api/models.py:326-331`) — is reused for
an unparseable/exhausted maintenance-window schedule: fail open (treat as
"not in a window"), never raise into the caller.

**Suppression integration point.** Extend `Flip.select_channels()` (an
existing method on `Check`'s companion `Flip` model, confirmed present in
`hc/api/models.py`) to return `[]` when `self.new_status == "down"` and
`self.owner.in_maintenance_window(self.created)`. This reuses the *exact*
existing no-notification seam already exercised in production:
`hc/api/management/commands/sendalerts.py:35-37` —
`channels = flip.select_channels(); if not channels: return None`. No
change is needed to `sendalerts.py`, `Flip.notify`, or `Flip` persistence.
Critically, `Flip` creation in `handle_going_down()`
(`hc/api/management/commands/sendalerts.py:170-175`, `flip.save()`) runs
unconditionally, *before* `select_channels()` is ever consulted by the
notify path — so requirement (2), ping/status-history visibility, holds by
construction: suppression only prunes the channel list consumed
downstream, it never touches `Flip`/`Ping` persistence or `Check.status`.

**API v3 boundary.** `maintenance_windows` becomes a new key in
`CheckDict`/`Check.to_dict()` (both confirmed present in
`hc/api/models.py`), read/write-through on the existing v3 check
create/update request flow in `hc/api/views.py`. That flow already
validates `schedule` and `tz` through Pydantic `@field_validator`s in the
same request model (`hc/api/views.py:114-132`): `check_schedule` builds
`CronSim(v, datetime(2000, 1, 1))` and calls `next()`, raising
`PydanticCustomError("cron_syntax", ...)` on `CronSimError`/`StopIteration`.
Reuse this exact pattern per `maintenance_windows[].schedule` entry, plus a
sibling validator requiring `duration` to be a positive integer bounded to
at most 31 days (`0 < duration <= 2678400`), so malformed entries are
rejected at the request boundary (INVALID_STATE) and never reach
`Check.maintenance_windows` in storage or `in_maintenance_window()` at
evaluation time.

**Dependency readiness.** No new dependency. `CronSim`/`OnCalendar`/
`ZoneInfo` are already imported and load-bearing in `hc/api/models.py`
(`hc/api/models.py:311-322`) and `hc/api/views.py`
(`hc/api/views.py:114-132`) — owner: existing repository dependency;
identity: the same `CronSim`/`OnCalendar` already used for `kind="cron"`/
`"oncalendar"` checks; declared=yes (already imported in both files);
present=yes (already exercised by existing production code paths read
above). No manifest delta, no install.

### Obligations (RED_TO_GREEN)

Derived from the closed architecture obligation vocabulary.
`BROAD_INPUT_DOMAIN`
is deliberately not claimed: no PBT framework (e.g. Hypothesis) is declared
in this repository's `requirements.txt`/`requirements-dev.txt` (checked,
absent), so time/schedule-boundary behavior is proven through named
canonical examples under `time_machine.travel`, the same technique this
repository's own cron tests already use — not a fabricated PBT adapter.

**1. REUSE_CANDIDATE** — reuse of the `CronSim`/`ZoneInfo` cron-in-timezone
algebra and the `select_channels()` suppression seam.
- Observable law: `in_maintenance_window(at)` for `{schedule, duration}`
  returns True iff `at` falls in `[trigger, trigger+duration)` for the most
  recent `schedule` trigger at/before `at`, computed in `ZoneInfo(check.tz)`
  exactly as `get_grace_start()` computes cron-kind occurrences.
- Input domain / invalid boundaries: valid five-field cron strings;
  `duration` in `(0, 2678400]` seconds; invalid: `duration <= 0` or
  malformed cron, both rejected at the API boundary (obligation 4), never
  reaching this oracle.
- Observation point: `Check.in_maintenance_window()`, observed through
  `Flip.select_channels()`'s return value — the same call site
  `sendalerts.py:35` already uses, not an internal-only seam.
- Base-revision production symbols / test helper ATD must reuse:
  `hc.api.models.Check`, `Check.get_grace_start`
  (`hc/api/models.py:299-336`, the pattern to mirror), `hc.test.BaseTestCase`
  and `time_machine` (both imported at `hc/api/tests/test_check_model.py:7,12`).
- Fixture/lifecycle isolation: in-memory `Check()` instance (unsaved), as
  `test_status_works_with_cron_syntax` does
  (`hc/api/tests/test_check_model.py:44-59`); set `kind`/`schedule`/`tz`/
  `maintenance_windows`/`status`/`last_ping` directly; wrap assertions in
  `with time_machine.travel(<iso-instant>):` — no DB fixture required.
- Oracle target locator: `hc/api/tests/test_check_model.py`, new
  `test_in_maintenance_window` method in `CheckModelTestCase`, placed after
  `test_status_works_with_cron_syntax` (line 59).
- Canonical examples (2): (a) `{"schedule": "0 0 * * *", "duration": 3600}`,
  `tz="UTC"`: `at=2000-01-02T00:30:00Z` → True; `at=2000-01-02T01:30:00Z` →
  False. (b) same window, `tz="America/New_York"`, `at` chosen across a
  DST-transition midnight, mirroring the DST-safety rationale already
  documented at `hc/api/models.py:314-315`.
- Verification argv: `python manage.py test hc.api.tests.test_check_model`.
- Intended RED observation: `AttributeError: 'Check' object has no
  attribute 'in_maintenance_window'`.

**2. ARCHITECTURE_BOUNDARY_CHANGE** — new field on the v3 check
representation.
- Observable law: GET on a check with `maintenance_windows` set returns
  that exact list; POST/PUT accepting `maintenance_windows` persists it
  verbatim and a subsequent GET round-trips it unchanged; omitted key
  defaults to `[]`.
- Input domain / invalid boundaries: same cron/duration validity boundary
  as obligation 4.
- Observation point: the v3 check create/update request-validation flow in
  `hc/api/views.py`, the same Pydantic request model already validating
  `schedule`/`tz` via `@field_validator` (`hc/api/views.py:114-132`).
- Base-revision production symbols: `Check.to_dict`, `CheckDict` (both
  confirmed present in `hc/api/models.py`).
- Fixture/lifecycle isolation: Django `TestCase` DB-transaction rollback
  per test (`hc.test.BaseTestCase` default).
- Oracle target locator: `hc/api/tests/test_check_model.py` (to_dict
  round-trip assertion) plus the existing v3 check-update API test module
  under `hc/api/tests/` (exact file to be confirmed by DISTILL against the
  `update_check`/`create_check` handlers already located at
  `hc/api/views.py`).
- Canonical examples (2): (a) create with
  `maintenance_windows: [{"schedule": "0 0 * * *", "duration": 3600}]` →
  GET returns the same list. (b) update omitting the key leaves a
  previously-set list unchanged (partial-update semantics matching
  existing `schedule`/`tz` fields).
- Verification argv: `python manage.py test hc.api.tests.test_check_model`.
- Intended RED observation: `KeyError`/`AssertionError` — `maintenance_windows`
  absent from `Check.to_dict()`'s returned dict.

**3. PRESERVATION** — ping/status history must survive suppression
unchanged.
- Observable law: for every `Flip` created by `handle_going_down()`
  (`hc/api/management/commands/sendalerts.py:123-177`) while the owning
  check is inside a maintenance window, the `Flip` row is persisted exactly
  as before this change (`sendalerts.py:170-175`, `flip.save()`) —
  suppression changes only `select_channels()`'s return value, never
  `Flip`/`Ping` creation or `Check.status`.
- Input domain: any status transition already covered by
  `handle_going_down()`.
- Observation point: `Flip.objects` after a suppressed transition.
- Base-revision symbols / test helper: `hc.api.models.Flip`,
  `hc.api.management.commands.sendalerts` (`sendalerts.py:170-175`),
  `hc.test.BaseTestCase`.
- Fixture/lifecycle isolation: Django `TestCase` transaction rollback,
  `time_machine.travel` for deterministic `alert_after`/`last_ping`.
- Oracle target locator: `hc/api/tests/test_notify.py` (existing
  Flip/notify test module).
- Canonical examples (2): (a) check in a maintenance window goes down →
  `Flip` row exists, `flip.select_channels() == []`. (b) check outside any
  window goes down → unchanged existing behavior (channels selected
  normally).
- Verification argv: `python manage.py test hc.api.tests.test_notify`.
- Intended RED observation: `select_channels()` returns the full channel
  list even while in a maintenance window (suppression not yet
  implemented) — `self.assertEqual(flip.select_channels(), [])` fails.

**4. INVALID_STATE** — malformed maintenance-window entries must be
unrepresentable in storage.
- Observable law: a `maintenance_windows` entry with a non-parseable
  `schedule` or `duration` outside `(0, 2678400]` is rejected by API
  create/update validation and never reaches `Check.maintenance_windows`.
- Input domain / invalid boundaries: malformed cron string (e.g.
  `"not a cron"`), `duration = 0`, negative `duration`, `duration >
  2678400`.
- Observation point: same request-validation flow as obligation 2
  (`hc/api/views.py:114-132` pattern, extended).
- Base-revision production symbols / test helper: the `check_schedule`
  `@field_validator` pattern (`hc/api/views.py:114-132`) to mirror for the
  new field; `hc.test.BaseTestCase`.
- Fixture/lifecycle isolation: Django test client POST/PUT against the v3
  endpoint, DB-transaction rollback per test.
- Oracle target locator: same v3 check-update API test module named in
  obligation 2.
- Canonical examples (2): (a) POST with
  `maintenance_windows: [{"schedule": "not a cron", "duration": 3600}]` →
  422/400 validation error, check not created with that entry. (b) POST
  with `duration: 0` → same validation error.
- Verification argv: `python manage.py test hc.api.tests.test_check_model`.
- Intended RED observation: the malformed entry is currently accepted and
  stored (no validator exists yet) — the negative-case assertion (expect a
  validation error) fails.

### Residual stress (four-layer failure law)

- **Domain** (`Check.in_maintenance_window`): a check with a
  hand-corrupted persisted `schedule` (bypassing API validation, e.g. via
  direct DB write) must not raise uncaught inside `select_channels()`;
  isolate `CronSim` construction the same way `get_grace_start()` already
  isolates `OnCalendar`'s `StopIteration` (`hc/api/models.py:326-331`) —
  fail open (not suppressed) rather than raising and blocking the
  `sendalerts` worker thread.
- **Application** (`sendalerts.py`): no change required — the existing
  `if not channels: return None` short-circuit (`sendalerts.py:36-37`)
  already tolerates a zero-channel `Flip`.
- **Adapter** (v3 endpoint): malformed `maintenance_windows` on POST/PUT is
  a 4xx validation error at the request boundary, never a 5xx surfaced from
  a downstream cron-parse exception.
- **Infrastructure** (DB): `maintenance_windows` is check-scoped JSON;
  existing rows default to `[]`, no migration of existing data, no
  cross-check contagion.

### Citations verified: 15/15 (line-checked: 8, symbol-checked: 7)

Line-checked (`Read`, this consult):
1. `hc/api/models.py:199-203` — `kind`/`schedule`/`tz` fields.
2. `hc/api/models.py:311-322` — `CronSim`+`ZoneInfo` cron-in-timezone
   pattern in `get_grace_start()`.
3. `hc/api/models.py:326-331` — `OnCalendar`/`StopIteration` fail-safe
   pattern in `get_grace_start()`.
4. `hc/api/management/commands/sendalerts.py:35-37` — `select_channels()`
   empty-list short circuit.
5. `hc/api/management/commands/sendalerts.py:170-175` — `Flip` persisted
   (`flip.save()`) before `notify()` runs.
6. `hc/api/tests/test_check_model.py:7,12` — `time_machine` and
   `hc.test.BaseTestCase` imports.
7. `hc/api/tests/test_check_model.py:44-59` —
   `test_status_works_with_cron_syntax` canonical example.
8. `hc/api/views.py:114-132` — `check_schedule` Pydantic `@field_validator`
   (`CronSim`/`OnCalendar` validation pattern to reuse).

Symbol-checked (`des code-fact query.atoms-in-file --root
hc/api/models.py`, provider `ast`, confidence `approx`):
9. `Check`
10. `Flip`
11. `CheckDict`
12. `to_dict`
13. `select_channels`
14. `notify`
15. `create_flip`
