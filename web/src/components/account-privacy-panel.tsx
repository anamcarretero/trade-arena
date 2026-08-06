import Link from "next/link";
import {deleteAccount} from "../app/[locale]/app/account/actions";
import {copy, type Locale} from "../lib/i18n";

export function AccountPrivacyPanel({locale}: {locale: Locale}) {
  const text = copy[locale];
  return <div className="privacy-grid">
    <section className="privacy-card">
      <p className="eyebrow">JSON / v1</p><h2>{text.exportData}</h2>
      <p>{text.exportDataIntro}</p>
      <Link className="secondary" href="/account/export" prefetch={false}>{text.downloadExport}</Link>
    </section>
    <section className="privacy-card danger-zone">
      <p className="eyebrow">Privacy / Delete</p><h2>{text.deleteAccount}</h2>
      <p>{text.deleteAccountIntro}</p>
      <form action={deleteAccount}>
        <input type="hidden" name="locale" value={locale}/>
        <label className="delete-confirmation">
          <input type="checkbox" name="confirm_account_deletion" value="yes" required/>
          <span>{text.deleteConfirmation}</span>
        </label>
        <button className="danger-primary" type="submit">{text.deletePermanently}</button>
      </form>
    </section>
  </div>;
}
