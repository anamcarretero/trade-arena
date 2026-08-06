import type {Metadata} from "next";
import {notFound} from "next/navigation";
import {PricingPage} from "@/components/pricing-page";
import {isLocale} from "@/lib/i18n";
import {readSessionToken} from "@/lib/session";

export async function generateMetadata({params}: {params: Promise<{locale: string}>}): Promise<Metadata> {
  const {locale} = await params;
  if (!isLocale(locale)) return {};
  return {
    title: locale === "es" ? "Planes" : "Plans",
    description: locale === "es"
      ? "Consulta el plan Free de TradeArena y sus límites."
      : "Explore TradeArena's Free plan and its limits."
  };
}

export default async function Pricing({params}: {params: Promise<{locale: string}>}) {
  const {locale} = await params;
  if (!isLocale(locale)) notFound();
  const authenticated = Boolean(await readSessionToken());
  return <PricingPage locale={locale} authenticated={authenticated} />;
}
