import test from "node:test";
import assert from "node:assert/strict";
import { matchesAccept, selectFiles } from "../src/file-upload-state.ts";
const file = (name, type="image/png", size=100, lastModified=1) => ({ name, type, size, lastModified });

test("accept supports extension, MIME and wildcard without trusting filenames alone", () => {
  assert.equal(matchesAccept(file("pic.PNG", "image/png"), ".png"), true);
  assert.equal(matchesAccept(file("pic.png", "text/plain"), "image/*"), false);
  assert.equal(matchesAccept(file("a.jpg", "image/jpeg"), "application/pdf,.jpg"), true);
  assert.equal(matchesAccept(file("evil.exe", "application/octet-stream"), ".png,image/*"), false);
});
test("enforces max count, size, total budget, duplicate and single mode", () => {
  const input = [file("a.png"),file("b.png"),file("c.png")];
  const result = selectFiles([], input, {maxFiles:2,maxSizeBytes:1000,maxTotalBytes:1000});
  assert.deepEqual(result.files.map(f=>f.name),["a.png","b.png"]);
  assert.equal(result.rejected[0].reason,"count");
  assert.equal(selectFiles([input[0]],[input[0]],{}).rejected[0].reason,"duplicate");
  assert.equal(selectFiles([],input,{multiple:false}).files.length,1);
  assert.equal(selectFiles([], [file("big.png","image/png",1001)],{maxSizeBytes:1000}).rejected[0].reason,"size");
  assert.equal(selectFiles([input[0]], [input[1]],{maxTotalBytes:150}).rejected[0].reason,"total_size");
});
test("untrusted MIME is validated before any network operation",()=>{
  assert.equal(selectFiles([], [file("x.svg","image/svg+xml")],{accept:"image/png,image/jpeg"}).rejected[0].reason,"type");
});
