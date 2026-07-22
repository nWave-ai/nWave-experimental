// state_delta_test.cpp — contract tests for the C++ state-delta port.
//
// Mirrors `tests/state_delta/unit/test_matcher.py` and the Go/C# ports'
// predicate tests. No PBT library is available in this pilot's build
// environment (zero third-party test-framework dependency by design) — the
// "property" tests below are small hand-rolled bounded loops over generated
// inputs, not a substitute for `nwave_ai.state_delta`'s Hypothesis suite.

#include <random>
#include <string>

#include "../testkit/testkit.hpp"
#include "state_delta.hpp"

using namespace statedelta;

namespace {

std::string random_lowercase_string(std::mt19937& rng, int min_len, int max_len) {
    std::uniform_int_distribution<int> len_dist(min_len, max_len);
    std::uniform_int_distribution<int> char_dist('a', 'z');
    int len = len_dist(rng);
    std::string s;
    for (int i = 0; i < len; ++i) {
        s.push_back(static_cast<char>(char_dist(rng)));
    }
    return s;
}

} // namespace

// ---------------------------------------------------------------------------
// Walking skeleton + core semantics
// ---------------------------------------------------------------------------

TEST("assert_state_delta returns cleanly on a clean prepend transition") {
    assert_state_delta(
        Snapshot{{"PATH", Value{"/usr/bin"}}},
        Snapshot{{"PATH", Value{"/des/bin:/usr/bin"}}},
        {"PATH"},
        {{"PATH", prepended_with("/des/bin")}});
}

TEST("assert_state_delta_collect reports predicate failure with full context") {
    std::vector<Violation> violations = assert_state_delta_collect(
        Snapshot{{"PATH", Value{"/usr/bin"}}},
        Snapshot{{"PATH", Value{"/wrong"}}},
        {"PATH"},
        {{"PATH", prepended_with("/des/bin")}});
    ASSERT_TRUE(violations.size() == 1);
    const Violation& v = violations[0];
    ASSERT_TRUE(v.kind == ViolationKind::PredicateFailed);
    ASSERT_TRUE(v.key == "PATH");
    ASSERT_TRUE(v.predicate_name == "prepended_with(/des/bin)");
}

TEST("implicit-unchanged enforcement catches an undeclared change") {
    std::vector<Violation> violations = assert_state_delta_collect(
        Snapshot{{"PATH", Value{"/u/bin"}}, {"HOME", Value{"/home/u"}}},
        Snapshot{{"PATH", Value{"/des/bin:/u/bin"}}, {"HOME", Value{"/home/changed"}}},
        {"PATH", "HOME"},
        {{"PATH", prepended_with("/des/bin")}});
    ASSERT_TRUE(violations.size() == 1);
    ASSERT_TRUE(violations[0].kind == ViolationKind::UndeclaredChange);
    ASSERT_TRUE(violations[0].key == "HOME");
}

TEST("assert_state_delta_collect aggregates multiple violations (A7)") {
    std::vector<Violation> violations = assert_state_delta_collect(
        Snapshot{{"PATH", Value{"/u"}}, {"HOME", Value{"/h"}}, {"X", Value{"1"}}},
        Snapshot{{"PATH", Value{"/wrong"}}, {"HOME", Value{"/h2"}}, {"X", Value{"1"}}},
        {"PATH", "HOME", "X"},
        {{"PATH", prepended_with("/des")}, {"HOME", unchanged()}});
    ASSERT_TRUE(violations.size() == 2);
    ASSERT_TRUE((violations[0].key == "HOME" && violations[1].key == "PATH") ||
                (violations[0].key == "PATH" && violations[1].key == "HOME"));
}

TEST("strict mode flags keys present outside the declared universe") {
    std::vector<Violation> violations = assert_state_delta_collect(
        Snapshot{{"PATH", Value{"/u"}}, {"EXTRA", Value{"x"}}},
        Snapshot{{"PATH", Value{"/des:/u"}}, {"EXTRA", Value{"x2"}}},
        {"PATH"},
        {{"PATH", prepended_with("/des")}},
        AssertOptions{/*strict=*/true});
    bool found = false;
    for (const auto& v : violations) {
        if (v.kind == ViolationKind::StrictUniverseMismatch && v.key == "EXTRA") {
            found = true;
        }
    }
    ASSERT_TRUE(found);
}

// ---------------------------------------------------------------------------
// Predicate library — parity with the Python/Go/C# canonical
// ---------------------------------------------------------------------------

TEST("unchanged() passes iff deep-equal") {
    std::mt19937 rng(42);
    for (int i = 0; i < 30; ++i) {
        std::string v = random_lowercase_string(rng, 0, 12);
        ASSERT_TRUE(unchanged().eval(Value{v}, Value{v}).ok);
    }
    ASSERT_TRUE(!unchanged().eval(Value{"a"}, Value{"b"}).ok);
    Record r1{{"email", "a@x.com"}};
    Record r2{{"email", "a@x.com"}};
    ASSERT_TRUE(unchanged().eval(Value{std::vector<Record>{r1}}, Value{std::vector<Record>{r2}}).ok);
}

TEST("prepended_with composes old and new by string concatenation") {
    ASSERT_TRUE(prepended_with("/des/bin").eval(Value{"/usr/bin"}, Value{"/des/bin:/usr/bin"}).ok);
    ASSERT_TRUE(!prepended_with("/des/bin").eval(Value{"/usr/bin"}, Value{"/wrong"}).ok);

    std::mt19937 rng(7);
    for (int i = 0; i < 30; ++i) {
        std::string tail = random_lowercase_string(rng, 0, 10);
        std::string composed = "PRE:" + tail;
        ASSERT_TRUE(prepended_with("PRE").eval(Value{tail}, Value{composed}).ok);
    }
}

TEST("appended_with composes old and new by string concatenation") {
    ASSERT_TRUE(appended_with(".bak").eval(Value{"/etc/hosts"}, Value{"/etc/hosts:.bak"}).ok);
    ASSERT_TRUE(!appended_with(".bak").eval(Value{"/etc/hosts"}, Value{"/etc/hosts"}).ok);
}

TEST("set_to ignores old and compares new by value") {
    ASSERT_TRUE(set_to(Value{"active"}).eval(Value{"inactive"}, Value{"active"}).ok);
    ASSERT_TRUE(!set_to(Value{"active"}).eval(Value{"inactive"}, Value{"pending"}).ok);
}

TEST("containing finds substrings and list membership") {
    ASSERT_TRUE(containing(Value{"/usr/bin"}).eval(Value{""}, Value{"/des/bin:/usr/bin"}).ok);
    ASSERT_TRUE(!containing(Value{"/usr/bin"}).eval(Value{""}, Value{"/des/bin:/opt/bin"}).ok);

    Record target{{"id", "1"}};
    Record other{{"id", "2"}};
    ASSERT_TRUE(containing(Value{std::vector<Record>{target}})
                    .eval(Value{}, Value{std::vector<Record>{other, target}})
                    .ok);
}

TEST("normalized_to compares under a normaliser") {
    auto expand_home = [](const Value& v) -> Value {
        if (!v.is_string()) return v;
        const std::string& s = v.as_string();
        std::string needle = "$HOME";
        auto pos = s.find(needle);
        if (pos == std::string::npos) return v;
        return Value{s.substr(0, pos) + "/home/u" + s.substr(pos + needle.size())};
    };
    ASSERT_TRUE(normalized_to(expand_home)
                    .eval(Value{"/home/u/.local/bin"}, Value{"$HOME/.local/bin"})
                    .ok);
    ASSERT_TRUE(!normalized_to(expand_home)
                     .eval(Value{"/home/u/.local/bin"}, Value{"$HOME/.other/bin"})
                     .ok);
}

TEST("idempotent_after passes when the first segment already matches") {
    ASSERT_TRUE(idempotent_after("DES_BIN").eval(Value{"anything"}, Value{"DES_BIN:/usr/bin"}).ok);
    ASSERT_TRUE(!idempotent_after("DES_BIN").eval(Value{"anything"}, Value{"/usr/bin:/opt/bin"}).ok);
}

TEST("legacy_healed follows the four-case paper trace") {
    const std::string legacy = "DES_BIN:SYSTEM_PATH_FALLBACK";
    auto detector = [legacy](const Value& v) { return v.is_string() && v.as_string() == legacy; };
    auto healed = [legacy](const Value& v) {
        if (!v.is_string()) return false;
        const std::string& s = v.as_string();
        return s != legacy && s.size() > 8 && s.substr(0, 8) == "DES_BIN:";
    };
    Predicate pred = legacy_healed(detector, healed);
    ASSERT_TRUE(pred.eval(Value{legacy}, Value{"DES_BIN:/usr/bin"}).ok);
    ASSERT_TRUE(!pred.eval(Value{legacy}, Value{legacy}).ok);
    ASSERT_TRUE(!pred.eval(Value{"/usr/bin"}, Value{"DES_BIN:/usr/bin"}).ok);
}

TEST("prepended_with_item composes list state by prepending one item") {
    Record a{{"v", "a"}};
    Record x{{"v", "x"}};
    ASSERT_TRUE(prepended_with_item(a).eval(Value{std::vector<Record>{}}, Value{std::vector<Record>{a}}).ok);
    ASSERT_TRUE(
        prepended_with_item(a).eval(Value{std::vector<Record>{x}}, Value{std::vector<Record>{a, x}}).ok);
    ASSERT_TRUE(
        !prepended_with_item(a).eval(Value{std::vector<Record>{x}}, Value{std::vector<Record>{x, a}}).ok);
    ASSERT_TRUE(
        !prepended_with_item(a).eval(Value{std::vector<Record>{x}}, Value{std::vector<Record>{a}}).ok);
}

TEST("appended_with_item composes list state by appending one item") {
    Record z{{"v", "z"}};
    Record x{{"v", "x"}};
    ASSERT_TRUE(appended_with_item(z).eval(Value{std::vector<Record>{}}, Value{std::vector<Record>{z}}).ok);
    ASSERT_TRUE(
        appended_with_item(z).eval(Value{std::vector<Record>{x}}, Value{std::vector<Record>{x, z}}).ok);
    ASSERT_TRUE(
        !appended_with_item(z).eval(Value{std::vector<Record>{x}}, Value{std::vector<Record>{z, x}}).ok);
}

// ---------------------------------------------------------------------------
// Universe semantics — bounded hand-rolled property loops
// ---------------------------------------------------------------------------

TEST("universe forbids a hidden mutation on an adjacent slot") {
    std::mt19937 rng(99);
    for (int i = 0; i < 20; ++i) {
        std::string old_home = random_lowercase_string(rng, 1, 8);
        std::string new_home = random_lowercase_string(rng, 1, 8);
        if (old_home == new_home) continue;
        std::vector<Violation> violations = assert_state_delta_collect(
            Snapshot{{"PATH", Value{"/u"}}, {"HOME", Value{old_home}}},
            Snapshot{{"PATH", Value{"/des:/u"}}, {"HOME", Value{new_home}}},
            {"PATH", "HOME"},
            {{"PATH", prepended_with("/des")}});
        ASSERT_TRUE(!violations.empty());
    }
}

TEST("universe permits mutation only when a matching predicate is declared") {
    std::vector<Violation> violations = assert_state_delta_collect(
        Snapshot{{"PATH", Value{"/u"}}, {"HOME", Value{"/h"}}},
        Snapshot{{"PATH", Value{"/des:/u"}}, {"HOME", Value{"/h"}}},
        {"PATH", "HOME"},
        {{"PATH", prepended_with("/des")}});
    ASSERT_TRUE(violations.empty());
}
