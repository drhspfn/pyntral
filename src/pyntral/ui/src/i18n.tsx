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
    "login.title": "Вход", "login.subtitle": "Войдите с учётной записью администратора.",
    "login.username": "Имя пользователя", "login.password": "Пароль", "login.submit": "Продолжить",
    "login.show_password": "Показать пароль", "login.hide_password": "Скрыть пароль", "login.toggle_theme": "Переключить тему",
    "nav.overview": "Обзор", "nav.sign_out": "Выйти",
    "resources.description": "Просмотр и управление записями.",
    "actions.new": "Новая запись", "actions.create": "Создать запись",
    "actions.save": "Сохранить изменения",
    "table.columns": "Столбцы", "table.filters": "Фильтры",
    "table.clear_filters": "Очистить фильтры", "table.sort_by": "Сортировка",
  },
  es: {
    "login.title": "Iniciar sesión", "login.subtitle": "Usa tu cuenta de administrador para continuar.",
    "login.username": "Usuario", "login.password": "Contraseña", "login.submit": "Continuar",
    "login.show_password": "Mostrar contraseña", "login.hide_password": "Ocultar contraseña", "login.toggle_theme": "Cambiar tema",
    "nav.overview": "Resumen", "nav.sign_out": "Cerrar sesión",
    "resources.description": "Consulta y administra tus registros.",
    "actions.new": "Nuevo registro", "actions.create": "Crear registro",
    "actions.save": "Guardar cambios",
    "table.columns": "Columnas", "table.filters": "Filtros",
    "table.clear_filters": "Borrar filtros", "table.sort_by": "Ordenar por",
  },
  fr: {
    "login.title": "Connexion", "login.subtitle": "Utilisez votre compte administrateur pour continuer.",
    "login.username": "Identifiant", "login.password": "Mot de passe", "login.submit": "Continuer",
    "login.show_password": "Afficher le mot de passe", "login.hide_password": "Masquer le mot de passe", "login.toggle_theme": "Changer de thème",
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
