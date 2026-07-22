#pragma once
// feature_specifications_test.hpp — step functions backing the scenarios.
//
// Responsibilities:
//   - Construct the SUT through the PRODUCTION composition root
//     (productionapp::App). Swap only external / non-deterministic ports
//     with fakes (clock, RNG, paid APIs) — this toy feature uses none.
//   - Capture the universe via app.capture_universe(...).
//   - Assert via statedelta::assert_state_delta.
//
// No domain language leaks into the production-app wiring; no
// production-app details leak into the scenarios (feature_scenarios_test.cpp).

#include <string>

namespace feature_test {

void given_a_fresh_signup_registry();
void when_user_signs_up_with_email(const std::string& email);
void then_user_is_added_to_registry_and_audited_once(const std::string& email);
void when_user_attempts_duplicate_signup(const std::string& email);
void then_second_signup_is_rejected_and_state_is_unchanged();

} // namespace feature_test
