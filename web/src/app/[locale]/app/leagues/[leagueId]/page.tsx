import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {CopyInvitationLink} from "@/components/copy-invitation-link";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {CompetitionSection} from "@/components/competition-section";
import {competitionDashboard, leagueCompetitions, leagueDetail, ownAccount} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {invitationPath} from "@/lib/invitations";
import {canManageLeague, occupiedSeats} from "@/lib/league-state";
import {inviteMember, removeMember, revokeInvitation} from "../actions";
import {StatusMessage} from "@/components/status-message";

export default async function LeaguePage({params, searchParams}: {
  params: Promise<{locale: string; leagueId: string}>;
  searchParams: Promise<{error?: string; status?: string}>;
}) {
  const {locale: rawLocale, leagueId} = await params;
  if (!isLocale(rawLocale)) notFound();
  const account = await ownAccount();
  const returnTo = `/${rawLocale}/app/leagues/${encodeURIComponent(leagueId)}`;
  if (!account) redirect(`/auth/login?locale=${rawLocale}&returnTo=${encodeURIComponent(returnTo)}`);
  if (!account.profile) redirect(`/${rawLocale}/app/profile`);
  const text = copy[rawLocale];
  const league = await leagueDetail(leagueId);
  if (!league) return <AccessDenied locale={rawLocale} message={text.leagueAccessError}/>;
  const competitions = await leagueCompetitions(leagueId);
  if (!competitions) return <AccessDenied locale={rawLocale} message={text.leagueAccessError}/>;
  const state = await searchParams;
  const manager = canManageLeague(league);
  const dashboards = Object.fromEntries((await Promise.all(competitions
    .map(async competition => {
      const dashboard = await competitionDashboard(leagueId, competition.id);
      return dashboard ? [competition.id, dashboard] as const : null;
    }))).filter(entry => entry !== null));
  const occupied = occupiedSeats(league);
  const emptySeats = Math.max(0, league.max_members - occupied);

  return <main id="main-content" className="app-shell arena-shell" tabIndex={-1}>
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link>
      <nav className="app-nav" aria-label={text.appNavigation}><Link href={`/${rawLocale}/app`}>{text.backToLeagues}</Link><LocaleSwitcher locale={rawLocale} suffix={`/app/leagues/${league.id}`} /></nav>
    </header>

    <section className="league-hero">
      <div><p className="eyebrow">{text.privateLeague} · {text.freePlan}</p><h1 tabIndex={-1}>{league.name}</h1><p>{occupied}/{league.max_members} {text.seats} · {roleLabel(league.actor_role, text)}</p></div>
      <div className="league-orbit" aria-hidden="true"><strong>{occupied}</strong><span>/ {league.max_members}</span></div>
    </section>

    {state.error && <StatusMessage kind="error" className="arena-message">
      {state.error === "access" ? text.leagueAccessError : state.error === "league-full" ? text.leagueFullError : text.leagueActionError}
    </StatusMessage>}
    {state.status && <StatusMessage kind="status" className="arena-message">
      {state.status === "invited" ? text.invitedStatus : state.status === "revoked" ? text.revokedStatus : state.status === "removed" ? text.removedStatus : state.status === "competition-created" ? text.competitionCreatedStatus : state.status === "competition-started" ? text.competitionStartedStatus : state.status === "order-cancelled" ? text.orderCancelledStatus : state.status === "reported-trade-created" ? text.reportedTradeCreatedStatus : state.status === "reported-trade-corrected" ? text.reportedTradeCorrectedStatus : text.orderSubmittedStatus}
    </StatusMessage>}

    <section className="arena-section">
      <div className="section-heading"><p className="eyebrow">Arena / 02</p><h2>{text.members}</h2></div>
      <div className="seat-grid">
        {league.members.map((member, index) => <article className="seat-card occupied" key={member.user_id}>
          <span className={`player-index player-${index + 1}`}>0{index + 1}</span>
          <div className="player-avatar">{initials(member.display_name || text.memberFallback)}</div>
          <div className="seat-copy"><span>{roleLabel(member.role, text)}</span><h3>{member.display_name || text.memberFallback}</h3><p>{text.joined}: {formatDate(member.joined_at, rawLocale)}</p></div>
          {manager && member.role !== "owner" && <form action={removeMember} className="seat-action"><input type="hidden" name="locale" value={rawLocale}/><input type="hidden" name="league_id" value={league.id}/><input type="hidden" name="user_id" value={member.user_id}/><button className="danger-button" type="submit">{text.remove}</button></form>}
        </article>)}
        {league.invitations.map((invitation, index) => <article className="seat-card pending" key={invitation.id}>
          <span className="player-index pending-index">0{league.members.length + index + 1}</span>
          <div className="player-avatar pending-avatar">@</div>
          <div className="seat-copy"><span>{text.pendingSlot}</span><h3>{invitation.email}</h3><p>{text.expires}: {formatDate(invitation.expires_at, rawLocale)}</p></div>
        </article>)}
        {Array.from({length: emptySeats}, (_, index) => <article className="seat-card empty" key={`empty-${index}`}>
          <span className="player-index">0{occupied + index + 1}</span><div className="empty-mark">+</div><div className="seat-copy"><span>{text.emptySlot}</span><h3>{text.emptySlotIntro}</h3></div>
        </article>)}
      </div>
    </section>

    <CompetitionSection locale={rawLocale} leagueId={league.id} competitions={competitions} manager={manager} dashboards={dashboards}/>

    {manager && <section className="league-admin-grid">
      <div className="admin-panel">
        <p className="eyebrow">Invite / Link</p><h2>{text.inviteByLink}</h2><p>{text.inviteIntro}</p>
        {occupied < league.max_members && <form action={inviteMember} className="inline-form stacked"><input type="hidden" name="locale" value={rawLocale}/><input type="hidden" name="league_id" value={league.id}/><label>{text.inviteEmail}<input name="email" type="email" required maxLength={254} autoComplete="email"/></label><button className="primary" type="submit">{text.generateLink}<span aria-hidden="true">↗</span></button></form>}
      </div>
      <div className="admin-panel invitation-list-panel">
        <p className="eyebrow">Link / 07D</p><h2>{text.invitations}</h2>
        {league.invitations.length === 0 ? <p className="empty-copy">{text.emptySlot}</p> : league.invitations.map(invitation => <div className="pending-link" key={invitation.id}>
          <div><strong>{invitation.email}</strong><span>{text.expires}: {formatDate(invitation.expires_at, rawLocale)}</span></div>
          <div className="pending-link-actions"><CopyInvitationLink path={invitationPath(rawLocale, invitation.id)} label={text.copyLink} copiedLabel={text.copiedLink}/><form action={revokeInvitation}><input type="hidden" name="locale" value={rawLocale}/><input type="hidden" name="league_id" value={league.id}/><input type="hidden" name="invitation_id" value={invitation.id}/><button className="danger-button" type="submit">{text.revoke}</button></form></div>
        </div>)}
      </div>
    </section>}
  </main>;
}

function AccessDenied({locale, message}: {locale: "es" | "en"; message: string}) {
  const text = copy[locale];
  return <main id="main-content" className="app-shell arena-shell" tabIndex={-1}><header className="topbar"><Link className="wordmark" href={`/${locale}/app`}>TRADE<span>ARENA</span></Link><LocaleSwitcher locale={locale} suffix="/app"/></header><section className="access-state"><p className="eyebrow">404 / Private</p><h1 tabIndex={-1}>{text.privateLeague}</h1><p>{message}</p><Link className="secondary" href={`/${locale}/app`}>{text.backToLeagues}</Link></section></main>;
}

function formatDate(value: string, locale: "es" | "en") {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {dateStyle: "medium"}).format(new Date(value));
}

function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase();
}

function roleLabel(role: "owner" | "admin" | "member", text: typeof copy.es | typeof copy.en) {
  return role === "owner" ? text.ownerRole : role === "admin" ? text.adminRole : text.memberRole;
}
