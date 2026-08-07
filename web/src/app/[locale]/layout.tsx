import {notFound} from "next/navigation";
import {isLocale} from "@/lib/i18n";
import {AccessibilityShell} from "@/components/accessibility-shell";

export function generateStaticParams() { return [{locale: "es"}, {locale: "en"}]; }

export default async function LocaleLayout({children, params}: {children: React.ReactNode; params: Promise<{locale: string}>}) {
  const {locale} = await params;
  if (!isLocale(locale)) notFound();
  return <AccessibilityShell locale={locale}>{children}</AccessibilityShell>;
}
