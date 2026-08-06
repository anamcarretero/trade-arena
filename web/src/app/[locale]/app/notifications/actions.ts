"use server";

import {redirect} from "next/navigation";
import {apiFetch} from "@/lib/api";
import {isLocale} from "@/lib/i18n";

export async function markNotificationRead(formData: FormData) {
  const locale = String(formData.get("locale") ?? "");
  if (!isLocale(locale)) throw new Error("Unsupported locale");
  const notificationId = String(formData.get("notification_id") ?? "");
  const response = await apiFetch(
    `/api/v1/notifications/${encodeURIComponent(notificationId)}/read`,
    {method: "POST"}
  );
  if (response.status === 403) {
    redirect(`/auth/login?locale=${locale}&returnTo=/${locale}/app/notifications`);
  }
  if (!response.ok) redirect(`/${locale}/app/notifications?error=read`);
  redirect(`/${locale}/app/notifications?status=read`);
}
