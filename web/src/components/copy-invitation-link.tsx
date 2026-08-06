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

  return <button className="copy-button" type="button" onClick={copy} aria-live="polite">
    {copied ? copiedLabel : label}
  </button>;
}
