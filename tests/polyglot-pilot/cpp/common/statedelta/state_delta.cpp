#include "state_delta.hpp"

#include <set>
#include <sstream>

namespace statedelta {

namespace {

Value get_or_null(const Snapshot& snap, const std::string& key) {
    auto it = snap.find(key);
    if (it == snap.end()) return Value{};
    return it->second;
}

std::string record_repr(const Record& r) {
    std::ostringstream oss;
    oss << "{";
    bool first = true;
    for (const auto& [k, v] : r) {
        if (!first) oss << ", ";
        first = false;
        oss << k << "=" << v;
    }
    oss << "}";
    return oss.str();
}

} // namespace

std::string to_string(ViolationKind kind) {
    switch (kind) {
        case ViolationKind::UndeclaredChange: return "undeclared_change";
        case ViolationKind::PredicateFailed: return "predicate_failed";
        case ViolationKind::StrictUniverseMismatch: return "strict_universe_mismatch";
    }
    return "unknown";
}

std::string repr(const Value& v) {
    if (v.is_null()) return "null";
    if (v.is_string()) return "\"" + v.as_string() + "\"";
    std::ostringstream oss;
    oss << "[";
    bool first = true;
    for (const auto& r : v.as_records()) {
        if (!first) oss << ", ";
        first = false;
        oss << record_repr(r);
    }
    oss << "]";
    return oss.str();
}

std::string Violation::describe() const {
    std::ostringstream oss;
    oss << "  kind=\"" << to_string(kind) << "\" key=\"" << key << "\""
        << " old=" << repr(old_value) << " new=" << repr(new_value);
    if (!predicate_name.empty()) {
        oss << " predicate_name=\"" << predicate_name << "\"";
    }
    if (!reason.empty()) {
        oss << " reason=\"" << reason << "\"";
    }
    return oss.str();
}

namespace {

std::string format_violations(const std::vector<Violation>& violations) {
    std::ostringstream oss;
    oss << "assert_state_delta: " << violations.size() << " violation(s) detected:";
    for (const auto& v : violations) {
        oss << "\n" << v.describe();
    }
    return oss.str();
}

} // namespace

StateDeltaViolation::StateDeltaViolation(std::vector<Violation> violations)
    : violations_(std::move(violations)), message_(format_violations(violations_)) {}

// ---------------------------------------------------------------------------
// Predicate factories
// ---------------------------------------------------------------------------

Predicate unchanged() {
    return Predicate{"unchanged()", [](const Value& old_v, const Value& new_v) {
                          if (old_v == new_v) return PredicateResult::pass();
                          return PredicateResult::fail("expected unchanged, got old=" +
                                                        repr(old_v) + " new=" + repr(new_v));
                      }};
}

Predicate set_to(Value value) {
    std::string name = "set_to(" + repr(value) + ")";
    return Predicate{name, [value](const Value&, const Value& new_v) {
                          if (new_v == value) return PredicateResult::pass();
                          return PredicateResult::fail("expected " + repr(value) + ", got " +
                                                        repr(new_v));
                      }};
}

Predicate prepended_with(const std::string& prefix, const std::string& sep) {
    std::string name = "prepended_with(" + prefix + ")";
    return Predicate{name, [prefix, sep](const Value& old_v, const Value& new_v) {
                          if (!old_v.is_string() || !new_v.is_string()) {
                              return PredicateResult::fail("prepended_with requires string old/new");
                          }
                          std::string expected = prefix + sep + old_v.as_string();
                          if (new_v.as_string() == expected) return PredicateResult::pass();
                          return PredicateResult::fail("expected \"" + expected + "\", got \"" +
                                                        new_v.as_string() + "\"");
                      }};
}

Predicate appended_with(const std::string& suffix, const std::string& sep) {
    std::string name = "appended_with(" + suffix + ")";
    return Predicate{name, [suffix, sep](const Value& old_v, const Value& new_v) {
                          if (!old_v.is_string() || !new_v.is_string()) {
                              return PredicateResult::fail("appended_with requires string old/new");
                          }
                          std::string expected = old_v.as_string() + sep + suffix;
                          if (new_v.as_string() == expected) return PredicateResult::pass();
                          return PredicateResult::fail("expected \"" + expected + "\", got \"" +
                                                        new_v.as_string() + "\"");
                      }};
}

Predicate containing(const Value& needle) {
    std::string name = "containing(" + repr(needle) + ")";
    return Predicate{name, [needle](const Value&, const Value& new_v) {
                          if (new_v.is_string() && needle.is_string()) {
                              if (new_v.as_string().find(needle.as_string()) != std::string::npos) {
                                  return PredicateResult::pass();
                              }
                              return PredicateResult::fail("\"" + needle.as_string() + "\" not in \"" +
                                                            new_v.as_string() + "\"");
                          }
                          if (new_v.is_records() && needle.is_records() &&
                              needle.as_records().size() == 1) {
                              const Record& target = needle.as_records()[0];
                              for (const auto& r : new_v.as_records()) {
                                  if (r == target) return PredicateResult::pass();
                              }
                              return PredicateResult::fail("element not found in list");
                          }
                          return PredicateResult::fail("containing: unsupported value shapes");
                      }};
}

Predicate normalized_to(std::function<Value(const Value&)> normalizer) {
    return Predicate{"normalized_to(<normalizer>)",
                      [normalizer](const Value& old_v, const Value& new_v) {
                          if (normalizer(old_v) == normalizer(new_v)) return PredicateResult::pass();
                          return PredicateResult::fail("normalized values differ");
                      }};
}

Predicate idempotent_after(const std::string& prefix, const std::string& sep) {
    std::string name = "idempotent_after(" + prefix + ")";
    return Predicate{name, [prefix, sep](const Value&, const Value& new_v) {
                          if (!new_v.is_string()) {
                              return PredicateResult::fail("idempotent_after requires string new");
                          }
                          const std::string& s = new_v.as_string();
                          auto pos = s.find(sep);
                          std::string first_segment = (pos == std::string::npos) ? s : s.substr(0, pos);
                          if (first_segment == prefix) return PredicateResult::pass();
                          return PredicateResult::fail("first segment of \"" + s + "\" is not \"" +
                                                        prefix + "\"");
                      }};
}

Predicate legacy_healed(std::function<bool(const Value&)> detector,
                         std::function<bool(const Value&)> healed_check) {
    return Predicate{"legacy_healed(<det>,<heal>)",
                      [detector, healed_check](const Value& old_v, const Value& new_v) {
                          if (detector(old_v) && healed_check(new_v)) return PredicateResult::pass();
                          return PredicateResult::fail("legacy_healed: detector or healed_check failed");
                      }};
}

Predicate appended_with_item(const Record& item) {
    std::string name = "appended_with_item(" + record_repr(item) + ")";
    return Predicate{name, [item](const Value& old_v, const Value& new_v) {
                          if (!old_v.is_records() || !new_v.is_records()) {
                              return PredicateResult::fail("appended_with_item requires list old/new");
                          }
                          const std::vector<Record>& old_list = old_v.as_records();
                          const std::vector<Record>& new_list = new_v.as_records();
                          if (new_list.size() != old_list.size() + 1) {
                              return PredicateResult::fail(
                                  "expected len " + std::to_string(old_list.size() + 1) + ", got " +
                                  std::to_string(new_list.size()));
                          }
                          for (std::size_t i = 0; i < old_list.size(); ++i) {
                              if (!(old_list[i] == new_list[i])) {
                                  return PredicateResult::fail("prefix divergence at index " +
                                                                std::to_string(i));
                              }
                          }
                          if (!(new_list.back() == item)) {
                              return PredicateResult::fail("tail element does not equal expected item");
                          }
                          return PredicateResult::pass();
                      }};
}

Predicate prepended_with_item(const Record& item) {
    std::string name = "prepended_with_item(" + record_repr(item) + ")";
    return Predicate{name, [item](const Value& old_v, const Value& new_v) {
                          if (!old_v.is_records() || !new_v.is_records()) {
                              return PredicateResult::fail("prepended_with_item requires list old/new");
                          }
                          const std::vector<Record>& old_list = old_v.as_records();
                          const std::vector<Record>& new_list = new_v.as_records();
                          if (new_list.size() != old_list.size() + 1) {
                              return PredicateResult::fail(
                                  "expected len " + std::to_string(old_list.size() + 1) + ", got " +
                                  std::to_string(new_list.size()));
                          }
                          if (!(new_list.front() == item)) {
                              return PredicateResult::fail("head element does not equal expected item");
                          }
                          for (std::size_t i = 0; i < old_list.size(); ++i) {
                              if (!(old_list[i] == new_list[i + 1])) {
                                  return PredicateResult::fail("tail divergence at index " +
                                                                std::to_string(i));
                              }
                          }
                          return PredicateResult::pass();
                      }};
}

// ---------------------------------------------------------------------------
// Driving functions
// ---------------------------------------------------------------------------

std::vector<Violation> assert_state_delta_collect(
    const Snapshot& before,
    const Snapshot& after,
    const std::vector<std::string>& universe,
    const std::map<std::string, Predicate>& expected,
    AssertOptions options) {
    std::vector<Violation> violations;

    // Universe deduplication (mirrors Python `set` semantics); std::set
    // iteration is sorted, giving deterministic violation ordering.
    std::set<std::string> universe_set(universe.begin(), universe.end());

    if (options.strict) {
        std::set<std::string> seen;
        for (const auto& [k, v] : before) {
            (void)v;
            seen.insert(k);
        }
        for (const auto& [k, v] : after) {
            (void)v;
            seen.insert(k);
        }
        for (const auto& key : seen) {
            if (universe_set.find(key) == universe_set.end()) {
                violations.push_back(Violation{ViolationKind::StrictUniverseMismatch, key,
                                                get_or_null(before, key), get_or_null(after, key), "",
                                                ""});
            }
        }
    }

    for (const auto& key : universe_set) {
        Value old_value = get_or_null(before, key);
        Value new_value = get_or_null(after, key);

        auto it = expected.find(key);
        if (it != expected.end()) {
            PredicateResult result = it->second.eval(old_value, new_value);
            if (!result.ok) {
                violations.push_back(Violation{ViolationKind::PredicateFailed, key, old_value,
                                                new_value, it->second.name, result.reason});
            }
            continue;
        }

        if (!(old_value == new_value)) {
            violations.push_back(
                Violation{ViolationKind::UndeclaredChange, key, old_value, new_value, "", ""});
        }
    }

    return violations;
}

void assert_state_delta(
    const Snapshot& before,
    const Snapshot& after,
    const std::vector<std::string>& universe,
    const std::map<std::string, Predicate>& expected,
    AssertOptions options) {
    std::vector<Violation> violations =
        assert_state_delta_collect(before, after, universe, expected, options);
    if (!violations.empty()) {
        throw StateDeltaViolation(std::move(violations));
    }
}

} // namespace statedelta
