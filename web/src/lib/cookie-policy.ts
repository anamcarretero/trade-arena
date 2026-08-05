export function cookiePolicy(appBaseUrl: string | undefined) {
  const secure = appBaseUrl?.startsWith("https://") ?? false;
  return {
    secure,
    sessionName: secure ? "__Host-tradearena_session" : "tradearena_session",
    transactionName: secure ? "__Host-tradearena_login" : "tradearena_login"
  };
}
