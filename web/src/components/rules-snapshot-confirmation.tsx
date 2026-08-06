import type {Competition} from "../lib/api";
import {copy, type Locale} from "../lib/i18n";

export function RulesSnapshotConfirmation({
  locale, competition
}: {locale: Locale; competition: Competition}) {
  const text = copy[locale];
  const snapshot = competition.rules_snapshot;
  if (!snapshot) return null;
  return <div className="snapshot-confirmation" role="status">
    <span className="snapshot-lock" aria-hidden="true">✓</span>
    <div>
      <strong>{text.snapshotLocked}</strong>
      <p>{text.snapshotExplanation}</p>
      <dl>
        <div><dt>{text.initialCapital}</dt><dd>{snapshot.rules.initial_capital} {snapshot.rules.currency}</dd></div>
        <div><dt>{text.marketCalendar}</dt><dd>{snapshot.calendar.market} · {snapshot.calendar.timezone}</dd></div>
        <div><dt>{text.snapshotPeriod}</dt><dd>{formatDate(snapshot.calendar.starts_at, locale)} — {formatDate(snapshot.calendar.ends_at, locale)}</dd></div>
      </dl>
    </div>
  </div>;
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {
    dateStyle: "medium", timeZone: "UTC"
  }).format(new Date(value));
}
