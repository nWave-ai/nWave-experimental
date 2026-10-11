import test from "node:test";
import assert from "node:assert/strict";

test("the promised value is missing", () => {
  assert.equal(0, 1, "WHAT: value is absent; WHY: promised behavior must exist; HOW: deliver the value");
});
