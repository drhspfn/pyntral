import { useId, useState, type CSSProperties } from "react";
import { useMutation } from "@tanstack/react-query";
import { ArrowRight, CircleAlert, Eye, EyeOff, Moon, Sun } from "lucide-react";
import { api, setCsrf } from "./api";
import { Brand } from "./brand";
import { Icon } from "./icon";
import { Button, Card, FormField, TextInput } from "./ui";
import { useI18n } from "./i18n";
import type { AuthState, LoginScreenProps, PublicLoginConfig } from "./types";

export const defaultLoginConfig: PublicLoginConfig = {
  login: {
    layout: "centered", sidePosition: "left", brandPosition: "form", formAlign: "center", card: true, maxWidth: 420,
    brand: { title: "Pyntral", icon: "command", showIcon: true, showTitle: true, showSubtitle: true,
      align: "center", direction: "vertical", divider: false, iconSize: 24, iconBackground: true, linkToDashboard: false },
    title: "Sign in", subtitle: "Use your administrator account to continue.", formIcon: null,
    usernameLabel: "Username", passwordLabel: "Password", submitLabel: "Continue",
    showThemeToggle: true, showPasswordToggle: true,
  },
  theme: { default: "system", animations: true, tokens: {} },
};

/** Default sign-in UI; can also be wrapped by the existing auth.login extension. */
export function LoginScreen({ config, themeMode, toggleTheme, onAuthenticated }: LoginScreenProps) {
  const settings = config.login;
  const { t } = useI18n();
  const id = useId();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const login = useMutation({
    mutationFn: () => api<AuthState>("/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }),
    onSuccess: state => { setCsrf(state.csrf); onAuthenticated(state); },
  });
  const label = (key: string, configured: string, fallback: string) => configured === fallback ? t(key, fallback) : configured;
  const brand = settings.brand && <Brand config={settings.brand} themeMode={themeMode}/>;
  const form = <form className="ra-login-form" aria-labelledby={`${id}-title`}
    onSubmit={event => { event.preventDefault(); if (!login.isPending) login.mutate(); }}>
    {(settings.brandPosition === "form" || settings.brandPosition === "side") &&
      <div className={`ra-login-brand ${settings.brandPosition === "side" ? "mobile-only" : ""}`}>{brand}</div>}
    <div className={`ra-login-heading align-${settings.formAlign}`}>
      {settings.formIcon != null && <div className="ra-login-glyph"><Icon icon={settings.formIcon} size={24}/></div>}
      {settings.eyebrow && <div className="eyebrow">{settings.eyebrow}</div>}
      <h1 id={`${id}-title`}>{label("login.title", settings.title, "Sign in")}</h1>
      {settings.subtitle && <p>{label("login.subtitle", settings.subtitle, "Use your administrator account to continue.")}</p>}
    </div>
    {login.error && <div className="alert" role="alert"><CircleAlert size={17}/><span>
      {login.error instanceof Error ? login.error.message : t("login.error", "Sign in failed")}
    </span></div>}
    <FormField label={label("login.username", settings.usernameLabel, "Username")} htmlFor={`${id}-username`}>
      <TextInput id={`${id}-username`} name="username" autoComplete="username" autoFocus required
        maxLength={320} value={username} onChange={event => setUsername(event.target.value)}/>
    </FormField>
    <FormField label={label("login.password", settings.passwordLabel, "Password")} htmlFor={`${id}-password`}>
      <div className="ra-login-password">
        <TextInput id={`${id}-password`} name="password" type={visible && settings.showPasswordToggle ? "text" : "password"}
          autoComplete="current-password" required maxLength={4096} value={password} onChange={event => setPassword(event.target.value)}/>
        {settings.showPasswordToggle && <Button type="button" variant="ghost" className="ra-login-password-toggle"
          aria-label={visible ? t("login.hide_password", "Hide password") : t("login.show_password", "Show password")}
          aria-pressed={visible} onClick={() => setVisible(!visible)} startIcon={visible ? <EyeOff size={17}/> : <Eye size={17}/>}/>}
      </div>
    </FormField>
    <Button type="submit" variant="primary" className="ra-login-submit" loading={login.isPending}
      endIcon={<ArrowRight size={17}/>}>{label("login.submit", settings.submitLabel, "Continue")}</Button>
    {settings.footer && <p className="ra-login-footer">{settings.footer}</p>}
  </form>;
  return <main className={`ra-login-page layout-${settings.layout} side-${settings.sidePosition}`}
    style={{ "--ra-login-width": `${settings.maxWidth}px` } as CSSProperties}>
    {settings.showThemeToggle && <Button type="button" className="ra-login-theme" variant="secondary"
      aria-label={t("login.toggle_theme", "Toggle theme")} title={t("login.toggle_theme", "Toggle theme")}
      onClick={toggleTheme} startIcon={themeMode === "light" ? <Moon size={18}/> : <Sun size={18}/>}/>}
    {settings.layout === "split" && <aside className="ra-login-side">
      <div>{settings.brandPosition === "side" && brand}</div>
      <div className="ra-login-side-content">
        {settings.sideTitle && <h2>{settings.sideTitle}</h2>}
        {settings.sideDescription && <p>{settings.sideDescription}</p>}
      </div>
      <div className="ra-login-side-footer">{settings.sideFooter}</div>
    </aside>}
    <div className="ra-login-panel">
      {settings.card ? <Card className="ra-login-card">{form}</Card> : <div className="ra-login-card is-flat">{form}</div>}
    </div>
  </main>;
}
