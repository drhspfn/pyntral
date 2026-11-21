/** Localized, overridable UI messages; display text only, not authorization. */
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import type { LocalizationConfig } from "./types";

export interface Translator {
  locale: string;
  t(key: string, fallback: string, variables?: Record<string, string | number>): string;
}

const Context = createContext<Translator>({ locale: "en", t: (_key, fallback) => fallback });

export function I18nProvider({ config, children }: { config?: LocalizationConfig; children: ReactNode }) {
  const locale = config?.code || "en";
  const messages = config?.messages || {};
  const value = useMemo<Translator>(() => ({
    locale,
    t: (key, fallback, variables) => {
      const template = messages[key] ?? fallback;
      return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g,
        (match, name: string) => variables?.[name] == null ? match : String(variables[name]));
    },
  }), [locale, messages]);
  useEffect(() => { const old = document.documentElement.lang; document.documentElement.lang = locale;
    return () => { document.documentElement.lang = old; }; }, [locale]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n(): Translator { return useContext(Context); }
