"use client";

import {useParams} from "next/navigation";
import {useEffect} from "react";

export default function AppError({error, reset}: {error: Error & {digest?: string}; reset: () => void}) {
  const params = useParams<{locale?: string}>();
  const locale = params.locale === "en" ? "en" : "es";

  useEffect(() => {
    console.error(error);
  }, [error]);

  return <main id="main-content" className="app-shell access-state" tabIndex={-1}>
    <div role="alert" aria-live="assertive">
      <p className="eyebrow">TradeArena / Error</p>
      <h1 tabIndex={-1}>{locale === "es" ? "No hemos podido cargar esta pantalla" : "We could not load this screen"}</h1>
      <p>{locale === "es" ? "Tus datos no se han modificado. Puedes volver a intentarlo." : "Your data has not changed. You can try again."}</p>
      <button className="primary" type="button" onClick={reset}>
        {locale === "es" ? "Reintentar" : "Try again"}
      </button>
    </div>
  </main>;
}
