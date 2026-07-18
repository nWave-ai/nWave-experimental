---- MODULE Claim_MC_EagerFenced_TTrace_1784382400 ----
EXTENDS Sequences, Claim_MC_EagerFenced, TLCExt, Toolbox, Naturals, TLC, Claim_MC_EagerFenced_TEConstants

_expression ==
    LET Claim_MC_EagerFenced_TEExpression == INSTANCE Claim_MC_EagerFenced_TEExpression
    IN Claim_MC_EagerFenced_TEExpression!expression
----

_trace ==
    LET Claim_MC_EagerFenced_TETrace == INSTANCE Claim_MC_EagerFenced_TETrace
    IN Claim_MC_EagerFenced_TETrace!trace
----

_prop ==
    ~(([]<>(
            owner = ([w1 |-> "NoOwner", w2 |-> "NoOwner"])
            /\
            alive = ([c1 |-> FALSE, c2 |-> TRUE])
            /\
            working = ([c1 |-> "w2", c2 |-> "w2"])
            /\
            landed = ([w1 |-> 1, w2 |-> 0])
    ))/\([]<>(
            owner = ([w1 |-> "NoOwner", w2 |-> "NoOwner"])
            /\
            alive = ([c1 |-> FALSE, c2 |-> TRUE])
            /\
            working = ([c1 |-> "w2", c2 |-> "NoItem"])
            /\
            landed = ([w1 |-> 1, w2 |-> 0])
    )))
----

_init ==
    /\ owner = _TETrace[1].owner
    /\ working = _TETrace[1].working
    /\ alive = _TETrace[1].alive
    /\ landed = _TETrace[1].landed
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
           \/ /\ i = _TTraceLassoEnd
              /\ j = _TTraceLassoStart
        /\ owner  = _TETrace[i].owner
        /\ owner' = _TETrace[j].owner
        /\ working  = _TETrace[i].working
        /\ working' = _TETrace[j].working
        /\ alive  = _TETrace[i].alive
        /\ alive' = _TETrace[j].alive
        /\ landed  = _TETrace[i].landed
        /\ landed' = _TETrace[j].landed

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("Claim_MC_EagerFenced_TTrace_1784382400.json", _TETrace)


_view ==
    <<owner, working, alive, landed, IF TLCGet("level") = _TTraceLassoEnd + 1 THEN _TTraceLassoStart ELSE TLCGet("level")>>
=============================================================================

 Note that you can extract this module `Claim_MC_EagerFenced_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `Claim_MC_EagerFenced_TEExpression.tla` file takes precedence 
  over the module `Claim_MC_EagerFenced_TEExpression` below).

---- MODULE Claim_MC_EagerFenced_TEExpression ----
EXTENDS Sequences, Claim_MC_EagerFenced, TLCExt, Toolbox, Naturals, TLC, Claim_MC_EagerFenced_TEConstants

expression == 
    [
        \* To hide variables of the `Claim_MC_EagerFenced` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        owner |-> owner
        ,working |-> working
        ,alive |-> alive
        ,landed |-> landed
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_ownerUnchanged |-> owner = owner'
        
        \* Format the `owner` variable as Json value.
        \* ,_ownerJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(owner)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_ownerModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].owner # _TETrace[s-1].owner
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE Claim_MC_EagerFenced_TETrace ----
\*EXTENDS IOUtils, Claim_MC_EagerFenced, TLC, Claim_MC_EagerFenced_TEConstants
\*
\*trace == IODeserialize("Claim_MC_EagerFenced_TTrace_1784382400.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE Claim_MC_EagerFenced_TETrace ----
EXTENDS Claim_MC_EagerFenced, TLC, Claim_MC_EagerFenced_TEConstants

trace == 
    <<
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "NoOwner"],alive |-> [c1 |-> TRUE, c2 |-> TRUE],working |-> [c1 |-> "NoItem", c2 |-> "NoItem"],landed |-> [w1 |-> 0, w2 |-> 0]]),
    ([owner |-> [w1 |-> "c2", w2 |-> "NoOwner"],alive |-> [c1 |-> TRUE, c2 |-> TRUE],working |-> [c1 |-> "NoItem", c2 |-> "w1"],landed |-> [w1 |-> 0, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "NoOwner"],alive |-> [c1 |-> TRUE, c2 |-> TRUE],working |-> [c1 |-> "NoItem", c2 |-> "NoItem"],landed |-> [w1 |-> 1, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "c1"],alive |-> [c1 |-> TRUE, c2 |-> TRUE],working |-> [c1 |-> "w2", c2 |-> "NoItem"],landed |-> [w1 |-> 1, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "c1"],alive |-> [c1 |-> FALSE, c2 |-> TRUE],working |-> [c1 |-> "w2", c2 |-> "NoItem"],landed |-> [w1 |-> 1, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "NoOwner"],alive |-> [c1 |-> FALSE, c2 |-> TRUE],working |-> [c1 |-> "w2", c2 |-> "NoItem"],landed |-> [w1 |-> 1, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "c2"],alive |-> [c1 |-> FALSE, c2 |-> TRUE],working |-> [c1 |-> "w2", c2 |-> "w2"],landed |-> [w1 |-> 1, w2 |-> 0]]),
    ([owner |-> [w1 |-> "NoOwner", w2 |-> "NoOwner"],alive |-> [c1 |-> FALSE, c2 |-> TRUE],working |-> [c1 |-> "w2", c2 |-> "w2"],landed |-> [w1 |-> 1, w2 |-> 0]])
    >>
----


=============================================================================

---- MODULE Claim_MC_EagerFenced_TEConstants ----
EXTENDS Claim_MC_EagerFenced

CONSTANTS _TTraceLassoStart, _TTraceLassoEnd

=============================================================================

---- CONFIG Claim_MC_EagerFenced_TTrace_1784382400 ----
CONSTANTS
_TTraceLassoStart = 6
_TTraceLassoEnd = 8

PROPERTY
    _prop

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

VIEW
    _view

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Sat Jul 18 14:46:40 BST 2026