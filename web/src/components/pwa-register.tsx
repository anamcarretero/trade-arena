"use client";

import {useEffect} from "react";

export function PwaRegister() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return;

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
