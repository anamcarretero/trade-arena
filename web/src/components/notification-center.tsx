import type {Notification} from "../lib/api";
import {copy, type Locale} from "../lib/i18n";
import {markNotificationRead} from "../app/[locale]/app/notifications/actions";

export function NotificationCenter({locale, notifications}: {
  locale: Locale; notifications: Notification[];
}) {
  const text = copy[locale];
  return <section className="notification-center">
    {notifications.length === 0 ? <p className="empty-copy">{text.noNotifications}</p> :
      <div className="notification-list">{notifications.map(item => {
        const unread = item.read_at === null;
        const message = typeof item.payload.message === "string"
          ? item.payload.message : item.kind;
        return <article className={`notification-card ${unread ? "unread" : "read"}`} key={item.id}>
          <div className="notification-copy">
            <span className={`status-pill ${unread ? "live" : ""}`}>
              {unread ? text.unreadNotification : text.readNotification}
            </span>
            <h2>{message}</h2>
            <p className="meta">{formatDate(item.created_at, locale)}</p>
          </div>
          {unread && <form action={markNotificationRead}>
            <input type="hidden" name="locale" value={locale}/>
            <input type="hidden" name="notification_id" value={item.id}/>
            <button className="secondary compact" type="submit">{text.markAsRead}</button>
          </form>}
        </article>;
      })}</div>}
  </section>;
}

function formatDate(value: string, locale: Locale) {
  return new Intl.DateTimeFormat(locale === "es" ? "es-ES" : "en-GB", {
    dateStyle: "medium", timeStyle: "short"
  }).format(new Date(value));
}
