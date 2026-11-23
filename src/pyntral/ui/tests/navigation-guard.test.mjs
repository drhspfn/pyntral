import test from "node:test";
import assert from "node:assert/strict";
import { hasNavigationBlocker, mayLeavePage, registerNavigationBlocker } from "../src/navigation-guard.ts";

test("clean navigation is allowed without a blocker", async () => {
  assert.equal(hasNavigationBlocker(), false);
  assert.equal(await mayLeavePage(), true);
});

test("dirty forms can reject navigation and unregister on unmount", async () => {
  const unregister = registerNavigationBlocker(async () => false);
  assert.equal(hasNavigationBlocker(), true);
  assert.equal(await mayLeavePage(), false);
  unregister();
  assert.equal(hasNavigationBlocker(), false);
  assert.equal(await mayLeavePage(), true);
});

test("stale cleanup cannot remove a replacement blocker", async () => {
  const stale = registerNavigationBlocker(async () => false);
  const fresh = registerNavigationBlocker(async () => true);
  stale();
  assert.equal(await mayLeavePage(), true);
  fresh();
  assert.equal(hasNavigationBlocker(), false);
});
