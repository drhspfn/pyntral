import type { BadgeTone } from "./types.ts";

const tones: Record<string, BadgeTone> = {
  success:"success", succeeded:"success", completed:"success", complete:"success", fulfilled:"success", active:"success", ready:"success",
  failed:"danger", error:"danger", cancelled:"danger", canceled:"danger", rejected:"danger",
  running:"primary", processing:"primary", in_progress:"primary", open:"primary",
  pending:"warning", queued:"warning", waiting:"warning", warning:"warning", retrying:"warning",
};
export function statusTone(value: string, overrides: Readonly<Record<string, BadgeTone>> = {}, fallback: BadgeTone = "neutral", auto = true): BadgeTone {
  if (Object.hasOwn(overrides, value)) return overrides[value];
  const key = value.trim().toLowerCase().replace(/[ -]+/g,"_");
  return auto && Object.hasOwn(tones,key) ? tones[key] : fallback;
}
export function statusLabel(value: string, labels: Readonly<Record<string,string>> = {}): string {
  return Object.hasOwn(labels, value) ? labels[value] : value;
}
export function useDefaultRecordLink(index: number, enabled: boolean | undefined, custom: boolean, inlineCode: boolean, canShow: boolean, id: unknown): boolean {
  return index === 0 && enabled !== false && !custom && !inlineCode && canShow && id != null;
}
