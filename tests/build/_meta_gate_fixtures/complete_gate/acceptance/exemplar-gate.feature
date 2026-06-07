# Meta-gate planted fixture (complete_gate self-AT).
#
# The third leg of the triad for the synthetic `exemplar_gate`: a sibling
# `*-gate.feature` whose kebab stem (`exemplar-gate`) is prefixed by the gate
# dir name in kebab form (`exemplar-gate` <- `exemplar_gate`). Presence of
# this file is what lets the meta-gate resolve the self-AT for the gate.

@feature-meta-gate-planted @component
Feature: exemplar gate self-AT (planted, never executed by behaviour)
  This .feature is a structural presence marker only. It is discovered by the
  meta-gate's filesystem walk, never collected as a real pytest-bdd scenario
  (no steps module binds it). It exists so the meta-gate can confirm the
  complete-gate exemplar has all three golden artifacts.
