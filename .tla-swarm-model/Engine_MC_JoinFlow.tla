---- MODULE Engine_MC_JoinFlow ----
(* Baseline pile: 2 lanes, 3 items total, MaxWorkers=2. i1 (lane L1) and   *)
(* i2 (lane L2) have no predecessors and disjoint scope; i3 is a JOIN in  *)
(* lane L1 (its lane-predecessor is i1, its extra join-predecessor is i2) *)
(* and cannot start until BOTH have landed. StrictLanding=TRUE (correct   *)
(* readiness rule). Expectation: all invariants hold, EventualDrain holds *)
(* -- see REPORT.md S6 for the hand-argument (finite monotonic system).   *)
EXTENDS Naturals, FiniteSets, TLC

Items == {"i1", "i2", "i3"}
Lanes == {"L1", "L2"}
NoPred == "NoPred"
LaneOf == ("i1" :> "L1") @@ ("i2" :> "L2") @@ ("i3" :> "L1")
LanePred == ("i1" :> NoPred) @@ ("i2" :> NoPred) @@ ("i3" :> "i1")
JoinPred == ("i1" :> {}) @@ ("i2" :> {}) @@ ("i3" :> {"i2"})
Scope == ("i1" :> {"f1"}) @@ ("i2" :> {"f2"}) @@ ("i3" :> {"f3"})
MaxWorkers == 2
StrictLanding == TRUE

VARIABLES status, mergeLock

INSTANCE Engine
====
