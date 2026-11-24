import test from "node:test";
import assert from "node:assert/strict";
import {formatJson, jsonSource, normalizeLanguage} from "../src/code-state.ts";
test("format JSON without changing strings, large numbers or duplicate keys", () => {
  const raw = '{"id":9007199254740993,"a":"x y","a":[{},[],1e10]}';
  const formatted = formatJson(raw);
  assert.ok(formatted.includes("9007199254740993"));
  assert.ok(formatted.includes('"x y"'));
  assert.equal(formatted.match(/"a"/g).length,2);
  assert.deepEqual(JSON.parse(formatted),JSON.parse(raw));
  assert.equal(formatJson("{bad"),null);
  assert.equal(formatJson('{"text":"a\\\\b"}'),'{\n  "text": "a\\\\b"\n}');
  assert.equal(jsonSource({ok:true}),'{"ok":true}');
  assert.equal(normalizeLanguage("C#"),"csharp");
});

test("large/deep JSON is left untouched instead of expanding without bound", () => {
  assert.equal(formatJson("[".repeat(300) + "0" + "]".repeat(300)),null);
  assert.equal(formatJson(JSON.stringify("x".repeat(100001))),null);
  assert.equal(normalizeLanguage("constructor"),"constructor");
});
