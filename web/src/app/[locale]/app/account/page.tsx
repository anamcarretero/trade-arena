import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {AccountPrivacyPanel} from "@/components/account-privacy-panel";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {ownAccount} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {StatusMessage} from "@/components/status-message";

export default async function AccountPage({params, searchParams}: {
  params: Promise<{locale: string}>; searchParams: Promise<{error?: string}>;
}) {
  const {locale} = await params;
  if (!isLocale(locale)) notFound();
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${locale}&returnTo=/${locale}/app/account`);
  const text = copy[locale];
  return <main id="main-content" className="app-shell arena-shell" tabIndex={-1}>
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${locale}/app`}>TRADE<span>ARENA</span></Link>
      <nav className="app-nav" aria-label={text.appNavigation}><Link href={`/${locale}/app/notifications`}>{text.notifications}</Link><LocaleSwitcher locale={locale} suffix="/app/account"/></nav>
    </header>
    <section className="compact-hero">
      <p className="eyebrow">{account.user.email}</p><h1 tabIndex={-1}>{text.account}</h1>
      <p>{text.accountPrivacyIntro}</p>
    </section>
    {(await searchParams).error && <StatusMessage kind="error" className="arena-message">{text.deleteError}</StatusMessage>}
    <AccountPrivacyPanel locale={locale}/>
  </main>;
}
