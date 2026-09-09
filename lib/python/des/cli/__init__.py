"""des.cli — composition root for every DES CLI entry-point invocation.

The runtime freshness gate (§1 of fix-des-self-hosted-gate-sync feature-delta)
fires here at import time. The unified ``des`` console-script dispatcher (and
every ``des <subcommand>`` invocation through it) and every DES hook process
pays one process-startup probe that the installed copy of DES is consistent
with the source-of-truth it is supposed to enforce.

The two lines below are the wiring; the gate's behaviour lives in
:mod:`des.runtime.freshness`. The wiring is exercised end-to-end by the
slice-01 walking-skeleton ATs under
``tests/installer/acceptance/fix-des-self-hosted-gate-sync/``.
"""

from des.runtime.freshness import assert_fresh_or_explain


assert_fresh_or_explain()
