"use client";

import {useEffect} from "react";
import type {Locale} from "../lib/i18n";

export function AccessibilityShell({locale, children}: {
  locale: Locale;
  children: React.ReactNode;
}) {
  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  useEffect(() => {
    const restoreFocus = (event: MouseEvent) => {
      const link = (event.target as Element | null)?.closest<HTMLAnchorElement>("a[href]");
      if (!link || link.origin !== window.location.origin || link.target === "_blank") return;
      const previousHeading = document.querySelector("#main-content h1");
      const observer = new MutationObserver(() => {
        const nextHeading = document.querySelector<HTMLElement>("#main-content h1");
        if (!nextHeading || nextHeading === previousHeading) return;
        observer.disconnect();
        window.setTimeout(() => nextHeading.focus({preventScroll: true}), 100);
      });
      observer.observe(document.body, {childList: true, subtree: true});
      window.setTimeout(() => observer.disconnect(), 5000);
    };
    document.addEventListener("click", restoreFocus, true);
    return () => document.removeEventListener("click", restoreFocus, true);
  }, []);

  return <>
    <a className="skip-link" href="#main-content">
      {locale === "es" ? "Saltar al contenido principal" : "Skip to main content"}
    </a>
    {children}
  </>;
}
