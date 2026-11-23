/** Pure validation shared by the controlled FileUpload atom. Never trust it as server validation. */
export interface FileLike {
  name: string;
  size: number;
  type: string;
  lastModified?: number;
}
export interface FileConstraints {
  multiple?: boolean;
  maxFiles?: number;
  maxSizeBytes?: number;
  maxTotalBytes?: number;
  accept?: string;
}
export interface FileRejection<T extends FileLike = FileLike> {
  file: T;
  reason: "type" | "size" | "total_size" | "count" | "duplicate";
}
export function matchesAccept(file: FileLike, accept?: string): boolean {
  if (!accept?.trim()) return true;
  const mime = file.type.toLowerCase();
  const name = file.name.toLowerCase();
  return accept.split(",").map(part => part.trim().toLowerCase()).filter(Boolean).some(part =>
    part.startsWith(".") ? name.endsWith(part) :
    part.endsWith("/*") ? mime.startsWith(part.slice(0, -1)) :
    mime === part);
}
export function selectFiles<T extends FileLike>(
  existing: readonly T[], incoming: readonly T[], options: FileConstraints = {},
): { files: T[]; rejected: FileRejection<T>[] } {
  const files = [...existing];
  const rejected: FileRejection<T>[] = [];
  const maxFiles = options.multiple === false ? 1 : options.maxFiles ?? 10;
  const maxSize = options.maxSizeBytes ?? 10 * 1024 * 1024;
  const maxTotal = options.maxTotalBytes ?? 50 * 1024 * 1024;
  let total = files.reduce((sum, file) => sum + file.size, 0);
  for (const file of incoming) {
    let reason: FileRejection<T>["reason"] | null = null;
    if (!matchesAccept(file, options.accept)) reason = "type";
    else if (!Number.isFinite(file.size) || file.size < 0 || file.size > maxSize) reason = "size";
    else if (files.some(item => item.name === file.name && item.size === file.size &&
      item.lastModified === file.lastModified)) reason = "duplicate";
    else if (files.length >= maxFiles) reason = "count";
    else if (total + file.size > maxTotal) reason = "total_size";
    if (reason) rejected.push({ file, reason });
    else { files.push(file); total += file.size; }
  }
  return { files, rejected };
}
export function formatFileSize(size: number): string {
  if (size < 1024) return size + " B";
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + " KB";
  return (size / (1024 * 1024)).toFixed(1) + " MB";
}

/** Human-readable, actionable validation feedback; stable reason codes remain public. */
export function formatFileRejection<T extends FileLike>(
  rejection: FileRejection<T>, options: FileConstraints = {},
): string {
  const { file, reason } = rejection;
  const label = file.name || "Unnamed file";
  switch (reason) {
    case "type":
      return `${label}: unsupported file type${options.accept ? ` (allowed: ${options.accept})` : ""}.`;
    case "size":
      return `${label}: file is ${formatFileSize(file.size)}, maximum allowed is ${formatFileSize(options.maxSizeBytes ?? 10 * 1024 * 1024)}.`;
    case "total_size":
      return `${label}: adding this file would exceed the total ${formatFileSize(options.maxTotalBytes ?? 50 * 1024 * 1024)} limit.`;
    case "count":
      return `${label}: you can select up to ${options.multiple === false ? 1 : options.maxFiles ?? 10} file(s).`;
    case "duplicate":
      return `${label}: this file is already selected.`;
  }
}
