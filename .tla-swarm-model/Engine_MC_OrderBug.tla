---- MODULE Engine_MC_OrderBug ----
(* 2 items, ONE lane, plain same-lane sequential dependency (i2 follows   *)
(* i1, no join at all). StrictLanding=FALSE: the readiness check accepts  *)
(* "predecessor has been admitted/dispatched" instead of requiring        *)
(* "predecessor has landed" -- a plausible off-by-one bug (reading a      *)
(* dispatched-set instead of a committed-set). Expectation: OrderRespected*)
(* is VIOLATED -- see REPORT.md S6 Trace 3 for the 2-step hand trace.     *)
EXTENDS Naturals, FiniteSets, TLC

Items == {"i1", "i2"}
Lanes == {"L1"}
NoPred == "NoPred"
LaneOf == ("i1" :> "L1") @@ ("i2" :> "L1")
LanePred == ("i1" :> NoPred) @@ ("i2" :> "i1")
JoinPred == ("i1" :> {}) @@ ("i2" :> {})
Scope == ("i1" :> {"f1"}) @@ ("i2" :> {"f2"})
MaxWorkers == 2
StrictLanding == FALSE

VARIABLES status, mergeLock

INSTANCE Engine
====
