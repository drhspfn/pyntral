/** Immutable reorder helpers shared by SortableList and list consumers. */
export function moveSortableItem<T>(items: readonly T[], from: number, to: number): T[] {
  const result = [...items];
  if (!Number.isInteger(from) || !Number.isInteger(to) || from < 0 || to < 0 ||
      from >= result.length || to >= result.length || from === to) return result;
  const [item] = result.splice(from, 1);
  result.splice(to, 0, item);
  return result;
}
export function sameSortableOrder<T>(before: readonly T[], after: readonly T[], key: (item: T) => string): boolean {
  return before.length === after.length && before.every((item, index) => key(item) === key(after[index]));
}
