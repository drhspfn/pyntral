import { strict as assert } from 'node:assert';
import { test } from 'node:test';
import { changeFilterOperator, filterControlWidth } from '../src/filter-state.ts';

test('changing equals to contains keeps an existing text search', () => {
  const original = { operator: 'eq', value: 'Chair' };
  assert.deepEqual(changeFilterOperator(original, 'contains'), { operator: 'contains', value: 'Chair' });
  assert.equal(original.operator, 'eq', 'state transitions must not mutate inputs');
});

test('changing equality to numeric range moves value into the lower bound', () => {
  const range = changeFilterOperator({ operator: 'eq', value: '100' }, 'between');
  assert.deepEqual(range, { operator: 'between', value: '100', from: '100', to: '' });
  // Switching back after editing a range retains the original scalar draft.
  assert.equal(changeFilterOperator({ ...range, to: '500' }, 'gte').value, '100');
  assert.equal(changeFilterOperator({ ...range, from: '300', to: '500' }, 'gte').value, '300');
});

test('editing a range without a prior scalar keeps the lower value for single-value comparisons', () => {
  assert.equal(changeFilterOperator({ operator: 'between', from: '3', to: '9' }, 'lt').value, '3');
});

test('explicit filter widths and SQL type constraints affect width safely', () => {
  const field = { kind: 'string', maxLength: 10 };
  assert.ok(filterControlWidth(field, false) < filterControlWidth({ kind: 'string', maxLength: 120 }, false));
  assert.ok(filterControlWidth({ kind: 'integer', precision: 4 }, true) < 400);
  assert.equal(filterControlWidth({ kind: 'number', filterWidth: 280 }, true), 280);
  assert.equal(filterControlWidth({ kind: 'string', filterWidth: 600 }, false), 560);
  assert.ok(filterControlWidth({ kind: 'date' }, true) > filterControlWidth({ kind: 'date' }, false));
});
