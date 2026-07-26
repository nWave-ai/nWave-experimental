# Regression guard for the nWave runtime-asset tier shipping contract.
#
# HISTORY -- this guard was reoriented, not written fresh. It began as
# `fix-installer-never-ships-data-tree`, guarding a `_install_des_data` method
# that copied `nWave/data/` to `<claude_dir>/data/`. That method was removed:
# its premise was false. `nWave/data/` was ALREADY shipped, by
# `_install_nwave_runtime_assets`, to `<claude_dir>/lib/nWave/data/` -- which
# is where the consumers actually resolve it (`Path(__file__).parents[N] /
# "nWave" / ...` lands on `<claude_dir>/lib/nWave` in the installed layout).
# The second destination had no reader, and its source probe lacked the
# nested-first logic the real method has, so it ABORTED the DES plugin install
# on the pipx channel -- the primary channel for end users.
#
# What survived the retraction is the QUESTION that fix was asking, which was
# a good one: an install that omits the assets its runtime resolves must not
# report success. That contract belongs on the method that actually ships
# them, and this feature moves it there.
#
# THE DEFECT NOW GUARDED: `_install_nwave_runtime_assets` collapsed every
# non-shipping outcome onto a silent `info` log plus `return None` -- an
# incomplete distribution and a legitimately asset-less target produced the
# SAME invisible result. A distribution built with a gap therefore installed
# "successfully" and failed later, on the operator's machine.
#
# THE CONTRACT: the two outcomes are distinguished by a DECLARED FACT -- the
# presence of `framework-catalog.yaml`, which every real nWave distribution
# ships and no external target carries. A tree that declares itself an nWave
# tier must be WHOLE (refusal names the channel); a tree that does not is
# declared N/A and the install proceeds, per the target-machine-agnosticism
# mandate. Arrival at the destination is verified per ENTRY, never inferred
# from "copytree did not raise".
#
# Driving port: DESPlugin._install_nwave_runtime_assets(context, using_prebuilt)
# -- the real plugin method, real filesystem under tmp_path. The nested-first
# source probe is NOT exercised for its own sake here; it is pre-existing,
# already covered, and deliberately untouched.

@feature-installer-runtime-asset-tier-fail-loud
Feature: The DES installer ships a whole nWave runtime-asset tier, or refuses out loud

  As an operator installing nWave
  I need an install that cannot silently omit the runtime assets its own package resolves
  So that a distribution built with a gap is caught at install time on the builder's side,
    instead of surfacing later as a missing-file crash on my machine

  Background:
    Given an isolated installation target

  @slice-01 @walking_skeleton @driving_port @contract-shape:bounded-change
  Scenario: A declared nWave tier ships every runtime asset family
    Given a framework source tree that declares itself an nWave tier
    When the DES plugin ships the nWave runtime assets
    Then the assets are reported as shipped
    And every declared asset family exists at the destination
    And the destination carries the "data" family

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: An entry that fails to arrive at the destination is refused, not reported as shipped
    Given a framework source tree that declares itself an nWave tier
    And the copy step silently drops the "data" family on its way to the destination
    When the DES plugin ships the nWave runtime assets
    Then the assets are refused
    And the refusal names "data" as missing
    And the refusal explains WHAT, WHY, and HOW

  # An INDIVIDUAL missing family is deliberately NOT a refusal: which families
  # a tier ships varies by channel and by era, and nothing declares which ones
  # a given tree owes. Treating the candidate list as a mandate would invent a
  # requirement the codebase never made. What a channel gap actually produces
  # is a tier that yields NOTHING, and that is what this scenario pins.
  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A tier that ships the catalogue but no asset family at all is refused, naming the channel
    Given a framework source tree that declares itself an nWave tier carrying no asset family
    When the DES plugin ships the nWave runtime assets from a prebuilt distribution
    Then the assets are refused
    And the refusal explains WHAT, WHY, and HOW
    And the refusal names the distribution channel to fix

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: A tier missing one family still ships the families it does carry
    Given a framework source tree that declares itself an nWave tier without its "dispatch" family
    When the DES plugin ships the nWave runtime assets
    Then the assets are reported as shipped
    And the destination carries the "data" family

  @slice-01 @driving_port @contract-shape:bounded-change
  Scenario: An external target carrying no nWave tier is declared not-applicable and the install continues
    Given a framework source tree that carries no nWave tier
    When the DES plugin ships the nWave runtime assets
    Then the assets are declared not applicable
    And the install is not refused
