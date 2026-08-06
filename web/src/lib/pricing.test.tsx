import {renderToStaticMarkup} from "react-dom/server";
import {describe, expect, it} from "vitest";
import {PricingPage} from "../components/pricing-page";
import {PublicHeader} from "../components/public-header";
import {pricingCopy, pricingCta} from "./pricing";

describe("public pricing", () => {
  it("publishes the real Free limits in Spanish and English", () => {
    expect(pricingCopy.es.plans[0].features).toEqual([
      "Una liga activa",
      "Dos plazas",
      "3.000 USD de capital virtual inicial por competición"
    ]);
    expect(pricingCopy.en.plans[0].features).toEqual([
      "One active league",
      "Two seats",
      "USD 3,000 starting virtual capital per competition"
    ]);
  });

  it("keeps Friends and Club unavailable without prices or purchase actions", () => {
    for (const locale of ["es", "en"] as const) {
      const futurePlans = pricingCopy[locale].plans.slice(1);
      expect(futurePlans.map(plan => plan.name)).toEqual(["Friends", "Club"]);
      expect(futurePlans.every(plan => plan.availability === "coming-soon")).toBe(true);
      const html = renderToStaticMarkup(<PricingPage locale={locale} authenticated={false}/>);
      expect(html).toContain(locale === "es" ? "Próximamente" : "Coming soon");
      expect(html).not.toMatch(/€|\$\d|checkout|subscribe|suscrib|comprar|buy now/i);
    }
  });

  it("sends the Free call to sign-in or the app according to session state", () => {
    expect(pricingCta("es", false)).toEqual({
      href: "/auth/login?locale=es&returnTo=/es/app",
      label: "Empezar con Free"
    });
    expect(pricingCta("en", true)).toEqual({href: "/en/app", label: "Go to the app"});
  });

  it("exposes pricing in public navigation in both locales", () => {
    for (const locale of ["es", "en"] as const) {
      const html = renderToStaticMarkup(<PublicHeader locale={locale} page="home"/>);
      expect(html).toContain(`href="/${locale}/pricing"`);
      expect(html).toContain(locale === "es" ? "Navegación principal" : "Primary navigation");
    }
  });

  it("renders a labelled landmark, one page heading and explicit plan statuses", () => {
    const html = renderToStaticMarkup(<PricingPage locale="en" authenticated={false}/>);
    expect(html.match(/<h1/g)).toHaveLength(1);
    expect(html).toContain("aria-labelledby=\"pricing-title\"");
    expect(html).toContain("aria-current=\"page\"");
    expect(html).toContain("Friends: Not available yet");
    expect(html).toContain("Club: Not available yet");
  });
});
