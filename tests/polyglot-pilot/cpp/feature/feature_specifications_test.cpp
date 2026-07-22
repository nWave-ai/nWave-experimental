#include "feature_specifications_test.hpp"

#include <memory>
#include <vector>

#include "../common/statedelta/state_delta.hpp"
#include "../common/testkit/testkit.hpp"
#include "../productionapp/app.hpp"

namespace feature_test {

namespace {

// Universe for the signup feature — port-exposed observables only:
//   - registry.users : list of registered user records (driven-port state)
//   - audit.events   : append-only audit trail (driven-port state)
// Do NOT add internal fields here; refactoring would break the test.
const std::vector<std::string> kSignupUniverse = {"registry.users", "audit.events"};

// Per-test state, mirrors the Go fixture's file-level package variables —
// this pilot's runner executes tests sequentially, so shared state is safe
// for the chained-narrative (Pillar 2) pattern.
std::unique_ptr<productionapp::App> g_app;
statedelta::Snapshot g_state_before;

} // namespace

void given_a_fresh_signup_registry() {
    g_app = std::make_unique<productionapp::App>();
    g_state_before = g_app->capture_universe(kSignupUniverse);
}

void when_user_signs_up_with_email(const std::string& email) {
    try {
        g_app->signup(productionapp::SignupInput{email});
    } catch (const std::exception& e) {
        FAIL_TEST(std::string("signup failed unexpectedly for \"") + email + "\": " + e.what());
    }
}

void then_user_is_added_to_registry_and_audited_once(const std::string& email) {
    statedelta::Snapshot state_after = g_app->capture_universe(kSignupUniverse);
    statedelta::assert_state_delta(
        g_state_before, state_after, kSignupUniverse,
        {
            {"registry.users", statedelta::appended_with_item(statedelta::Record{{"email", email}})},
            {"audit.events", statedelta::appended_with_item(
                                  statedelta::Record{{"type", "UserSignedUp"}, {"email", email}})},
        });
}

void when_user_attempts_duplicate_signup(const std::string& email) {
    // Re-baseline before the duplicate attempt so the state-delta assertion
    // measures the change *caused by the duplicate*, not the original signup.
    g_state_before = g_app->capture_universe(kSignupUniverse);
    try {
        g_app->signup(productionapp::SignupInput{email});
        FAIL_TEST(std::string("expected duplicate signup to fail for \"") + email + "\", got success");
    } catch (const productionapp::DuplicateSignupError&) {
        // expected
    }
}

void then_second_signup_is_rejected_and_state_is_unchanged() {
    statedelta::Snapshot state_after = g_app->capture_universe(kSignupUniverse);
    // Both slots must be unchanged — the duplicate must produce zero delta.
    statedelta::assert_state_delta(
        g_state_before, state_after, kSignupUniverse,
        {
            {"registry.users", statedelta::unchanged()},
            {"audit.events", statedelta::unchanged()},
        });
}

} // namespace feature_test
