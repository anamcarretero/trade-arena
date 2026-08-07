import Link from "next/link";
import type {Competition, CompetitionDashboard} from "../lib/api";
import {copy, type Locale} from "../lib/i18n";
import {createCompetition, startCompetition} from "../app/[locale]/app/leagues/actions";
import {RulesSnapshotConfirmation} from "./rules-snapshot-confirmation";

export function CompetitionSection({
  locale, leagueId, competitions, manager, dashboards
}: {
  locale: Locale;
  leagueId: string;
  competitions: Competition[];
  manager: boolean;
  dashboards: Record<string, CompetitionDashboard>;
}) {
  const text = copy[locale];
  return <section className="arena-section competition-section">
    <div className="section-heading">
      <p className="eyebrow">Arena / 03</p>
      <h2>{text.competitions}</h2>
      <p>{text.competitionIntro}</p>
    </div>
    {manager && <form action={createCompetition} className="competition-form">
      <input type="hidden" name="locale" value={locale}/>
      <input type="hidden" name="league_id" value={leagueId}/>
      <label>{text.competitionName}<input name="name" required maxLength={120}/></label>
      <label>{text.startsOn}<input name="starts_on" type="date" required/></label>
      <label>{text.endsOn}<input name="ends_on" type="date" required/></label>
      <button className="primary" type="submit">{text.createDraft}<span aria-hidden="true">＋</span></button>
    </form>}
    {competitions.length === 0 ? <p className="empty-copy">{text.noCompetitions}</p> :
      <div className="competition-grid">{competitions.map(competition =>
        <article className={`competition-card ${competition.status}`} key={competition.id}>
          <div className="competition-card-head">
            <div><span>{competition.status === "draft" ? text.draftCompetition : text.activeCompetition}</span><h3>{competition.name}</h3></div>
            <strong>{formatDate(competition.starts_at, locale)} — {formatDate(competition.ends_at, locale)}</strong>
          </div>
          {competition.rules_snapshot ? <RulesSnapshotConfirmation locale={locale} competition={competition}/> :
            manager && <form action={startCompetition}>
              <input type="hidden" name="locale" value={locale}/>
              <input type="hidden" name="league_id" value={leagueId}/>
              <input type="hidden" name="competition_id" value={competition.id}/>
              <button className="primary" type="submit">{text.startCompetition}<span aria-hidden="true">→</span></button>
            </form>}
          <div className="competition-summary">
            <span>{dashboards[competition.id]?.data_status === "empty" ? text.dashboardNoData : text.dashboardLeader}</span>
            <strong>{leaderName(dashboards[competition.id])}</strong>
          </div>
          <Link className="secondary" href={`/${locale}/app/leagues/${encodeURIComponent(leagueId)}/competitions/${encodeURIComponent(competition.id)}`}>
            {text.openCompetition}
          </Link>
        </article>)}</div>}
  </section>;
}

function leaderName(dashboard?: CompetitionDashboard) {
  const leader = dashboard?.summary.leader as null | {display_name?: string} | undefined;
  return leader?.display_name ?? "—";
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {
    dateStyle: "medium", timeZone: "UTC"
  }).format(new Date(value));
}
