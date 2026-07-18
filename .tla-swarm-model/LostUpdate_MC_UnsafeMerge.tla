---- MODULE LostUpdate_MC_UnsafeMerge ----
(* Both items are worktree items (no direct-to-trunk item at all here).   *)
(* The merge landing mechanism is UNSCOPED (restores the worktree's full  *)
(* stale cut-time snapshot for out-of-scope files instead of leaving      *)
(* current trunk state alone). Expectation: NoLostUpdate is VIOLATED --   *)
(* see REPORT.md S6 Trace 2 for the 6-step hand trace: i1 is cut before   *)
(* i2 exists, i2 lands f2 while i1 is still running, then i1's stale      *)
(* merge silently reverts i2's already-landed change to f2.               *)
EXTENDS Naturals, TLC

Items == {"i1", "i2"}
Files == {"f1", "f2"}
Scope == ("i1" :> {"f1"}) @@ ("i2" :> {"f2"})
DirectItems == {}
DirectApplyScoped == TRUE
MergeScoped == FALSE

VARIABLES status, version, visible, snapshot, mergeLock

INSTANCE LostUpdate
====
