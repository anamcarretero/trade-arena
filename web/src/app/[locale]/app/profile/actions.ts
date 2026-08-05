"use server";

import {redirect} from "next/navigation";
import {apiFetch} from "@/lib/api";
import {isLocale} from "@/lib/i18n";
import {saveLocale} from "@/lib/session";

export async function updateProfile(formData: FormData) {
  const localeValue = String(formData.get("locale") ?? "");
  if (!isLocale(localeValue)) throw new Error("Unsupported locale");
  const response = await apiFetch("/api/v1/me/profile", {
    method: "PATCH",
    body: JSON.stringify({
      display_name: String(formData.get("display_name") ?? ""),
      birth_date: String(formData.get("birth_date") ?? ""),
      locale: localeValue,
      accepted_terms_at: new Date().toISOString()
    })
  });
  if (response.status === 403) redirect(`/auth/login?locale=${localeValue}&returnTo=/${localeValue}/app/profile`);
  if (!response.ok) redirect(`/${localeValue}/app/profile?error=profile`);
  await saveLocale(localeValue);
  redirect(`/${localeValue}/app`);
}
