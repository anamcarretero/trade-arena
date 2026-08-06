import type {Locale} from "./i18n";

export function invitationPath(locale: Locale, invitationId: string) {
  return `/${locale}/invite/${encodeURIComponent(invitationId)}`;
}
