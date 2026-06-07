@feature-fix-atdd-pure-spine-dogfood-defects
Feature: A feature-end-cycle dispatch is accepted by the marker contract

  As the ADR-028 D6 feature-end cycle that must run E_BATCH_REFACTOR and
    F_FINAL_REVIEW once per feature (G_COMMIT is the per-slice terminal phase,
    not part of the feature-end cycle)
  I want a feature-end-cycle dispatch to carry a marker the U0 contract accepts,
    and incoherent phase/scope pairs to be rejected
  So that the feature-end cycle becomes dispatchable without opening a
    marker-faking hole that would bypass the per-slice carpaccio order gate

  # slice-02 -- the marker-contract fix (Option A: a closed `DES-SLICE` union
  # of `slice-NN` plus the literal `feature-end`). Today a feature-end dispatch
  # has no valid DES-SLICE value -- `slice_id` is None -> the dispatch is
  # classified "defective" and refused at both U0 sites.
  #
  # SUT state model -- `classify_atdd_pure_dispatch` resolves a marker set to:
  #   VALID     -- atdd_pure mode + a known phase + a COHERENT (phase, scope) pair
  #   DEFECTIVE -- a marker absent / malformed, OR an incoherent (phase, scope) pair
  #   ABSENT    -- no atdd_pure mode marker (a classic dispatch)
  # Coherence is the closed-world cross-field rule:
  #   phase in feature-end-phases  XOR  scope == feature-end
  # where feature-end-phases = {E_BATCH_REFACTOR, F_FINAL_REVIEW} (ADR-028 D6;
  # G_COMMIT is the per-slice terminal phase -- (G_COMMIT, slice-NN) is COHERENT
  # and classified valid, matching the atdd-pure-spine-hardening contract).
  #
  # Driving port: `des.domain.des_marker_parser` -- the single domain chokepoint
  # both U0 sites (carpaccio_intercept, pre_tool_use_service) delegate to.
  # Layer 1-2 (pure no-I/O domain) -> a parametrized Scenario Outline is the
  # enumerable, closed phase x scope grid; the domain is finite -> parametrize,
  # not PBT (falsifier-gate: closed-world finite domain).
  #
  # RED contract: AT(1) (feature-end coherent) + AT(3) (incoherent pairs) FAIL
  # on master -- the `feature-end` literal is rejected by `slice-\d+`. AT(1)
  # folds in the per-slice no-regression rows so the no-regression guarantee
  # rides the same delivered AT (some of those rows already pass on master --
  # the xfail scaffold is non-strict, DELIVER turns the whole AT green).

  @slice-02 @walking_skeleton @wiring_e2e @driving_port @contract-shape:pure-function
  Scenario Outline: A coherent dispatch is recognised as valid
    Given a crafter dispatch for phase <phase> scoped to <scope>
    When the marker contract classifies the dispatch
    Then the dispatch is recognised as valid

    Examples: feature-end-cycle dispatches (RED until slice-02)
      | phase            | scope       |
      | E_BATCH_REFACTOR | feature-end |
      | F_FINAL_REVIEW   | feature-end |

    Examples: per-slice dispatches (no regression)
      | phase       | scope    |
      | A_GREEN_ATS | slice-01 |
      | A_GREEN_ATS | slice-12 |
      | G_COMMIT    | slice-12 |

  @slice-02 @error @driving_port @contract-shape:bounded-change
  Scenario Outline: A malformed scope marker is rejected as defective
    Given a crafter dispatch for phase A_GREEN_ATS scoped to <malformed_scope>
    When the marker contract classifies the dispatch
    Then the dispatch is rejected as defective

    Examples:
      | malformed_scope |
      | slice1          |
      | slice-3-->      |

  @slice-02 @error @driving_port @contract-shape:bounded-change
  Scenario Outline: An incoherent phase and scope pair is rejected as defective
    Given a crafter dispatch for phase <phase> scoped to <scope>
    When the marker contract classifies the dispatch
    Then the dispatch is rejected as defective

    Examples: per-slice phase carrying the feature-end scope
      | phase       | scope       |
      | A_GREEN_ATS | feature-end |

    Examples: feature-end phase carrying a per-slice scope
      | phase            | scope    |
      | E_BATCH_REFACTOR | slice-01 |
      | F_FINAL_REVIEW   | slice-01 |
