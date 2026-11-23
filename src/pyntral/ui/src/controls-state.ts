/** Framework-independent selection rules shared by choice controls and tests. */
export function changeGroupSelection<T extends string | number>(
  current: readonly T[], value: T, checked: boolean,
  limits: { minSelected?: number; maxSelected?: number } = {},
): T[] {
  const existing = current.includes(value);
  if (checked === existing) return [...current];
  if (checked) {
    if (limits.maxSelected !== undefined && current.length >= limits.maxSelected) return [...current];
    return [...current, value];
  }
  if (current.length <= (limits.minSelected ?? 0)) return [...current];
  return current.filter((item) => item !== value);
}
