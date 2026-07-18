---- MODULE Engine ----
(* The pile-draining engine, parameterized over its pile of Items. Models  *)
(* lane sequencing, cross-lane joins, admission via scope-disjointness,    *)
(* a worker-count cap, and a single serialized trunk-write (merge) lock.   *)
(* StrictLanding toggles the readiness check for a predecessor between the *)
(* correct rule ("landed" only) and a plausible bug ("admitted/dispatched  *)
(* is enough") to demonstrate an ORDER-RESPECTED violation on demand.      *)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Items,          \* work items in this pile
    Lanes,          \* lane identifiers
    LaneOf,         \* Items -> Lanes
    LanePred,       \* Items -> Items \cup {NoPred} : same-lane predecessor
    NoPred,         \* sentinel: "no same-lane predecessor" (first item in its lane)
    JoinPred,       \* Items -> SUBSET Items : extra cross-lane predecessors (join)
    Scope,          \* Items -> SUBSET Files : declared file scope per item
    MaxWorkers,     \* concurrency cap (ephemeral-worktree slots)
    StrictLanding   \* TRUE = predecessor readiness requires "landed" (correct);
                    \* FALSE = "admitted" suffices (the bug under test)

ASSUME MaxWorkers \in Nat \ {0}
ASSUME StrictLanding \in {TRUE, FALSE}
ASSUME \A i \in Items : LaneOf[i] \in Lanes
ASSUME \A i \in Items : LanePred[i] = NoPred \/ LanePred[i] \in Items
ASSUME \A i \in Items : JoinPred[i] \subseteq Items

\* full predecessor set: same-lane chain predecessor, plus any declared join predecessors
Pred(i) == (IF LanePred[i] = NoPred THEN {} ELSE {LanePred[i]}) \cup JoinPred[i]

VARIABLES
    status,     \* Items -> {"pending","running","merging","landed"}
    mergeLock   \* BOOLEAN : the single shared trunk-write slot

vars == <<status, mergeLock>>

Init ==
    /\ status = [i \in Items |-> "pending"]
    /\ mergeLock = FALSE

InFlight == {i \in Items : status[i] \in {"running", "merging"}}

\* readiness check under test: correct rule vs the plausible bug
AdmittedOrLanded(p) ==
    IF StrictLanding THEN status[p] = "landed"
    ELSE status[p] \in {"running", "merging", "landed"}

CanStart(i) ==
    /\ status[i] = "pending"
    /\ \A p \in Pred(i) : AdmittedOrLanded(p)
    /\ Cardinality(InFlight) < MaxWorkers
    /\ \A j \in InFlight : Scope[i] \cap Scope[j] = {}

Start(i) ==
    /\ CanStart(i)
    /\ status' = [status EXCEPT ![i] = "running"]
    /\ UNCHANGED mergeLock

CanMerge(i) == status[i] = "running" /\ mergeLock = FALSE

StartMerge(i) ==
    /\ CanMerge(i)
    /\ status' = [status EXCEPT ![i] = "merging"]
    /\ mergeLock' = TRUE

CanFinish(i) == status[i] = "merging"

FinishMerge(i) ==
    /\ CanFinish(i)
    /\ status' = [status EXCEPT ![i] = "landed"]
    /\ mergeLock' = FALSE

Next == \E i \in Items : Start(i) \/ StartMerge(i) \/ FinishMerge(i)

\* whole-formula weak fairness suffices here: status is monotonic and
\* acyclic (pending->running->merging->landed, never back), so every
\* behavior has at most 3*|Items| non-stuttering steps ever possible --
\* see REPORT.md section 6 for the closed-form argument.
Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

\* ---------------------------------------------------------------- *)
\* properties                                                       *)
\* ---------------------------------------------------------------- *)

TypeOK ==
    /\ status \in [Items -> {"pending", "running", "merging", "landed"}]
    /\ mergeLock \in {TRUE, FALSE}

Terminating == \A i \in Items : status[i] = "landed"

\* SAFETY property 2 (ORDER RESPECTED)
OrderRespected ==
    \A i \in Items :
        status[i] \in {"running", "merging", "landed"} =>
            (\A p \in Pred(i) : status[p] = "landed")

\* SAFETY property 3 (SCOPE DISJOINTNESS HOLDS)
ScopeDisjointness ==
    \A i \in Items : \A j \in Items :
        (i # j /\ status[i] \in {"running", "merging"} /\ status[j] \in {"running", "merging"})
            => Scope[i] \cap Scope[j] = {}

WorkerCapRespected == Cardinality(InFlight) <= MaxWorkers

\* LIVENESS property 5 (NO DEADLOCK), stated and checked as a plain state
\* invariant rather than a temporal property: from ANY reachable state,
\* either the pile is drained, or some item can progress.
NoDeadlock ==
    Terminating \/ (\E i \in Items : CanStart(i) \/ CanMerge(i) \/ CanFinish(i))

\* LIVENESS property 6 (EVENTUAL DRAIN)
EventualDrain == <>Terminating

====
