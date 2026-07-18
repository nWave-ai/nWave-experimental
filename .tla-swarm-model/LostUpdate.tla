---- MODULE LostUpdate ----
(* Isolates the trunk-write race: does landing an item ever silently revert *)
(* another item's already-landed change to a file outside the landing      *)
(* item's own declared scope?  Two independent unsafe mechanisms are       *)
(* modeled as toggles so each can be demonstrated in its own MC config:    *)
(*   - DirectApplyScoped=FALSE : the small-item direct-to-trunk path       *)
(*     "blasts" (resets to empty) every file outside its own scope, the    *)
(*     shape of a `git reset --hard` / `checkout .` style landing.         *)
(*   - MergeScoped=FALSE       : the worktree-merge path restores its      *)
(*     entire stale cut-time snapshot for out-of-scope files instead of    *)
(*     leaving current trunk state untouched — the shape of a full-tree    *)
(*     snapshot-copy merge rather than a scoped-diff apply.                *)
EXTENDS Naturals

CONSTANTS
    Items,              \* work items in this pile
    Files,              \* trunk file universe
    Scope,              \* Items -> SUBSET Files : declared file scope per item
    DirectItems,        \* SUBSET Items : items below the size floor (bypass worktree)
    DirectApplyScoped,  \* does the direct-apply landing write ONLY its own scope?
    MergeScoped         \* does the worktree-merge landing write ONLY its own scope?

ASSUME DirectItems \subseteq Items
ASSUME DirectApplyScoped \in {TRUE, FALSE}
ASSUME MergeScoped \in {TRUE, FALSE}
ASSUME \A i \in Items : Scope[i] \subseteq Files

WorktreeItems == Items \ DirectItems

VARIABLES
    status,     \* Items -> {"pending","running","applying","merging","landed"}
    version,    \* Files -> Nat : TRUE count of legitimate scoped landings that touched f
    visible,    \* Files -> Nat : what is actually observable on trunk right now
    snapshot,   \* Items -> [Files -> Nat] : `visible` captured at the item's cut time
    mergeLock   \* BOOLEAN : the single shared trunk-write slot

vars == <<status, version, visible, snapshot, mergeLock>>

Init ==
    /\ status = [i \in Items |-> "pending"]
    /\ version = [f \in Files |-> 0]
    /\ visible = [f \in Files |-> 0]
    /\ snapshot = [i \in Items |-> [f \in Files |-> 0]]
    /\ mergeLock = FALSE

\* ---------------------------------------------------------------- *)
\* worktree path (large items) : ephemeral worktree cut from HEAD   *)
\* ---------------------------------------------------------------- *)

Start(i) ==
    /\ i \in WorktreeItems
    /\ status[i] = "pending"
    /\ status' = [status EXCEPT ![i] = "running"]
    /\ snapshot' = [snapshot EXCEPT ![i] = visible]   \* cut from current HEAD
    /\ UNCHANGED <<version, visible, mergeLock>>

StartMerge(i) ==
    /\ i \in WorktreeItems
    /\ status[i] = "running"
    /\ mergeLock = FALSE
    /\ status' = [status EXCEPT ![i] = "merging"]
    /\ mergeLock' = TRUE
    /\ UNCHANGED <<version, visible, snapshot>>

LandedVersion(i) == [f \in Files |-> IF f \in Scope[i] THEN version[f] + 1 ELSE version[f]]

FinishMerge(i) ==
    /\ i \in WorktreeItems
    /\ status[i] = "merging"
    /\ LET nv == LandedVersion(i)
           scoped   == [f \in Files |-> IF f \in Scope[i] THEN nv[f] ELSE visible[f]]
           unscoped == [f \in Files |-> IF f \in Scope[i] THEN nv[f] ELSE snapshot[i][f]]
       IN
        /\ version' = nv
        /\ visible' = IF MergeScoped THEN scoped ELSE unscoped
    /\ status' = [status EXCEPT ![i] = "landed"]
    /\ mergeLock' = FALSE
    /\ UNCHANGED snapshot

\* ---------------------------------------------------------------- *)
\* direct-to-trunk path (small items, bypass the worktree entirely) *)
\* ---------------------------------------------------------------- *)

StartDirect(i) ==
    /\ i \in DirectItems
    /\ status[i] = "pending"
    /\ mergeLock = FALSE
    /\ status' = [status EXCEPT ![i] = "applying"]
    /\ mergeLock' = TRUE
    /\ snapshot' = [snapshot EXCEPT ![i] = visible]
    /\ UNCHANGED <<version, visible>>

FinishDirect(i) ==
    /\ i \in DirectItems
    /\ status[i] = "applying"
    /\ LET nv == LandedVersion(i)
           scoped == [f \in Files |-> IF f \in Scope[i] THEN nv[f] ELSE visible[f]]
           blast  == [f \in Files |-> IF f \in Scope[i] THEN nv[f] ELSE 0]
       IN
        /\ version' = nv
        /\ visible' = IF DirectApplyScoped THEN scoped ELSE blast
    /\ status' = [status EXCEPT ![i] = "landed"]
    /\ mergeLock' = FALSE
    /\ UNCHANGED snapshot

Next ==
    \E i \in Items :
        Start(i) \/ StartMerge(i) \/ FinishMerge(i) \/ StartDirect(i) \/ FinishDirect(i)

Spec == Init /\ [][Next]_vars

\* ---------------------------------------------------------------- *)
\* properties                                                       *)
\* ---------------------------------------------------------------- *)

TypeOK ==
    /\ status \in [Items -> {"pending", "running", "applying", "merging", "landed"}]
    /\ version \in [Files -> Nat]
    /\ visible \in [Files -> Nat]
    /\ mergeLock \in {TRUE, FALSE}

\* SAFETY property 1 (NO LOST UPDATE) : what is visible on trunk always
\* equals the true count of everything that has legitimately landed.
NoLostUpdate == \A f \in Files : visible[f] = version[f]

\* defensive bound in case a spec bug ever made this grow unboundedly --
\* logically version[f] can never exceed |Items| here, so this never bites
\* a correct spec, it only stops TLC from exploring past a runaway one.
LUStateConstraint == \A f \in Files : version[f] <= 4

====
