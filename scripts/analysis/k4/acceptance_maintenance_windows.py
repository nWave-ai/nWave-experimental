"""K4 hidden acceptance — healthchecks maintenance windows.

Copied into the subject as `hc/api/tests/test_k4_acceptance.py` AFTER both arms
have delivered. Neither arm ever sees it. It is blind by construction rather
than by promise: it was authored and committed before any delivery existed, so
there was nothing to tune it against.

It lives here, outside `tests/`, because it is a Django test for a different
repository. nWave's own pytest never collects it.

## What it may touch, and why the boundary is drawn there

Only surfaces that exist in healthchecks TODAY: the `Project`/`Check`/`Channel`
ORM for fixture setup, the ping and management-API endpoints, the `sendalerts`
command and its module-level `notify()`, and `Flip`/`Notification` rows as
observations. Plus exactly one thing the arms were also told: the pre-registered
`maintenance_windows` API field.

It may NOT import anything an arm introduced, nor assert on any name beyond that
field. A suite needing an arm's internals measures whether that arm guessed the
author, not whether the feature works.

## The two pinned outcomes, and the one they discriminate

The requirement pins that a window suppresses notification and that the outage
stays visible in the check's history. The second is not decoration: it selects
among the seams the tree offers, and an implementation that simply never lets
the check go down fails it. `Flip` is that history — the front end renders
events from it — so asserting a flip exists is asserting on the product's own
history mechanism, not on an arm's choice.

`time_machine.travel` is the subject's own clock idiom, used by eight of its
test modules. Using it is not a hint about design.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from datetime import timedelta as td

import time_machine
from django.test import Client, tag
from hc.api.management.commands.sendalerts import Command, notify
from hc.api.models import Channel, Check, Flip, Notification
from hc.test import BaseTestCase


#: A Sunday, 02:30 UTC. Sunday because the windows below recur weekly; 02:30
#: because it sits inside a 02:00 window and outside a 05:00 one, and because
#: 02:30 UTC is 04:30 in Europe/Rome — which is what makes the timezone cases
#: below able to fail in BOTH directions.
CURRENT_TIME = datetime(2026, 8, 9, 2, 30, tzinfo=timezone.utc)

API_KEY = "X" * 32


# Tagged so the regression run can EXCLUDE it. Without the tag the subject's
# own suite would re-run these cases, and a feature failure would show up as a
# regression too - two measurements that are supposed to be independent,
# collapsed into one.
@tag("k4")
@time_machine.travel(CURRENT_TIME)
class MaintenanceWindowAcceptance(BaseTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.project.api_key = API_KEY
        self.project.save()
        self.channel = Channel.objects.create(project=self.project, kind="email")
        self.channel.value = json.dumps(
            {"value": "alice@example.org", "up": True, "down": True}
        )
        self.channel.save()

    # ---- helpers, deliberately thin -------------------------------------

    def _api(self) -> Client:
        return Client(headers={"x-api-key": API_KEY})

    def _check_with_windows(self, windows: list[dict], tz: str = "UTC") -> Check:
        """Create a check through the API so the window arrives by the
        pre-registered contract, not by an ORM field only one arm would have."""
        response = self._api().post(
            "/api/v3/checks/",
            data=json.dumps({"name": "svc", "tz": tz, "maintenance_windows": windows}),
            content_type="application/json",
        )
        self.assertIn(
            response.status_code,
            (200, 201),
            f"creating a check with maintenance_windows failed: {response.content!r}",
        )
        check = Check.objects.get(code=response.json()["uuid"])
        # Without this the check has no channels, `select_channels()` returns
        # empty, and EVERY case reads zero notifications — including the ones
        # that are supposed to prove an alert still goes out. The first run of
        # this suite did exactly that: three cases failed and two "passed"
        # vacuously. `assign_all_channels` is the product's own method.
        check.assign_all_channels()
        return check

    #: `last_ping` is chosen so the check flips INSIDE the window, not merely so
    #: that it flips. `sendalerts` stamps the flip with `going_down_after()` --
    #: `last_ping + timeout + grace`, the moment the outage began -- not with the
    #: current time, and a correct implementation asks whether THAT moment is in
    #: a window. The first version used `last_ping = now - 2 days`, which placed
    #: the flip ~23 hours in the past, on the WRONG DAY for a weekly window. Both
    #: arms suppressed correctly and this suite still called them failures.
    #:
    #: It survived the red check because on the unmodified subject nothing
    #: suppresses, so the flip's timestamp could not matter. **Watching a test
    #: fail without an implementation does not show that it passes with a correct
    #: one.** Red alone is half a verification; these five minutes are the other
    #: half, paid late.
    _AGE = td(days=1, hours=1, minutes=5)

    def _drive_it_down(self, check: Check) -> None:
        """Age the check so it flips five minutes ago, then run the real path."""
        # `_AGE` assumes the subject's DEFAULT timeout (1 day) and grace (1 hour),
        # because `going_down_after()` is `last_ping + timeout + grace`. That was
        # an implicit assumption until independent review named it. Asserted, not
        # commented: a delivery that changes those defaults would silently move
        # the flip out of the window and this suite would report a feature
        # failure that is really a fixture failure — which has happened once
        # already in this campaign.
        self.assertEqual(
            (check.timeout, check.grace),
            (td(days=1), td(hours=1)),
            "the subject's default timeout/grace changed; _AGE no longer places "
            "the flip inside the window and every window case is invalid",
        )
        Check.objects.filter(id=check.id).update(
            status="up",
            last_ping=CURRENT_TIME - self._AGE,
            alert_after=CURRENT_TIME - td(minutes=1),
        )
        Command().handle_going_down()
        for flip in Flip.objects.filter(owner=check, processed=None):
            notify(flip)

    def _assert_outage_is_still_visible(self, check: Check) -> None:
        check.refresh_from_db()
        self.assertEqual(check.status, "down", "the outage was erased, not suppressed")
        self.assertTrue(
            Flip.objects.filter(owner=check, new_status="down").exists(),
            "no flip recorded: an operator could not tell afterwards what broke",
        )

    # ---- the cases -------------------------------------------------------

    def test_a_check_failing_inside_a_window_notifies_nobody(self) -> None:
        check = self._check_with_windows(
            [{"schedule": "0 2 * * SUN", "duration": 3600}]
        )

        self._drive_it_down(check)

        self.assertEqual(Notification.objects.count(), 0)
        self._assert_outage_is_still_visible(check)

    def test_a_check_failing_outside_a_window_still_notifies(self) -> None:
        """The discriminating twin. Without it, an arm that suppressed every
        notification unconditionally would pass the case above."""
        check = self._check_with_windows(
            [{"schedule": "0 5 * * SUN", "duration": 3600}]
        )

        self._drive_it_down(check)

        self.assertEqual(Notification.objects.count(), 1)

    def test_a_check_with_no_window_is_unaffected(self) -> None:
        """The regression case: the feature must not change the default product."""
        check = self._check_with_windows([])

        self._drive_it_down(check)

        self.assertEqual(Notification.objects.count(), 1)

    def test_the_window_is_read_in_the_checks_own_timezone(self) -> None:
        """04:00 Europe/Rome is 02:00 UTC in August, and the clock reads 02:30
        UTC. An arm evaluating the schedule in UTC finds 04:00 still ahead and
        pages anyway."""
        check = self._check_with_windows(
            [{"schedule": "0 4 * * SUN", "duration": 3600}], tz="Europe/Rome"
        )

        self._drive_it_down(check)

        self.assertEqual(Notification.objects.count(), 0)
        self._assert_outage_is_still_visible(check)

    def test_a_timezone_window_that_has_already_closed_still_notifies(self) -> None:
        """The mirror. 02:00 Europe/Rome closed at 01:00 UTC, well before the
        flip at 02:25 UTC, so a correct arm pages.

        **Corrected after independent review 2026-08-07.** This docstring used to
        claim the case above was "passed by an arm that applies the offset
        backwards" — it is not, and the attribution was simply wrong. Worked
        through, the two cases catch different mistakes:

        | mistake | caught by |
        |---|---|
        | offset applied backwards (04:00 Rome read as 06:00 UTC) | the case ABOVE |
        | window treated as always-open, time ignored | THIS case |
        | timezone ignored, schedule read in UTC | **both** |

        So the pair is still justified — neither case is redundant — but for a
        reason other than the one written here. A comment that misnames what a
        test discriminates is worse than none: it tells the next reader the
        coverage is somewhere it is not."""
        check = self._check_with_windows(
            [{"schedule": "0 2 * * SUN", "duration": 3600}], tz="Europe/Rome"
        )

        self._drive_it_down(check)

        self.assertEqual(Notification.objects.count(), 1)

    def test_the_api_round_trips_the_declared_contract(self) -> None:
        """Read-back through the pre-registered field. A window that cannot be
        read is a window an operator cannot audit before trusting it."""
        windows = [{"schedule": "0 2 * * SUN", "duration": 3600}]
        check = self._check_with_windows(windows)

        response = self._api().get(f"/api/v3/checks/{check.code}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["maintenance_windows"], windows)
