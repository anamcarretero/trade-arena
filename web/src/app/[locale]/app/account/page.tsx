import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {AccountPrivacyPanel} from "@/components/account-privacy-panel";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {ownAccount} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";

export default async function AccountPage({params, searchParams}: {
  params: Promise<{locale: string}>; searchParams: Promise<{error?: string}>;
}) {
  const {locale} = await params;
  if (!isLocale(locale)) notFound();
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${locale}&returnTo=/${locale}/app/account`);
  const text = copy[locale];
  return <main className="app-shell arena-shell">
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${locale}/app`}>TRADE<span>ARENA</span></Link>
      <div className="app-nav"><Link href={`/${locale}/app/notifications`}>{text.notifications}</Link><LocaleSwitcher locale={locale} suffix="/app/account"/></div>
    </header>
    <section className="compact-hero">
      <p className="eyebrow">{account.user.email}</p><h1>{text.account}</h1>
      <p>{text.accountPrivacyIntro}</p>
    </section>
    {(await searchParams).error && <p className="error arena-message" role="alert">{text.deleteError}</p>}
    <AccountPrivacyPanel locale={locale}/>
  </main>;
}
