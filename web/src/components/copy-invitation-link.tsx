"use client";

import {useState} from "react";

export function CopyInvitationLink({path, label, copiedLabel}: {
  path: string;
  label: string;
  copiedLabel: string;
}) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    await navigator.clipboard.writeText(new URL(path, window.location.origin).toString());
    setCopied(true);
  }

  return <>
    <button className="copy-button" type="button" onClick={copy}>
      {copied ? copiedLabel : label}
    </button>
    <span className="visually-hidden" role="status" aria-live="polite" aria-atomic="true">
      {copied ? copiedLabel : ""}
    </span>
  </>;
}
