import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {NotificationCenter} from "@/components/notification-center";
import {ownAccount, ownNotifications} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";

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
  return <main className="app-shell arena-shell">
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${locale}/app`}>TRADE<span>ARENA</span></Link>
      <div className="app-nav"><Link href={`/${locale}/app/account`}>{text.account}</Link><LocaleSwitcher locale={locale} suffix="/app/notifications"/></div>
    </header>
    <section className="compact-hero">
      <p className="eyebrow">TradeArena / Notifications</p>
      <h1>{text.notifications}</h1><p>{text.notificationsIntro}</p>
    </section>
    {state.status === "read" && <p className="success arena-message">{text.notificationReadStatus}</p>}
    {state.error && <p className="error arena-message" role="alert">{text.notificationError}</p>}
    <NotificationCenter locale={locale} notifications={notifications}/>
  </main>;
}
