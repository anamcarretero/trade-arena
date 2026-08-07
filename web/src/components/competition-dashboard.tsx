import type {CompetitionDashboard} from "@/lib/api";
import {copy, type Locale} from "@/lib/i18n";

type Player = CompetitionDashboard["players"][number];
type Winner = {date: string; player_ids: string[]; return: string; provisional: boolean};
type Daily = {date: string; provisional: boolean; players: Array<{player_id: string; display_name: string; daily_return: string | null; cumulative_return: string | null; complete: boolean}>};
type Month = {month: string; winner: null | {player_id: string; return: string}; series: Array<{player_id: string; display_name: string; points: Array<{date: string; return: string}>}>};

export function CompetitionDashboardView({locale, dashboard}: {
  locale: Locale; dashboard: CompetitionDashboard;
}) {
  const text = copy[locale];
  const summary = dashboard.summary as {leader: null | {player_id: string; display_name: string; cumulative_return: string}; best_day: Winner | null; gap: string};
  const monthly = dashboard.monthly as {current: Month | null; previous: Month | null};
  const winners = dashboard.daily_winners as Winner[];
  const days = dashboard.daily_results as Daily[];
  const playerNames = new Map(dashboard.players.map(player => [player.id, player.display_name]));

  if (dashboard.data_status === "empty") return <section className="dashboard-empty">
    <p>{text.noDashboardHistory}</p>
  </section>;

  return <div className="dashboard-stack">
    {dashboard.data_status === "incomplete" && <p className="dashboard-warning" role="status">{text.incompleteData}</p>}
    {dashboard.data_status === "provisional" && <p className="dashboard-warning" role="status">{text.provisionalData}</p>}

    <section className="dashboard-chart-card">
      <div className="section-heading"><p className="eyebrow">Performance / XNYS</p><h2>{text.cumulativeReturn}</h2></div>
      <ReturnChart locale={locale} players={dashboard.players}/>
      {summary.leader && <p className="chart-leader"><strong>{summary.leader.display_name}</strong> {percent(summary.leader.cumulative_return, locale)}</p>}
    </section>

    <section className="dashboard-metrics">
      <Metric label={text.bestOfDay} value={summary.best_day ? summary.best_day.player_ids.map(id => playerNames.get(id)).join(", ") : "—"}/>
      <Metric label={text.leaderGap} value={percent(summary.gap, locale)}/>
    </section>

    <section className="dashboard-pair">
      <MonthCard title={text.currentMonth} month={monthly.current} locale={locale} names={playerNames}/>
      <MonthCard title={text.previousMonth} month={monthly.previous} locale={locale} names={playerNames}/>
    </section>

    <section className="dashboard-pair">
      <DashboardCard title={text.badges}>
        {dashboard.badges.length ? <div className="badge-cloud">{dashboard.badges.map((badge, index) => {
          const item = badge as {player_id?: string; key?: string};
          return <span key={`${item.player_id}-${item.key}-${index}`}>{playerNames.get(item.player_id ?? "")} · {badgeLabel(item.key ?? "", locale)}</span>;
        })}</div> : <p className="empty-copy">—</p>}
      </DashboardCard>
      <DashboardCard title={text.recentTrades}>
        {dashboard.recent_trades.length ? <div className="dashboard-list">{dashboard.recent_trades.map((trade, index) => <div key={`${trade.executed_at}-${index}`}>
          <strong>{trade.display_name} · {trade.symbol}</strong><span>{trade.type === "correction" ? text.compensatesExecution : trade.type === "buy" ? text.buy : text.sell} · {formatDate(trade.executed_at, locale)}</span>
        </div>)}</div> : <p className="empty-copy">{text.noExecutions}</p>}
      </DashboardCard>
    </section>

    <DashboardCard title={text.leagueInsights}>
      <ul className="insight-list">{dashboard.insights.map((insight, index) => <li key={index}>{insightLabel(insight as Record<string, unknown>, playerNames, locale)}</li>)}</ul>
    </DashboardCard>

    <DashboardCard title={text.ranking}>
      <div className="player-detail-grid">{dashboard.players.map(player => <PlayerCard player={player} locale={locale} key={player.id}/>)}</div>
    </DashboardCard>

    <section className="dashboard-pair">
      <DashboardCard title={text.dailyChampions}>
        <div className="dashboard-list">{winners.map(winner => <div key={winner.date}><strong>{formatDate(winner.date, locale)}</strong><span>{winner.player_ids.map(id => playerNames.get(id)).join(", ")} · {percent(winner.return, locale)}</span></div>)}</div>
      </DashboardCard>
      <DashboardCard title={text.leaguePortfolio}><Allocation rows={dashboard.league_allocation} locale={locale}/></DashboardCard>
    </section>

    <DashboardCard title={text.playerPortfolios}>
      <div className="allocation-grid">{dashboard.players.map(player => <div key={player.id}><h4>{player.display_name}</h4><Allocation rows={player.allocation} locale={locale}/></div>)}</div>
    </DashboardCard>

    <DashboardCard title={text.dailyResults}>
      <div className="day-detail-list">{days.map(day => <details key={day.date}><summary>{formatDate(day.date, locale)}{day.provisional ? " · provisional" : ""}</summary>
        <div>{day.players.map(player => <p key={player.player_id}><strong>{player.display_name}</strong><span>{player.complete && player.daily_return !== null ? percent(player.daily_return, locale) : "—"} / {player.cumulative_return !== null ? percent(player.cumulative_return, locale) : "—"}</span></p>)}</div>
      </details>)}</div>
    </DashboardCard>
  </div>;
}

function ReturnChart({players, locale}: {players: Player[]; locale: Locale}) {
  const points = players.flatMap(player => player.series.filter(point => point.cumulative_return !== null));
  if (!points.length) return <div className="chart-empty">—</div>;
  const dates = [...new Set(points.map(point => point.date))].sort();
  const values = points.map(point => Number(point.cumulative_return));
  const min = Math.min(0, ...values), max = Math.max(0, ...values), span = max - min || .01;
  const x = (date: string) => 30 + (dates.indexOf(date) / Math.max(1, dates.length - 1)) * 640;
  const y = (value: number) => 20 + ((max - value) / span) * 190;
  return <div className="responsive-chart"><svg viewBox="0 0 700 240" role="img" aria-label={copy[locale].cumulativeReturn}>
    <line x1="30" y1={y(0)} x2="670" y2={y(0)} className="zero-line"/>
    {players.map(player => {
      const valid = player.series.filter(point => point.cumulative_return !== null);
      const path = valid.map((point, index) => `${index ? "L" : "M"}${x(point.date)},${y(Number(point.cumulative_return))}`).join(" ");
      return <path key={player.id} d={path} className={`player-line color-${colorIndex(player.id)}`}/>;
    })}
  </svg><div className="chart-legend">{players.map(player => <span key={player.id} className={`color-${colorIndex(player.id)}`}>{player.display_name}</span>)}</div></div>;
}

function PlayerCard({player, locale}: {player: Player; locale: Locale}) {
  const stats = player.statistics as {best_daily_return?: string; worst_daily_return?: string; current_streak?: number; sessions?: number};
  return <details className="player-detail"><summary><span>{player.rank ?? "—"}</span><strong>{player.display_name}</strong><em>{player.cumulative_return ? percent(player.cumulative_return, locale) : "—"}</em></summary>
    <div className="player-stat-row"><span>Max {percent(stats.best_daily_return ?? "0", locale)}</span><span>Min {percent(stats.worst_daily_return ?? "0", locale)}</span><span>{stats.sessions ?? 0} XNYS</span><span>Streak {stats.current_streak ?? 0}</span></div>
    <Allocation rows={player.allocation} locale={locale}/>
  </details>;
}

function MonthCard({title, month, locale, names}: {title: string; month: Month | null; locale: Locale; names: Map<string, string>}) {
  return <DashboardCard title={title}>{month?.winner ? <p className="month-winner"><strong>{names.get(month.winner.player_id)}</strong><span>{percent(month.winner.return, locale)}</span></p> : <p className="empty-copy">—</p>}
    {month && <div className="month-series">{month.series.map(item => <div key={item.player_id}><span>{item.display_name}</span><strong>{item.points.length ? percent(item.points.at(-1)?.return ?? "0", locale) : "—"}</strong></div>)}</div>}
  </DashboardCard>;
}

function DashboardCard({title, children}: {title: string; children: React.ReactNode}) {
  return <section className="competition-data-card"><h3>{title}</h3>{children}</section>;
}

function Metric({label, value}: {label: string; value: string}) { return <article><span>{label}</span><strong>{value}</strong></article>; }

function Allocation({rows, locale}: {rows: Array<{symbol: string; weight: string}>; locale: Locale}) {
  return <div className="allocation-list">{rows.map(row => <div key={row.symbol}><span>{row.symbol}</span><i><b style={{width: `${Math.max(0, Math.min(100, Number(row.weight) * 100))}%`}}/></i><strong>{percent(row.weight, locale)}</strong></div>)}</div>;
}

function colorIndex(id: string) { return [...id].reduce((sum, char) => sum + char.charCodeAt(0), 0) % 6; }
function percent(value: string, locale: Locale) { return new Intl.NumberFormat(locale === "es" ? "es-ES" : "en-GB", {style: "percent", minimumFractionDigits: 2, maximumFractionDigits: 2}).format(Number(value)); }
function formatDate(value: string, locale: Locale) { return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {dateStyle: "medium"}).format(new Date(value)); }
function badgeLabel(key: string, locale: Locale) { const labels: Record<string, [string, string]> = {five_green_sessions: ["5 jornadas verdes", "5 green sessions"], return_5: ["+5 % acumulado", "+5% cumulative"], return_10: ["+10 % acumulado", "+10% cumulative"], return_25: ["+25 % acumulado", "+25% cumulative"]}; return labels[key]?.[locale === "es" ? 0 : 1] ?? key; }
function insightLabel(item: Record<string, unknown>, names: Map<string, string>, locale: Locale) {
  const name = names.get(String(item.player_id ?? "")) ?? "";
  const value = item.value ? percent(String(item.value), locale) : "";
  const es: Record<string, string> = {leader: `${name} lidera con ${value}.`, close_competition: `La competición está ajustada: ${value} de distancia.`, clear_leader: `El liderato tiene ${value} de ventaja.`, best_day: `La última mejor jornada fue ${value}.`, green_streak: `${name} encadena ${item.sessions} jornadas verdes.`, red_streak: `${name} encadena ${item.sessions} jornadas rojas.`};
  const en: Record<string, string> = {leader: `${name} leads on ${value}.`, close_competition: `The competition is close: a ${value} gap.`, clear_leader: `The leader has a ${value} advantage.`, best_day: `The latest best daily result was ${value}.`, green_streak: `${name} has ${item.sessions} green sessions in a row.`, red_streak: `${name} has ${item.sessions} red sessions in a row.`};
  return (locale === "es" ? es : en)[String(item.kind)] ?? String(item.kind);
}
