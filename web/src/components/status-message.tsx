"use client";

import {useEffect, useRef} from "react";

export function StatusMessage({kind, className = "", children}: {
  kind: "error" | "status";
  className?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    ref.current?.focus({preventScroll: true});
  }, []);

  return <p
    ref={ref}
    className={`${kind === "error" ? "error" : "success"} ${className}`.trim()}
    role={kind === "error" ? "alert" : "status"}
    aria-live={kind === "error" ? "assertive" : "polite"}
    aria-atomic="true"
    tabIndex={-1}
  >{children}</p>;
}
