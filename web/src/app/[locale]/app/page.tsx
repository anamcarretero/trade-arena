import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {ownAccount, ownInvitations, ownLeagues} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {invitationPath} from "@/lib/invitations";
import {canCreateFreeLeague, occupiedSeats} from "@/lib/league-state";
import {acceptInvitation, createLeague} from "./leagues/actions";

export default async function Dashboard({params, searchParams}: {
  params: Promise<{locale: string}>;
  searchParams: Promise<{error?: string}>;
}) {
  const {locale: rawLocale} = await params;
  if (!isLocale(rawLocale)) notFound();
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${rawLocale}&returnTo=/${rawLocale}/app`);
  if (!account.profile) redirect(`/${rawLocale}/app/profile`);
  const [leagues, invitations] = await Promise.all([ownLeagues(), ownInvitations()]);
  if (!leagues || !invitations) redirect(`/auth/login?locale=${rawLocale}&returnTo=/${rawLocale}/app`);
  const text = copy[rawLocale];
  const error = (await searchParams).error;
  const canCreate = canCreateFreeLeague(leagues);

  return <main className="app-shell arena-shell">
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link>
      <div className="app-nav"><Link href={`/${rawLocale}/app/profile`}>{text.editProfile}</Link><LocaleSwitcher locale={rawLocale} suffix="/app" /></div>
    </header>

    <section className="arena-hero">
      <div><p className="eyebrow">{account.user.email}</p><h1>{text.arenaHome}</h1><p>{text.arenaIntro}</p></div>
      <form action="/auth/logout" method="post"><button className="text-button" type="submit">{text.logout}</button></form>
    </section>

    {error && <p className="error arena-message" role="alert">
      {error === "league-limit" ? text.leagueLimitError : text.leagueActionError}
    </p>}

    {invitations.length > 0 && <section className="arena-section">
      <div className="section-heading"><p className="eyebrow">TradeArena / Invite</p><h2>{text.pendingInvitations}</h2></div>
      <div className="invitation-grid">
        {invitations.map(invitation => <article className="invitation-card" key={invitation.id}>
          <span className="status-pill">{text.pendingSlot}</span>
          <p>{text.invitationFor}</p><h3>{invitation.league_name}</h3>
          <p className="meta">{text.expires}: {formatDate(invitation.expires_at, rawLocale)}</p>
          <div className="card-actions">
            <Link className="secondary compact" href={invitationPath(rawLocale, invitation.id)}>{text.reviewInvitation}</Link>
            <form action={acceptInvitation}><input type="hidden" name="locale" value={rawLocale}/><input type="hidden" name="invitation_id" value={invitation.id}/><button className="primary compact" type="submit">{text.acceptInvitation}</button></form>
          </div>
        </article>)}
      </div>
    </section>}

    <section className="arena-section">
      <div className="section-heading"><p className="eyebrow">TradeArena / Leagues</p><h2>{text.yourLeagues}</h2></div>
      {leagues.length === 0 ? <p className="empty-copy">{text.noLeagues}</p> : <div className="league-grid">
        {leagues.map(league => <article className="league-card" key={league.id}>
          <div className="league-card-top"><span className="status-pill live"><i/>{text.privateLeague}</span><span>{text.freePlan}</span></div>
          <h3>{league.name}</h3>
          <div className="seat-meter" aria-label={`${league.members.length + league.invitations.length}/${league.max_members} ${text.seats}`}>
            {Array.from({length: league.max_members}, (_, index) => <i className={index < occupiedSeats(league) ? "filled" : ""} key={index}/>) }
          </div>
          <p>{occupiedSeats(league)}/{league.max_members} {text.seats} · {roleLabel(league.actor_role, text)}</p>
          <Link className="card-link" href={`/${rawLocale}/app/leagues/${encodeURIComponent(league.id)}`}>{text.openLeague}<span aria-hidden="true">↗</span></Link>
        </article>)}
      </div>}
    </section>

    {canCreate && <section className="create-league-panel">
      <div><p className="eyebrow">Free / 01</p><h2>{text.createLeague}</h2><p>{text.createLeagueIntro}</p></div>
      <form action={createLeague} className="inline-form"><input type="hidden" name="locale" value={rawLocale}/><label>{text.leagueName}<input name="name" required minLength={1} maxLength={80}/></label><button className="primary" type="submit">{text.create}<span aria-hidden="true">→</span></button></form>
    </section>}
  </main>;
}

function formatDate(value: string, locale: "es" | "en") {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {dateStyle: "medium"}).format(new Date(value));
}

function roleLabel(role: "owner" | "admin" | "member", text: typeof copy.es | typeof copy.en) {
  return role === "owner" ? text.ownerRole : role === "admin" ? text.adminRole : text.memberRole;
}
