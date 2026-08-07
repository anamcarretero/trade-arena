import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {CompetitionDashboardView} from "@/components/competition-dashboard";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {TradingPanel} from "@/components/trading-panel";
import {competitionDashboard, competitionPortfolio, competitionRanking, leagueCompetitions, ownAccount} from "@/lib/api";
import {copy, isLocale} from "@/lib/i18n";
import {StatusMessage} from "@/components/status-message";

export default async function CompetitionPage({params, searchParams}: {
  params: Promise<{locale: string; leagueId: string; competitionId: string}>;
  searchParams: Promise<{error?: string; status?: string}>;
}) {
  const {locale: rawLocale, leagueId, competitionId} = await params;
  if (!isLocale(rawLocale)) notFound();
  const own = await ownAccount();
  const path = `/${rawLocale}/app/leagues/${encodeURIComponent(leagueId)}/competitions/${encodeURIComponent(competitionId)}`;
  if (!own) redirect(`/auth/login?locale=${rawLocale}&returnTo=${encodeURIComponent(path)}`);
  if (!own.profile) redirect(`/${rawLocale}/app/profile`);
  const [dashboard, competitions] = await Promise.all([
    competitionDashboard(leagueId, competitionId), leagueCompetitions(leagueId)
  ]);
  const competition = competitions?.find(item => item.id === competitionId);
  if (!dashboard || !competition) notFound();
  const text = copy[rawLocale];
  const state = await searchParams;
  const [portfolio, ranking] = competition.status === "draft" ? [null, null] : await Promise.all([
    competitionPortfolio(leagueId, competitionId), competitionRanking(leagueId, competitionId)
  ]);

  return <main id="main-content" className="app-shell arena-shell competition-dashboard-page" tabIndex={-1}>
    <header className="topbar app-topbar">
      <Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link>
      <nav className="app-nav" aria-label={text.appNavigation}><Link href={`/${rawLocale}/app/leagues/${encodeURIComponent(leagueId)}`}>{text.backToLeague}</Link><LocaleSwitcher locale={rawLocale} suffix={`/app/leagues/${leagueId}/competitions/${competitionId}`}/></nav>
    </header>
    <section className="competition-dashboard-hero">
      <div><p className="eyebrow">{text.competitionDashboard} · {competition.status}</p><h1 tabIndex={-1}>{competition.name}</h1><p>{formatDate(competition.starts_at, rawLocale)} — {formatDate(competition.ends_at, rawLocale)} · XNYS</p></div>
      <span className={`data-status ${dashboard.data_status}`}>{text.dashboardStatus[dashboard.data_status]}</span>
    </section>

    {state.error && <StatusMessage kind="error" className="arena-message">{text.leagueActionError}</StatusMessage>}
    {state.status && <StatusMessage kind="status" className="arena-message">{state.status === "reported-trade-created" ? text.reportedTradeCreatedStatus : state.status === "reported-trade-corrected" ? text.reportedTradeCorrectedStatus : state.status === "order-cancelled" ? text.orderCancelledStatus : text.orderSubmittedStatus}</StatusMessage>}

    <CompetitionDashboardView locale={rawLocale} dashboard={dashboard}/>

    {portfolio && ranking && <section className="dashboard-private-panel">
      <p className="eyebrow">{text.privateOwnData}</p>
      <TradingPanel locale={rawLocale} leagueId={leagueId} competitionId={competitionId} portfolio={portfolio} ranking={ranking}/>
    </section>}
  </main>;
}

function formatDate(value: string, locale: "es" | "en") {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {dateStyle: "long"}).format(new Date(value));
}
