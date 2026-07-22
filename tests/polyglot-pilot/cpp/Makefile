# Makefile — polyglot pilot (C++). Mirrors the minimalism of the Go/Rust
# fixtures' go.mod/Cargo.toml: no CMake dependency (unavailable in this
# pilot's build environment), just g++ + make. Two self-contained test
# binaries, zero third-party test framework — common/testkit is a small
# hand-rolled runner.

CXX ?= g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Werror -O0 -g

BUILD_DIR := build

STATEDELTA_TEST_SRCS := \
	common/statedelta/state_delta.cpp \
	common/statedelta/state_delta_test.cpp \
	common/testkit/test_main.cpp

FEATURE_TEST_SRCS := \
	common/statedelta/state_delta.cpp \
	productionapp/app.cpp \
	feature/feature_specifications_test.cpp \
	feature/feature_scenarios_test.cpp \
	common/testkit/test_main.cpp

STATEDELTA_TEST_BIN := $(BUILD_DIR)/state_delta_test
FEATURE_TEST_BIN := $(BUILD_DIR)/feature_test

.PHONY: all test clean

all: $(STATEDELTA_TEST_BIN) $(FEATURE_TEST_BIN)

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)

$(STATEDELTA_TEST_BIN): $(STATEDELTA_TEST_SRCS) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $(STATEDELTA_TEST_SRCS)

$(FEATURE_TEST_BIN): $(FEATURE_TEST_SRCS) | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -o $@ $(FEATURE_TEST_SRCS)

test: all
	./$(STATEDELTA_TEST_BIN)
	./$(FEATURE_TEST_BIN)

clean:
	rm -rf $(BUILD_DIR)
