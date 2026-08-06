import Link from "next/link";
import {notFound, redirect} from "next/navigation";
import {LocaleSwitcher} from "@/components/locale-switcher";
import {copy, isLocale} from "@/lib/i18n";
import {ownAccount} from "@/lib/api";
import {updateProfile} from "./actions";

export default async function Profile({params, searchParams}: {params: Promise<{locale: string}>; searchParams: Promise<{error?: string}>}) {
  const {locale: rawLocale} = await params;
  if (!isLocale(rawLocale)) notFound();
  const account = await ownAccount();
  if (!account) redirect(`/auth/login?locale=${rawLocale}&returnTo=/${rawLocale}/app/profile`);
  const text = copy[rawLocale];
  const profile = account.profile;
  return <main className="app-shell">
    <header className="topbar"><Link className="wordmark" href={`/${rawLocale}/app`}>TRADE<span>ARENA</span></Link><LocaleSwitcher locale={rawLocale} suffix="/app/profile" /></header>
    <section className="profile-grid">
      <div className="profile-copy"><p className="eyebrow">{account.user.email}</p><h1>{text.profile}</h1><p className="lede">{text.profileIntro}</p><div className="profile-signal" aria-hidden="true"><span/><span/><span/><span/><span/></div></div>
      <form action={updateProfile} className="profile-form">
        {(await searchParams).error && <p className="error" role="alert">{text.authError}</p>}
        <label>{text.displayName}<input name="display_name" required minLength={1} maxLength={80} defaultValue={profile?.display_name ?? ""} autoComplete="name" /></label>
        <label>{text.birthDate}<input name="birth_date" type="date" required defaultValue={profile?.birth_date ?? ""} autoComplete="bday" /></label>
        <fieldset><legend>{text.language}</legend><label className="radio"><input name="locale" type="radio" value="es" defaultChecked={(profile?.locale ?? rawLocale) === "es"}/> Español</label><label className="radio"><input name="locale" type="radio" value="en" defaultChecked={(profile?.locale ?? rawLocale) === "en"}/> English</label></fieldset>
        <label className="check"><input name="terms" type="checkbox" required defaultChecked={Boolean(profile)}/><span>{text.terms}</span></label>
        <button className="primary" type="submit">{text.save}<span aria-hidden="true">→</span></button>
      </form>
    </section>
  </main>;
}
