import { useMemo, useState, useId, type CSSProperties } from "react";
import { Check, ChevronDown, ChevronRight, Copy } from "lucide-react";
import { formatJson, jsonSource } from "./code-state";
import { codeLanguage, languageLabel, highlightedCode } from "./code-highlight";
import { useI18n } from "./i18n";

export interface CodeBlockProps {
  code: string;
  language?: string;
  title?: string;
  inline?: boolean;
  highlight?: boolean;
  highlightToggle?: boolean;
  format?: boolean;
  formatToggle?: boolean;
  indent?: number;
  copyable?: boolean;
  collapsible?: boolean;
  collapsed?: boolean;
  defaultCollapsed?: boolean;
  onCollapsedChange?: (collapsed: boolean) => void;
  showLanguage?: boolean;
  wrap?: boolean;
  minHeight?: number | string;
  maxHeight?: number | string;
  minWidth?: number | string;
  maxWidth?: number | string;
  fontSize?: number | string;
  className?: string;
  style?: CSSProperties;
}
/** Read-only source viewer. Copy copies the displayed text, never markup. */
export function CodeBlock({
  code, language = "auto", title, inline = false, highlight = true, highlightToggle = false, format = true,
  formatToggle = true, indent = 2, copyable = true, collapsible = false, collapsed,
  defaultCollapsed = false, onCollapsedChange, showLanguage = true, wrap = false,
  minHeight, maxHeight = 360, minWidth, maxWidth = "100%", fontSize, className = "", style,
}: CodeBlockProps) {
  const { t } = useI18n();
  const id = useId();
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed);
  const [formatOverride, setFormatOverride] = useState<boolean | null>(null);
  const [highlightOverride, setHighlightOverride] = useState<boolean | null>(null);
  const highlighting = highlightOverride ?? highlight;
  const [copyResult, setCopyResult] = useState<{ text: string; status: "copied" | "failed" } | null>(null);
  const isCollapsed = !inline && collapsible && (collapsed ?? internalCollapsed);
  // Avoid excessive work on very large logs; raw text remains fully available.
  const formatted = useMemo(() => code.length <= 100000 ? formatJson(code, indent) : null, [code, indent]);
  const resolved = useMemo(() => codeLanguage(code, language, formatted !== null), [code, language, formatted]);
  const isJson = resolved === "json" && formatted !== null;
  const pretty = (formatOverride ?? format) && isJson;
  const displayed = pretty ? formatted! : code;
  const html = useMemo(() => highlighting && !isCollapsed ? highlightedCode(displayed, resolved) : null,
    [displayed, resolved, highlighting, isCollapsed]);
  const copyState = copyResult?.text === displayed ? copyResult.status : "idle";
  const copy = async () => {
    try { await navigator.clipboard.writeText(displayed); setCopyResult({text: displayed, status: "copied"}); }
    catch { setCopyResult({text: displayed, status: "failed"}); }
  };
  const toggle = () => {
    const next = !isCollapsed;
    if (collapsed === undefined) setInternalCollapsed(next);
    onCollapsedChange?.(next);
  };
  // highlight.js emits escaped source + span markup; raw source is never injected as HTML.
  const content = html === null ? <code>{displayed}</code> : <code dangerouslySetInnerHTML={{ __html: html }}/>;
  if (inline) return <span className={`ra-code-inline ${className}`} style={{ minWidth, maxWidth, fontSize, ...style }}>{content}</span>;
  return <div className={`ra-code-block ${className}`} style={{ minWidth, maxWidth, ...style }}>
    {(title || showLanguage || copyable || collapsible || highlightToggle || (isJson && formatToggle)) && <div className="ra-code-header">
      <div className="ra-code-heading">
        {collapsible && <button type="button" className="ra-code-control" aria-label={isCollapsed ? t("code.expand", "Expand code") : t("code.collapse", "Collapse code")}
          aria-expanded={!isCollapsed} aria-controls={id} onClick={toggle}>{isCollapsed ? <ChevronRight size={15}/> : <ChevronDown size={15}/>}</button>}
        {title && <strong title={title}>{title}</strong>}
        {showLanguage && <span className="ra-code-language">{languageLabel(resolved)}</span>}
      </div>
      <div className="ra-code-actions">
        {highlightToggle && <button type="button" className="ra-code-control" aria-pressed={highlighting}
          onClick={() => setHighlightOverride(!highlighting)}>{t("code.highlight", "Highlight")}</button>}
        {isJson && formatToggle && <button type="button" className="ra-code-control" aria-pressed={pretty}
          onClick={() => { setFormatOverride(!pretty); setCopyResult(null); }}>{t("code.format", "Format")}</button>}
        {copyable && <button type="button" className="ra-code-control" onClick={() => { void copy(); }}
          aria-label={t("code.copy", "Copy code")}>{copyState === "copied" ? <Check size={14}/> : <Copy size={14}/>}
          <span>{copyState === "copied" ? t("code.copied", "Copied") : t("code.copy", "Copy")}</span></button>}
      </div>
    </div>}
    {copyState === "failed" && <div className="ra-code-error" role="status">{t("code.copy_failed", "Clipboard unavailable; select and copy the text manually.")}</div>}
    <pre id={id} hidden={isCollapsed} tabIndex={isCollapsed ? undefined : 0}
      className={wrap ? "ra-code-wrap" : ""} style={{ minHeight, maxHeight, fontSize }}>{content}</pre>
  </div>;
}
export interface JsonViewProps extends Omit<CodeBlockProps, "code" | "language"> { value: unknown }
/** Render JSON objects or serialized JSON strings; malformed JSON stays readable. */
export function JsonView({ value, ...props }: JsonViewProps) {
  return <CodeBlock {...props} code={jsonSource(value)} language="json"/>;
}
