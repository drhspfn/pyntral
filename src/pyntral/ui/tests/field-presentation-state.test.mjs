import test from "node:test";
import assert from "node:assert/strict";
import {statusTone,statusLabel,shouldLinkRecord} from "../src/field-presentation-state.ts";
test("statuses use explicit overrides, known meanings and neutral fallback",()=>{
  assert.equal(statusTone("COMPLETED"),"success");
  assert.equal(statusTone("in progress"),"primary");
  assert.equal(statusTone("pending",{pending:"danger"}),"danger");
  assert.equal(statusTone("unknown",{},"warning"),"warning");
  assert.equal(statusTone("completed",{},"neutral",false),"neutral");
  assert.equal(statusTone("constructor"),"neutral");
  assert.equal(statusLabel("running",{running:"In progress"}),"In progress");
});
test("custom first cells never get nested interactive links",()=>{
  assert.equal(shouldLinkRecord(0,true,false,false,true,0),true);
  assert.equal(shouldLinkRecord(0,true,true,false,true,1),false);
  assert.equal(shouldLinkRecord(0,false,false,false,true,1),false);
  assert.equal(shouldLinkRecord(0,true,false,true,true,1),false);
  assert.equal(shouldLinkRecord(0,true,false,false,true,null),false);
  assert.equal(shouldLinkRecord(1,true,false,false,true,1),false);
});
