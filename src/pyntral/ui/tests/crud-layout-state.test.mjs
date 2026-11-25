import test from "node:test";
import assert from "node:assert/strict";
import { resolveCrudLayout } from "../src/crud-layout-state.ts";
test("standard slots default to below the heading", () => {
  assert.deepEqual(resolveCrudLayout(), {showHeading:true,beforePosition:"after_heading"});
  assert.deepEqual(resolveCrudLayout({showHeading:false}), {showHeading:false,beforePosition:"after_heading"});
  assert.deepEqual(resolveCrudLayout({beforePosition:"above_heading"}), {showHeading:true,beforePosition:"above_heading"});
});
test("complete overrides keep their slots outside and control their own heading", () => {
  assert.deepEqual(resolveCrudLayout({showHeading:false,beforePosition:"after_heading"}, true), {showHeading:false,beforePosition:"above_heading"});
});
