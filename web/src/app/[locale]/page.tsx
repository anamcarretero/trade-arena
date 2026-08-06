import {MarketPreview} from "@/components/market-preview";
import {PublicHeader} from "@/components/public-header";
import {copy, isLocale} from "@/lib/i18n";
import {notFound} from "next/navigation";

export default async function Landing({params, searchParams}: {params: Promise<{locale: string}>; searchParams: Promise<{auth_error?: string}>}) {
  const {locale: rawLocale} = await params;
  if (!isLocale(rawLocale)) notFound();
  const locale = rawLocale;
  const text = copy[locale];
  const authError = Boolean((await searchParams).auth_error);
  return <main className="landing">
    <PublicHeader locale={locale} page="home" />
    <section className="hero">
      <div className="hero-copy">
        <p className="eyebrow">{text.eyebrow}</p>
        <h1><span className="gradient-text">{text.taglineAccent}</span><span>{text.taglineMain}</span></h1>
        <p className="lede">{text.intro}</p>
        {authError && <p className="error" role="alert">{text.authError}</p>}
        <a className="primary" href={`/auth/login?locale=${locale}&returnTo=/${locale}/app`}>{text.access}<span aria-hidden="true">↗</span></a>
      </div>
      <MarketPreview locale={locale} />
    </section>
    <section className="feature-heading"><p className="eyebrow">TradeArena / 03</p><h2>{text.featureHeading}</h2><p>{text.featureIntro}</p></section>
    <section className="features" aria-label="TradeArena">
      {[["01", text.featureOne, text.featureOneText], ["02", text.featureTwo, text.featureTwoText], ["03", text.featureThree, text.featureThreeText]].map(([number, title, description]) =>
        <article key={number}><span>{number}</span><h2>{title}</h2><p>{description}</p></article>)}
    </section>
  </main>;
}
