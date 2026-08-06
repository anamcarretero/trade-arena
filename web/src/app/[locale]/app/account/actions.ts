"use server";

import {redirect} from "next/navigation";
import {apiFetch} from "@/lib/api";
import {isLocale} from "@/lib/i18n";
import {clearSession} from "@/lib/session";

export async function deleteAccount(formData: FormData) {
  const locale = String(formData.get("locale") ?? "");
  if (!isLocale(locale)) throw new Error("Unsupported locale");
  const response = await apiFetch("/api/v1/me", {
    method: "DELETE",
    body: JSON.stringify({
      confirm_account_deletion: formData.get("confirm_account_deletion") === "yes"
    })
  });
  if (response.status === 403) {
    await clearSession();
    redirect(`/auth/login?locale=${locale}&returnTo=/${locale}/app/account`);
  }
  if (!response.ok) redirect(`/${locale}/app/account?error=delete`);
  await clearSession();
  redirect(`/${locale}?account_deleted=1`);
}
