import type {Locale} from "../lib/i18n";

export function LocaleSwitcher({locale, suffix = ""}: {locale: Locale; suffix?: string}) {
  const other = locale === "es" ? "en" : "es";
  const destination = `/${other}${suffix}`;
  return <nav className="locale" aria-label={locale === "es" ? "Idioma" : "Language"}>
    <span aria-current="page">{locale.toUpperCase()}</span>
    <span aria-hidden="true">/</span>
    <a href={`/language?locale=${other}&returnTo=${encodeURIComponent(destination)}`} hrefLang={other}>{other.toUpperCase()}</a>
  </nav>;
}
