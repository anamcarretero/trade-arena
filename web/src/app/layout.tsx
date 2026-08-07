import type {Metadata, Viewport} from "next";
import {headers} from "next/headers";
import {PwaRegister} from "@/components/pwa-register";
import "./globals.css";

export const metadata: Metadata = {
  title: {default: "TradeArena", template: "%s · TradeArena"},
  description: "Private simulated-investing leagues.",
  applicationName: "TradeArena",
  appleWebApp: {capable: true, title: "TradeArena", statusBarStyle: "black-translucent"}
};

export const viewport: Viewport = {themeColor: "#2962ff", colorScheme: "dark"};

export default async function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  const locale = (await headers()).get("x-tradearena-locale") === "en" ? "en" : "es";
  return <html lang={locale} data-scroll-behavior="smooth"><body><PwaRegister />{children}</body></html>;
}
