#pragma once
// state_delta.hpp — C++ port of nwave_ai.state_delta (Python canonical).
//
// Polyglot pilot. Mirrors the contract of
// `nwave_ai/state_delta/{matcher,predicates}.py`:
//
//   - Predicate signature: PredicateResult(const Value& old, const Value& new_)
//   - Universe = vector<string> (set semantics; duplicates ignored)
//   - assert_state_delta collects ALL violations across the universe before
//     throwing a single StateDeltaViolation aggregating them (multi-violation
//     contract A7).
//   - Strict mode reports any key present in before|after but not in universe
//     as a StrictUniverseMismatch violation.
//   - Implicit-unchanged: a key in universe but NOT in expected requires
//     deep-equal between before[key] and after[key]; difference =>
//     UndeclaredChange violation.
//
// Value is a small closed variant (monostate | string | vector<Record>) —
// enough to represent this pilot's port-exposed state. Record is a flat
// string-to-string map (mirrors the C# port's Dictionary<string,object?>
// trick for structural equality without reflection or RTTI).
//
// Zero external dependencies.
//
// Source of truth: Python module at `nwave_ai/state_delta/`. Keep the
// contract in sync; deviations are bugs.

#include <functional>
#include <map>
#include <string>
#include <variant>
#include <vector>

namespace statedelta {

using Record = std::map<std::string, std::string>;

struct Value {
    std::variant<std::monostate, std::string, std::vector<Record>> data;

    Value() : data(std::monostate{}) {}
    Value(std::string s) : data(std::move(s)) {}
    Value(const char* s) : data(std::string(s)) {}
    Value(std::vector<Record> v) : data(std::move(v)) {}

    bool operator==(const Value& other) const { return data == other.data; }
    bool operator!=(const Value& other) const { return !(*this == other); }

    bool is_null() const { return std::holds_alternative<std::monostate>(data); }
    bool is_string() const { return std::holds_alternative<std::string>(data); }
    bool is_records() const { return std::holds_alternative<std::vector<Record>>(data); }

    const std::string& as_string() const { return std::get<std::string>(data); }
    const std::vector<Record>& as_records() const { return std::get<std::vector<Record>>(data); }
};

using Snapshot = std::map<std::string, Value>;

struct PredicateResult {
    bool ok;
    std::string reason;

    static PredicateResult pass() { return {true, ""}; }
    static PredicateResult fail(std::string reason) { return {false, std::move(reason)}; }
};

struct Predicate {
    std::string name;
    std::function<PredicateResult(const Value&, const Value&)> fn;

    PredicateResult eval(const Value& old_value, const Value& new_value) const {
        return fn(old_value, new_value);
    }
};

enum class ViolationKind {
    UndeclaredChange,
    PredicateFailed,
    StrictUniverseMismatch,
};

std::string to_string(ViolationKind kind);
std::string repr(const Value& v);

struct Violation {
    ViolationKind kind;
    std::string key;
    Value old_value;
    Value new_value;
    std::string predicate_name; // empty when the violation is not a predicate failure
    std::string reason;         // empty unless the predicate returned a reason

    std::string describe() const;
};

class StateDeltaViolation : public std::exception {
public:
    explicit StateDeltaViolation(std::vector<Violation> violations);

    const char* what() const noexcept override { return message_.c_str(); }
    const std::vector<Violation>& violations() const { return violations_; }

private:
    std::vector<Violation> violations_;
    std::string message_;
};

struct AssertOptions {
    // Strict reports any key in before|after that is NOT in universe as a
    // StrictUniverseMismatch violation. Default false.
    bool strict = false;
};

// ---------------------------------------------------------------------------
// Predicate factories — mirror nwave_ai/state_delta/predicates.py
// ---------------------------------------------------------------------------

Predicate unchanged();
Predicate set_to(Value value);
Predicate prepended_with(const std::string& prefix, const std::string& sep = ":");
Predicate appended_with(const std::string& suffix, const std::string& sep = ":");
Predicate containing(const Value& needle);
Predicate normalized_to(std::function<Value(const Value&)> normalizer);
Predicate idempotent_after(const std::string& prefix, const std::string& sep = ":");
Predicate legacy_healed(std::function<bool(const Value&)> detector,
                         std::function<bool(const Value&)> healed_check);
// Slice-shaped helpers — C++ extension beyond Python parity, mirrors the Go
// port's AppendedWithItem/PrependedWithItem for list-shaped state.
Predicate appended_with_item(const Record& item);
Predicate prepended_with_item(const Record& item);

// ---------------------------------------------------------------------------
// Driving functions
// ---------------------------------------------------------------------------

// Returns violations (empty on success). Does not throw — for callers that
// prefer inspecting violations directly over exception handling.
std::vector<Violation> assert_state_delta_collect(
    const Snapshot& before,
    const Snapshot& after,
    const std::vector<std::string>& universe,
    const std::map<std::string, Predicate>& expected,
    AssertOptions options = {});

// Throws StateDeltaViolation on any violation. This is the driving entry
// point for tests.
void assert_state_delta(
    const Snapshot& before,
    const Snapshot& after,
    const std::vector<std::string>& universe,
    const std::map<std::string, Predicate>& expected,
    AssertOptions options = {});

} // namespace statedelta
