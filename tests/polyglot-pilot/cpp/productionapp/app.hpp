#pragma once
// app.hpp — toy minimal signup feature for the polyglot pilot.
//
// Composition root: constructs an in-memory registry and audit log, exposes
// signup (driving operation) and capture_universe (state inspection at
// port-exposed slots). Real-feature shape: in-process domain + driven ports
// (here both in-memory).
//
// Universe slots exposed:
//   - "registry.users" : list of records shaped {"email": ...}
//   - "audit.events"   : list of records shaped {"type": ..., "email": ...}
//
// Internal field names are NOT part of the universe — refactoring internals
// stays GREEN.

#include <stdexcept>
#include <string>
#include <vector>

#include "../common/statedelta/state_delta.hpp"

namespace productionapp {

using statedelta::Record;
using statedelta::Value;

// DuplicateSignupError signals an already-registered email.
struct DuplicateSignupError : std::runtime_error {
    std::string email;
    explicit DuplicateSignupError(std::string email_)
        : std::runtime_error("duplicate signup rejected: " + email_), email(std::move(email_)) {}
};

// EmptyEmailError is thrown when signup receives a blank email.
struct EmptyEmailError : std::runtime_error {
    EmptyEmailError() : std::runtime_error("signup: email must be non-empty") {}
};

// SignupInput is the driving-port input shape for signup.
struct SignupInput {
    std::string email;
};

// App is the production composition root for the toy signup feature.
class App {
public:
    App() = default;

    // signup is the driving port — registers a user by email. Throws
    // DuplicateSignupError when the email already exists, EmptyEmailError
    // when the input is blank.
    Record signup(const SignupInput& in);

    // capture_universe returns a snapshot of the requested universe slots.
    // Returned records are copies so test assertions cannot mutate
    // production state by accident.
    statedelta::Snapshot capture_universe(const std::vector<std::string>& keys) const;

private:
    std::vector<Record> users_;
    std::vector<Record> events_;
};

} // namespace productionapp
