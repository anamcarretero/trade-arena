import Link from "next/link";
import {redirect, notFound} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {copy, isLocale} from "@/lib/i18n";
import {ownAccount} from "@/lib/api";

export default async function Dashboard({params}: {params: Promise<{locale: string}>}) {
  const {locale: rawLocale} = await params;
  if (!isLocale(rawLocale)) notFound();
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${rawLocale}&returnTo=/${rawLocale}/app`);
  if (!account.profile) redirect(`/${rawLocale}/app/profile`);
  const text = copy[rawLocale];
  return <main className="app-shell">
    <header className="topbar"><Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link><LocaleSwitcher locale={rawLocale} suffix="/app" /></header>
    <section className="dashboard-card">
      <div className="dashboard-copy">
        <p className="eyebrow">{account.user.email}</p>
        <h1>{text.welcome},<br/><em>{account.profile.display_name}</em>.</h1>
        <p>{text.accountReady}</p>
        <div className="actions"><Link className="secondary" href={`/${rawLocale}/app/profile`}>{text.editProfile}</Link><form action="/auth/logout" method="post"><button className="text-button" type="submit">{text.logout}</button></form></div>
      </div>
      <div className="account-panel" aria-hidden="true">
        <div className="account-panel-head"><span>TA / 01</span><i /></div>
        <div className="account-orbit"><span>3K</span><small>USD</small></div>
        <div className="account-bars"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div>
      </div>
    </section>
  </main>;
}
