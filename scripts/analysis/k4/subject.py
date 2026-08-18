"""K4's ONE subject identity: the SUT URL and the pinned base revision every
campaign measures every arm against.

Before this module, `preflight.py` cloned `--depth 1` off the SUT's default
branch fresh per campaign -- whatever commit happened to be at the tip the
moment the clone ran, never recorded anywhere. Two consequences, both named
in the K4 matrix: row 2 (the acceptance oracle's own RED/GREEN self-probe,
see `run_acceptance._self_probe_oracle_red`) had no fixed base to be
reproducible AGAINST, and nothing stopped two arms of the SAME pair -- or two
pairs of the SAME campaign -- from landing on two different upstream commits
if the SUT's default branch moved mid-run.

`SUT_PINNED_REV` closes both: it is the single source `preflight.py` (which
clones and checks it out), `run_acceptance.py` (which cross-checks a scored
pair's own base commit against it before trusting a self-probe), and
`paired_campaign.py`'s `declared_identity_violations` (which compares the
`git checkout` target BOTH arms declared, generically -- see that function's
docstring for why it never imports this module directly) all key off.
"""

from __future__ import annotations


#: The subject under test for every K4 campaign.
SUT_URL = "https://github.com/healthchecks/healthchecks.git"

#: "Improve Slack instructions", 2026-08-11 -- the exact commit the row-2
#: self-probe was validated against by hand (docs/analysis/2026-08-05-des-
#: simplification-evidence-backed-roadmap.md, matrix row 2): the unmodified
#: oracle RED here, a replanted historical-defect (ef37b76b0) fixture ALSO
#: RED here, and the unmodified oracle GREEN against a real delivered arm
#: built from this exact commit.
#:
#: Every campaign clones `SUT_URL` and checks out exactly this commit --
#: never a shallow clone's moving default-branch tip. Bump it deliberately,
#: in a reviewed change, if the subject needs to move; never let a campaign
#: silently drift onto whatever the SUT's default branch happens to be that
#: day.
SUT_PINNED_REV = "49653c350cddc47fc00a471bd1b08b5771a7967c"
