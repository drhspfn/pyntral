import { useEffect, useRef, useState } from "react";
import { Download, FileImage, FileText, X } from "lucide-react";
import { Button } from "./button";
import { formatFileSize } from "./file-upload-state";

export interface FileRowProps {
  name: string;
  size: number;
  mimeType?: string;
  file?: File;
  /** Optional URL for a raster thumbnail; downloaded lazily when the row becomes visible. */
  previewUrl?: string;
  preview?: boolean;
  href?: string;
  onRemove?: () => void;
  disabled?: boolean;
}
const safeRaster = /^(image\/png|image\/jpeg|image\/gif|image\/webp|image\/avif)$/;
function FilePreview({ file, url, mimeType, enabled }: {
  file?: File; url?: string; mimeType: string; enabled: boolean;
}) {
  const frame = useRef<HTMLDivElement>(null);
  const [src, setSrc] = useState<string | null>(null);
  const image = safeRaster.test(mimeType);
  useEffect(() => {
    setSrc(null);
    if (!enabled || !image || (!file && !url)) return;
    const controller = new AbortController();
    let objectUrl: string | undefined;
    let observer: IntersectionObserver | undefined;
    const display = (blob: Blob) => {
      if (controller.signal.aborted) return;
      objectUrl = URL.createObjectURL(blob);
      setSrc(objectUrl);
    };
    if (file) display(file);
    else if (url) {
      const load = () => {
        observer?.disconnect();
        void fetch(url, { signal: controller.signal, credentials: "same-origin" })
          .then(response => {
            if (!response.ok) throw new Error("Preview unavailable");
            return response.blob();
          })
          .then(blob => display(blob.slice(0, blob.size, mimeType)))
          .catch(() => { /* A missing or unreadable preview retains the file icon. */ });
      };
      if (frame.current && typeof IntersectionObserver !== "undefined") {
        observer = new IntersectionObserver(entries => {
          if (entries.some(entry => entry.isIntersecting)) load();
        });
        observer.observe(frame.current);
      } else load();
    }
    return () => { controller.abort(); observer?.disconnect(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [file, url, mimeType, enabled, image]);
  return <div ref={frame} className="ra-file-preview" aria-hidden="true">
    {src ? <img src={src} alt="" className="ra-file-thumbnail" onError={() => setSrc(null)}/> :
      image ? <FileImage size={20}/> : <FileText size={20}/>}
  </div>;
}

export function FileRow({ name, size, mimeType = "", file, previewUrl, preview = true,
  href, onRemove, disabled = false }: FileRowProps) {
  const type = mimeType || file?.type || "";
  return <div className="ra-file-row">
    <FilePreview file={file} url={previewUrl} mimeType={type} enabled={preview}/>
    <div className="ra-file-info">
      {href ? <a href={href} download title={name} className="ra-file-name">{name}</a> :
        <strong title={name} className="ra-file-name">{name}</strong>}
      <small>{formatFileSize(size)} · {type || "Unknown type"}</small>
    </div>
    <div className="ra-file-row-actions">
      {href && <a href={href} download className="ra-file-download" aria-label={`Download ${name}`} title="Download">
        <Download size={16}/></a>}
      {onRemove && <Button type="button" variant="ghost" className="ra-file-remove" disabled={disabled}
        aria-label={`Remove ${name}`} title="Remove" onClick={onRemove} startIcon={<X size={17}/>}/>}
    </div>
  </div>;
}
