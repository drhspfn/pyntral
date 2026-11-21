import test from 'node:test';
import assert from 'node:assert/strict';
import { parseTablePreferences, orderedColumns } from '../src/table-prefs.ts';

test('table preferences reject unknown columns and validate density', () => {
  const state = parseTablePreferences({order: ['b','bad','a'], hidden:['b','invalid'],
    pinned:'bad', density:'unknown'}, ['a','b']);
  assert.deepEqual(state.order,['b','a']);
  assert.deepEqual(state.hidden,['b']);
  assert.equal(state.pinned,null);
  assert.equal(state.density,'comfortable');
});

test('table order and visibility never expose a hidden server column', () => {
  const prefs = parseTablePreferences({order:['b','a'],hidden:['a']}, ['a','b']);
  assert.deepEqual(orderedColumns(['a','b'],prefs),['b']);
});
