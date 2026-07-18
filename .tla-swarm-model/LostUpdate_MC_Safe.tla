---- MODULE LostUpdate_MC_Safe ----
(* Control config: both landing mechanisms are scope-exact. Expectation: *)
(* NoLostUpdate holds in every reachable state (argued in REPORT.md S6). *)
EXTENDS Naturals, TLC

Items == {"i1", "i2"}
Files == {"f1", "f2"}
Scope == ("i1" :> {"f1"}) @@ ("i2" :> {"f2"})
DirectItems == {"i1"}
DirectApplyScoped == TRUE
MergeScoped == TRUE

VARIABLES status, version, visible, snapshot, mergeLock

INSTANCE LostUpdate
====
