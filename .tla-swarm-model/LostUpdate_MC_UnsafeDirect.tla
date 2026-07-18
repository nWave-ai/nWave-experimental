---- MODULE LostUpdate_MC_UnsafeDirect ----
(* i1 is a small item that bypasses the worktree and applies directly to  *)
(* trunk; its landing mechanism is UNSCOPED (blast: resets every file     *)
(* outside its own scope to empty). i2 is a normal worktree item.         *)
(* Expectation: NoLostUpdate is VIOLATED -- see REPORT.md S6 Trace 1 for  *)
(* the 5-step hand trace (i2 lands f2, then i1's direct-apply wipes it).  *)
EXTENDS Naturals, TLC

Items == {"i1", "i2"}
Files == {"f1", "f2"}
Scope == ("i1" :> {"f1"}) @@ ("i2" :> {"f2"})
DirectItems == {"i1"}
DirectApplyScoped == FALSE
MergeScoped == TRUE

VARIABLES status, version, visible, snapshot, mergeLock

INSTANCE LostUpdate
====
