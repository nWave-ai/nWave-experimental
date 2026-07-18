---- MODULE Claim ----
(* Concurrent drain: N independent claimer instances drain ONE shared pile. *)
(* This breaks the "single sequential control loop" assumption that the     *)
(* Engine spec relied on for admission atomicity.                          *)
(*                                                                          *)
(* KEY POINT: two claimers taking the SAME item have IDENTICAL scopes, so   *)
(* the scope-disjointness admission test is structurally incapable of       *)
(* catching it (identical is the opposite of overlapping-but-distinct --    *)
(* the test is about which FILES are touched, not which ITEM is taken).     *)
(*                                                                          *)
(* Toggles:                                                                 *)
(*   ClaimEnabled : is an in-progress item marked so other claimers see it  *)
(*                  as unavailable?  FALSE = only "landed" is recorded, so  *)
(*                  in-flight work is invisible to peers.                   *)
(*   ExpiryMode   : "none"   -- a claim is never released except by landing *)
(*                             (a dead claimer's claim wedges the pile)     *)
(*                  "ondeath"-- claim released only when the holder is      *)
(*                             observably dead (idealised perfect failure   *)
(*                             detector -- NOT implementable, see report)   *)
(*                  "eager"  -- claim may lapse at any time, including      *)
(*                             while the holder is alive and still working  *)
(*                             (models a lease too short / a slow holder    *)
(*                             indistinguishable from a dead one)           *)
(*   Fenced       : must a claimer still HOLD the claim at landing time for *)
(*                  its land to be accepted?  This is the fencing check.    *)
EXTENDS Naturals, FiniteSets

CONSTANTS
    Items,          \* the shared pile
    Claimers,       \* concurrent agent instances draining it
    Mortal,         \* SUBSET Claimers : which instances may die mid-flight
    NoItem,         \* sentinel: claimer is idle
    NoOwner,        \* sentinel: item is unclaimed
    ClaimEnabled,
    ExpiryMode,
    Fenced

ASSUME Mortal \subseteq Claimers
ASSUME ClaimEnabled \in {TRUE, FALSE}
ASSUME Fenced \in {TRUE, FALSE}
ASSUME ExpiryMode \in {"none", "ondeath", "eager"}

VARIABLES
    working,    \* Claimers -> Items \cup {NoItem} : what each instance is doing
    owner,      \* Items -> Claimers \cup {NoOwner} : who holds the claim
    landed,     \* Items -> Nat : how many times this item has been landed (!)
    alive       \* Claimers -> BOOLEAN

vars == <<working, owner, landed, alive>>

Init ==
    /\ working = [c \in Claimers |-> NoItem]
    /\ owner = [i \in Items |-> NoOwner]
    /\ landed = [i \in Items |-> 0]
    /\ alive = [c \in Claimers |-> TRUE]

\* What a claimer perceives as "still needs doing".
\* With claims OFF, an item someone else is ALREADY working on still looks
\* available -- because nothing but landing is recorded anywhere.
Available(i) ==
    IF ClaimEnabled
    THEN landed[i] = 0 /\ owner[i] = NoOwner
    ELSE landed[i] = 0

Take(c, i) ==
    /\ alive[c]
    /\ working[c] = NoItem
    /\ Available(i)
    /\ working' = [working EXCEPT ![c] = i]
    /\ owner' = IF ClaimEnabled THEN [owner EXCEPT ![i] = c] ELSE owner
    /\ UNCHANGED <<landed, alive>>

\* Landing. Under Fenced, a claimer that has LOST its claim (expired, and
\* possibly re-taken by someone else) is refused -- this is the fencing token
\* check. Without fencing, a lapsed holder still lands, on top of whoever
\* else took over.
CanLand(c, i) ==
    /\ alive[c]
    /\ working[c] = i
    /\ (Fenced => owner[i] = c)

Land(c, i) ==
    /\ CanLand(c, i)
    /\ landed' = [landed EXCEPT ![i] = landed[i] + 1]
    /\ working' = [working EXCEPT ![c] = NoItem]
    /\ owner' = IF ClaimEnabled THEN [owner EXCEPT ![i] = NoOwner] ELSE owner
    /\ UNCHANGED alive

\* A fenced-out claimer must be able to give up, or it wedges itself holding
\* an item it can never land.
Abandon(c, i) ==
    /\ alive[c]
    /\ working[c] = i
    /\ Fenced
    /\ owner[i] # c
    /\ working' = [working EXCEPT ![c] = NoItem]
    /\ UNCHANGED <<owner, landed, alive>>

Die(c) ==
    /\ c \in Mortal
    /\ alive[c]
    /\ alive' = [alive EXCEPT ![c] = FALSE]
    /\ UNCHANGED <<working, owner, landed>>

\* Claim expiry / lease lapse.
Expire(i) ==
    /\ ClaimEnabled
    /\ owner[i] # NoOwner
    /\ landed[i] = 0
    /\ \/ /\ ExpiryMode = "ondeath"
          /\ ~alive[owner[i]]              \* perfect failure detector (idealised)
       \/ ExpiryMode = "eager"             \* lapses regardless of liveness
    /\ owner' = [owner EXCEPT ![i] = NoOwner]
    /\ UNCHANGED <<working, landed, alive>>

Next ==
    \/ \E c \in Claimers : \E i \in Items : Take(c, i) \/ Land(c, i) \/ Abandon(c, i)
    \/ \E c \in Claimers : Die(c)
    \/ \E i \in Items : Expire(i)

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

\* ---------------------------------------------------------------- *)
\* properties                                                       *)
\* ---------------------------------------------------------------- *)

TypeOK ==
    /\ working \in [Claimers -> Items \cup {NoItem}]
    /\ owner \in [Items -> Claimers \cup {NoOwner}]
    /\ alive \in [Claimers -> {TRUE, FALSE}]

\* SAFETY: no item is ever landed twice (the double-take consequence).
NoDoubleLand == \A i \in Items : landed[i] <= 1

\* SAFETY: no two live claimers are simultaneously working the same item.
NoDoubleTake ==
    \A i \in Items :
        Cardinality({c \in Claimers : working[c] = i /\ alive[c]}) <= 1

\* LIVENESS: the pile drains despite a claimer dying mid-flight.
Drained == \A i \in Items : landed[i] > 0
EventualDrain == <>Drained

ClaimStateConstraint == \A i \in Items : landed[i] <= 3

====
