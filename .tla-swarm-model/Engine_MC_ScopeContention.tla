---- MODULE Engine_MC_ScopeContention ----
(* 2 items, 2 DIFFERENT lanes, NO declared Pred between them at all -- but *)
(* their declared scopes OVERLAP (both touch "fShared"). Tests whether    *)
(* the safety work is actually done by scope-disjointness rather than by  *)
(* lane membership or declared dependency edges. Expectation: all         *)
(* invariants hold (the two items are forced to serialize despite having  *)
(* nothing declared between them, and despite 2 free worker slots), and   *)
(* EventualDrain still holds -- see REPORT.md S7.                         *)
EXTENDS Naturals, FiniteSets, TLC

Items == {"i1", "i2"}
Lanes == {"L1", "L2"}
NoPred == "NoPred"
LaneOf == ("i1" :> "L1") @@ ("i2" :> "L2")
LanePred == ("i1" :> NoPred) @@ ("i2" :> NoPred)
JoinPred == ("i1" :> {}) @@ ("i2" :> {})
Scope == ("i1" :> {"fShared"}) @@ ("i2" :> {"fShared"})
MaxWorkers == 2
StrictLanding == TRUE

VARIABLES status, mergeLock

INSTANCE Engine
====
