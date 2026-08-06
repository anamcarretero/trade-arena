function required(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required`);
  return value;
}

export function serverConfig() {
  const auth0Domain = required("AUTH0_DOMAIN").replace(/^https:\/\//, "").replace(/\/$/, "");
  return {
    auth0Domain,
    auth0ClientId: required("AUTH0_CLIENT_ID"),
    auth0ClientSecret: required("AUTH0_CLIENT_SECRET"),
    appBaseUrl: required("APP_BASE_URL").replace(/\/$/, ""),
    apiBaseUrl: required("API_BASE_URL").replace(/\/$/, ""),
    bffSharedSecret: required("BFF_SHARED_SECRET")
  };
}
