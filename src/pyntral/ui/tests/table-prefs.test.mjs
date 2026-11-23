import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultTablePreferences, moveColumn, reorderColumns, setColumnVisible, parseTablePreferences, orderedColumns } from '../src/table-prefs.ts';

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

test('columns cannot all be hidden; hiding a pinned column releases the pin', () => {
  const prefs = {order: ['a', 'b'], hidden:['b'], pinned:'a', density:'comfortable',presets:{}};
  assert.deepEqual(setColumnVisible(['a','b'], prefs, 'a', false), prefs);
  const unhidden = setColumnVisible(['a','b'], prefs, 'b', true);
  const hidden = setColumnVisible(['a','b'], unhidden, 'a', false);
  assert.deepEqual(hidden.hidden, ['a']);
  assert.equal(hidden.pinned, null);
});
test('moveColumn preserves a stable complete ordering', () => {
  const prefs = defaultTablePreferences();
  const moved = moveColumn(['a','b','c'], prefs, 'b', -1);
  assert.deepEqual(moved.order,['b','a','c']);
  assert.deepEqual(moveColumn(['a','b','c'],moved,'b',-1), moved);
  assert.deepEqual(moveColumn(['a','b','c'],moved,'b',1).order,['a','b','c']);
});

test('drag order retains visibility and pinned settings', () => {
  const names = ['id','name','status'];
  const prefs = {...defaultTablePreferences(), hidden:['status'], pinned:'id'};
  const next = reorderColumns(names, prefs, ['name','status','id']);
  assert.deepEqual(next.order, ['name','status','id']);
  assert.deepEqual(orderedColumns(names, next), ['name','id']);
  assert.deepEqual(next.hidden, ['status']);
  assert.equal(next.pinned, 'id');
});
test('invalid drag reorder cannot inject, drop or repeat a column', () => {
  const names = ['a','b'], prefs = defaultTablePreferences();
  for (const values of [['a'],['a','a'],['a','x']]) {
    assert.equal(reorderColumns(names, prefs, values), prefs);
  }
});
