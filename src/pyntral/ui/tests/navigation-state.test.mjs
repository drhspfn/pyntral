import test from "node:test";
import assert from "node:assert/strict";
import { navigationMatches, categoryRoute } from "../src/navigation-state.ts";
test("search includes ancestors, matches category descendants and preserves source tree", () => {
  const child = {id:"nodes",label:"Nœuds",children:[]};
  const leaf = {id:"budget",label:"Budget Usage",children:[]};
  const group = {id:"Operations",label:"Operations",children:[child,leaf]};
  const hidden = {id:"other",label:"Other",children:[]};
  const tree = [group,hidden];
  assert.deepEqual([...navigationMatches(tree,"budget usage")], [leaf,group]);
  assert.equal(navigationMatches(tree,"operations").size,3);
  assert.equal(navigationMatches(tree,"absent").size,0);
  assert.equal(navigationMatches(tree,"nodes").has(child),true);
  assert.equal(group.children.length,2);
  assert.equal(categoryRoute("Operations/Media & files"),"groups/Operations/Media%20%26%20files");
});
