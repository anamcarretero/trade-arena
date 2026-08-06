import Link from "next/link";
import {LocaleSwitcher} from "./locale-switcher";
import type {Locale} from "../lib/i18n";
import {pricingCopy} from "../lib/pricing";

export function PublicHeader({locale, page, authenticated = false}: {
  locale: Locale;
  page: "home" | "pricing";
  authenticated?: boolean;
}) {
  const text = pricingCopy[locale];
  const sessionHref = authenticated ? `/${locale}/app` : `/auth/login?locale=${locale}&returnTo=/${locale}/app`;
  return <header className="topbar public-topbar">
    <Link className="wordmark" href={`/${locale}`}>TRADE<span>ARENA</span></Link>
    <nav className="public-nav" aria-label={text.navLabel}>
      <Link href={`/${locale}/pricing`} aria-current={page === "pricing" ? "page" : undefined}>{text.pricingNav}</Link>
      <Link className="nav-session" href={sessionHref}>{authenticated ? text.appNav : text.accessNav}</Link>
    </nav>
    <LocaleSwitcher locale={locale} suffix={page === "pricing" ? "/pricing" : ""} />
  </header>;
}
