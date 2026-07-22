#pragma once
// testkit.hpp — minimal hand-rolled test runner for the C++ polyglot pilot.
//
// No CMake/GoogleTest/Catch2 available in this pilot's build environment —
// a tiny self-registering runner keeps the fixture dependency-free while
// still giving Given-When-Then style scenarios a home. Mirrors the spirit
// (not the API) of `go test` / xunit's `[Fact]`.

#include <exception>
#include <functional>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

namespace testkit {

struct AssertionFailure {
    std::string message;
};

struct TestCase {
    std::string name;
    std::function<void()> fn;
};

inline std::vector<TestCase>& registry() {
    static std::vector<TestCase> tests;
    return tests;
}

struct Registrar {
    Registrar(const std::string& name, std::function<void()> fn) {
        registry().push_back(TestCase{name, std::move(fn)});
    }
};

inline int run_all() {
    int failures = 0;
    for (auto& t : registry()) {
        try {
            t.fn();
            std::cout << "[PASS] " << t.name << "\n";
        } catch (const AssertionFailure& e) {
            std::cout << "[FAIL] " << t.name << ": " << e.message << "\n";
            ++failures;
        } catch (const std::exception& e) {
            std::cout << "[FAIL] " << t.name << " (unexpected exception): " << e.what() << "\n";
            ++failures;
        }
    }
    std::cout << registry().size() << " test(s), " << failures << " failure(s)\n";
    return failures == 0 ? 0 : 1;
}

} // namespace testkit

#define TESTKIT_CONCAT_(a, b) a##b
#define TESTKIT_CONCAT(a, b) TESTKIT_CONCAT_(a, b)

#define TEST(name)                                                                     \
    static void TESTKIT_CONCAT(testkit_fn_, __LINE__)();                               \
    static testkit::Registrar TESTKIT_CONCAT(testkit_reg_, __LINE__)(                  \
        name, TESTKIT_CONCAT(testkit_fn_, __LINE__));                                  \
    static void TESTKIT_CONCAT(testkit_fn_, __LINE__)()

#define ASSERT_TRUE(cond)                                                              \
    do {                                                                               \
        if (!(cond)) {                                                                 \
            std::ostringstream oss;                                                    \
            oss << "ASSERT_TRUE(" #cond ") failed at " << __FILE__ << ":" << __LINE__; \
            throw testkit::AssertionFailure{oss.str()};                                \
        }                                                                              \
    } while (0)

#define ASSERT_FALSE(cond) ASSERT_TRUE(!(cond))

#define FAIL_TEST(msg)                                                                 \
    do {                                                                               \
        std::ostringstream oss;                                                        \
        oss << msg << " at " << __FILE__ << ":" << __LINE__;                           \
        throw testkit::AssertionFailure{oss.str()};                                    \
    } while (0)
