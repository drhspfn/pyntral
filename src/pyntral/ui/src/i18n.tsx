/** Localized, overridable UI messages; display text only, not authorization. */
import { createContext, useContext, useEffect, useMemo, type ReactNode } from "react";
import type { LocalizationConfig } from "./types";

export interface Translator {
  locale: string;
  t(key: string, fallback: string, variables?: Record<string, string | number>): string;
}

/** Bundled core messages; application dictionaries take precedence. */
const coreMessages: Record<string, Record<string, string>> = {
  de: {
    "login.title": "Anmelden", "login.subtitle": "Melden Sie sich mit Ihrem Administratorkonto an.",
    "login.username": "Benutzername", "login.password": "Passwort", "login.submit": "Weiter",
    "login.show_password": "Passwort anzeigen", "login.hide_password": "Passwort ausblenden", "login.toggle_theme": "Design wechseln",
    "code.expand": "Code erweitern", "code.collapse": "Code einklappen", "code.copy": "Kopieren", "code.copied": "Kopiert", "code.format": "Formatieren", "code.highlight": "Syntaxfarben", "code.copy_failed": "Zwischenablage nicht verfügbar; Text manuell kopieren.",
    "loading.records": "Datensätze werden geladen…", "nav.overview": "Übersicht", "nav.search": "Navigation durchsuchen", "nav.no_results": "Keine passenden Seiten", "nav.sign_out": "Abmelden",
    "resources.description": "Datensätze anzeigen und verwalten.",
    "actions.new": "Neuer Datensatz", "actions.create": "Datensatz erstellen",
    "actions.save": "Änderungen speichern",
    "table.columns": "Spalten", "table.filters": "Filter",
    "table.clear_filters": "Filter zurücksetzen", "table.sort_by": "Sortieren nach",
  },
  fr: {
    "login.title": "Connexion", "login.subtitle": "Utilisez votre compte administrateur pour continuer.",
    "login.username": "Identifiant", "login.password": "Mot de passe", "login.submit": "Continuer",
    "login.show_password": "Afficher le mot de passe", "login.hide_password": "Masquer le mot de passe", "login.toggle_theme": "Changer de thème",
    "code.expand": "Développer le code", "code.collapse": "Réduire le code", "code.copy": "Copier", "code.copied": "Copié", "code.format": "Formater", "code.highlight": "Coloration", "code.copy_failed": "Presse-papiers indisponible ; copiez le texte manuellement.",
    "loading.records": "Chargement des enregistrements…", "nav.overview": "Vue d'ensemble", "nav.search": "Rechercher dans la navigation", "nav.no_results": "Aucune page correspondante", "nav.sign_out": "Se déconnecter",
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
