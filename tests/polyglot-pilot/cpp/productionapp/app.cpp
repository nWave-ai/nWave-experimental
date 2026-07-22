#include "app.hpp"

#include <algorithm>
#include <cctype>

namespace productionapp {

namespace {

std::string normalize_email(const std::string& raw) {
    std::size_t start = raw.find_first_not_of(" \t\n\r");
    std::size_t end = raw.find_last_not_of(" \t\n\r");
    std::string trimmed = (start == std::string::npos) ? "" : raw.substr(start, end - start + 1);
    std::transform(trimmed.begin(), trimmed.end(), trimmed.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    return trimmed;
}

} // namespace

Record App::signup(const SignupInput& in) {
    std::string email = normalize_email(in.email);
    if (email.empty()) {
        throw EmptyEmailError();
    }
    for (const auto& u : users_) {
        auto it = u.find("email");
        if (it != u.end() && it->second == email) {
            throw DuplicateSignupError(email);
        }
    }
    Record record{{"email", email}};
    users_.push_back(record);
    events_.push_back(Record{{"type", "UserSignedUp"}, {"email", email}});
    return record;
}

statedelta::Snapshot App::capture_universe(const std::vector<std::string>& keys) const {
    statedelta::Snapshot snapshot;
    for (const auto& key : keys) {
        if (key == "registry.users") {
            snapshot[key] = Value{users_};
        } else if (key == "audit.events") {
            snapshot[key] = Value{events_};
        } else {
            // Unknown slot — leave as null so state-delta sees the absence
            // explicitly rather than silently fabricating a value.
            snapshot[key] = Value{};
        }
    }
    return snapshot;
}

} // namespace productionapp
