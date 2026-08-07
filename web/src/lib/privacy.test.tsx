import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it, vi} from "vitest";

vi.mock("../app/[locale]/app/notifications/actions", () => ({
  markNotificationRead: async () => undefined
}));
vi.mock("../app/[locale]/app/account/actions", () => ({
  deleteAccount: async () => undefined
}));

import {AccountPrivacyPanel} from "../components/account-privacy-panel";
import {NotificationCenter} from "../components/notification-center";
import type {Notification} from "./api";

const notifications = [{
  id: "notification-1", kind: "competition.started",
  payload: {message: "Season ready"}, created_at: "2026-08-06T12:00:00Z",
  read_at: null
}, {
  id: "notification-2", kind: "invitation.accepted",
  payload: {}, created_at: "2026-08-05T12:00:00Z",
  read_at: "2026-08-05T13:00:00Z"
}] satisfies Notification[];

describe("TA-036 privacy UI", () => {
  it.each([
    ["es", "No leída", "Marcar como leída"],
    ["en", "Unread", "Mark as read"]
  ] as const)("renders notification read state in %s", (locale, unread, action) => {
    const html = renderToStaticMarkup(
      <NotificationCenter locale={locale} notifications={notifications}/>
    );
    expect(html).toContain(unread);
    expect(html).toContain(action);
    expect(html).toContain("Season ready");
    expect((html.match(/notification_id/g) ?? [])).toHaveLength(1);
  });

  it.each([
    ["es", "Exportar mis datos", "Borrar cuenta permanentemente"],
    ["en", "Export my data", "Permanently delete account"]
  ] as const)("renders export and explicit deletion confirmation in %s", (locale, exportLabel, deleteLabel) => {
    const html = renderToStaticMarkup(<AccountPrivacyPanel locale={locale}/>);
    expect(html).toContain(exportLabel);
    expect(html).toContain(deleteLabel);
    expect(html).toContain('name="confirm_account_deletion"');
    expect(html).toContain("required");
  });
});
