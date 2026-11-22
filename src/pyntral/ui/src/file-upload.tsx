/** Controlled file picker. File bytes remain in the browser unless an explicit upload callback runs. */
import { useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type DragEvent, type KeyboardEvent } from "react";
import { FileImage, FilePlus2, FileText, LoaderCircle, Paperclip, Trash2, UploadCloud, X } from "lucide-react";
import { formatFileSize, formatFileRejection, selectFiles, type FileConstraints, type FileRejection } from "./file-upload-state";

export interface FileUploadReceipt {
  /** Server-verified object identifier; never derive it from the filename. */
  key: string;
  name: string;
  size: number;
  mimeType: string;
}
export interface FileUploadContext {
  signal: AbortSignal;
  onProgress: (progress: number) => void;
}
export interface FileUploadProps extends FileConstraints {
  files: readonly File[];
  onFilesChange: (files: File[]) => void;
  onRejected?: (rejections: FileRejection<File>[]) => void;
  preview?: boolean;
  allowPaste?: boolean;
  disabled?: boolean;
  id?: string;
  className?: string;
  label?: string;
  /** No upload happens unless the consumer explicitly provides this callback and presses Upload. */
  onUpload?: (file: File, context: FileUploadContext) => Promise<FileUploadReceipt>;
  onUploaded?: (receipts: FileUploadReceipt[]) => void;
}
function FilePreview({ file, enabled }: { file: File; enabled: boolean }) {
  const [src, setSrc] = useState<string | null>(null);
  const safeImage = /^(image\/png|image\/jpeg|image\/gif|image\/webp)$/.test(file.type);
  useEffect(() => {
    if (!enabled || !safeImage) return;
    const url = URL.createObjectURL(file);
    setSrc(url);
    return () => { URL.revokeObjectURL(url); setSrc(null); };
  }, [file, enabled, safeImage]);
  return src ? <img src={src} alt="" className="ra-file-thumbnail"/> :
    safeImage ? <FileImage size={20}/> : <FileText size={20}/>;
}
export function FileUpload({
  files, onFilesChange, onRejected, multiple = true, maxFiles = 10,
  maxSizeBytes = 10 * 1024 * 1024, maxTotalBytes = 50 * 1024 * 1024,
  accept, preview = true, allowPaste = true, disabled = false,
  id, className = "", label = "Add files", onUpload, onUploaded,
}: FileUploadProps) {
  const input = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  useEffect(() => () => abort.current?.abort(), []);
  const constraints = { multiple, maxFiles, maxSizeBytes, maxTotalBytes, accept };
  const add = (incoming: File[]) => {
    if (disabled || uploading || !incoming.length) return;
    const result = selectFiles(files, incoming, constraints);
    if (result.rejected.length) {
      setError(result.rejected.map(item => formatFileRejection(item, constraints)).join(" "));
      onRejected?.(result.rejected);
    } else setError(null);
    if (result.files.length !== files.length) onFilesChange(result.files);
  };
  const drop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault(); setDragging(false);
    if (!disabled) add(Array.from(event.dataTransfer.files));
  };
  const paste = (event: ClipboardEvent<HTMLDivElement>) => {
    if (!allowPaste || disabled || event.target instanceof HTMLInputElement ||
        event.target instanceof HTMLTextAreaElement) return;
    const pasted = Array.from(event.clipboardData.files);
    if (pasted.length) { event.preventDefault(); add(pasted); }
  };
  const upload = async () => {
    if (!onUpload || disabled || uploading || !files.length) return;
    const controller = new AbortController();
    abort.current = controller;
    setUploading(true); setProgress(0); setError(null);
    const receipts: FileUploadReceipt[] = [];
    try {
      // Deliberately sequential to avoid unrestricted client parallelism.
      for (const [index, file] of files.entries()) {
        if (controller.signal.aborted) break;
        const receipt = await onUpload(file, { signal: controller.signal,
          onProgress: percent => setProgress(Math.min(100, Math.max(0,
            ((index + Math.max(0, Math.min(percent, 100)) / 100) / files.length) * 100))) });
        if (!receipt || !receipt.key) throw new Error("Upload callback returned no object key");
        receipts.push(receipt);
        setProgress((receipts.length / files.length) * 100);
      }
      if (!controller.signal.aborted && receipts.length === files.length) onUploaded?.(receipts);
    } catch (cause) { if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Upload failed"); }
    finally { abort.current = null; setUploading(false); }
  };
  const pick = (event: ChangeEvent<HTMLInputElement>) => {
    add(Array.from(event.target.files ?? []));
    event.target.value = ""; // Selecting the same file twice still fires change.
  };
  const openPicker = () => { if (!disabled && !uploading) input.current?.click(); };
  const keydown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter" || event.key === " ") { event.preventDefault(); openPicker(); }
  };
  return <div className={`ra-file-upload ${className}`} data-ra-file-upload="">
    <input ref={input} id={id} className="ra-visually-hidden" type="file"
      multiple={multiple} accept={accept} disabled={disabled || uploading} onChange={pick}
      aria-label={label} tabIndex={-1}/>
    <div className={`ra-file-dropzone ${dragging ? "is-over" : ""} ${disabled ? "is-disabled" : ""}`}
      role="button" tabIndex={disabled ? -1 : 0} aria-disabled={disabled || uploading}
      aria-label={label} onClick={openPicker} onKeyDown={keydown} onPaste={paste}
      onDragEnter={event => { event.preventDefault(); if (!disabled) setDragging(true); }}
      onDragOver={event => { event.preventDefault(); if (!disabled) event.dataTransfer.dropEffect = "copy"; }}
      onDragLeave={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) setDragging(false); }}
      onDrop={drop}>
      <UploadCloud size={25} strokeWidth={1.7}/>
      <strong>{label}</strong>
      <span>Choose or drop {multiple ? "files" : "a file"}{allowPaste ? " · Paste from clipboard" : ""}</span>
      <small>{files.length}/{multiple ? maxFiles : 1} files · Up to {formatFileSize(maxSizeBytes)} each</small>
    </div>
    {!!files.length && <div className="ra-file-list" aria-live="polite">
      {files.map((file, index) => <div key={file.name + ":" + file.lastModified + ":" + index} className="ra-file-row">
        <FilePreview file={file} enabled={preview}/>
        <div className="ra-file-info"><strong title={file.name}>{file.name}</strong>
          <small>{formatFileSize(file.size)} · {file.type || "Unknown type"}</small></div>
        <button type="button" className="ra-file-remove" aria-label={`Remove ${file.name}`}
          disabled={disabled || uploading} onClick={() => onFilesChange(files.filter((_, i) => i !== index))}>
          <X size={16}/></button>
      </div>)}
    </div>}
    {error && <p className="ra-file-error" role="alert">{error}</p>}
    <div className="ra-file-actions">
      <span><Paperclip size={13}/> {files.length} selected</span>
      {!!files.length && <button type="button" className="btn subtle" disabled={disabled || uploading}
        onClick={() => onFilesChange([])}><Trash2 size={14}/> Clear</button>}
      {onUpload && <button type="button" className="btn primary" disabled={disabled || uploading || !files.length}
        onClick={() => { void upload(); }}>{uploading ? <LoaderCircle className="spin" size={15}/> : <FilePlus2 size={15}/>}
          {uploading ? `Uploading ${Math.round(progress)}%` : "Upload"}</button>}
      {uploading && <button type="button" className="btn subtle" onClick={() => abort.current?.abort()}>Cancel</button>}
    </div>
  </div>;
}
