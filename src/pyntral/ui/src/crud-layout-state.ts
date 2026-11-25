import type { CrudLayoutDef } from "./types.ts";

/** Full replacements own their headings. Their slots stay outside the replacement. */
export function resolveCrudLayout(layout?: CrudLayoutDef, custom = false) {
  return {
    showHeading: layout?.showHeading !== false,
    beforePosition: custom || layout?.beforePosition === "above_heading" ? "above_heading" as const : "after_heading" as const,
  };
}
