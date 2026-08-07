import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {NotificationCenter} from "@/components/notification-center";
import {ownAccount, ownNotifications} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {StatusMessage} from "@/components/status-message";

export default async function NotificationsPage({params, searchParams}: {
  params: Promise<{locale: string}>;
  searchParams: Promise<{error?: string; status?: string}>;
}) {
  const {locale} = await params;
  if (!isLocale(locale)) notFound();
  const [account, notifications] = await Promise.all([
    ownAccount(), ownNotifications()
  ]);
  if (!account || !notifications) {
    redirect(`/auth/login?locale=${locale}&returnTo=/${locale}/app/notifications`);
  }
  const text = copy[locale];
  const state = await searchParams;
  return <main id="main-content" className="app-shell arena-shell" tabIndex={-1}>
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${locale}/app`}>TRADE<span>ARENA</span></Link>
      <nav className="app-nav" aria-label={text.appNavigation}><Link href={`/${locale}/app/account`}>{text.account}</Link><LocaleSwitcher locale={locale} suffix="/app/notifications"/></nav>
    </header>
    <section className="compact-hero">
      <p className="eyebrow">TradeArena / Notifications</p>
      <h1 tabIndex={-1}>{text.notifications}</h1><p>{text.notificationsIntro}</p>
    </section>
    {state.status === "read" && <StatusMessage kind="status" className="arena-message">{text.notificationReadStatus}</StatusMessage>}
    {state.error && <StatusMessage kind="error" className="arena-message">{text.notificationError}</StatusMessage>}
    <NotificationCenter locale={locale} notifications={notifications}/>
  </main>;
}
