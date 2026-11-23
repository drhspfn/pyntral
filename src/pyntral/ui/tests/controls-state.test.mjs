import test from 'node:test';
import assert from 'node:assert/strict';
import { changeGroupSelection } from '../src/controls-state.ts';

test('checkbox group supports multiple choices without duplicate values', () => {
  assert.deepEqual(changeGroupSelection(['a'], 'b', true), ['a','b']);
  assert.deepEqual(changeGroupSelection(['a'], 'a', true), ['a']);
  assert.deepEqual(changeGroupSelection(['a','b'], 'a', false), ['b']);
});

test('selection max and min rules never silently uncheck other choices', () => {
  assert.deepEqual(changeGroupSelection(['a'], 'b', true, {maxSelected: 1}), ['a']);
  assert.deepEqual(changeGroupSelection(['a'], 'a', false, {minSelected: 1}), ['a']);
  assert.deepEqual(changeGroupSelection(['a'], 'b', true, {maxSelected: 2}), ['a','b']);
});
