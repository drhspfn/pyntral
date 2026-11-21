import test from 'node:test';
import assert from 'node:assert/strict';
import { moveSortableItem, sameSortableOrder } from '../src/sortable-state.ts';

test('moves rows without mutating caller arrays', () => {
  const rows = ['a','b','c'];
  assert.deepEqual(moveSortableItem(rows, 0, 2), ['b','c','a']);
  assert.deepEqual(moveSortableItem(rows, 2, 0), ['c','a','b']);
  assert.deepEqual(rows, ['a','b','c']);
});
test('invalid positions and identical moves have no effect', () => {
  const rows = ['a', 'b'];
  for (const [from, to] of [[-1,0],[0,2],[0,0],[NaN,1],[0.5,1]]) {
    assert.deepEqual(moveSortableItem(rows, from, to), rows);
  }
});
test('stable keys rather than object references determine whether ordering changed', () => {
  const key = (item) => item.id;
  assert.equal(sameSortableOrder([{id:1},{id:2}], [{id:1},{id:2}], key), true);
  assert.equal(sameSortableOrder([{id:1},{id:2}], [{id:2},{id:1}], key), false);
  assert.equal(sameSortableOrder([{id:1}], [{id:1},{id:2}], key), false);
});
