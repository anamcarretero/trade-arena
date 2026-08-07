"use client";

import {useEffect} from "react";

export function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

    if (process.env.NODE_ENV !== "production") {
      const wasControlled = Boolean(navigator.serviceWorker.controller);
      void navigator.serviceWorker.getRegistration().then(async registration => {
        const removed = registration ? await registration.unregister() : false;
        if ("caches" in window) {
          const keys = await window.caches.keys();
          await Promise.all(keys.filter(key => key.startsWith("tradearena-shell-")).map(key => window.caches.delete(key)));
        }
        if (wasControlled && removed) window.location.reload();
      }).catch(() => undefined);
      return;
    }

    const hadController = Boolean(navigator.serviceWorker.controller);
    let refreshing = false;
    const reloadOnUpdate = () => {
      if (!hadController || refreshing) return;
      refreshing = true;
      window.location.reload();
    };

    navigator.serviceWorker.addEventListener("controllerchange", reloadOnUpdate);
    void navigator.serviceWorker
      .register("/sw.js")
      .then(registration => registration.update())
      .catch(() => undefined);

    return () => navigator.serviceWorker.removeEventListener("controllerchange", reloadOnUpdate);
  }, []);
  return null;
}
