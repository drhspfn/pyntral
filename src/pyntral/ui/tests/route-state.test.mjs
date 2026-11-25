import test from "node:test";
import assert from "node:assert/strict";
import {adminDestination, splitAdminLocation} from "../src/route-state.ts";
import {filtersFromSearch} from "../src/filter-state.ts";
test("admin-relative routes preserve filters and stay in the mount",()=>{
  const dest=adminDestination("/console","/resources/edges?filter.from_node_id=12");
  assert.equal(dest,"/console/resources/edges?filter.from_node_id=12");
  assert.deepEqual(splitAdminLocation("/console",dest),{route:"resources/edges",search:"?filter.from_node_id=12"});
  assert.throws(()=>adminDestination("/console","../other"));
  assert.throws(()=>adminDestination("/console","https://example.com"));
  assert.throws(()=>adminDestination("/console","//example.com"));
});
test("filter deep links initialize authorized controls, including equality shorthand",()=>{
  const fields=[{name:"agent_id",kind:"integer",filterOperators:["eq","neq"]},
    {name:"secret",kind:"string",views:{filter:{visible:false}}}];
  const result=filtersFromSearch(fields,"?filter.agent_id=12&filter.secret=private&filter.unknown=1");
  assert.deepEqual({...result},{agent_id:{operator:"eq",value:"12"}});
});
