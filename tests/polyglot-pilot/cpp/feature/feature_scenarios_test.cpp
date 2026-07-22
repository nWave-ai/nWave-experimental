// feature_scenarios_test.cpp — domain-language acceptance scenarios.
//
// Gojko Adzic Pillars 1+2:
//   - Pillar 1: scenarios written in the domain language, no infrastructure
//               noise
//   - Pillar 2: chained narrative — each scenario's Given may be the
//               composition of the previous scenario's Given + When
//
// Step functions (given_*, when_*, then_*) are defined in
// feature_specifications_test.cpp. This file contains NO direct asserts and
// NO test-double wiring — those live in the specifications module.
//
// Production composition (Tier A): step functions construct the SUT through
// the real composition root and swap only external / non-deterministic
// ports with fakes. State-delta assertions go through this project's
// common/statedelta port.

#include "../common/testkit/testkit.hpp"
#include "feature_specifications_test.hpp"

using namespace feature_test;

TEST("Signup: user added to registry") {
    given_a_fresh_signup_registry();
    when_user_signs_up_with_email("alice@example.com");
    then_user_is_added_to_registry_and_audited_once("alice@example.com");
}

TEST("Signup: duplicate rejected") {
    // Pillar 2: this Given is the composition of the previous scenario's
    // Given + When — start with a registry already containing alice.
    given_a_fresh_signup_registry();
    when_user_signs_up_with_email("alice@example.com");

    when_user_attempts_duplicate_signup("alice@example.com");
    then_second_signup_is_rejected_and_state_is_unchanged();
}
