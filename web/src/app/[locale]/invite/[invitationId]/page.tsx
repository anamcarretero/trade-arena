import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {ownAccount, ownInvitations} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {invitationPath} from "@/lib/invitations";
import {acceptInvitation} from "../../app/leagues/actions";

export default async function InvitationPage({params, searchParams}: {
  params: Promise<{locale: string; invitationId: string}>;
  searchParams: Promise<{error?: string}>;
}) {
  const {locale: rawLocale, invitationId} = await params;
  if (!isLocale(rawLocale)) notFound();
  const path = invitationPath(rawLocale, invitationId);
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${rawLocale}&returnTo=${encodeURIComponent(path)}`);
  if (!account.profile) redirect(`/${rawLocale}/app/profile`);
  const invitations = await ownInvitations();
  if (!invitations) redirect(`/auth/login?locale=${rawLocale}&returnTo=${encodeURIComponent(path)}`);
  const invitation = invitations.find(item => item.id === invitationId);
  const text = copy[rawLocale];
  const error = Boolean((await searchParams).error);

  return <main className="app-shell invitation-shell">
    <header className="topbar"><Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link><LocaleSwitcher locale={rawLocale} suffix={`/invite/${encodeURIComponent(invitationId)}`}/></header>
    <section className="invitation-accept-card">
      <div className="invite-signal" aria-hidden="true"><span>01</span><i/><span>02</span></div>
      <p className="eyebrow">TradeArena / Invite</p>
      <h1>{text.invitationTitle}</h1>
      {!invitation || error ? <><p className="error" role="alert">{text.invitationAccessError}</p><Link className="secondary" href={`/${rawLocale}/app`}>{text.backToLeagues}</Link></> : <>
        <p>{text.invitationIntro}</p><h2>{invitation.league_name}</h2><p className="meta">{text.expires}: {formatDate(invitation.expires_at, rawLocale)}</p>
        <form action={acceptInvitation}><input type="hidden" name="locale" value={rawLocale}/><input type="hidden" name="invitation_id" value={invitation.id}/><button className="primary" type="submit">{text.acceptInvitation}<span aria-hidden="true">→</span></button></form>
      </>}
    </section>
  </main>;
}

function formatDate(value: string, locale: "es" | "en") {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {dateStyle: "long"}).format(new Date(value));
}
