/** Localized, overridable UI messages; display text only, not authorization. */
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import type { LocalizationConfig } from "./types";

export interface Translator {
  locale: string;
  t(key: string, fallback: string, variables?: Record<string, string | number>): string;
}

/** Bundled core messages; application dictionaries take precedence. */
const coreMessages: Record<string, Record<string, string>> = {
  ru: {
    "nav.overview": "Обзор", "nav.sign_out": "Выйти",
    "resources.description": "Просмотр и управление записями.",
    "actions.new": "Новая запись", "actions.create": "Создать запись",
    "actions.save": "Сохранить изменения",
    "table.columns": "Столбцы", "table.filters": "Фильтры",
    "table.clear_filters": "Очистить фильтры", "table.sort_by": "Сортировка",
  },
  es: {
    "nav.overview": "Resumen", "nav.sign_out": "Cerrar sesión",
    "resources.description": "Consulta y administra tus registros.",
    "actions.new": "Nuevo registro", "actions.create": "Crear registro",
    "actions.save": "Guardar cambios",
    "table.columns": "Columnas", "table.filters": "Filtros",
    "table.clear_filters": "Borrar filtros", "table.sort_by": "Ordenar por",
  },
  fr: {
    "nav.overview": "Vue d'ensemble", "nav.sign_out": "Se déconnecter",
    "resources.description": "Consulter et gérer les enregistrements.",
    "actions.new": "Nouvel enregistrement", "actions.create": "Créer",
    "actions.save": "Enregistrer",
    "table.columns": "Colonnes", "table.filters": "Filtres",
    "table.clear_filters": "Effacer les filtres", "table.sort_by": "Trier par",
  },
};

const Context = createContext<Translator>({ locale: "en", t: (_key, fallback) => fallback });

export function I18nProvider({ config, children }: { config?: LocalizationConfig; children: ReactNode }) {
  const locale = config?.code || "en";
  const messages = config?.messages || {};
  const language = locale.toLowerCase().split("-")[0];
  const bundled = coreMessages[locale.toLowerCase()] || coreMessages[language] || {};
  const value = useMemo<Translator>(() => ({
    locale,
    t: (key, fallback, variables) => {
      const template = messages[key] ?? bundled[key] ?? fallback;
      return template.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g,
        (match, name: string) => variables?.[name] == null ? match : String(variables[name]));
    },
  }), [locale, messages, bundled]);
  useEffect(() => { const old = document.documentElement.lang; document.documentElement.lang = locale;
    return () => { document.documentElement.lang = old; }; }, [locale]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}
export function useI18n(): Translator { return useContext(Context); }
