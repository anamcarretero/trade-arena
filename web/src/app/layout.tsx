import type {Metadata, Viewport} from "next";
import {PwaRegister} from "@/components/pwa-register";
import "./globals.css";

export const metadata: Metadata = {
  title: {default: "TradeArena", template: "%s · TradeArena"},
  description: "Private simulated-investing leagues.",
  applicationName: "TradeArena",
  appleWebApp: {capable: true, title: "TradeArena", statusBarStyle: "black-translucent"}
};

export const viewport: Viewport = {themeColor: "#2962ff", colorScheme: "dark"};

export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="es"><body><PwaRegister />{children}</body></html>;
}
