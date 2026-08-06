import Link from "next/link";
import type {Locale} from "../lib/i18n";
import {pricingCopy, pricingCta} from "../lib/pricing";
import {PublicHeader} from "./public-header";

export function PricingPage({locale, authenticated}: {locale: Locale; authenticated: boolean}) {
  const text = pricingCopy[locale];
  const cta = pricingCta(locale, authenticated);
  return <main className="landing pricing-shell">
    <PublicHeader locale={locale} page="pricing" authenticated={authenticated} />
    <section className="pricing-hero" aria-labelledby="pricing-title">
      <p className="eyebrow">{text.eyebrow}</p>
      <h1 id="pricing-title">{text.title}</h1>
      <p>{text.intro}</p>
    </section>
    <section className="pricing-grid" aria-label={text.pricingNav}>
      {text.plans.map((plan, index) => {
        const available = plan.availability === "available";
        return <article className={`pricing-card${available ? " featured" : " future"}`} key={plan.name}>
          <div className="pricing-card-head">
            <span className={`status-pill${available ? " live" : ""}`}>{available && <i aria-hidden="true"/>}{available ? text.available : text.comingSoon}</span>
            <span aria-hidden="true">0{index + 1}</span>
          </div>
          <h2>{plan.name}</h2>
          <p>{plan.description}</p>
          {available ? <>
            <h3>{text.limitsLabel}</h3>
            <ul>{plan.features.map(feature => <li key={feature}><span aria-hidden="true">✓</span>{feature}</li>)}</ul>
            <Link className="primary pricing-cta" href={cta.href}>{cta.label}<span aria-hidden="true">→</span></Link>
          </> : <p className="unavailable-note" aria-label={`${plan.name}: ${text.unavailable}`}>{text.unavailable}</p>}
        </article>;
      })}
    </section>
  </main>;
}
